"""Rutas administrativas: gestión de usuarios y overview del sistema."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
        .select("credits")
        .eq("type", "purchase")
        .gte("created_at", since_30d)
        .execute()
    )
    total_revenue_30d = sum(
        float(r.get("credits", 0)) for r in (revenue_result.data or [])
    )

    # Pagos recientes (últimos 10 purchases con nombre de cliente)
    payments_result = (
        sb.table("credit_transactions")
        .select("id, client_id, credits, created_at, reason")
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
            "amount": float(p.get("credits", 0)),
            "created_at": p["created_at"],
            "description": p.get("reason"),
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


@router.get("/audit-logs")
async def list_admin_audit_logs(
    admin: CurrentUser = Depends(require_admin),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    user_id: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """Lista global de audit logs para admin, con filtros y paginación."""
    sb = get_supabase()

    query = (
        sb.table("audit_logs")
        .select("*", count="exact")
        .order("created_at", desc=True)
    )

    if user_id:
        query = query.eq("user_id", user_id)
    if action:
        query = query.eq("action", action)
    if resource_type:
        query = query.eq("resource_type", resource_type)
    if date_from:
        query = query.gte("created_at", date_from)
    if date_to:
        # Incluir todo el día final
        query = query.lte("created_at", date_to + "T23:59:59.999Z")

    offset = (page - 1) * per_page
    query = query.range(offset, offset + per_page - 1)
    result = query.execute()
    logs = result.data or []

    # Resolver emails de usuarios
    user_ids = list({log["user_id"] for log in logs if log.get("user_id")})
    user_emails: dict[str, str] = {}
    if user_ids:
        users_result = (
            sb.table("users")
            .select("id, email")
            .in_("id", user_ids)
            .execute()
        )
        user_emails = {str(u["id"]): u["email"] for u in (users_result.data or [])}

    # Resolver nombres de clientes
    client_ids = list({log["client_id"] for log in logs if log.get("client_id")})
    client_names: dict[str, str] = {}
    if client_ids:
        clients_result = (
            sb.table("clients")
            .select("id, name")
            .in_("id", client_ids)
            .execute()
        )
        client_names = {str(c["id"]): c["name"] for c in (clients_result.data or [])}

    # Enriquecer logs con email y nombre de cliente
    enriched = []
    for log in logs:
        entry = dict(log)
        entry["user_email"] = user_emails.get(str(log.get("user_id", "")))
        entry["client_name"] = client_names.get(str(log.get("client_id", "")))
        enriched.append(entry)

    return {
        "data": enriched,
        "total": result.count or 0,
        "page": page,
        "per_page": per_page,
    }


@router.get("/api-keys")
async def list_all_api_keys(
    admin: CurrentUser = Depends(require_admin),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
) -> dict[str, Any]:
    """Lista todas las API keys de todos los clientes (solo admin)."""
    sb = get_supabase()

    offset = (page - 1) * per_page
    result = (
        sb.table("api_keys")
        .select("id, client_id, name, key_prefix, scopes, is_active, last_used_at, created_at", count="exact")
        .order("created_at", desc=True)
        .range(offset, offset + per_page - 1)
        .execute()
    )
    keys = result.data or []

    # Resolver nombres de clientes
    client_ids = list({k["client_id"] for k in keys if k.get("client_id")})
    client_names: dict[str, str] = {}
    if client_ids:
        clients_result = (
            sb.table("clients")
            .select("id, name")
            .in_("id", client_ids)
            .execute()
        )
        client_names = {str(c["id"]): c["name"] for c in (clients_result.data or [])}

    data = []
    for k in keys:
        prefix = k.get("key_prefix", "")
        data.append({
            "id": k["id"],
            "client_id": k["client_id"],
            "client_name": client_names.get(str(k["client_id"]), "Desconocido"),
            "name": k.get("name"),
            "key_prefix": (prefix[:8] + "...") if len(prefix) > 8 else prefix + "...",
            "scopes": k.get("scopes", []),
            "is_active": k.get("is_active", True),
            "created_at": k.get("created_at"),
            "last_used_at": k.get("last_used_at"),
        })

    return {
        "data": data,
        "total": result.count or 0,
        "page": page,
        "per_page": per_page,
    }


@router.get("/phone-numbers")
async def list_phone_numbers(
    admin: CurrentUser = Depends(require_admin),
) -> list[dict[str, Any]]:
    """Lista todos los numeros de telefono asignados a agentes (solo admin)."""
    sb = get_supabase()

    result = (
        sb.table("agents")
        .select("id, name, client_id, phone_number, phone_sid, livekit_sip_trunk_id, agent_type, is_active")
        .neq("phone_number", "null")
        .order("created_at", desc=True)
        .execute()
    )
    agents = result.data or []

    # Filtrar los que realmente tienen phone_number (neq null puede no filtrar correctamente)
    agents = [a for a in agents if a.get("phone_number")]

    # Resolver nombres de clientes
    client_ids = list({a["client_id"] for a in agents if a.get("client_id")})
    client_names: dict[str, str] = {}
    if client_ids:
        clients_result = (
            sb.table("clients")
            .select("id, name")
            .in_("id", client_ids)
            .execute()
        )
        client_names = {str(c["id"]): c["name"] for c in (clients_result.data or [])}

    return [
        {
            "agent_id": a["id"],
            "agent_name": a.get("name", "Sin nombre"),
            "client_id": a["client_id"],
            "client_name": client_names.get(str(a["client_id"]), "Desconocido"),
            "phone_number": a["phone_number"],
            "phone_sid": a.get("phone_sid"),
            "livekit_sip_trunk_id": a.get("livekit_sip_trunk_id"),
            "agent_type": a.get("agent_type", "inbound"),
            "is_active": a.get("is_active", True),
        }
        for a in agents
    ]


@router.get("/webhook-dlq")
async def list_webhook_dlq(
    admin: CurrentUser = Depends(require_admin),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
) -> dict[str, Any]:
    """Lista entregas en dead letter queue de todos los clientes (solo admin)."""
    sb = get_supabase()

    offset = (page - 1) * per_page
    result = (
        sb.table("webhook_deliveries")
        .select("id, event, endpoint_id, status_code, error, attempt, delivered_at, payload, webhook_endpoints!inner(url, client_id)", count="exact")
        .eq("status", "dead_letter")
        .order("delivered_at", desc=True)
        .range(offset, offset + per_page - 1)
        .execute()
    )
    deliveries = result.data or []

    # Resolver nombres de clientes
    client_ids = list({
        d["webhook_endpoints"]["client_id"]
        for d in deliveries
        if d.get("webhook_endpoints", {}).get("client_id")
    })
    client_names: dict[str, str] = {}
    if client_ids:
        clients_result = (
            sb.table("clients")
            .select("id, name")
            .in_("id", client_ids)
            .execute()
        )
        client_names = {str(c["id"]): c["name"] for c in (clients_result.data or [])}

    data = []
    for d in deliveries:
        ep = d.get("webhook_endpoints", {})
        data.append({
            "id": d["id"],
            "event": d.get("event"),
            "endpoint_url": ep.get("url"),
            "client_id": ep.get("client_id"),
            "client_name": client_names.get(str(ep.get("client_id", "")), "Desconocido"),
            "status_code": d.get("status_code"),
            "error": d.get("error"),
            "attempt": d.get("attempt"),
            "delivered_at": d.get("delivered_at"),
        })

    return {
        "data": data,
        "total": result.count or 0,
        "page": page,
        "per_page": per_page,
    }


@router.post("/webhook-dlq/{delivery_id}/retry")
async def admin_retry_dead_letter(
    delivery_id: str,
    admin: CurrentUser = Depends(require_admin),
) -> dict[str, bool]:
    """Reintenta una entrega en dead letter queue (solo admin). No requiere client_id."""
    import asyncio

    sb = get_supabase()

    # Obtener la entrega fallida
    delivery = (
        sb.table("webhook_deliveries")
        .select("*")
        .eq("id", delivery_id)
        .eq("status", "dead_letter")
        .limit(1)
        .execute()
    )
    if not delivery.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entrega no encontrada en DLQ",
        )

    dlv = delivery.data[0]

    # Obtener el endpoint
    ep = (
        sb.table("webhook_endpoints")
        .select("*")
        .eq("id", dlv["endpoint_id"])
        .limit(1)
        .execute()
    )
    if not ep.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Endpoint no encontrado",
        )

    # Re-despachar el evento
    from api.services.webhook_service import _deliver_webhook

    asyncio.create_task(
        _deliver_webhook(ep.data[0], dlv["event"], dlv["payload"])
    )

    # Marcar el original como reintentado
    sb.table("webhook_deliveries").update({
        "status": "retried",
    }).eq("id", delivery_id).execute()

    logger.info("Admin %s reintentó webhook delivery %s", admin.email, delivery_id)
    return {"retried": True}


@router.patch("/api-keys/{key_id}")
async def admin_revoke_api_key(
    key_id: str,
    admin: CurrentUser = Depends(require_admin),
) -> dict[str, bool]:
    """Revoca (desactiva) una API key (solo admin). No requiere client_id."""
    sb = get_supabase()
    result = (
        sb.table("api_keys")
        .update({"is_active": False})
        .eq("id", key_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key no encontrada",
        )
    logger.info("Admin %s revocó API key %s", admin.email, key_id)
    return {"revoked": True}
