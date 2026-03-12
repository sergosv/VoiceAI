"""Rutas administrativas: gestión de usuarios y overview del sistema."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from api.deps import get_supabase
from api.middleware.auth import CurrentUser, require_admin

router = APIRouter()
logger = logging.getLogger("api.admin")


# --- Schemas ---


class UserUpdateRequest(BaseModel):
    """Campos editables de un usuario por admin."""

    role: str | None = None
    is_active: bool | None = None
    display_name: str | None = None


class UserOut(BaseModel):
    """Representación de usuario para respuesta."""

    id: str
    email: str
    role: str
    client_id: str | None = None
    display_name: str | None = None
    is_active: bool
    created_at: str
    client_name: str | None = None


class SystemOverview(BaseModel):
    """Estadísticas globales del sistema."""

    total_clients: int
    total_users: int
    total_calls_24h: int
    total_revenue_30d: float
    recent_payments: list[dict[str, Any]]
    failed_webhooks: int
    active_campaigns: int


# --- Endpoints ---


@router.get("/users", response_model=list[UserOut])
async def list_users(
    admin: CurrentUser = Depends(require_admin),
) -> list[UserOut]:
    """Lista todos los usuarios con el nombre de su cliente asociado."""
    sb = get_supabase()

    # Obtener usuarios
    result = (
        sb.table("users")
        .select("id, email, role, client_id, display_name, is_active, created_at")
        .order("created_at", desc=True)
        .execute()
    )
    users = result.data or []

    # Obtener nombres de clientes en un solo query para evitar N+1
    client_ids = list({u["client_id"] for u in users if u.get("client_id")})
    client_names: dict[str, str] = {}
    if client_ids:
        clients_result = (
            sb.table("clients")
            .select("id, name")
            .in_("id", client_ids)
            .execute()
        )
        client_names = {c["id"]: c["name"] for c in (clients_result.data or [])}

    return [
        UserOut(
            id=str(u["id"]),
            email=u["email"],
            role=u["role"],
            client_id=str(u["client_id"]) if u.get("client_id") else None,
            display_name=u.get("display_name"),
            is_active=u.get("is_active", True),
            created_at=u["created_at"],
            client_name=client_names.get(str(u["client_id"])) if u.get("client_id") else None,
        )
        for u in users
    ]


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    req: UserUpdateRequest,
    admin: CurrentUser = Depends(require_admin),
) -> UserOut:
    """Actualiza rol, estado activo o display_name de un usuario (solo admin)."""
    updates = req.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sin cambios",
        )

    # Validar rol si se envía
    if "role" in updates and updates["role"] not in ("admin", "client"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rol inválido. Opciones: admin, client",
        )

    sb = get_supabase()

    # Verificar que el usuario existe
    existing = (
        sb.table("users")
        .select("id")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    result = (
        sb.table("users")
        .update(updates)
        .eq("id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error actualizando usuario",
        )

    u = result.data[0]

    # Obtener nombre del cliente si aplica
    client_name: str | None = None
    if u.get("client_id"):
        client_result = (
            sb.table("clients")
            .select("name")
            .eq("id", u["client_id"])
            .limit(1)
            .execute()
        )
        if client_result.data:
            client_name = client_result.data[0]["name"]

    logger.info("Admin %s actualizó usuario %s: %s", admin.email, user_id, updates)

    return UserOut(
        id=str(u["id"]),
        email=u["email"],
        role=u["role"],
        client_id=str(u["client_id"]) if u.get("client_id") else None,
        display_name=u.get("display_name"),
        is_active=u.get("is_active", True),
        created_at=u["created_at"],
        client_name=client_name,
    )


@router.get("/system/overview", response_model=SystemOverview)
async def system_overview(
    admin: CurrentUser = Depends(require_admin),
) -> SystemOverview:
    """Estadísticas globales del sistema: clientes, usuarios, llamadas, ingresos."""
    sb = get_supabase()
    now = datetime.now(timezone.utc)

    # Total clientes
    clients_result = sb.table("clients").select("id", count="exact").execute()
    total_clients = clients_result.count or 0

    # Total usuarios
    users_result = sb.table("users").select("id", count="exact").execute()
    total_users = users_result.count or 0

    # Llamadas últimas 24h
    since_24h = (now - timedelta(hours=24)).isoformat()
    calls_result = (
        sb.table("calls")
        .select("id", count="exact")
        .gte("started_at", since_24h)
        .execute()
    )
    total_calls_24h = calls_result.count or 0

    # Ingresos últimos 30 días (compras de créditos)
    since_30d = (now - timedelta(days=30)).isoformat()
    revenue_result = (
        sb.table("credit_transactions")
        .select("amount")
        .eq("type", "purchase")
        .gte("created_at", since_30d)
        .execute()
    )
    total_revenue_30d = sum(
        float(r.get("amount", 0)) for r in (revenue_result.data or [])
    )

    # Pagos recientes (últimos 10 purchases con nombre de cliente)
    payments_result = (
        sb.table("credit_transactions")
        .select("id, client_id, amount, created_at, description")
        .eq("type", "purchase")
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )
    payments = payments_result.data or []

    # Resolver nombres de clientes para los pagos
    payment_client_ids = list({p["client_id"] for p in payments if p.get("client_id")})
    payment_client_names: dict[str, str] = {}
    if payment_client_ids:
        pc_result = (
            sb.table("clients")
            .select("id, name")
            .in_("id", payment_client_ids)
            .execute()
        )
        payment_client_names = {c["id"]: c["name"] for c in (pc_result.data or [])}

    recent_payments = [
        {
            "id": p["id"],
            "client_id": p["client_id"],
            "client_name": payment_client_names.get(str(p["client_id"]), "Desconocido"),
            "amount": float(p.get("amount", 0)),
            "created_at": p["created_at"],
            "description": p.get("description"),
        }
        for p in payments
    ]

    # Webhooks fallidos (dead letter)
    failed_wh_result = (
        sb.table("webhook_deliveries")
        .select("id", count="exact")
        .eq("status", "dead_letter")
        .execute()
    )
    failed_webhooks = failed_wh_result.count or 0

    # Campañas activas
    campaigns_result = (
        sb.table("campaigns")
        .select("id", count="exact")
        .eq("status", "running")
        .execute()
    )
    active_campaigns = campaigns_result.count or 0

    return SystemOverview(
        total_clients=total_clients,
        total_users=total_users,
        total_calls_24h=total_calls_24h,
        total_revenue_30d=round(total_revenue_30d, 2),
        recent_payments=recent_payments,
        failed_webhooks=failed_webhooks,
        active_campaigns=active_campaigns,
    )
