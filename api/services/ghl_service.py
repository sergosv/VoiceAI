"""Orquestador de mensajes inbound de GoHighLevel (multi-canal)."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone

from supabase import create_client, Client

from agent.config_loader import (
    ResolvedConfig,
    load_config_by_agent_id,
    load_api_integrations,
    load_mcp_servers,
)
from api.services.chat_service import chat_turn
from api.services.chat_store import Conversation
from api.services.whatsapp.history import deserialize_history, serialize_history
from api.services.whatsapp.provider import InboundMessage
from api.services.whatsapp.gohighlevel import GoHighLevelProvider

logger = logging.getLogger(__name__)

_locks: dict[str, asyncio.Lock] = {}
_provider = GoHighLevelProvider()


def _get_lock(config_id: str, remote_phone: str) -> asyncio.Lock:
    key = f"ghl:{config_id}:{remote_phone}"
    if key not in _locks:
        _locks[key] = asyncio.Lock()
    return _locks[key]


def _get_supabase() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


async def load_ghl_config_by_location(location_id: str) -> dict | None:
    """Carga ghl_config por ghl_location_id."""
    sb = _get_supabase()
    result = (
        sb.table("ghl_configs")
        .select("*")
        .eq("ghl_location_id", location_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def _is_within_schedule(config: dict) -> bool:
    """Verifica si el momento actual está dentro del horario configurado."""
    schedule = config.get("schedule")
    if not schedule:
        return True

    from zoneinfo import ZoneInfo

    tz_name = schedule.get("timezone", "America/Mexico_City")
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("America/Mexico_City")

    now = datetime.now(tz)
    day_key = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][now.weekday()]

    day_config = schedule.get(day_key)
    if not day_config or not day_config.get("active", False):
        return False

    start_str = day_config.get("start", "00:00")
    end_str = day_config.get("end", "23:59")

    try:
        start_h, start_m = map(int, start_str.split(":"))
        end_h, end_m = map(int, end_str.split(":"))
    except (ValueError, AttributeError):
        return True

    current_minutes = now.hour * 60 + now.minute
    start_minutes = start_h * 60 + start_m
    end_minutes = end_h * 60 + end_m

    return start_minutes <= current_minutes <= end_minutes


async def _send_ghl(config: dict, msg: InboundMessage, text: str) -> str | None:
    """Envía respuesta vía GHL con contactId y channel inyectados."""
    send_config = dict(config)
    if msg.ghl_contact_id:
        send_config["_ghl_contact_id"] = msg.ghl_contact_id
    if msg.channel:
        send_config["_ghl_channel"] = msg.channel
    return await _provider.send_text(send_config, msg.remote_phone, text)


async def process_ghl_inbound(msg: InboundMessage) -> None:
    """Procesa un mensaje entrante de GHL end-to-end.

    1. Resolver ghl_config por location_id
    2. Verificar auto_reply, pausa, horario
    3. Buscar/crear contacto y sesión
    4. Ejecutar chat_turn
    5. Enviar respuesta vía GHL API
    6. Persistir historial + mensajes
    """
    sb = _get_supabase()

    # 1. Resolver config
    if not msg.ghl_location_id:
        logger.warning("GHL: mensaje sin location_id de %s", msg.remote_phone)
        return

    config = await load_ghl_config_by_location(msg.ghl_location_id)
    if not config:
        logger.warning("GHL: no config encontrada para location %s", msg.ghl_location_id)
        return

    config_id = config["id"]

    # 2. Verificaciones
    if not config.get("auto_reply", True):
        logger.info("GHL: auto_reply desactivado para config %s", config_id)
        await _save_message(sb, None, msg, "inbound")
        return

    if config.get("is_paused", False):
        paused_msg = config.get(
            "paused_message",
            "En este momento un agente humano esta atendiendo. Te responderemos pronto.",
        )
        await _send_ghl(config, msg, paused_msg)
        return

    if not _is_within_schedule(config):
        away_msg = config.get(
            "away_message",
            "En este momento no estamos disponibles. Te responderemos en horario de atencion.",
        )
        await _send_ghl(config, msg, away_msg)
        return

    if msg.message_type != "text":
        media_response = config.get(
            "media_response",
            "Solo puedo procesar mensajes de texto por ahora.",
        )
        await _send_ghl(config, msg, media_response)
        return

    if not msg.text.strip():
        return

    # Verificar human takeover
    active_conv = (
        sb.table("ghl_conversations")
        .select("id, is_human_controlled, message_count")
        .eq("config_id", config_id)
        .eq("remote_phone", msg.remote_phone)
        .eq("status", "active")
        .order("last_message_at", desc=True)
        .limit(1)
        .execute()
    )
    if active_conv.data and active_conv.data[0].get("is_human_controlled"):
        conv_id = active_conv.data[0]["id"]
        await _save_message(sb, conv_id, msg, "inbound")
        sb.table("ghl_conversations").update({
            "last_message_at": datetime.now(timezone.utc).isoformat(),
            "message_count": (active_conv.data[0].get("message_count", 0) or 0) + 1,
        }).eq("id", conv_id).execute()
        return

    # Lock por (config_id, phone)
    lock = _get_lock(config_id, msg.remote_phone)
    async with lock:
        await _process_locked(sb, config, msg)


async def _process_locked(sb: Client, config: dict, msg: InboundMessage) -> None:
    """Procesa el mensaje con lock adquirido."""
    config_id = config["id"]
    agent_id = config["agent_id"]
    client_id = config["client_id"]

    # Cargar config del agente
    resolved = await load_config_by_agent_id(agent_id)
    if not resolved:
        logger.error("GHL: agente %s no encontrado", agent_id)
        return

    # Buscar/crear contacto
    contact_id = await _resolve_contact(sb, client_id, msg)

    # Buscar/crear sesión
    conv_row = await _get_or_create_conversation(sb, config_id, contact_id, msg, config)
    if not conv_row:
        return
    conv_id = conv_row["id"]

    # Deserializar historial
    history = deserialize_history(conv_row.get("history") or [])

    # Cargar integraciones y MCP
    api_integrations = await load_api_integrations(client_id, agent_id)
    mcp_servers = await load_mcp_servers(client_id, agent_id)

    # System prompt
    system_prompt = _build_ghl_system_prompt(resolved, msg.channel, api_integrations, mcp_servers)

    # Conversation efímera
    conversation = Conversation(
        id=conv_id,
        config=resolved,
        system_prompt=system_prompt,
        history=history,
        created_at=0,
        turn_count=conv_row.get("message_count", 0) // 2,
        client_id=client_id,
    )

    # Guardar inbound
    await _save_message(sb, conv_id, msg, "inbound")

    # Chat turn
    try:
        agent_text, tool_calls = await chat_turn(
            conversation, msg.text,
            api_integrations=api_integrations,
            mcp_servers=mcp_servers or None,
        )
    except Exception as e:
        logger.error("GHL: error en chat_turn — %s", e, exc_info=True)
        agent_text = "Disculpa, tuve un problema procesando tu mensaje. Intenta de nuevo."
        tool_calls = []

    # Enviar respuesta
    provider_msg_id = await _send_ghl(config, msg, agent_text)

    # Guardar outbound
    out_msg = InboundMessage(
        remote_phone=msg.remote_phone,
        text=agent_text,
        message_type="text",
        channel=msg.channel,
        provider_message_id=provider_msg_id,
    )
    await _save_message(sb, conv_id, out_msg, "outbound", tool_calls=tool_calls or None)

    # Persistir historial
    serialized = serialize_history(conversation.history)
    now = datetime.now(timezone.utc).isoformat()
    try:
        sb.table("ghl_conversations").update({
            "history": serialized,
            "message_count": (conv_row.get("message_count", 0) or 0) + 2,
            "last_message_at": now,
        }).eq("id", conv_id).execute()
    except Exception:
        logger.exception("GHL: error actualizando conversación %s", conv_id)


# ── Helpers ─────────────────────────────────────────────


async def _resolve_contact(sb: Client, client_id: str, msg: InboundMessage) -> str | None:
    """Busca o crea contacto. Para GHL webchat sin phone, usa contactId."""
    phone = msg.remote_phone
    # Si remote_phone es un contactId de GHL (no un número), no crear contacto por phone
    if not phone or phone == "unknown":
        return None
    # Si parece un ID de GHL (no numérico), no buscar por phone
    if not phone.replace("+", "").isdigit():
        return None

    clean = phone.lstrip("+").replace(" ", "").replace("-", "")
    result = (
        sb.table("contacts")
        .select("id")
        .eq("client_id", client_id)
        .eq("phone", f"+{clean}")
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0]["id"]

    result = (
        sb.table("contacts")
        .select("id")
        .eq("client_id", client_id)
        .eq("phone", clean)
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0]["id"]

    new_contact = {
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "phone": f"+{clean}",
        "source": f"ghl-{msg.channel}",
    }
    try:
        sb.table("contacts").insert(new_contact).execute()
        return new_contact["id"]
    except Exception as e:
        logger.error("GHL: error creando contacto — %s", e)
        return None


async def _get_or_create_conversation(
    sb: Client,
    config_id: str,
    contact_id: str | None,
    msg: InboundMessage,
    config: dict,
) -> dict | None:
    """Busca sesión activa o crea una nueva."""
    timeout_minutes = config.get("session_timeout_minutes", 30)

    result = (
        sb.table("ghl_conversations")
        .select("*")
        .eq("config_id", config_id)
        .eq("remote_phone", msg.remote_phone)
        .eq("status", "active")
        .order("last_message_at", desc=True)
        .limit(1)
        .execute()
    )

    if result.data:
        conv = result.data[0]
        last_msg = conv.get("last_message_at")
        if last_msg:
            if isinstance(last_msg, str):
                last_dt = datetime.fromisoformat(last_msg.replace("Z", "+00:00"))
            else:
                last_dt = last_msg
            now = datetime.now(timezone.utc)
            elapsed = (now - last_dt).total_seconds() / 60
            if elapsed > timeout_minutes:
                sb.table("ghl_conversations").update(
                    {"status": "expired"}
                ).eq("id", conv["id"]).execute()
            else:
                return conv

    new_conv = {
        "id": str(uuid.uuid4()),
        "config_id": config_id,
        "contact_id": contact_id,
        "remote_phone": msg.remote_phone,
        "channel": msg.channel,
        "ghl_contact_id": msg.ghl_contact_id,
        "history": [],
        "status": "active",
        "message_count": 0,
    }
    try:
        sb.table("ghl_conversations").insert(new_conv).execute()
    except Exception:
        logger.exception("GHL: error creando conversación para %s", msg.remote_phone)
        return None

    # Greeting
    greeting = config.get("greeting")
    if greeting:
        try:
            await _send_ghl(config, msg, greeting)
        except Exception:
            logger.exception("GHL: error enviando greeting a %s", msg.remote_phone)
        await _save_message(
            sb, new_conv["id"],
            InboundMessage(remote_phone=msg.remote_phone, text=greeting, channel=msg.channel),
            "outbound",
        )
        new_conv["message_count"] = 1

    return new_conv


async def _save_message(
    sb: Client,
    conversation_id: str | None,
    msg: InboundMessage,
    direction: str,
    tool_calls: list[dict] | None = None,
) -> None:
    """Guarda un mensaje en ghl_messages."""
    if not conversation_id:
        return

    record = {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "direction": direction,
        "content": msg.text,
        "message_type": msg.message_type,
        "channel": msg.channel,
        "provider_message_id": msg.provider_message_id,
        "status": "sent",
    }
    if tool_calls:
        record["tool_calls"] = tool_calls

    try:
        sb.table("ghl_messages").insert(record).execute()
    except Exception as e:
        logger.error("GHL: error guardando mensaje — %s", e)


def _build_ghl_system_prompt(
    config: ResolvedConfig,
    channel: str,
    api_integrations: list[dict] | None = None,
    mcp_servers: list[dict] | None = None,
) -> str:
    """Construye system prompt adaptado para mensajería GHL."""
    from agent.agent_factory import _build_tool_instructions, _build_api_instructions
    from api.services.chat_service import _build_mcp_prompt_section

    base = config.agent.system_prompt
    tool_instructions = _build_tool_instructions(config.client.enabled_tools)
    api_instructions = _build_api_instructions(api_integrations or [])
    mcp_instructions = _build_mcp_prompt_section(mcp_servers or [])

    prompt = base + tool_instructions + api_instructions + mcp_instructions

    if config.agent.examples:
        prompt += f"\n\n## Ejemplos de conversación\n{config.agent.examples}"

    channel_names = {
        "whatsapp": "WhatsApp",
        "sms": "SMS",
        "webchat": "Web Chat",
        "facebook": "Facebook Messenger",
        "instagram": "Instagram DM",
        "email": "Email",
        "google": "Google Business Messages",
    }
    ch_name = channel_names.get(channel, channel)

    prompt += (
        f"\n\n## Canal: {ch_name}\n"
        f"Estás respondiendo por {ch_name}. Reglas importantes:\n"
        "- Sé conciso. Los mensajes largos se ven mal en chat.\n"
        "- Usa párrafos cortos separados por saltos de línea.\n"
        "- NO uses markdown complejo (headers, tablas). Solo *negritas* y _cursivas_.\n"
        "- Puedes usar emojis con moderación para hacer la conversación amigable.\n"
        "- No menciones que eres una IA a menos que te pregunten directamente.\n"
        "- Responde en el idioma del usuario.\n"
    )

    return prompt
