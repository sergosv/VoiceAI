"""Public API v1 — endpoints autenticados por X-API-Key."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.auth_apikey import get_api_key_client, require_scope
from api.deps import get_supabase
from api.utils.url_validator import validate_url_not_private

router = APIRouter(prefix="/v1", tags=["public-api-v1"])


# ── Calls ──


@router.get("/calls")
async def list_calls(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    direction: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    api_key: dict = Depends(require_scope("calls:read")),
) -> dict:
    """Lista llamadas del cliente."""
    sb = get_supabase()
    client_id = api_key["client_id"]
    query = (
        sb.table("calls")
        .select(
            "id, agent_id, direction, caller_number, callee_number, "
            "duration_seconds, status, summary, cost_total, "
            "started_at, ended_at, resumen_ia, sentimiento, lead_score"
        )
        .eq("client_id", client_id)
        .order("started_at", desc=True)
        .range(offset, offset + limit - 1)
    )
    if direction:
        query = query.eq("direction", direction)
    if status_filter:
        query = query.eq("status", status_filter)
    result = query.execute()
    return {"data": result.data or [], "count": len(result.data or [])}


@router.get("/calls/{call_id}")
async def get_call(
    call_id: str,
    api_key: dict = Depends(require_scope("calls:read")),
) -> dict:
    """Obtiene detalles de una llamada."""
    sb = get_supabase()
    result = (
        sb.table("calls")
        .select("*")
        .eq("id", call_id)
        .eq("client_id", api_key["client_id"])
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Llamada no encontrada")
    return {"data": result.data[0]}


# ── Contacts ──


@router.get("/contacts")
async def list_contacts(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None),
    api_key: dict = Depends(require_scope("contacts:read")),
) -> dict:
    """Lista contactos del cliente."""
    sb = get_supabase()
    client_id = api_key["client_id"]
    query = (
        sb.table("contacts")
        .select("id, name, phone, email, source, lead_score, tags, call_count, last_call_at, created_at")
        .eq("client_id", client_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
    )
    if search:
        safe_search = re.sub(r'[,.()*%:!]', '', search)  # strip PostgREST special chars
        query = query.or_(f"name.ilike.%{safe_search}%,phone.ilike.%{safe_search}%,email.ilike.%{safe_search}%")
    result = query.execute()
    return {"data": result.data or [], "count": len(result.data or [])}


@router.get("/contacts/{contact_id}")
async def get_contact(
    contact_id: str,
    api_key: dict = Depends(require_scope("contacts:read")),
) -> dict:
    """Obtiene detalles de un contacto."""
    sb = get_supabase()
    result = (
        sb.table("contacts")
        .select("*")
        .eq("id", contact_id)
        .eq("client_id", api_key["client_id"])
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contacto no encontrado")
    return {"data": result.data[0]}


# ── Agents ──


@router.get("/agents")
async def list_agents(
    api_key: dict = Depends(require_scope("agents:read")),
) -> dict:
    """Lista agentes del cliente."""
    sb = get_supabase()
    result = (
        sb.table("agents")
        .select(
            "id, name, slug, phone_number, agent_type, conversation_mode, "
            "is_active, created_at"
        )
        .eq("client_id", api_key["client_id"])
        .order("created_at", desc=True)
        .execute()
    )
    return {"data": result.data or [], "count": len(result.data or [])}


@router.get("/agents/{agent_id}")
async def get_agent(
    agent_id: str,
    api_key: dict = Depends(require_scope("agents:read")),
) -> dict:
    """Obtiene detalles de un agente (sin secrets)."""
    sb = get_supabase()
    result = (
        sb.table("agents")
        .select(
            "id, name, slug, phone_number, agent_type, agent_mode, "
            "conversation_mode, greeting, system_prompt, is_active, created_at"
        )
        .eq("id", agent_id)
        .eq("client_id", api_key["client_id"])
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente no encontrado")
    return {"data": result.data[0]}


# ── Conversation Results ──


@router.get("/conversation-results")
async def list_conversation_results(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    mode: str | None = Query(None),
    agent_id: str | None = Query(None),
    api_key: dict = Depends(require_scope("calls:read")),
) -> dict:
    """Lista resultados de modos de conversación."""
    sb = get_supabase()
    query = (
        sb.table("conversation_results")
        .select("*")
        .eq("client_id", api_key["client_id"])
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
    )
    if mode:
        query = query.eq("mode", mode)
    if agent_id:
        query = query.eq("agent_id", agent_id)
    result = query.execute()
    return {"data": result.data or [], "count": len(result.data or [])}


# ── Webhooks Management ──


@router.get("/webhooks")
async def list_webhooks(
    api_key: dict = Depends(require_scope("webhooks:read")),
) -> dict:
    """Lista webhook endpoints."""
    from api.services.webhook_service import list_webhook_endpoints
    endpoints = await list_webhook_endpoints(api_key["client_id"])
    return {"data": endpoints, "count": len(endpoints)}


@router.post("/webhooks", status_code=status.HTTP_201_CREATED)
async def create_webhook(
    body: dict,
    api_key: dict = Depends(require_scope("webhooks:write")),
) -> dict:
    """Crea un webhook endpoint."""
    from api.services.webhook_service import create_webhook_endpoint
    url = body.get("url")
    events = body.get("events", [])
    description = body.get("description")
    if not url:
        raise HTTPException(status_code=400, detail="url es requerido")
    if not events:
        raise HTTPException(status_code=400, detail="events es requerido (lista de eventos)")
    if not validate_url_not_private(url):
        raise HTTPException(status_code=400, detail="URL no permitida: no se permiten direcciones internas o privadas")
    endpoint = await create_webhook_endpoint(api_key["client_id"], url, events, description)
    return {"data": endpoint}


@router.delete("/webhooks/{endpoint_id}")
async def delete_webhook(
    endpoint_id: str,
    api_key: dict = Depends(require_scope("webhooks:write")),
) -> dict:
    """Elimina un webhook endpoint."""
    from api.services.webhook_service import delete_webhook_endpoint
    deleted = await delete_webhook_endpoint(endpoint_id, api_key["client_id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Webhook no encontrado")
    return {"deleted": True}
