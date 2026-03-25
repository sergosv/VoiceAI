"""Rutas de gestión del Asistente Personal (PA)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_supabase
from api.middleware.auth import CurrentUser, get_current_user
from api.schemas_pa import (
    PaCallerCreateRequest,
    PaCallerOut,
    PaEmailConfigOut,
    PaEmailConfigRequest,
    PaMemoryItemOut,
    PaTaskUpdateRequest,
)

router = APIRouter()
logger = logging.getLogger("api.pa")


def _check_agent_access(sb, agent_id: str, user: CurrentUser) -> dict:
    """Verifica que el agente existe y el usuario tiene acceso."""
    result = (
        sb.table("agents")
        .select("id, client_id, agent_category")
        .eq("id", agent_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente no encontrado")
    agent = result.data[0]
    if user.role == "client" and user.client_id != agent["client_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")
    return agent


# ── Authorized Callers ───────────────────────────────────


@router.get("/{agent_id}/pa/callers", response_model=list[PaCallerOut])
async def list_callers(
    agent_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> list[PaCallerOut]:
    """Lista los callers autorizados de un agente PA."""
    sb = get_supabase()
    _check_agent_access(sb, agent_id, user)
    result = (
        sb.table("pa_authorized_callers")
        .select("*")
        .eq("agent_id", agent_id)
        .order("created_at")
        .execute()
    )
    return [PaCallerOut(**row) for row in (result.data or [])]


@router.post("/{agent_id}/pa/callers", response_model=PaCallerOut, status_code=201)
async def add_caller(
    agent_id: str,
    req: PaCallerCreateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> PaCallerOut:
    """Agrega un caller autorizado a un agente PA."""
    sb = get_supabase()
    _check_agent_access(sb, agent_id, user)
    try:
        result = (
            sb.table("pa_authorized_callers")
            .insert({
                "agent_id": agent_id,
                "phone_number": req.phone_number,
                "label": req.label,
                "is_owner": req.is_owner,
                "reminder_delivery": req.reminder_delivery,
            })
            .execute()
        )
    except Exception as e:
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ese número ya está autorizado para este agente.",
            )
        raise
    if not result.data:
        raise HTTPException(status_code=500, detail="Error creando caller")
    return PaCallerOut(**result.data[0])


@router.delete("/{agent_id}/pa/callers/{caller_id}")
async def remove_caller(
    agent_id: str,
    caller_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Elimina un caller autorizado."""
    sb = get_supabase()
    _check_agent_access(sb, agent_id, user)
    sb.table("pa_authorized_callers").delete().eq("id", caller_id).eq("agent_id", agent_id).execute()
    return {"message": "Caller eliminado"}


# ── Memory Items ─────────────────────────────────────────


@router.get("/{agent_id}/pa/memory", response_model=list[PaMemoryItemOut])
async def list_memory(
    agent_id: str,
    item_type: str | None = None,
    q: str | None = None,
    limit: int = 50,
    user: CurrentUser = Depends(get_current_user),
) -> list[PaMemoryItemOut]:
    """Lista o busca items de memoria del PA."""
    sb = get_supabase()
    _check_agent_access(sb, agent_id, user)

    # Si hay query, usar búsqueda semántica
    if q:
        try:
            from agent.embeddings import generate_embedding
            import asyncio
            embedding = await generate_embedding(q)
            result = sb.rpc("search_pa_memory", {
                "p_agent_id": agent_id,
                "p_query_embedding": embedding,
                "p_item_types": [item_type] if item_type else None,
                "p_limit": limit,
            }).execute()
            return [PaMemoryItemOut(**row) for row in (result.data or [])]
        except Exception as e:
            logger.warning("Error en búsqueda semántica PA: %s — fallback a query directa", e)

    # Query directa
    query = (
        sb.table("pa_memory_items")
        .select("id, agent_id, item_type, content, metadata, is_completed, created_at, updated_at")
        .eq("agent_id", agent_id)
        .eq("is_deleted", False)
        .order("created_at", desc=True)
        .limit(limit)
    )
    if item_type:
        query = query.eq("item_type", item_type)

    result = query.execute()
    return [PaMemoryItemOut(**row) for row in (result.data or [])]


@router.delete("/{agent_id}/pa/memory/{item_id}")
async def delete_memory_item(
    agent_id: str,
    item_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Soft delete de un item de memoria."""
    sb = get_supabase()
    _check_agent_access(sb, agent_id, user)
    sb.table("pa_memory_items").update({"is_deleted": True}).eq("id", item_id).eq("agent_id", agent_id).execute()
    return {"message": "Item eliminado"}


# ── Tasks ────────────────────────────────────────────────


@router.get("/{agent_id}/pa/tasks", response_model=list[PaMemoryItemOut])
async def list_tasks(
    agent_id: str,
    completed: bool = False,
    user: CurrentUser = Depends(get_current_user),
) -> list[PaMemoryItemOut]:
    """Lista tareas del PA."""
    sb = get_supabase()
    _check_agent_access(sb, agent_id, user)
    query = (
        sb.table("pa_memory_items")
        .select("id, agent_id, item_type, content, metadata, is_completed, created_at, updated_at")
        .eq("agent_id", agent_id)
        .eq("item_type", "task")
        .eq("is_deleted", False)
        .order("created_at", desc=True)
        .limit(100)
    )
    if not completed:
        query = query.eq("is_completed", False)
    result = query.execute()
    return [PaMemoryItemOut(**row) for row in (result.data or [])]


@router.patch("/{agent_id}/pa/tasks/{task_id}", response_model=PaMemoryItemOut)
async def update_task(
    agent_id: str,
    task_id: str,
    req: PaTaskUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> PaMemoryItemOut:
    """Actualiza una tarea (marcar completa, editar contenido)."""
    sb = get_supabase()
    _check_agent_access(sb, agent_id, user)
    updates: dict = {}
    if req.is_completed is not None:
        updates["is_completed"] = req.is_completed
    if req.content is not None:
        updates["content"] = req.content
    if req.metadata is not None:
        import json
        updates["metadata"] = json.dumps(req.metadata)
    if not updates:
        raise HTTPException(status_code=400, detail="Nada que actualizar")

    result = (
        sb.table("pa_memory_items")
        .update(updates)
        .eq("id", task_id)
        .eq("agent_id", agent_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return PaMemoryItemOut(**result.data[0])


# ── Email Config ─────────────────────────────────────────


@router.get("/{agent_id}/pa/email-config", response_model=PaEmailConfigOut | None)
async def get_email_config(
    agent_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Obtiene la configuración de email del PA."""
    sb = get_supabase()
    _check_agent_access(sb, agent_id, user)
    result = (
        sb.table("pa_email_config")
        .select("*")
        .eq("agent_id", agent_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return PaEmailConfigOut(**result.data[0])


@router.put("/{agent_id}/pa/email-config", response_model=PaEmailConfigOut)
async def save_email_config(
    agent_id: str,
    req: PaEmailConfigRequest,
    user: CurrentUser = Depends(get_current_user),
) -> PaEmailConfigOut:
    """Crea o actualiza la configuración de email del PA."""
    sb = get_supabase()
    _check_agent_access(sb, agent_id, user)

    row = {
        "agent_id": agent_id,
        "from_name": req.from_name,
        "from_email": req.from_email,
        "reply_to": req.reply_to,
        "signature": req.signature,
    }

    # Upsert: intentar update primero, si no existe crear
    existing = (
        sb.table("pa_email_config")
        .select("id")
        .eq("agent_id", agent_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        result = (
            sb.table("pa_email_config")
            .update(row)
            .eq("agent_id", agent_id)
            .execute()
        )
    else:
        result = sb.table("pa_email_config").insert(row).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Error guardando configuración de email")
    return PaEmailConfigOut(**result.data[0])
