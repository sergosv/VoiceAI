"""Rutas API para agentes proactivos — scheduled actions y reglas."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.deps import get_supabase
from api.middleware.auth import CurrentUser, get_current_user

router = APIRouter()


# ── Schemas ──


class ScheduledActionCreate(BaseModel):
    agent_id: str
    rule_type: str = Field(..., min_length=1, max_length=50)
    channel: str = Field(..., pattern="^(call|whatsapp|sms)$")
    target_number: str = Field(..., min_length=7, max_length=20)
    message: str | None = None
    scheduled_at: str = Field(..., description="ISO 8601 datetime")
    max_attempts: int = Field(default=2, ge=1, le=10)
    target_contact_id: str | None = None
    metadata: dict | None = None


class ScheduledActionOut(BaseModel):
    id: str
    agent_id: str
    client_id: str
    rule_type: str
    channel: str
    target_number: str
    target_contact_id: str | None = None
    message: str | None = None
    metadata: dict = Field(default_factory=dict)
    scheduled_at: str
    status: str
    attempts: int = 0
    max_attempts: int = 2
    last_attempt_at: str | None = None
    result: str | None = None
    source: str = "rule"
    source_call_id: str | None = None
    created_at: str | None = None


class ScheduledActionUpdate(BaseModel):
    status: str | None = Field(None, pattern="^(pending|cancelled)$")
    scheduled_at: str | None = None
    message: str | None = None


# ── Endpoints ──


@router.get("/agents/{agent_id}/scheduled-actions")
async def list_scheduled_actions(
    agent_id: str,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, le=200),
    user: CurrentUser = Depends(get_current_user),
) -> list[ScheduledActionOut]:
    """Lista acciones programadas de un agente."""
    sb = get_supabase()

    # Verificar acceso al agente
    agent = sb.table("agents").select("client_id").eq("id", agent_id).limit(1).execute()
    if not agent.data:
        raise HTTPException(status_code=404, detail="Agente no encontrado")
    if user.role != "admin" and agent.data[0]["client_id"] != user.client_id:
        raise HTTPException(status_code=403, detail="Sin acceso a este agente")

    query = (
        sb.table("scheduled_actions")
        .select("*")
        .eq("agent_id", agent_id)
        .order("scheduled_at", desc=True)
        .limit(limit)
    )
    if status_filter:
        query = query.eq("status", status_filter)

    result = query.execute()
    return [ScheduledActionOut(**row) for row in (result.data or [])]


@router.post("/agents/{agent_id}/scheduled-actions", status_code=201)
async def create_scheduled_action(
    agent_id: str,
    body: ScheduledActionCreate,
    user: CurrentUser = Depends(get_current_user),
) -> ScheduledActionOut:
    """Crea una acción programada manualmente."""
    sb = get_supabase()

    agent = sb.table("agents").select("client_id").eq("id", agent_id).limit(1).execute()
    if not agent.data:
        raise HTTPException(status_code=404, detail="Agente no encontrado")
    client_id = agent.data[0]["client_id"]
    if user.role != "admin" and client_id != user.client_id:
        raise HTTPException(status_code=403, detail="Sin acceso a este agente")

    data = {
        "agent_id": agent_id,
        "client_id": client_id,
        "rule_type": body.rule_type,
        "channel": body.channel,
        "target_number": body.target_number,
        "message": body.message,
        "scheduled_at": body.scheduled_at,
        "max_attempts": body.max_attempts,
        "target_contact_id": body.target_contact_id,
        "metadata": body.metadata or {},
        "source": "manual",
        "status": "pending",
    }
    result = sb.table("scheduled_actions").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Error creando acción programada")
    return ScheduledActionOut(**result.data[0])


@router.patch("/scheduled-actions/{action_id}")
async def update_scheduled_action(
    action_id: str,
    body: ScheduledActionUpdate,
    user: CurrentUser = Depends(get_current_user),
) -> ScheduledActionOut:
    """Actualiza una acción programada (cancelar o reprogramar)."""
    sb = get_supabase()

    existing = sb.table("scheduled_actions").select("*").eq("id", action_id).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Acción no encontrada")

    action = existing.data[0]
    if user.role != "admin" and action["client_id"] != user.client_id:
        raise HTTPException(status_code=403, detail="Sin acceso")

    if action["status"] not in ("pending",):
        raise HTTPException(
            status_code=400,
            detail=f"No se puede modificar una acción con status '{action['status']}'"
        )

    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Sin campos para actualizar")

    result = sb.table("scheduled_actions").update(updates).eq("id", action_id).execute()
    return ScheduledActionOut(**result.data[0])


@router.delete("/scheduled-actions/{action_id}", status_code=204)
async def delete_scheduled_action(
    action_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> None:
    """Elimina una acción programada pendiente."""
    sb = get_supabase()

    existing = sb.table("scheduled_actions").select("client_id, status").eq("id", action_id).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Acción no encontrada")

    if user.role != "admin" and existing.data[0]["client_id"] != user.client_id:
        raise HTTPException(status_code=403, detail="Sin acceso")

    if existing.data[0]["status"] not in ("pending", "failed", "cancelled"):
        raise HTTPException(status_code=400, detail="Solo se pueden eliminar acciones pendientes/fallidas/canceladas")

    sb.table("scheduled_actions").delete().eq("id", action_id).execute()


@router.get("/scheduled-actions/stats")
async def get_proactive_stats(
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Estadísticas de acciones proactivas del cliente."""
    sb = get_supabase()
    client_id = user.client_id

    # Conteos por status
    for s in ("pending", "completed", "failed", "cancelled", "executing"):
        pass  # Se puede optimizar con un solo query

    all_actions = (
        sb.table("scheduled_actions")
        .select("status, channel")
        .eq("client_id", client_id)
        .execute()
    )

    stats: dict = {
        "total": 0,
        "by_status": {},
        "by_channel": {},
    }
    for row in all_actions.data or []:
        stats["total"] += 1
        s = row["status"]
        stats["by_status"][s] = stats["by_status"].get(s, 0) + 1
        c = row["channel"]
        stats["by_channel"][c] = stats["by_channel"].get(c, 0) + 1

    return stats
