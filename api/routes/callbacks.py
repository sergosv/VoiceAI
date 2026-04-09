"""Endpoints para scheduled callbacks — devoluciones de llamada programadas."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.middleware.auth import CurrentUser, get_current_user
from api.deps import get_supabase

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Schemas ──

class CallbackOut(BaseModel):
    id: str
    client_id: str
    agent_id: str
    phone: str
    scheduled_at: str
    timezone: str
    context: str | None = None
    origin_call_id: str | None = None
    status: str
    attempts: int
    max_attempts: int
    last_attempt_at: str | None = None
    result_call_id: str | None = None
    failure_reason: str | None = None
    created_at: str
    updated_at: str
    # Joined fields
    agent_name: str | None = None
    agent_slug: str | None = None


class CallbackCancelRequest(BaseModel):
    reason: str | None = None


# ── Endpoints ──

@router.get("")
async def list_callbacks(
    user: CurrentUser = Depends(get_current_user),
    status: str | None = Query(None, description="Filter by status"),
    agent_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """Lista callbacks programados del cliente."""
    sb = get_supabase()
    effective_client_id = user.impersonating_client_id or user.client_id

    query = (
        sb.table("scheduled_callbacks")
        .select("*, agents(name, slug)", count="exact")
        .order("scheduled_at", desc=True)
    )
    if effective_client_id:
        query = query.eq("client_id", effective_client_id)

    if status:
        query = query.eq("status", status)
    if agent_id:
        query = query.eq("agent_id", agent_id)

    offset = (page - 1) * per_page
    query = query.range(offset, offset + per_page - 1)

    result = query.execute()

    callbacks = []
    for row in result.data or []:
        agent_info = row.pop("agents", None) or {}
        callbacks.append({
            **row,
            "agent_name": agent_info.get("name"),
            "agent_slug": agent_info.get("slug"),
        })

    return {
        "data": callbacks,
        "total": result.count or 0,
        "page": page,
        "per_page": per_page,
    }


@router.get("/stats")
async def callback_stats(
    user: CurrentUser = Depends(get_current_user),
):
    """Estadísticas de callbacks por status."""
    sb = get_supabase()
    client_id = user.impersonating_client_id or user.client_id

    result = sb.table("scheduled_callbacks").select(
        "status", count="exact"
    ).eq("client_id", client_id).execute()

    # Contar por status
    stats = {"pending": 0, "in_progress": 0, "completed": 0, "failed": 0, "cancelled": 0}
    for row in result.data or []:
        s = row.get("status", "pending")
        if s in stats:
            stats[s] += 1

    return stats


@router.patch("/{callback_id}/cancel")
async def cancel_callback(
    callback_id: str,
    body: CallbackCancelRequest | None = None,
    user: CurrentUser = Depends(get_current_user),
):
    """Cancela un callback pendiente."""
    sb = get_supabase()
    client_id = user.impersonating_client_id or user.client_id

    # Verificar que existe y pertenece al cliente
    existing = (
        sb.table("scheduled_callbacks")
        .select("id, status")
        .eq("id", callback_id)
        .eq("client_id", client_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Callback no encontrado")

    if existing.data[0]["status"] not in ("pending",):
        raise HTTPException(
            status_code=400,
            detail=f"Solo se pueden cancelar callbacks pendientes (estado actual: {existing.data[0]['status']})",
        )

    sb.table("scheduled_callbacks").update({
        "status": "cancelled",
        "failure_reason": body.reason if body else "Cancelado manualmente",
    }).eq("id", callback_id).execute()

    return {"ok": True, "message": "Callback cancelado"}


@router.delete("/{callback_id}")
async def delete_callback(
    callback_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Elimina un callback (solo si está cancelado o fallido)."""
    sb = get_supabase()
    client_id = user.impersonating_client_id or user.client_id

    existing = (
        sb.table("scheduled_callbacks")
        .select("id, status")
        .eq("id", callback_id)
        .eq("client_id", client_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Callback no encontrado")

    if existing.data[0]["status"] in ("pending", "in_progress"):
        raise HTTPException(
            status_code=400,
            detail="Cancela el callback antes de eliminarlo",
        )

    sb.table("scheduled_callbacks").delete().eq("id", callback_id).execute()
    return {"ok": True}


# ── Cron endpoint — ejecuta callbacks pendientes ──

@router.post("/process")
async def process_callbacks(
    user: CurrentUser = Depends(get_current_user),
):
    """Procesa callbacks pendientes cuya hora ya llegó.

    Llamar desde un cron job cada 1-2 minutos.
    También puede llamarse manualmente desde el dashboard.
    """
    # Solo admin puede disparar el procesamiento
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores")

    from api.services.callback_service import process_pending_callbacks
    stats = await process_pending_callbacks()

    logger.info("Callbacks procesados: %s", stats)
    return stats
