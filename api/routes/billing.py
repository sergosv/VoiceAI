"""Endpoints de créditos, paquetes, compras y admin pricing.

Cliente:
  GET  /billing/balance       — Balance actual
  GET  /billing/packages      — Paquetes disponibles
  POST /billing/purchase      — Iniciar compra
  GET  /billing/transactions  — Historial

Admin:
  GET   /billing/admin/pricing       — Config actual + calculados
  PATCH /billing/admin/pricing       — Actualizar + recalcular cascada
  POST  /billing/admin/gift-credits  — Regalar créditos
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import get_supabase
from api.middleware.auth import CurrentUser, get_current_user
from api.payments import create_mercadopago_preference, create_stripe_checkout
from api.schemas import GiftCreditsRequest, PricingUpdate, PurchaseRequest

router = APIRouter()
logger = logging.getLogger("billing")


# ===== ENDPOINTS CLIENTE =====


@router.get("/balance")
async def get_balance(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = None,
) -> dict:
    """Balance actual de créditos del cliente."""
    sb = get_supabase()
    effective_id = user.client_id if user.role == "client" else client_id
    if not effective_id:
        return {"balance": 0, "total_purchased": 0, "total_consumed": 0, "total_gifted": 0}

    result = (
        sb.table("credit_balances")
        .select("*")
        .eq("client_id", effective_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return {"balance": 0, "total_purchased": 0, "total_consumed": 0, "total_gifted": 0}
    return result.data[0]


@router.get("/packages")
async def list_packages(
    user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    """Paquetes disponibles con precios actuales."""
    sb = get_supabase()
    result = (
        sb.table("credit_packages")
        .select("*")
        .eq("is_active", True)
        .order("sort_order")
        .execute()
    )
    return result.data or []


@router.post("/purchase")
async def purchase_credits(
    purchase: PurchaseRequest,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Iniciar compra. Crea sesión de pago, retorna URL para redirigir."""
    sb = get_supabase()

    # Obtener paquete
    pkg_result = (
        sb.table("credit_packages")
        .select("*")
        .eq("id", purchase.package_id)
        .limit(1)
        .execute()
    )
    if not pkg_result.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paquete no encontrado")

    pkg = pkg_result.data[0]
    base_url = os.environ.get("DASHBOARD_URL", "https://innotecnia.app")

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

    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        "Método de pago inválido. Usa 'stripe' o 'mercadopago'",
    )


@router.get("/transactions")
async def list_transactions(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    """Historial de transacciones de créditos."""
    sb = get_supabase()
    effective_id = user.client_id if user.role == "client" else client_id
    if not effective_id:
        return []

    result = (
        sb.table("credit_transactions")
        .select("*")
        .eq("client_id", effective_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


# ===== ENDPOINTS ADMIN =====


@router.get("/admin/pricing")
async def get_pricing_config(
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Config actual + campos calculados para UI del admin."""
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo admin")

    sb = get_supabase()
    result = sb.table("pricing_config").select("*").limit(1).execute()
    if not result.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pricing config not found")

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
async def update_pricing(
    update: PricingUpdate,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Actualizar config de precios. RECALCULA TODOS LOS PAQUETES en cascada."""
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo admin")

    sb = get_supabase()
    data = update.model_dump(exclude_none=True)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    data["updated_by"] = user.email

    # Obtener ID de la config
    config = sb.table("pricing_config").select("id").limit(1).execute()
    if not config.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pricing config not found")

    # Actualizar config
    sb.table("pricing_config").update(data).eq("id", config.data[0]["id"]).execute()

    # CASCADA: recalcular todos los paquetes
    sb.rpc("recalculate_package_prices").execute()

    # Retornar paquetes actualizados para que admin vea resultado
    packages = (
        sb.table("credit_packages")
        .select("*")
        .eq("is_active", True)
        .order("sort_order")
        .execute()
    )

    return {
        "message": "Precios actualizados y paquetes recalculados",
        "packages": packages.data,
    }


@router.post("/admin/gift-credits")
async def gift_credits(
    gift: GiftCreditsRequest,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Regalar créditos a un cliente (admin only)."""
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo admin")

    sb = get_supabase()
    result = sb.rpc("add_credits", {
        "p_client_id": gift.client_id,
        "p_credits": gift.credits,
        "p_type": "gift",
        "p_reason": gift.reason,
        "p_admin_email": gift.admin_email,
    }).execute()

    return {"new_balance": result.data, "gifted": gift.credits}
