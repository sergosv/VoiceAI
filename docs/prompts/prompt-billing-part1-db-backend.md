# PROMPT PARA CLAUDE CODE - Sistema de Creditos y Facturacion (PARTE 1 de 2)
## DB + Backend + Pagos

Lee CLAUDE.md y ARCHITECTURE.md primero. Este prompt (2 partes) implementa monetizacion completa. PARTE 1: base de datos, billing en llamadas, pagos. PARTE 2: API endpoints, dashboard completo, alertas.

## CONCEPTO

1 credito = 1 minuto de llamada, TODO incluido (LLM, STT, TTS, telefonia, MCP, memoria). El cliente nunca ve costos por componente.

El admin tiene UN slider de margen de ganancia. Al moverlo, TODOS los paquetes se recalculan automaticamente. Formula: precio = costo_base / (1 - margen).

Ejemplo: costo real $0.035/min. Con 75% margen: $0.035/0.25 = $0.14/min. Con 65%: $0.10/min. Con 80%: $0.175/min.

---

## PARTE 1: BASE DE DATOS (migracion 013_billing_system.sql)

```sql
-- Habilitar si no esta habilitado
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- 1. CONFIGURACION DE PRECIOS (una sola fila)
-- ============================================
CREATE TABLE IF NOT EXISTS pricing_config (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    -- Costos base por minuto (lo que la plataforma paga a proveedores)
    cost_twilio_per_min NUMERIC(10,6) DEFAULT 0.013000,
    cost_stt_per_min NUMERIC(10,6) DEFAULT 0.006000,
    cost_llm_per_min NUMERIC(10,6) DEFAULT 0.003000,
    cost_tts_per_min NUMERIC(10,6) DEFAULT 0.008000,
    cost_livekit_per_min NUMERIC(10,6) DEFAULT 0.002000,
    cost_mcp_per_min NUMERIC(10,6) DEFAULT 0.003000,
    -- EL SLIDER PRINCIPAL: margen de ganancia
    profit_margin NUMERIC(4,3) DEFAULT 0.750,  -- 75%
    -- Config general
    free_credits_new_account INTEGER DEFAULT 10,
    alert_threshold_warning NUMERIC(3,2) DEFAULT 0.20,
    alert_threshold_critical NUMERIC(3,2) DEFAULT 0.05,
    base_currency TEXT DEFAULT 'USD',
    usd_to_mxn_rate NUMERIC(10,4) DEFAULT 20.0000,
    stripe_enabled BOOLEAN DEFAULT true,
    mercadopago_enabled BOOLEAN DEFAULT true,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by TEXT
);

INSERT INTO pricing_config (id) VALUES (gen_random_uuid()) ON CONFLICT DO NOTHING;

-- ============================================
-- 2. PAQUETES DE CREDITOS
-- ============================================
CREATE TABLE IF NOT EXISTS credit_packages (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    credits INTEGER NOT NULL,
    volume_discount NUMERIC(4,3) DEFAULT 0.000,
    price_usd NUMERIC(10,2),
    price_mxn NUMERIC(10,2),
    price_per_credit_usd NUMERIC(10,4),
    stripe_price_id_usd TEXT,
    sort_order INTEGER DEFAULT 0,
    is_popular BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO credit_packages (name, description, credits, volume_discount, sort_order, is_popular) VALUES
    ('Starter', 'Para probar y negocios pequenos', 100, 0.000, 1, false),
    ('Business', 'Para negocios en crecimiento', 500, 0.100, 2, true),
    ('Pro', 'Para alto volumen', 2000, 0.200, 3, false),
    ('Enterprise', 'Para operaciones grandes', 5000, 0.350, 4, false)
ON CONFLICT DO NOTHING;

-- ============================================
-- 3. BALANCE DE CREDITOS POR CLIENTE
-- ============================================
CREATE TABLE IF NOT EXISTS credit_balances (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE UNIQUE,
    balance NUMERIC(12,2) DEFAULT 0,
    total_purchased NUMERIC(12,2) DEFAULT 0,
    total_consumed NUMERIC(12,2) DEFAULT 0,
    total_gifted NUMERIC(12,2) DEFAULT 0,
    last_alert_sent_at TIMESTAMPTZ,
    last_alert_type TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE credit_balances ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own_balance" ON credit_balances FOR SELECT
    USING (client_id = auth.uid()::uuid);

-- ============================================
-- 4. TRANSACCIONES (historial completo)
-- ============================================
CREATE TABLE IF NOT EXISTS credit_transactions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    type TEXT NOT NULL,              -- 'purchase','consumption','gift','refund','adjustment'
    credits NUMERIC(12,2) NOT NULL,  -- Positivo=ingreso, Negativo=consumo
    balance_after NUMERIC(12,2) NOT NULL,
    -- Datos de compra
    payment_provider TEXT,
    payment_id TEXT,
    payment_status TEXT,
    amount_paid NUMERIC(10,2),
    currency TEXT,
    package_id UUID REFERENCES credit_packages(id),
    -- Datos de consumo
    call_id TEXT,
    agent_id UUID REFERENCES agents(id),
    duration_seconds INTEGER,
    -- Datos regalo/ajuste
    reason TEXT,
    admin_email TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_credit_tx_client ON credit_transactions(client_id, created_at DESC);
CREATE INDEX idx_credit_tx_payment ON credit_transactions(payment_provider, payment_id);
ALTER TABLE credit_transactions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own_tx" ON credit_transactions FOR SELECT
    USING (client_id = auth.uid()::uuid);

-- ============================================
-- 5. FUNCIONES
-- ============================================

-- Agregar creditos (compra, regalo, ajuste)
CREATE OR REPLACE FUNCTION add_credits(
    p_client_id UUID, p_credits NUMERIC, p_type TEXT,
    p_payment_provider TEXT DEFAULT NULL, p_payment_id TEXT DEFAULT NULL,
    p_amount_paid NUMERIC DEFAULT NULL, p_currency TEXT DEFAULT NULL,
    p_package_id UUID DEFAULT NULL, p_reason TEXT DEFAULT NULL,
    p_admin_email TEXT DEFAULT NULL
) RETURNS NUMERIC LANGUAGE plpgsql AS $$
DECLARE v_bal NUMERIC;
BEGIN
    INSERT INTO credit_balances (client_id, balance, total_purchased, total_gifted)
    VALUES (p_client_id, p_credits,
            CASE WHEN p_type='purchase' THEN p_credits ELSE 0 END,
            CASE WHEN p_type='gift' THEN p_credits ELSE 0 END)
    ON CONFLICT (client_id) DO UPDATE SET
        balance = credit_balances.balance + p_credits,
        total_purchased = credit_balances.total_purchased
            + CASE WHEN p_type='purchase' THEN p_credits ELSE 0 END,
        total_gifted = credit_balances.total_gifted
            + CASE WHEN p_type='gift' THEN p_credits ELSE 0 END,
        updated_at = NOW()
    RETURNING balance INTO v_bal;

    INSERT INTO credit_transactions (
        client_id, type, credits, balance_after,
        payment_provider, payment_id, payment_status,
        amount_paid, currency, package_id, reason, admin_email
    ) VALUES (
        p_client_id, p_type, p_credits, v_bal,
        p_payment_provider, p_payment_id,
        CASE WHEN p_type='purchase' THEN 'completed' ELSE NULL END,
        p_amount_paid, p_currency, p_package_id, p_reason, p_admin_email
    );
    RETURN v_bal;
END; $$;

-- Consumir creditos (por llamada) - con lock anti-race-condition
CREATE OR REPLACE FUNCTION consume_credits(
    p_client_id UUID, p_credits NUMERIC,
    p_call_id TEXT DEFAULT NULL, p_agent_id UUID DEFAULT NULL,
    p_duration_seconds INTEGER DEFAULT NULL
) RETURNS TABLE (success BOOLEAN, new_balance NUMERIC, was_insufficient BOOLEAN)
LANGUAGE plpgsql AS $$
DECLARE v_cur NUMERIC; v_new NUMERIC;
BEGIN
    SELECT balance INTO v_cur FROM credit_balances
    WHERE client_id = p_client_id FOR UPDATE;

    IF v_cur IS NULL OR v_cur <= 0 THEN
        RETURN QUERY SELECT false, COALESCE(v_cur, 0.0)::NUMERIC, true;
        RETURN;
    END IF;

    v_new := v_cur - p_credits;
    UPDATE credit_balances SET
        balance = v_new,
        total_consumed = total_consumed + p_credits,
        updated_at = NOW()
    WHERE client_id = p_client_id;

    INSERT INTO credit_transactions (
        client_id, type, credits, balance_after,
        call_id, agent_id, duration_seconds
    ) VALUES (
        p_client_id, 'consumption', -p_credits, v_new,
        p_call_id, p_agent_id, p_duration_seconds
    );
    RETURN QUERY SELECT true, v_new, (v_new <= 0);
END; $$;

-- Check creditos (antes de conectar llamada)
CREATE OR REPLACE FUNCTION check_credits(p_client_id UUID)
RETURNS TABLE (has_credits BOOLEAN, balance NUMERIC)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT COALESCE(cb.balance > 0, false), COALESCE(cb.balance, 0.0)
    FROM credit_balances cb WHERE cb.client_id = p_client_id;
    IF NOT FOUND THEN
        RETURN QUERY SELECT false, 0.0::NUMERIC;
    END IF;
END; $$;

-- CASCADA: recalcular paquetes cuando cambia pricing_config
CREATE OR REPLACE FUNCTION recalculate_package_prices()
RETURNS void LANGUAGE plpgsql AS $$
DECLARE v_c RECORD; v_cost NUMERIC; v_price NUMERIC;
BEGIN
    SELECT * INTO v_c FROM pricing_config LIMIT 1;
    v_cost := v_c.cost_twilio_per_min + v_c.cost_stt_per_min
            + v_c.cost_llm_per_min + v_c.cost_tts_per_min
            + v_c.cost_livekit_per_min + v_c.cost_mcp_per_min;
    v_price := v_cost / (1 - v_c.profit_margin);
    UPDATE credit_packages SET
        price_per_credit_usd = ROUND(v_price * (1 - volume_discount), 4),
        price_usd = ROUND(credits * v_price * (1 - volume_discount), 2),
        price_mxn = ROUND(credits * v_price * (1 - volume_discount)
                    * v_c.usd_to_mxn_rate, 2),
        updated_at = NOW()
    WHERE is_active = true;
END; $$;

-- Ejecutar recalculo inicial
SELECT recalculate_package_prices();
```

---

## PARTE 2: BILLING EN LLAMADAS (agent/billing.py)

```python
"""
agent/billing.py - Control de creditos en llamadas

1. check_can_take_call() - Verificar ANTES de conectar
2. start_tracking() - Iniciar cuando conecta
3. _incremental_billing() - Llamadas >5min: cobra cada minuto
4. finish_call() - Cobra restante al colgar
"""
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger("billing")


class CallBilling:
    """Una instancia por llamada."""

    def __init__(self, supabase_client, client_id: str):
        self.supabase = supabase_client
        self.client_id = client_id
        self.call_id = None
        self.agent_id = None
        self.start_time = None
        self._billing_task = None
        self._is_active = False

    async def check_can_take_call(self) -> dict:
        """Verificar creditos ANTES de conectar."""
        result = self.supabase.rpc(
            "check_credits", {"p_client_id": self.client_id}
        ).execute()
        if result.data:
            row = result.data[0] if isinstance(result.data, list) else result.data
            has = row.get("has_credits", False)
            bal = float(row.get("balance", 0))
            logger.info(f"Credit check {self.client_id}: balance={bal}, allowed={has}")
            return {"allowed": has, "balance": bal}
        return {"allowed": False, "balance": 0}

    def start_tracking(self, call_id: str, agent_id: str = None):
        """Iniciar tracking cuando la llamada se conecta."""
        self.call_id = call_id
        self.agent_id = agent_id
        self.start_time = datetime.utcnow()
        self._is_active = True
        self._billing_task = asyncio.create_task(self._incremental_billing())
        logger.info(f"Billing started for call {call_id}")

    async def _incremental_billing(self):
        """Llamadas largas (>5 min): cobra 1 credito cada minuto.
        Esto evita que una llamada de 30 min consuma todo de golpe al final."""
        try:
            await asyncio.sleep(300)  # Esperar 5 min antes de empezar
            while self._is_active:
                result = self.supabase.rpc("consume_credits", {
                    "p_client_id": self.client_id,
                    "p_credits": 1.0,
                    "p_call_id": self.call_id,
                    "p_agent_id": self.agent_id,
                    "p_duration_seconds": 60,
                }).execute()
                if result.data:
                    row = result.data[0] if isinstance(result.data, list) else result.data
                    if row.get("was_insufficient"):
                        logger.warning(
                            f"Client {self.client_id} out of credits mid-call"
                        )
                        # NO cortamos la llamada, pero marcamos para rechazar la siguiente
                        break
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            pass  # Normal al colgar

    async def finish_call(self, duration_seconds: int):
        """Finalizar billing. Cobra creditos restantes."""
        self._is_active = False
        if self._billing_task:
            self._billing_task.cancel()
            try:
                await self._billing_task
            except asyncio.CancelledError:
                pass

        total_minutes = duration_seconds / 60.0

        # Llamadas cortas (<5 min): no hubo billing incremental, cobrar todo
        if duration_seconds < 300:
            credits_to_consume = round(total_minutes, 2)
            if credits_to_consume > 0:
                self.supabase.rpc("consume_credits", {
                    "p_client_id": self.client_id,
                    "p_credits": credits_to_consume,
                    "p_call_id": self.call_id,
                    "p_agent_id": self.agent_id,
                    "p_duration_seconds": duration_seconds,
                }).execute()
        else:
            # Llamadas largas: cobrar minutos restantes
            already_billed = max((duration_seconds // 300) - 1, 0)
            remaining = total_minutes - already_billed
            if remaining > 0:
                self.supabase.rpc("consume_credits", {
                    "p_client_id": self.client_id,
                    "p_credits": round(remaining, 2),
                    "p_call_id": self.call_id,
                    "p_agent_id": self.agent_id,
                    "p_duration_seconds": duration_seconds,
                }).execute()

        logger.info(
            f"Call {self.call_id} billed: {total_minutes:.1f} min ({duration_seconds}s)"
        )
```

### Integrar en agent/main.py

```python
from billing import CallBilling

async def entrypoint(ctx: JobContext):
    # ... codigo existente de conexion, extraccion telefono ...
    caller_phone = extract_caller_phone(ctx)
    client = await get_client_by_phone(called_phone)
    if not client:
        return

    # ========= BILLING: Check ANTES de atender =========
    billing = CallBilling(supabase, client["id"])
    credit_check = await billing.check_can_take_call()

    if not credit_check["allowed"]:
        logger.warning(f"Client {client['id']} no credits, rejecting call")
        await play_message(ctx,
            "Lo sentimos, en este momento no podemos atender tu llamada. "
            "Por favor comunicate directamente al numero del negocio. Gracias."
        )
        return

    # ========= MEMORIA: Identify + Recall =========
    memory = AgentMemory(supabase, client["id"], channel="call")
    await memory.identify(caller_phone, "phone")
    memory_context = memory.build_memory_context()

    # ... construir agente con memory_context, conectar a room ...

    # ========= BILLING: Start tracking =========
    billing.start_tracking(
        call_id=ctx.room.name,
        agent_id=active_agent["id"]
    )

    # ========= AL TERMINAR LA LLAMADA =========
    @ctx.on("participant_disconnected")
    async def on_call_end():
        duration = get_call_duration(ctx)
        # Billing: consumir creditos
        await billing.finish_call(duration_seconds=duration)
        # Memoria: guardar recuerdo
        await memory.store(
            transcript=transcript_collector.get_transcript(),
            agent_id=active_agent["id"],
            agent_name=active_agent.get("agent_name"),
            duration_seconds=duration,
        )
```

---

## PARTE 3: PAGOS (api/payments.py)

```python
"""
api/payments.py - Procesamiento de pagos

Flujo completo:
1. Cliente elige paquete en dashboard
2. Backend crea sesion de pago (Stripe Checkout o MercadoPago Preference)
3. Cliente paga en pagina del proveedor
4. Webhook confirma pago
5. Se acreditan creditos automaticamente
"""
import os
import logging
import stripe

logger = logging.getLogger("payments")
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")


async def create_stripe_checkout(
    client_id: str,
    package_id: str,
    package_name: str,
    price_usd: float,
    credits: int,
    success_url: str,
    cancel_url: str,
) -> dict:
    """Crea sesion de Stripe Checkout. Retorna URL de pago."""
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"Creditos: {package_name}",
                        "description": f"{credits} minutos de agente IA",
                    },
                    "unit_amount": int(price_usd * 100),  # Stripe usa centavos
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            metadata={
                "client_id": client_id,
                "package_id": package_id,
                "credits": str(credits),
            },
        )
        return {"checkout_url": session.url, "session_id": session.id}
    except Exception as e:
        logger.error(f"Stripe checkout error: {e}")
        raise


async def create_mercadopago_preference(
    client_id: str,
    package_id: str,
    package_name: str,
    price_mxn: float,
    credits: int,
    success_url: str,
    cancel_url: str,
) -> dict:
    """Crea preferencia de Mercado Pago."""
    try:
        # Descomentar cuando se configure:
        # import mercadopago
        # mp_sdk = mercadopago.SDK(os.environ.get("MERCADOPAGO_ACCESS_TOKEN"))
        # preference_data = {
        #     "items": [{
        #         "title": f"Creditos: {package_name}",
        #         "description": f"{credits} minutos de agente IA",
        #         "quantity": 1,
        #         "currency_id": "MXN",
        #         "unit_price": float(price_mxn),
        #     }],
        #     "back_urls": {
        #         "success": success_url,
        #         "failure": cancel_url,
        #         "pending": cancel_url,
        #     },
        #     "auto_return": "approved",
        #     "external_reference": f"{client_id}|{package_id}|{credits}",
        #     "notification_url": os.environ.get("MERCADOPAGO_WEBHOOK_URL"),
        # }
        # result = mp_sdk.preference().create(preference_data)
        # preference = result["response"]
        # return {
        #     "checkout_url": preference["init_point"],
        #     "preference_id": preference["id"],
        # }
        return {"checkout_url": "", "preference_id": ""}  # PLACEHOLDER
    except Exception as e:
        logger.error(f"MercadoPago error: {e}")
        raise
```

### Webhooks (api/routes/webhooks.py)

```python
"""
api/routes/webhooks.py - Reciben confirmaciones de pago y acreditan creditos.
IMPORTANTE: Estos endpoints deben ser publicos (sin auth) para que Stripe/MP los llamen.
"""
from fastapi import APIRouter, Request, HTTPException
import stripe
import os

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")


@router.post("/stripe")
async def stripe_webhook(request: Request):
    """Webhook de Stripe. Valida firma, acredita creditos."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(400, "Invalid webhook signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        metadata = session.get("metadata", {})
        client_id = metadata.get("client_id")
        credits = int(metadata.get("credits", 0))
        amount_paid = session.get("amount_total", 0) / 100

        if client_id and credits > 0:
            supabase.rpc("add_credits", {
                "p_client_id": client_id,
                "p_credits": credits,
                "p_type": "purchase",
                "p_payment_provider": "stripe",
                "p_payment_id": session["id"],
                "p_amount_paid": amount_paid,
                "p_currency": "USD",
                "p_package_id": metadata.get("package_id"),
            }).execute()
            logger.info(f"Stripe: {credits} credits added to {client_id}")

    return {"status": "ok"}


@router.post("/mercadopago")
async def mercadopago_webhook(request: Request):
    """Webhook de Mercado Pago. Descomentar cuando se configure."""
    data = await request.json()
    # if data.get("type") == "payment":
    #     payment_id = data["data"]["id"]
    #     payment = mp_sdk.payment().get(payment_id)["response"]
    #     if payment["status"] == "approved":
    #         ref = payment["external_reference"]
    #         client_id, package_id, credits = ref.split("|")
    #         supabase.rpc("add_credits", {
    #             "p_client_id": client_id,
    #             "p_credits": int(credits),
    #             "p_type": "purchase",
    #             "p_payment_provider": "mercadopago",
    #             "p_payment_id": str(payment_id),
    #             "p_amount_paid": payment["transaction_amount"],
    #             "p_currency": "MXN",
    #             "p_package_id": package_id,
    #         }).execute()
    return {"status": "ok"}
```

---

Continua en PARTE 2 (prompt-billing-part2-api-dashboard.md): API endpoints, Dashboard cliente, Panel admin pricing, Alertas, Registro, Resumen.
