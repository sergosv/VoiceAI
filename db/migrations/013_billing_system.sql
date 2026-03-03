-- Migración 013: Sistema de créditos y facturación
-- 1 crédito = 1 minuto de llamada, todo incluido

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
    ('Starter', 'Para probar y negocios pequeños', 100, 0.000, 1, false),
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

-- Agregar créditos (compra, regalo, ajuste)
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

-- Consumir créditos (por llamada) - con lock anti-race-condition
CREATE OR REPLACE FUNCTION consume_credits(
    p_client_id UUID, p_credits NUMERIC,
    p_call_id TEXT DEFAULT NULL, p_agent_id UUID DEFAULT NULL,
    p_duration_seconds INTEGER DEFAULT NULL
) RETURNS TABLE (success BOOLEAN, new_balance NUMERIC, was_insufficient BOOLEAN)
LANGUAGE plpgsql AS $$
DECLARE v_cur NUMERIC; v_new NUMERIC;
BEGIN
    SELECT cb.balance INTO v_cur FROM credit_balances cb
    WHERE cb.client_id = p_client_id FOR UPDATE;

    IF v_cur IS NULL OR v_cur <= 0 THEN
        RETURN QUERY SELECT false, COALESCE(v_cur, 0.0)::NUMERIC, true;
        RETURN;
    END IF;

    v_new := v_cur - p_credits;
    UPDATE credit_balances SET
        balance = v_new,
        total_consumed = total_consumed + p_credits,
        updated_at = NOW()
    WHERE credit_balances.client_id = p_client_id;

    INSERT INTO credit_transactions (
        client_id, type, credits, balance_after,
        call_id, agent_id, duration_seconds
    ) VALUES (
        p_client_id, 'consumption', -p_credits, v_new,
        p_call_id, p_agent_id, p_duration_seconds
    );
    RETURN QUERY SELECT true, v_new, (v_new <= 0);
END; $$;

-- Check créditos (antes de conectar llamada)
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

-- Ejecutar recálculo inicial para poblar precios
SELECT recalculate_package_prices();
