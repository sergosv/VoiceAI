"""Rutas CRUD GoHighLevel config + inbox de conversaciones GHL."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from supabase import create_client

from api.routes.auth import get_current_user
from api.schemas import MessageResponse

logger = logging.getLogger(__name__)

# Router para config CRUD (montado en /api/clients)
router = APIRouter()

# Router para inbox/stats (montado en /api/ghl)
inbox_router = APIRouter()


def _sb():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def _check_client(user, client_id: str) -> None:
    role = user.role if hasattr(user, "role") else user.get("role")
    cid = user.client_id if hasattr(user, "client_id") else user.get("client_id")
    if role != "admin" and cid != client_id:
        raise HTTPException(403, "No autorizado para este cliente")


# ── Config CRUD (prefix: /api/clients) ──────────────────


@router.get("/{client_id}/agents/{agent_id}/ghl")
async def get_ghl_config(
    client_id: str,
    agent_id: str,
    user: dict = Depends(get_current_user),
) -> dict | None:
    """Obtiene la config de GHL de un agente."""
    _check_client(user, client_id)
    sb = _sb()
    result = (
        sb.table("ghl_configs")
        .select("*")
        .eq("agent_id", agent_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    row = dict(result.data[0])
    row["has_ghl_api_key"] = bool(row.pop("ghl_api_key", None))
    return row


@router.post("/{client_id}/agents/{agent_id}/ghl")
async def create_ghl_config(
    client_id: str,
    agent_id: str,
    body: dict,
    user: dict = Depends(get_current_user),
) -> dict:
    """Crea config de GHL para un agente."""
    _check_client(user, client_id)
    sb = _sb()

    existing = (
        sb.table("ghl_configs")
        .select("id")
        .eq("agent_id", agent_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        raise HTTPException(409, "Ya existe config GHL para este agente")

    record = {
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "agent_id": agent_id,
        "ghl_location_id": body.get("ghl_location_id", ""),
    }
    if body.get("ghl_api_key"):
        record["ghl_api_key"] = body["ghl_api_key"]
    for field in (
        "auto_reply", "greeting", "session_timeout_minutes",
        "media_response", "is_paused", "paused_message", "away_message", "schedule",
    ):
        if field in body:
            record[field] = body[field]

    result = sb.table("ghl_configs").insert(record).execute()
    row = dict(result.data[0])
    row["has_ghl_api_key"] = bool(row.pop("ghl_api_key", None))
    return row


@router.patch("/{client_id}/agents/{agent_id}/ghl")
async def update_ghl_config(
    client_id: str,
    agent_id: str,
    body: dict,
    user: dict = Depends(get_current_user),
) -> dict:
    """Actualiza config de GHL."""
    _check_client(user, client_id)
    sb = _sb()

    allowed = {
        "ghl_location_id", "ghl_api_key", "auto_reply", "greeting",
        "session_timeout_minutes", "media_response", "is_paused",
        "paused_message", "away_message", "schedule", "is_active",
    }
    updates = {k: v for k, v in body.items() if k in allowed and v is not None}
    if not updates:
        raise HTTPException(400, "Nada que actualizar")

    result = (
        sb.table("ghl_configs")
        .update(updates)
        .eq("agent_id", agent_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(404, "Config GHL no encontrada")
    row = dict(result.data[0])
    row["has_ghl_api_key"] = bool(row.pop("ghl_api_key", None))
    return row


@router.delete("/{client_id}/agents/{agent_id}/ghl", response_model=MessageResponse)
async def delete_ghl_config(
    client_id: str,
    agent_id: str,
    user: dict = Depends(get_current_user),
) -> MessageResponse:
    """Elimina config de GHL."""
    _check_client(user, client_id)
    sb = _sb()
    sb.table("ghl_configs").delete().eq("agent_id", agent_id).execute()
    return MessageResponse(message="Config GHL eliminada")


# ── Inbox — Conversaciones (prefix: /api/ghl) ──────


@inbox_router.get("/conversations")
async def list_ghl_conversations(
    status: str | None = None,
    agent_id: str | None = None,
    user: dict = Depends(get_current_user),
) -> list[dict]:
    """Lista conversaciones GHL del cliente."""
    sb = _sb()
    client_id = user.client_id if hasattr(user, "client_id") else user.get("client_id")
    is_admin = (user.role if hasattr(user, "role") else user.get("role")) == "admin"

    configs_q = sb.table("ghl_configs").select("id, agent_id")
    if not is_admin and client_id:
        configs_q = configs_q.eq("client_id", client_id)
    if agent_id:
        configs_q = configs_q.eq("agent_id", agent_id)
    configs_result = configs_q.execute()

    if not configs_result.data:
        return []

    config_ids = [c["id"] for c in configs_result.data]
    config_agent_map = {c["id"]: c["agent_id"] for c in configs_result.data}

    conv_q = sb.table("ghl_conversations").select("*").in_("config_id", config_ids)
    if status:
        conv_q = conv_q.eq("status", status)
    conv_q = conv_q.order("last_message_at", desc=True).limit(100)
    conv_result = conv_q.execute()

    if not conv_result.data:
        return []

    agent_ids_list = list(set(config_agent_map.values()))
    agents_result = sb.table("agents").select("id, name").in_("id", agent_ids_list).execute()
    agent_names = {a["id"]: a["name"] for a in (agents_result.data or [])}

    out = []
    for conv in conv_result.data:
        cfg_id = conv["config_id"]
        ag_id = config_agent_map.get(cfg_id)
        conv["agent_name"] = agent_names.get(ag_id) if ag_id else None
        out.append(conv)

    return out


@inbox_router.get("/conversations/{conversation_id}/messages")
async def get_ghl_messages(
    conversation_id: str,
    user: dict = Depends(get_current_user),
) -> list[dict]:
    """Obtiene mensajes de una conversación GHL."""
    sb = _sb()
    result = (
        sb.table("ghl_messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .limit(200)
        .execute()
    )
    return result.data or []


@inbox_router.post("/conversations/{conversation_id}/send", response_model=MessageResponse)
async def send_ghl_manual_message(
    conversation_id: str,
    body: dict,
    user: dict = Depends(get_current_user),
) -> MessageResponse:
    """Envía mensaje manual en conversación GHL."""
    sb = _sb()
    message = body.get("message", "")
    if not message:
        raise HTTPException(400, "Mensaje vacío")

    conv_result = (
        sb.table("ghl_conversations")
        .select("*, ghl_configs(*)")
        .eq("id", conversation_id)
        .limit(1)
        .execute()
    )
    if not conv_result.data:
        raise HTTPException(404, "Conversación no encontrada")

    conv = conv_result.data[0]
    ghl_config = conv.get("ghl_configs")
    if not ghl_config:
        raise HTTPException(500, "Config GHL no encontrada")

    # Inyectar contactId y channel para send_text
    if conv.get("ghl_contact_id"):
        ghl_config["_ghl_contact_id"] = conv["ghl_contact_id"]
    if conv.get("channel"):
        ghl_config["_ghl_channel"] = conv["channel"]

    from api.services.whatsapp.gohighlevel import GoHighLevelProvider

    provider = GoHighLevelProvider()
    provider_msg_id = await provider.send_text(
        ghl_config, conv["remote_phone"], message
    )

    if not provider_msg_id:
        raise HTTPException(502, "Error enviando mensaje")

    msg_record = {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "direction": "outbound",
        "content": message,
        "message_type": "text",
        "channel": conv.get("channel"),
        "provider_message_id": provider_msg_id,
        "status": "sent",
    }
    sb.table("ghl_messages").insert(msg_record).execute()

    now = datetime.now(timezone.utc).isoformat()
    sb.table("ghl_conversations").update({
        "last_message_at": now,
        "message_count": (conv.get("message_count", 0) or 0) + 1,
    }).eq("id", conversation_id).execute()

    return MessageResponse(message="Mensaje enviado")


@inbox_router.get("/stats")
async def get_ghl_stats(
    user: dict = Depends(get_current_user),
) -> dict:
    """Estadísticas básicas de GHL."""
    sb = _sb()
    client_id = user.client_id if hasattr(user, "client_id") else user.get("client_id")
    is_admin = (user.role if hasattr(user, "role") else user.get("role")) == "admin"

    configs_q = sb.table("ghl_configs").select("id")
    if not is_admin and client_id:
        configs_q = configs_q.eq("client_id", client_id)
    configs_result = configs_q.execute()

    if not configs_result.data:
        return {
            "total_conversations": 0,
            "active_conversations": 0,
            "total_messages": 0,
            "messages_today": 0,
        }

    config_ids = [c["id"] for c in configs_result.data]

    convs = (
        sb.table("ghl_conversations")
        .select("id, status, message_count")
        .in_("config_id", config_ids)
        .execute()
    )
    conv_data = convs.data or []
    total = len(conv_data)
    active = sum(1 for c in conv_data if c["status"] == "active")
    total_msgs = sum(c.get("message_count", 0) for c in conv_data)

    return {
        "total_conversations": total,
        "active_conversations": active,
        "total_messages": total_msgs,
        "messages_today": 0,
    }
