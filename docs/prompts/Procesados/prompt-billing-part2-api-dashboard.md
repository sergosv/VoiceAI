# PROMPT PARA CLAUDE CODE - Sistema de Creditos (PARTE 2 de 2)
## API + Dashboard Completo + Alertas

Continuacion de prompt-billing-part1.md. Esta parte tiene: API endpoints, dashboard COMPLETO del cliente, panel admin COMPLETO con slider de margen, registro con creditos gratis, alertas, y resumen de archivos.

---

## PARTE 4: API ENDPOINTS (api/routes/billing.py)

```python
"""
api/routes/billing.py - Endpoints de creditos, paquetes, compras, admin pricing.

Endpoints cliente:
  GET  /billing/balance/{client_id}      - Balance actual
  GET  /billing/packages                 - Paquetes disponibles
  POST /billing/purchase                 - Iniciar compra
  GET  /billing/transactions/{client_id} - Historial

Endpoints admin:
  GET   /billing/admin/pricing           - Config actual + calculados
  PATCH /billing/admin/pricing           - Actualizar + recalcular cascada
  POST  /billing/admin/gift-credits      - Regalar creditos
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import os

from payments import create_stripe_checkout, create_mercadopago_preference

router = APIRouter(prefix="/billing", tags=["billing"])


# ===== ENDPOINTS CLIENTE =====

@router.get("/balance/{client_id}")
async def get_balance(client_id: str):
    """Balance actual de creditos del cliente."""
    result = supabase.table("credit_balances") \
        .select("*") \
        .eq("client_id", client_id) \
        .single() \
        .execute()
    if not result.data:
        return {
            "balance": 0,
            "total_purchased": 0,
            "total_consumed": 0,
            "total_gifted": 0,
        }
    return result.data


@router.get("/packages")
async def list_packages():
    """Paquetes disponibles con precios actuales calculados."""
    result = supabase.table("credit_packages") \
        .select("*") \
        .eq("is_active", True) \
        .order("sort_order") \
        .execute()
    return result.data or []


@router.post("/purchase")
async def purchase_credits(purchase: PurchaseRequest):
    """Iniciar compra. Crea sesion de pago, retorna URL para redirigir."""
    # Obtener paquete
    package = supabase.table("credit_packages") \
        .select("*") \
        .eq("id", purchase.package_id) \
        .single() \
        .execute()
    if not package.data:
        raise HTTPException(404, "Package not found")

    pkg = package.data
    base_url = os.environ.get("DASHBOARD_URL", "https://app.example.com")

    if purchase.payment_method == "stripe":
        return await create_stripe_checkout(
            client_id=purchase.client_id,
            package_id=purchase.package_id,
            package_name=pkg["name"],
            price_usd=float(pkg["price_usd"]),
            credits=pkg["credits"],
            success_url=f"{base_url}/billing?status=success",
            cancel_url=f"{base_url}/billing?status=cancelled",
        )
    elif purchase.payment_method == "mercadopago":
        return await create_mercadopago_preference(
            client_id=purchase.client_id,
            package_id=purchase.package_id,
            package_name=pkg["name"],
            price_mxn=float(pkg["price_mxn"]),
            credits=pkg["credits"],
            success_url=f"{base_url}/billing?status=success",
            cancel_url=f"{base_url}/billing?status=cancelled",
        )

    raise HTTPException(400, "Invalid payment method. Use 'stripe' or 'mercadopago'")


@router.get("/transactions/{client_id}")
async def list_transactions(client_id: str, limit: int = 50):
    """Historial de transacciones de creditos."""
    result = supabase.table("credit_transactions") \
        .select("*") \
        .eq("client_id", client_id) \
        .order("created_at", desc=True) \
        .limit(limit) \
        .execute()
    return result.data or []


# ===== ENDPOINTS ADMIN =====

@router.get("/admin/pricing")
async def get_pricing_config():
    """Config actual + campos calculados para UI del admin."""
    result = supabase.table("pricing_config").select("*").limit(1).execute()
    if not result.data:
        raise HTTPException(404, "Pricing config not found")

    config = result.data[0]

    # Calcular campos derivados para mostrar en UI
    cost_per_min = (
        float(config["cost_twilio_per_min"])
        + float(config["cost_stt_per_min"])
        + float(config["cost_llm_per_min"])
        + float(config["cost_tts_per_min"])
        + float(config["cost_livekit_per_min"])
        + float(config["cost_mcp_per_min"])
    )
    margin = float(config["profit_margin"])
    price_per_credit = cost_per_min / (1 - margin) if margin < 1 else 0

    config["_calculated"] = {
        "cost_per_min_usd": round(cost_per_min, 4),
        "price_per_credit_usd": round(price_per_credit, 4),
        "profit_per_credit_usd": round(price_per_credit - cost_per_min, 4),
    }
    return config


@router.patch("/admin/pricing")
async def update_pricing(update: PricingUpdate):
    """Actualizar config de precios. RECALCULA TODOS LOS PAQUETES en cascada."""
    data = update.model_dump(exclude_none=True)
    data["updated_at"] = datetime.utcnow().isoformat()

    # Obtener ID de la config
    config = supabase.table("pricing_config").select("id").limit(1).execute()
    if not config.data:
        raise HTTPException(404, "Pricing config not found")

    # Actualizar config
    supabase.table("pricing_config") \
        .update(data) \
        .eq("id", config.data[0]["id"]) \
        .execute()

    # CASCADA: recalcular todos los paquetes
    supabase.rpc("recalculate_package_prices").execute()

    # Retornar paquetes actualizados para que admin vea resultado
    packages = supabase.table("credit_packages") \
        .select("*") \
        .eq("is_active", True) \
        .order("sort_order") \
        .execute()

    return {
        "message": "Precios actualizados y paquetes recalculados",
        "packages": packages.data,
    }


@router.post("/admin/gift-credits")
async def gift_credits(gift: GiftCreditsRequest):
    """Regalar creditos a un cliente (admin only)."""
    result = supabase.rpc("add_credits", {
        "p_client_id": gift.client_id,
        "p_credits": gift.credits,
        "p_type": "gift",
        "p_reason": gift.reason,
        "p_admin_email": gift.admin_email,
    }).execute()
    return {"new_balance": result.data, "gifted": gift.credits}


# ===== SCHEMAS =====

class PurchaseRequest(BaseModel):
    client_id: str
    package_id: str
    payment_method: str  # 'stripe' o 'mercadopago'


class PricingUpdate(BaseModel):
    cost_twilio_per_min: Optional[float] = None
    cost_stt_per_min: Optional[float] = None
    cost_llm_per_min: Optional[float] = None
    cost_tts_per_min: Optional[float] = None
    cost_livekit_per_min: Optional[float] = None
    cost_mcp_per_min: Optional[float] = None
    profit_margin: Optional[float] = None
    free_credits_new_account: Optional[int] = None
    usd_to_mxn_rate: Optional[float] = None


class GiftCreditsRequest(BaseModel):
    client_id: str
    credits: float
    reason: str
    admin_email: str
```

---

## PARTE 5: DASHBOARD CLIENTE COMPLETO (dashboard/src/pages/Billing.jsx)

Este es el componente COMPLETO con toda la logica. Muestra balance, paquetes de compra con Stripe y MercadoPago, e historial de transacciones.

```jsx
import React, { useState, useEffect } from "react";
import { useAuth } from "../hooks/useAuth";

// Helpers
function formatDate(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return d.toLocaleDateString("es-MX", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function typeLabel(type) {
    switch (type) {
        case "purchase": return "Compra";
        case "consumption": return "Consumo";
        case "gift": return "Regalo";
        case "refund": return "Reembolso";
        case "adjustment": return "Ajuste";
        default: return type;
    }
}

function typeBadgeClass(type) {
    switch (type) {
        case "purchase": return "bg-green-100 text-green-700";
        case "consumption": return "bg-red-100 text-red-700";
        case "gift": return "bg-purple-100 text-purple-700";
        case "refund": return "bg-yellow-100 text-yellow-700";
        default: return "bg-gray-100 text-gray-700";
    }
}

function txDetail(tx) {
    if (tx.type === "purchase") {
        return `${tx.currency} $${tx.amount_paid} via ${tx.payment_provider}`;
    }
    if (tx.type === "consumption" && tx.duration_seconds) {
        return `${Math.round(tx.duration_seconds / 60)} min llamada`;
    }
    return tx.reason || "";
}


export default function BillingPage() {
    const { clientId, token } = useAuth();
    const [balance, setBalance] = useState(null);
    const [packages, setPackages] = useState([]);
    const [transactions, setTransactions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [purchasing, setPurchasing] = useState(null);

    const API_BASE = import.meta.env.VITE_API_URL || "";

    // Cargar datos al montar
    useEffect(() => {
        if (!clientId) return;
        Promise.all([
            fetch(`${API_BASE}/billing/balance/${clientId}`, {
                headers: { Authorization: `Bearer ${token}` },
            }).then((r) => r.json()),
            fetch(`${API_BASE}/billing/packages`, {
                headers: { Authorization: `Bearer ${token}` },
            }).then((r) => r.json()),
            fetch(`${API_BASE}/billing/transactions/${clientId}?limit=50`, {
                headers: { Authorization: `Bearer ${token}` },
            }).then((r) => r.json()),
        ])
            .then(([bal, pkgs, txs]) => {
                setBalance(bal);
                setPackages(pkgs);
                setTransactions(txs);
            })
            .catch((err) => console.error("Billing load error:", err))
            .finally(() => setLoading(false));
    }, [clientId]);

    // Comprar paquete
    async function handlePurchase(packageId, paymentMethod) {
        setPurchasing(packageId + paymentMethod);
        try {
            const res = await fetch(`${API_BASE}/billing/purchase`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({
                    client_id: clientId,
                    package_id: packageId,
                    payment_method: paymentMethod,
                }),
            });
            const data = await res.json();
            if (data.checkout_url) {
                window.location.href = data.checkout_url;
            }
        } catch (err) {
            console.error("Purchase error:", err);
            alert("Error al procesar compra. Intenta de nuevo.");
        } finally {
            setPurchasing(null);
        }
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
            </div>
        );
    }

    return (
        <div className="max-w-4xl mx-auto p-6">
            {/* ===== BALANCE ACTUAL ===== */}
            <div className="bg-gradient-to-r from-blue-600 to-blue-800 rounded-xl p-6 text-white mb-8">
                <div className="text-sm opacity-80">Tu balance actual</div>
                <div className="text-4xl font-bold mt-1">
                    {balance?.balance?.toFixed(0) || 0} creditos
                </div>
                <div className="text-sm opacity-70 mt-1">
                    = {balance?.balance?.toFixed(0) || 0} minutos de agente IA
                </div>
                {balance?.balance < 20 && balance?.balance > 0 && (
                    <div className="mt-3 bg-yellow-500/20 rounded px-3 py-2 text-sm">
                        Tu balance es bajo. Recarga para no interrumpir el servicio.
                    </div>
                )}
                {balance?.balance <= 0 && (
                    <div className="mt-3 bg-red-500/20 rounded px-3 py-2 text-sm">
                        Sin creditos. Tu agente no podra atender llamadas hasta que recargues.
                    </div>
                )}
            </div>

            {/* ===== ESTADISTICAS ===== */}
            <div className="grid grid-cols-3 gap-4 mb-8">
                <div className="bg-white border rounded-lg p-4">
                    <div className="text-xs text-gray-500">Total comprado</div>
                    <div className="text-xl font-bold text-green-600">
                        {balance?.total_purchased?.toFixed(0) || 0} min
                    </div>
                </div>
                <div className="bg-white border rounded-lg p-4">
                    <div className="text-xs text-gray-500">Total consumido</div>
                    <div className="text-xl font-bold text-red-600">
                        {balance?.total_consumed?.toFixed(0) || 0} min
                    </div>
                </div>
                <div className="bg-white border rounded-lg p-4">
                    <div className="text-xs text-gray-500">Creditos de regalo</div>
                    <div className="text-xl font-bold text-purple-600">
                        {balance?.total_gifted?.toFixed(0) || 0} min
                    </div>
                </div>
            </div>

            {/* ===== PAQUETES DE CREDITOS ===== */}
            <h2 className="text-xl font-semibold mb-4">Comprar creditos</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                {packages.map((pkg) => (
                    <div
                        key={pkg.id}
                        className={`border rounded-xl p-5 relative ${
                            pkg.is_popular
                                ? "border-blue-500 ring-2 ring-blue-200"
                                : "border-gray-200"
                        }`}
                    >
                        {pkg.is_popular && (
                            <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-blue-500 text-white text-xs px-3 py-1 rounded-full">
                                Mas popular
                            </div>
                        )}
                        <h3 className="font-semibold text-lg">{pkg.name}</h3>
                        <p className="text-xs text-gray-400 mt-1">{pkg.description}</p>
                        <div className="text-3xl font-bold mt-3">
                            {pkg.credits.toLocaleString()}
                            <span className="text-sm font-normal text-gray-500">
                                {" "}min
                            </span>
                        </div>
                        <div className="text-sm text-gray-500 mt-1">
                            ${pkg.price_per_credit_usd}/min
                        </div>
                        <div className="mt-3">
                            <div className="text-xl font-semibold">
                                ${pkg.price_usd} USD
                            </div>
                            <div className="text-sm text-gray-400">
                                ${pkg.price_mxn} MXN
                            </div>
                        </div>
                        {pkg.volume_discount > 0 && (
                            <div className="text-xs text-green-600 mt-1">
                                {(pkg.volume_discount * 100).toFixed(0)}% descuento
                                incluido
                            </div>
                        )}
                        <div className="mt-4 space-y-2">
                            <button
                                onClick={() => handlePurchase(pkg.id, "stripe")}
                                disabled={purchasing !== null}
                                className="w-full bg-blue-600 text-white rounded py-2 text-sm hover:bg-blue-700 disabled:opacity-50"
                            >
                                {purchasing === pkg.id + "stripe"
                                    ? "Procesando..."
                                    : "Pagar con tarjeta"}
                            </button>
                            <button
                                onClick={() => handlePurchase(pkg.id, "mercadopago")}
                                disabled={purchasing !== null}
                                className="w-full bg-sky-500 text-white rounded py-2 text-sm hover:bg-sky-600 disabled:opacity-50"
                            >
                                {purchasing === pkg.id + "mercadopago"
                                    ? "Procesando..."
                                    : "Mercado Pago / OXXO"}
                            </button>
                        </div>
                    </div>
                ))}
            </div>

            {/* ===== HISTORIAL DE TRANSACCIONES ===== */}
            <h2 className="text-xl font-semibold mb-4">Historial de transacciones</h2>
            {transactions.length === 0 ? (
                <div className="text-center text-gray-400 py-8 border rounded-xl">
                    No hay transacciones aun
                </div>
            ) : (
                <div className="border rounded-xl overflow-hidden">
                    <table className="w-full text-sm">
                        <thead className="bg-gray-50">
                            <tr>
                                <th className="text-left p-3 font-medium">Fecha</th>
                                <th className="text-left p-3 font-medium">Tipo</th>
                                <th className="text-right p-3 font-medium">Creditos</th>
                                <th className="text-right p-3 font-medium">Balance</th>
                                <th className="text-left p-3 font-medium">Detalle</th>
                            </tr>
                        </thead>
                        <tbody>
                            {transactions.map((tx) => (
                                <tr key={tx.id} className="border-t hover:bg-gray-50">
                                    <td className="p-3 text-gray-600">
                                        {formatDate(tx.created_at)}
                                    </td>
                                    <td className="p-3">
                                        <span
                                            className={`px-2 py-0.5 rounded text-xs font-medium ${typeBadgeClass(
                                                tx.type
                                            )}`}
                                        >
                                            {typeLabel(tx.type)}
                                        </span>
                                    </td>
                                    <td
                                        className={`p-3 text-right font-medium ${
                                            tx.credits > 0
                                                ? "text-green-600"
                                                : "text-red-600"
                                        }`}
                                    >
                                        {tx.credits > 0 ? "+" : ""}
                                        {tx.credits}
                                    </td>
                                    <td className="p-3 text-right text-gray-600">
                                        {tx.balance_after}
                                    </td>
                                    <td className="p-3 text-gray-500 text-xs">
                                        {txDetail(tx)}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
```

---

## PARTE 6: PANEL ADMIN PRECIOS COMPLETO (dashboard/src/pages/admin/PricingConfig.jsx)

Este es el componente COMPLETO del panel admin. Incluye: 3 cards de resumen, SLIDER de margen, inputs de costos por proveedor, tipo de cambio, tabla de vista previa de paquetes recalculados en tiempo real, y boton guardar con cascada.

```jsx
import React, { useState, useEffect } from "react";
import { useAuth } from "../../hooks/useAuth";

export default function PricingConfigPage() {
    const { token } = useAuth();
    const [config, setConfig] = useState(null);
    const [packages, setPackages] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [saveMessage, setSaveMessage] = useState(null);

    const API_BASE = import.meta.env.VITE_API_URL || "";

    // Cargar config y paquetes al montar
    useEffect(() => {
        Promise.all([
            fetch(`${API_BASE}/billing/admin/pricing`, {
                headers: { Authorization: `Bearer ${token}` },
            }).then((r) => r.json()),
            fetch(`${API_BASE}/billing/packages`, {
                headers: { Authorization: `Bearer ${token}` },
            }).then((r) => r.json()),
        ])
            .then(([cfg, pkgs]) => {
                setConfig(cfg);
                setPackages(pkgs);
            })
            .catch((err) => console.error("Pricing load error:", err))
            .finally(() => setLoading(false));
    }, []);

    // Calculos en tiempo real
    const costPerMin = config
        ? parseFloat(config.cost_twilio_per_min || 0) +
          parseFloat(config.cost_stt_per_min || 0) +
          parseFloat(config.cost_llm_per_min || 0) +
          parseFloat(config.cost_tts_per_min || 0) +
          parseFloat(config.cost_livekit_per_min || 0) +
          parseFloat(config.cost_mcp_per_min || 0)
        : 0;

    const margin = config ? parseFloat(config.profit_margin || 0.75) : 0.75;
    const pricePerCredit = margin < 1 ? costPerMin / (1 - margin) : 0;
    const profitPerCredit = pricePerCredit - costPerMin;

    // Actualizar un campo de config
    function updateConfig(key, value) {
        setConfig((prev) => ({ ...prev, [key]: value }));
        setSaveMessage(null);
    }

    // Guardar y recalcular
    async function saveAndRecalculate() {
        setSaving(true);
        setSaveMessage(null);
        try {
            const res = await fetch(`${API_BASE}/billing/admin/pricing`, {
                method: "PATCH",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({
                    cost_twilio_per_min: parseFloat(config.cost_twilio_per_min),
                    cost_stt_per_min: parseFloat(config.cost_stt_per_min),
                    cost_llm_per_min: parseFloat(config.cost_llm_per_min),
                    cost_tts_per_min: parseFloat(config.cost_tts_per_min),
                    cost_livekit_per_min: parseFloat(config.cost_livekit_per_min),
                    cost_mcp_per_min: parseFloat(config.cost_mcp_per_min),
                    profit_margin: parseFloat(config.profit_margin),
                    free_credits_new_account: parseInt(
                        config.free_credits_new_account
                    ),
                    usd_to_mxn_rate: parseFloat(config.usd_to_mxn_rate),
                }),
            });
            const data = await res.json();
            if (data.packages) {
                setPackages(data.packages);
            }
            setSaveMessage({
                type: "success",
                text: "Precios actualizados y paquetes recalculados",
            });
        } catch (err) {
            console.error("Save error:", err);
            setSaveMessage({ type: "error", text: "Error al guardar" });
        } finally {
            setSaving(false);
        }
    }

    // Lista de proveedores para el grid de inputs
    const providerCosts = [
        { key: "cost_twilio_per_min", label: "Twilio (telefonia)" },
        { key: "cost_stt_per_min", label: "Deepgram (STT)" },
        { key: "cost_llm_per_min", label: "Gemini (LLM)" },
        { key: "cost_tts_per_min", label: "Cartesia (TTS)" },
        { key: "cost_livekit_per_min", label: "LiveKit Cloud" },
        { key: "cost_mcp_per_min", label: "MCP / Tools (promedio)" },
    ];

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
            </div>
        );
    }

    return (
        <div className="max-w-4xl mx-auto p-6">
            <h1 className="text-2xl font-bold mb-6">Configuracion de Precios</h1>

            {/* ===== 3 CARDS RESUMEN ===== */}
            <div className="grid grid-cols-3 gap-4 mb-8">
                <div className="bg-red-50 rounded-xl p-4">
                    <div className="text-sm text-red-600">Costo base / minuto</div>
                    <div className="text-2xl font-bold text-red-700">
                        ${costPerMin.toFixed(4)} USD
                    </div>
                    <div className="text-xs text-red-400">
                        Lo que pagas a proveedores
                    </div>
                </div>
                <div className="bg-green-50 rounded-xl p-4">
                    <div className="text-sm text-green-600">
                        Precio al cliente / minuto
                    </div>
                    <div className="text-2xl font-bold text-green-700">
                        ${pricePerCredit.toFixed(4)} USD
                    </div>
                    <div className="text-xs text-green-400">
                        Lo que cobra al cliente
                    </div>
                </div>
                <div className="bg-blue-50 rounded-xl p-4">
                    <div className="text-sm text-blue-600">
                        Tu ganancia / minuto
                    </div>
                    <div className="text-2xl font-bold text-blue-700">
                        ${profitPerCredit.toFixed(4)} USD
                    </div>
                    <div className="text-xs text-blue-400">
                        {(margin * 100).toFixed(0)}% de margen
                    </div>
                </div>
            </div>

            {/* ===== SLIDER DE MARGEN (EL CONTROL PRINCIPAL) ===== */}
            <div className="bg-white border rounded-xl p-6 mb-8">
                <h2 className="font-semibold text-lg mb-4">
                    Margen de ganancia
                </h2>
                <div className="flex items-center gap-4">
                    <span className="text-sm text-gray-500">50%</span>
                    <input
                        type="range"
                        min="0.50"
                        max="0.90"
                        step="0.01"
                        value={margin}
                        onChange={(e) =>
                            updateConfig("profit_margin", e.target.value)
                        }
                        className="flex-1 h-3 rounded-lg appearance-none cursor-pointer
                                   bg-gradient-to-r from-yellow-400 via-green-400 to-green-600"
                    />
                    <span className="text-sm text-gray-500">90%</span>
                    <span className="text-2xl font-bold w-20 text-center">
                        {(margin * 100).toFixed(0)}%
                    </span>
                </div>
                <div className="text-xs text-gray-400 mt-2">
                    Mueve el slider y los paquetes se recalculan al guardar.
                    Los clientes existentes no se afectan.
                </div>
            </div>

            {/* ===== COSTOS POR PROVEEDOR ===== */}
            <div className="bg-white border rounded-xl p-6 mb-8">
                <h2 className="font-semibold text-lg mb-4">
                    Costos por proveedor (USD / minuto)
                </h2>
                <p className="text-xs text-gray-400 mb-4">
                    Actualiza estos valores si cambian las tarifas de tus
                    proveedores. El costo total se suma automaticamente.
                </p>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    {providerCosts.map((item) => (
                        <div key={item.key}>
                            <label className="text-xs text-gray-500 block mb-1">
                                {item.label}
                            </label>
                            <input
                                type="number"
                                step="0.001"
                                min="0"
                                value={config?.[item.key] || 0}
                                onChange={(e) =>
                                    updateConfig(item.key, e.target.value)
                                }
                                className="w-full border rounded px-3 py-2 text-sm
                                           focus:ring-2 focus:ring-blue-200 focus:border-blue-400"
                            />
                        </div>
                    ))}
                </div>
                <div className="mt-4 pt-4 border-t flex justify-between items-center">
                    <span className="text-sm text-gray-500">
                        Costo total por minuto:
                    </span>
                    <span className="text-lg font-bold text-red-600">
                        ${costPerMin.toFixed(4)} USD
                    </span>
                </div>
            </div>

            {/* ===== TIPO DE CAMBIO ===== */}
            <div className="bg-white border rounded-xl p-6 mb-8">
                <h2 className="font-semibold text-lg mb-4">Tipo de cambio</h2>
                <div className="flex items-center gap-4">
                    <span className="text-sm">1 USD =</span>
                    <input
                        type="number"
                        step="0.01"
                        min="1"
                        value={config?.usd_to_mxn_rate || 20}
                        onChange={(e) =>
                            updateConfig("usd_to_mxn_rate", e.target.value)
                        }
                        className="border rounded px-3 py-2 w-32 text-sm
                                   focus:ring-2 focus:ring-blue-200"
                    />
                    <span className="text-sm">MXN</span>
                </div>
                <p className="text-xs text-gray-400 mt-2">
                    Actualiza manualmente. Puedes agregar API automatica
                    despues.
                </p>
            </div>

            {/* ===== CREDITOS GRATIS PARA NUEVAS CUENTAS ===== */}
            <div className="bg-white border rounded-xl p-6 mb-8">
                <h2 className="font-semibold text-lg mb-4">
                    Creditos de bienvenida
                </h2>
                <div className="flex items-center gap-4">
                    <span className="text-sm">Cuentas nuevas reciben:</span>
                    <input
                        type="number"
                        step="1"
                        min="0"
                        value={config?.free_credits_new_account || 10}
                        onChange={(e) =>
                            updateConfig(
                                "free_credits_new_account",
                                e.target.value
                            )
                        }
                        className="border rounded px-3 py-2 w-24 text-sm"
                    />
                    <span className="text-sm">creditos gratis</span>
                </div>
            </div>

            {/* ===== VISTA PREVIA PAQUETES (recalculados en tiempo real) ===== */}
            <div className="bg-white border rounded-xl p-6 mb-8">
                <h2 className="font-semibold text-lg mb-4">
                    Vista previa de paquetes
                </h2>
                <p className="text-xs text-gray-400 mb-4">
                    Estos precios se actualizan en tiempo real mientras mueves
                    el slider. Click en "Guardar" para aplicar.
                </p>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b bg-gray-50">
                                <th className="text-left p-2 font-medium">
                                    Paquete
                                </th>
                                <th className="text-right p-2 font-medium">
                                    Creditos
                                </th>
                                <th className="text-right p-2 font-medium">
                                    Descuento
                                </th>
                                <th className="text-right p-2 font-medium">
                                    $/min
                                </th>
                                <th className="text-right p-2 font-medium">
                                    Precio USD
                                </th>
                                <th className="text-right p-2 font-medium">
                                    Precio MXN
                                </th>
                                <th className="text-right p-2 font-medium">
                                    Tu ganancia
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            {packages.map((pkg) => {
                                const effectivePrice =
                                    pricePerCredit *
                                    (1 - (pkg.volume_discount || 0));
                                const pkgPriceUsd =
                                    pkg.credits * effectivePrice;
                                const pkgPriceMxn =
                                    pkgPriceUsd *
                                    parseFloat(
                                        config?.usd_to_mxn_rate || 20
                                    );
                                const pkgProfit =
                                    pkgPriceUsd -
                                    costPerMin * pkg.credits;

                                return (
                                    <tr
                                        key={pkg.id}
                                        className="border-b hover:bg-gray-50"
                                    >
                                        <td className="p-2 font-medium">
                                            {pkg.name}
                                            {pkg.is_popular && (
                                                <span className="ml-2 text-xs text-blue-500">
                                                    Popular
                                                </span>
                                            )}
                                        </td>
                                        <td className="p-2 text-right">
                                            {pkg.credits.toLocaleString()}
                                        </td>
                                        <td className="p-2 text-right">
                                            {pkg.volume_discount > 0
                                                ? `${(pkg.volume_discount * 100).toFixed(0)}%`
                                                : "-"}
                                        </td>
                                        <td className="p-2 text-right">
                                            ${effectivePrice.toFixed(4)}
                                        </td>
                                        <td className="p-2 text-right font-medium">
                                            ${pkgPriceUsd.toFixed(2)}
                                        </td>
                                        <td className="p-2 text-right">
                                            ${pkgPriceMxn.toFixed(2)}
                                        </td>
                                        <td className="p-2 text-right text-green-600 font-medium">
                                            ${pkgProfit.toFixed(2)}
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* ===== BOTON GUARDAR ===== */}
            {saveMessage && (
                <div
                    className={`mb-4 p-3 rounded-lg text-sm ${
                        saveMessage.type === "success"
                            ? "bg-green-50 text-green-700 border border-green-200"
                            : "bg-red-50 text-red-700 border border-red-200"
                    }`}
                >
                    {saveMessage.text}
                </div>
            )}
            <button
                onClick={saveAndRecalculate}
                disabled={saving}
                className="w-full bg-green-600 text-white rounded-xl py-3 font-semibold
                           hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed
                           transition-colors"
            >
                {saving
                    ? "Guardando y recalculando..."
                    : "Guardar y recalcular paquetes"}
            </button>
            <p className="text-xs text-gray-400 mt-2 text-center">
                Los clientes existentes no se afectan. Los nuevos precios
                aplican solo para compras futuras.
            </p>
        </div>
    );
}
```

---

## PARTE 7: REGISTRO + CREDITOS GRATIS

```python
"""
Agregar este hook en el flujo de registro de clientes.
Cuando un cliente se crea, recibe creditos de bienvenida automaticamente.
"""
async def on_client_created(client_id: str):
    """Hook post-registro. Otorga creditos de bienvenida."""
    # Leer cuantos creditos dar de la config
    config = supabase.table("pricing_config") \
        .select("free_credits_new_account") \
        .limit(1) \
        .execute()
    free_credits = config.data[0]["free_credits_new_account"] if config.data else 10

    # Acreditar
    supabase.rpc("add_credits", {
        "p_client_id": client_id,
        "p_credits": free_credits,
        "p_type": "gift",
        "p_reason": "Creditos de bienvenida",
    }).execute()

    logger.info(f"New client {client_id}: {free_credits} free credits added")
```

---

## PARTE 8: ALERTAS DE BALANCE BAJO (api/tasks/credit_alerts.py)

```python
"""
api/tasks/credit_alerts.py - Cron job para alertas de balance bajo.
Ejecutar cada hora con cron, Supabase Edge Function, o similar.

Logica:
- Si balance < 20% del total comprado -> email "warning"
- Si balance < 5% del total comprado -> email "critical"
- No repite la misma alerta si ya se envio
"""
import logging
from datetime import datetime

logger = logging.getLogger("credit_alerts")


async def check_low_balances():
    """Revisa balances bajos y envia alertas por email."""
    # Leer umbrales de la config
    config = supabase.table("pricing_config") \
        .select("alert_threshold_warning, alert_threshold_critical") \
        .limit(1) \
        .execute()
    if not config.data:
        return

    cfg = config.data[0]
    warning_threshold = float(cfg["alert_threshold_warning"])
    critical_threshold = float(cfg["alert_threshold_critical"])

    # Obtener clientes con balance > 0 (los de 0 ya estan bloqueados)
    balances = supabase.table("credit_balances") \
        .select("*, clients!inner(email, business_name)") \
        .gt("balance", 0) \
        .execute()

    for bal in (balances.data or []):
        # No alertar cuentas que solo tienen creditos gratis (nunca compraron)
        if bal["total_purchased"] == 0:
            continue

        # Calcular porcentaje restante
        remaining_pct = bal["balance"] / bal["total_purchased"]

        # Determinar tipo de alerta
        alert_type = None
        if remaining_pct <= critical_threshold:
            alert_type = "critical"
        elif remaining_pct <= warning_threshold:
            alert_type = "warning"

        # Enviar solo si es diferente a la ultima alerta enviada
        if alert_type and bal.get("last_alert_type") != alert_type:
            await send_credit_alert_email(
                email=bal["clients"]["email"],
                business_name=bal["clients"]["business_name"],
                balance=bal["balance"],
                alert_type=alert_type,
            )

            # Marcar alerta enviada para no repetir
            supabase.table("credit_balances").update({
                "last_alert_sent_at": datetime.utcnow().isoformat(),
                "last_alert_type": alert_type,
            }).eq("id", bal["id"]).execute()

            logger.info(
                f"Alert '{alert_type}' sent to {bal['clients']['email']} "
                f"(balance: {bal['balance']})"
            )


async def send_credit_alert_email(
    email: str, business_name: str, balance: float, alert_type: str
):
    """Envia email de alerta. Implementar con tu proveedor de email."""
    # TODO: Implementar con SendGrid, SES, Resend, etc.
    # Ejemplo con estructura basica:
    if alert_type == "critical":
        subject = f"URGENTE: Tu agente IA se quedara sin creditos pronto"
        body = (
            f"Hola {business_name},\n\n"
            f"Tu balance es de solo {balance:.0f} minutos. "
            f"Tu agente dejara de atender llamadas cuando se agoten.\n\n"
            f"Recarga ahora para no interrumpir tu servicio."
        )
    else:
        subject = f"Aviso: Tu balance de creditos esta bajo"
        body = (
            f"Hola {business_name},\n\n"
            f"Te quedan {balance:.0f} minutos de agente IA. "
            f"Te recomendamos recargar pronto para evitar interrupciones."
        )
    logger.info(f"Would send email to {email}: {subject}")
```

---

## PARTE 9: RESUMEN DE ARCHIVOS

```
ARCHIVOS NUEVOS:
  db/migrations/013_billing_system.sql         <- Tablas + funciones SQL
  agent/billing.py                              <- CallBilling: check/track/consume
  api/payments.py                               <- Stripe checkout + MP preference
  api/routes/billing.py                         <- Endpoints: balance, packages, purchase, admin
  api/routes/webhooks.py                        <- Webhooks: Stripe + MercadoPago
  api/tasks/credit_alerts.py                    <- Cron alertas balance bajo
  dashboard/src/pages/Billing.jsx               <- Vista cliente completa
  dashboard/src/pages/admin/PricingConfig.jsx   <- Vista admin completa con slider

ARCHIVOS MODIFICADOS:
  agent/main.py           <- Agregar billing check + consume en flujo de llamada
  api/main.py             <- Registrar routers de billing y webhooks
  dashboard/src/App.jsx   <- Agregar rutas /billing y /admin/pricing
  requirements.txt        <- Agregar: stripe, mercadopago

VARIABLES DE ENTORNO NUEVAS:
  STRIPE_SECRET_KEY         <- Clave secreta de Stripe
  STRIPE_WEBHOOK_SECRET     <- Secreto para validar webhooks Stripe
  MERCADOPAGO_ACCESS_TOKEN  <- Token de Mercado Pago
  MERCADOPAGO_WEBHOOK_URL   <- URL publica para webhooks MP
  DASHBOARD_URL             <- URL base del dashboard (para redirects)

NO SE TOCAN:
  Pipeline de voz (STT/TTS), Orquestador, MCP, Memoria, LiveKit, Twilio
```

## PARTE 10: ORDEN DE IMPLEMENTACION

1. Migracion SQL: tablas + funciones (15 min)
2. agent/billing.py: clase CallBilling (20 min)
3. agent/main.py: integrar check + consume (10 min)
4. api/routes/billing.py: endpoints cliente + admin (20 min)
5. dashboard Billing.jsx: vista cliente (30 min)
6. dashboard PricingConfig.jsx: admin con slider (30 min)
7. api/payments.py + webhooks: Stripe (30 min)
8. Mercado Pago integration (30 min)
9. api/tasks/credit_alerts.py: cron (15 min)
10. Probar end-to-end (20 min)

Tiempo estimado total: ~3.5 horas.
Prioridad: Steps 1-6 primero (funciona sin pagos reales con gift-credits).

## PARTE 11: PRUEBA END-TO-END

1. Ejecutar migracion SQL -> verificar tablas y datos iniciales
2. Crear cliente nuevo -> verificar recibe 10 creditos gratis
3. GET /billing/balance/{id} -> balance=10
4. GET /billing/transactions/{id} -> 1 transaccion tipo "gift"
5. Simular llamada de 2 min -> consume_credits -> balance=8
6. Dashboard cliente: muestra balance, historial con consumo
7. Admin: abrir PricingConfig, mover slider 75% a 65%
8. Guardar -> verificar paquetes recalculados (precios mas bajos)
9. Comprar paquete Starter con Stripe test card 4242424242424242
10. Webhook recibe -> creditos acreditados -> balance actualizado
11. Agotar creditos a 0 -> llamar -> agente dice "no puedo atenderte"
12. Verificar que llamada activa NO se corta, solo se bloquean nuevas
