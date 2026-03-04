"""Rutas CRUD WhatsApp config + inbox de conversaciones."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from supabase import create_client

from api.routes.auth import get_current_user
from api.schemas import (
    MessageResponse,
    WhatsAppConfigCreateRequest,
    WhatsAppConfigOut,
    WhatsAppConfigUpdateRequest,
    WhatsAppConversationOut,
    WhatsAppMessageOut,
    WhatsAppSendRequest,
    WhatsAppStatsOut,
    whatsapp_config_out_from_row,
)

logger = logging.getLogger(__name__)

# Router para config CRUD (montado en /api/clients)
router = APIRouter()

# Router para inbox/stats (montado en /api/whatsapp)
inbox_router = APIRouter()


def _sb():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def _check_client(user: dict, client_id: str) -> None:
    if user["role"] != "admin" and user.get("client_id") != client_id:
        raise HTTPException(403, "No autorizado para este cliente")


# ── Config CRUD (prefix: /api/clients) ──────────────────


@router.get("/{client_id}/agents/{agent_id}/whatsapp", response_model=WhatsAppConfigOut | None)
async def get_whatsapp_config(
    client_id: str,
    agent_id: str,
    user: dict = Depends(get_current_user),
) -> WhatsAppConfigOut | None:
    """Obtiene la config de WhatsApp de un agente."""
    _check_client(user, client_id)
    sb = _sb()
    result = (
        sb.table("whatsapp_configs")
        .select("*")
        .eq("agent_id", agent_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return whatsapp_config_out_from_row(result.data[0])


@router.post("/{client_id}/agents/{agent_id}/whatsapp", response_model=WhatsAppConfigOut)
async def create_whatsapp_config(
    client_id: str,
    agent_id: str,
    body: WhatsAppConfigCreateRequest,
    user: dict = Depends(get_current_user),
) -> WhatsAppConfigOut:
    """Crea config de WhatsApp para un agente."""
    _check_client(user, client_id)
    sb = _sb()

    # Verificar que no exista
    existing = (
        sb.table("whatsapp_configs")
        .select("id")
        .eq("agent_id", agent_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        raise HTTPException(409, "Ya existe config WhatsApp para este agente")

    record = {
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "agent_id": agent_id,
        **body.model_dump(exclude_none=True),
    }

    result = sb.table("whatsapp_configs").insert(record).execute()
    return whatsapp_config_out_from_row(result.data[0])


@router.patch("/{client_id}/agents/{agent_id}/whatsapp", response_model=WhatsAppConfigOut)
async def update_whatsapp_config(
    client_id: str,
    agent_id: str,
    body: WhatsAppConfigUpdateRequest,
    user: dict = Depends(get_current_user),
) -> WhatsAppConfigOut:
    """Actualiza config de WhatsApp."""
    _check_client(user, client_id)
    sb = _sb()

    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(400, "Nada que actualizar")

    result = (
        sb.table("whatsapp_configs")
        .update(updates)
        .eq("agent_id", agent_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(404, "Config no encontrada")
    return whatsapp_config_out_from_row(result.data[0])


@router.delete("/{client_id}/agents/{agent_id}/whatsapp", response_model=MessageResponse)
async def delete_whatsapp_config(
    client_id: str,
    agent_id: str,
    user: dict = Depends(get_current_user),
) -> MessageResponse:
    """Elimina config de WhatsApp."""
    _check_client(user, client_id)
    sb = _sb()
    sb.table("whatsapp_configs").delete().eq("agent_id", agent_id).execute()
    return MessageResponse(message="Config WhatsApp eliminada")


# ── Inbox — Conversaciones (prefix: /api/whatsapp) ──────


@inbox_router.get("/conversations", response_model=list[WhatsAppConversationOut])
async def list_conversations(
    status: str | None = None,
    agent_id: str | None = None,
    user: dict = Depends(get_current_user),
) -> list[WhatsAppConversationOut]:
    """Lista conversaciones WhatsApp del cliente."""
    sb = _sb()
    client_id = user.get("client_id")
    is_admin = user["role"] == "admin"

    # Buscar configs del cliente (o todas si admin)
    configs_q = sb.table("whatsapp_configs").select("id, agent_id")
    if not is_admin and client_id:
        configs_q = configs_q.eq("client_id", client_id)
    if agent_id:
        configs_q = configs_q.eq("agent_id", agent_id)
    configs_result = configs_q.execute()

    if not configs_result.data:
        return []

    config_ids = [c["id"] for c in configs_result.data]
    config_agent_map = {c["id"]: c["agent_id"] for c in configs_result.data}

    # Buscar conversaciones
    conv_q = sb.table("whatsapp_conversations").select("*").in_("config_id", config_ids)
    if status:
        conv_q = conv_q.eq("status", status)
    conv_q = conv_q.order("last_message_at", desc=True).limit(100)
    conv_result = conv_q.execute()

    if not conv_result.data:
        return []

    # Cargar nombres de agentes y contactos para enriquecer
    agent_ids_list = list(set(config_agent_map.values()))
    agents_result = sb.table("agents").select("id, name").in_("id", agent_ids_list).execute()
    agent_names = {a["id"]: a["name"] for a in (agents_result.data or [])}

    contact_ids = [c["contact_id"] for c in conv_result.data if c.get("contact_id")]
    contact_names: dict[str, str] = {}
    if contact_ids:
        contacts_result = (
            sb.table("contacts").select("id, name, phone").in_("id", contact_ids).execute()
        )
        for ct in contacts_result.data or []:
            contact_names[ct["id"]] = ct.get("name") or ct.get("phone", "")

    out: list[WhatsAppConversationOut] = []
    for conv in conv_result.data:
        cfg_id = conv["config_id"]
        ag_id = config_agent_map.get(cfg_id)
        out.append(WhatsAppConversationOut(
            id=conv["id"],
            config_id=cfg_id,
            contact_id=conv.get("contact_id"),
            remote_phone=conv["remote_phone"],
            status=conv["status"],
            message_count=conv.get("message_count", 0),
            last_message_at=conv.get("last_message_at"),
            created_at=conv.get("created_at"),
            agent_name=agent_names.get(ag_id) if ag_id else None,
            contact_name=(
                contact_names.get(conv.get("contact_id", ""))
                if conv.get("contact_id") else None
            ),
        ))

    return out


@inbox_router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[WhatsAppMessageOut],
)
async def get_conversation_messages(
    conversation_id: str,
    user: dict = Depends(get_current_user),
) -> list[WhatsAppMessageOut]:
    """Obtiene mensajes de una conversación."""
    sb = _sb()
    result = (
        sb.table("whatsapp_messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .limit(200)
        .execute()
    )
    return [WhatsAppMessageOut(**m) for m in (result.data or [])]


@inbox_router.post(
    "/conversations/{conversation_id}/close",
    response_model=MessageResponse,
)
async def close_conversation(
    conversation_id: str,
    user: dict = Depends(get_current_user),
) -> MessageResponse:
    """Cierra una conversación manualmente."""
    sb = _sb()
    sb.table("whatsapp_conversations").update(
        {"status": "closed"}
    ).eq("id", conversation_id).execute()
    return MessageResponse(message="Conversación cerrada")


@inbox_router.post(
    "/conversations/{conversation_id}/send",
    response_model=MessageResponse,
)
async def send_manual_message(
    conversation_id: str,
    body: WhatsAppSendRequest,
    user: dict = Depends(get_current_user),
) -> MessageResponse:
    """Envía mensaje manual (human takeover)."""
    sb = _sb()

    # Cargar conversación con su config
    conv_result = (
        sb.table("whatsapp_conversations")
        .select("*, whatsapp_configs(*)")
        .eq("id", conversation_id)
        .limit(1)
        .execute()
    )
    if not conv_result.data:
        raise HTTPException(404, "Conversación no encontrada")

    conv = conv_result.data[0]
    wa_config = conv.get("whatsapp_configs")
    if not wa_config:
        raise HTTPException(500, "Config WhatsApp no encontrada")

    # Enviar mensaje
    from api.services.whatsapp.router import get_provider

    provider = get_provider(wa_config["provider"])
    provider_msg_id = await provider.send_text(
        wa_config, conv["remote_phone"], body.message
    )

    if not provider_msg_id:
        raise HTTPException(502, "Error enviando mensaje")

    # Guardar en DB
    msg_record = {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "direction": "outbound",
        "content": body.message,
        "message_type": "text",
        "provider_message_id": provider_msg_id,
        "status": "sent",
    }
    sb.table("whatsapp_messages").insert(msg_record).execute()

    # Actualizar last_message_at
    now = datetime.now(timezone.utc).isoformat()
    sb.table("whatsapp_conversations").update({
        "last_message_at": now,
        "message_count": (conv.get("message_count", 0) or 0) + 1,
    }).eq("id", conversation_id).execute()

    return MessageResponse(message="Mensaje enviado")


# ── Stats ────────────────────────────────────────────────


@inbox_router.get("/stats", response_model=WhatsAppStatsOut)
async def get_whatsapp_stats(
    user: dict = Depends(get_current_user),
) -> WhatsAppStatsOut:
    """Estadísticas básicas de WhatsApp."""
    sb = _sb()
    client_id = user.get("client_id")
    is_admin = user["role"] == "admin"

    # Config IDs del cliente
    configs_q = sb.table("whatsapp_configs").select("id")
    if not is_admin and client_id:
        configs_q = configs_q.eq("client_id", client_id)
    configs_result = configs_q.execute()

    if not configs_result.data:
        return WhatsAppStatsOut()

    config_ids = [c["id"] for c in configs_result.data]

    # Total conversaciones
    convs = (
        sb.table("whatsapp_conversations")
        .select("id, status, message_count")
        .in_("config_id", config_ids)
        .execute()
    )
    conv_data = convs.data or []
    total_conversations = len(conv_data)
    active_conversations = sum(1 for c in conv_data if c["status"] == "active")
    total_msg_count = sum(c.get("message_count", 0) for c in conv_data)
    avg = total_msg_count / total_conversations if total_conversations > 0 else 0

    # Mensajes hoy
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()
    conv_ids = [c["id"] for c in conv_data]

    messages_today = 0
    if conv_ids:
        msgs = (
            sb.table("whatsapp_messages")
            .select("id", count="exact")
            .in_("conversation_id", conv_ids[:50])  # Limitar para performance
            .gte("created_at", today_start)
            .execute()
        )
        messages_today = msgs.count or 0

    return WhatsAppStatsOut(
        total_conversations=total_conversations,
        active_conversations=active_conversations,
        total_messages=total_msg_count,
        messages_today=messages_today,
        avg_messages_per_conversation=round(avg, 1),
    )
