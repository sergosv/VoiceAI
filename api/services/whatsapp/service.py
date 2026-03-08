"""Orquestador principal del canal WhatsApp."""

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
    load_whatsapp_config_by_evo_instance,
)
from api.services.chat_service import chat_turn
from api.services.chat_store import Conversation
from api.services.whatsapp.history import deserialize_history, serialize_history
from api.services.whatsapp.provider import InboundMessage
from api.services.whatsapp.router import get_provider

logger = logging.getLogger(__name__)

# Lock por (config_id, remote_phone) para evitar race conditions
_locks: dict[str, asyncio.Lock] = {}


def _get_lock(config_id: str, remote_phone: str) -> asyncio.Lock:
    """Obtiene o crea un lock por (config_id, phone)."""
    key = f"{config_id}:{remote_phone}"
    if key not in _locks:
        _locks[key] = asyncio.Lock()
    return _locks[key]


def _get_supabase() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


# ── Schedule check ──────────────────────────────────────


def _is_within_schedule(wa_config: dict) -> bool:
    """Verifica si el momento actual está dentro del horario configurado.

    Si no hay schedule configurado, retorna True (siempre activo).
    """
    schedule = wa_config.get("schedule")
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


# ── Orchestrator ────────────────────────────────────────


async def process_inbound_message(msg: InboundMessage) -> None:
    """Procesa un mensaje entrante de WhatsApp end-to-end.

    1. Resolver whatsapp_config
    2. Verificar auto_reply activo
    3. Buscar/crear contacto
    4. Buscar/crear sesión (conversation)
    5. Cargar config del agente
    6. Ejecutar chat_turn con historial persistido
    7. Enviar respuesta vía provider
    8. Persistir historial + log messages
    """
    sb = _get_supabase()

    # 1. Resolver config (solo Evolution — GHL usa ghl_service)
    wa_config: dict | None = None
    if msg.evo_instance_id:
        wa_config = await load_whatsapp_config_by_evo_instance(msg.evo_instance_id)

    if not wa_config:
        logger.warning("WA: no config encontrada para msg de %s", msg.remote_phone)
        return

    config_id = wa_config["id"]

    if not wa_config.get("auto_reply", True):
        logger.info("WA: auto_reply desactivado para config %s", config_id)
        await _save_message(sb, None, msg, "inbound")
        return

    # Verificar pausa manual
    if wa_config.get("is_paused", False):
        paused_msg = wa_config.get(
            "paused_message",
            "En este momento un agente humano esta atendiendo. Te responderemos pronto.",
        )
        provider = get_provider(wa_config["provider"])
        await provider.send_text(wa_config, msg.remote_phone, paused_msg)
        await _save_message(sb, None, msg, "inbound")
        return

    # Verificar horario
    if not _is_within_schedule(wa_config):
        away_msg = wa_config.get(
            "away_message",
            "En este momento no estamos disponibles. Te responderemos en horario de atencion.",
        )
        provider = get_provider(wa_config["provider"])
        await provider.send_text(wa_config, msg.remote_phone, away_msg)
        await _save_message(sb, None, msg, "inbound")
        return

    # Manejar media no soportada
    if msg.message_type != "text":
        media_response = wa_config.get(
            "media_response",
            "Solo puedo procesar mensajes de texto por ahora.",
        )
        provider = get_provider(wa_config["provider"])
        await provider.send_text(wa_config, msg.remote_phone, media_response)
        return

    if not msg.text.strip():
        return

    # Verificar human takeover por conversación
    active_conv = (
        sb.table("whatsapp_conversations")
        .select("id, is_human_controlled")
        .eq("config_id", config_id)
        .eq("remote_phone", msg.remote_phone)
        .eq("status", "active")
        .order("last_message_at", desc=True)
        .limit(1)
        .execute()
    )
    if active_conv.data and active_conv.data[0].get("is_human_controlled"):
        logger.info("WA: human takeover activo para %s, solo guardando mensaje", msg.remote_phone)
        conv_id = active_conv.data[0]["id"]
        await _save_message(sb, conv_id, msg, "inbound")
        # Actualizar last_message_at
        sb.table("whatsapp_conversations").update({
            "last_message_at": datetime.now(timezone.utc).isoformat(),
            "message_count": (active_conv.data[0].get("message_count", 0) or 0) + 1,
        }).eq("id", conv_id).execute()
        return

    # Lock por (config_id, phone)
    lock = _get_lock(config_id, msg.remote_phone)
    async with lock:
        await _process_locked(sb, wa_config, msg)


async def _process_locked(
    sb: Client,
    wa_config: dict,
    msg: InboundMessage,
) -> None:
    """Procesa el mensaje con lock adquirido."""
    config_id = wa_config["id"]
    agent_id = wa_config["agent_id"]
    client_id = wa_config["client_id"]

    # 2. Cargar config del agente
    resolved = await load_config_by_agent_id(agent_id)
    if not resolved:
        logger.error("WA: agente %s no encontrado", agent_id)
        return

    # 3. Buscar/crear contacto
    contact_id = await _resolve_contact(sb, client_id, msg.remote_phone)

    # 4. Buscar/crear sesión
    conv_row = await _get_or_create_conversation(
        sb, config_id, contact_id, msg.remote_phone, wa_config
    )
    conv_id = conv_row["id"]

    # 5. Deserializar historial
    history = deserialize_history(conv_row.get("history") or [])

    # Cargar integraciones y MCP servers
    api_integrations = await load_api_integrations(client_id, agent_id)
    mcp_servers = await load_mcp_servers(client_id, agent_id)
    if mcp_servers:
        logger.info(
            "WA: %d MCP servers cargados para agente %s: %s",
            len(mcp_servers),
            agent_id,
            [(s.get("name"), len(s.get("tools_cache") or [])) for s in mcp_servers],
        )
    else:
        logger.info("WA: sin MCP servers para agente %s", agent_id)

    # Construir system prompt para WhatsApp
    system_prompt = build_whatsapp_system_prompt(
        resolved, api_integrations=api_integrations, mcp_servers=mcp_servers or None,
    )

    # Crear Conversation efímera para chat_turn
    conversation = Conversation(
        id=conv_id,
        config=resolved,
        system_prompt=system_prompt,
        history=history,
        created_at=0,
        turn_count=conv_row.get("message_count", 0) // 2,
        client_id=client_id,
    )

    # 6. Guardar mensaje inbound
    await _save_message(sb, conv_id, msg, "inbound")

    # 7. Ejecutar chat_turn
    try:
        agent_text, tool_calls = await chat_turn(
            conversation, msg.text,
            api_integrations=api_integrations,
            mcp_servers=mcp_servers or None,
        )
    except Exception as e:
        logger.error("WA: error en chat_turn — %s", e, exc_info=True)
        agent_text = "Disculpa, tuve un problema procesando tu mensaje. Intenta de nuevo."
        tool_calls = []

    # 8. Enviar respuesta
    provider = get_provider(wa_config["provider"])
    provider_msg_id = await provider.send_text(
        wa_config, msg.remote_phone, agent_text
    )

    # 9. Guardar mensaje outbound
    out_msg = InboundMessage(
        remote_phone=msg.remote_phone,
        text=agent_text,
        message_type="text",
        provider_message_id=provider_msg_id,
    )
    await _save_message(
        sb, conv_id, out_msg, "outbound", tool_calls=tool_calls or None
    )

    # 10. Persistir historial actualizado
    serialized = serialize_history(conversation.history)
    now = datetime.now(timezone.utc).isoformat()
    try:
        sb.table("whatsapp_conversations").update({
            "history": serialized,
            "message_count": (conv_row.get("message_count", 0) or 0) + 2,
            "last_message_at": now,
        }).eq("id", conv_id).execute()
    except Exception:
        logger.exception("WA: error actualizando conversación %s", conv_id)

    # 11. Detectar cierre por IA
    close_tool = next(
        (tc for tc in (tool_calls or []) if tc.get("name") == "close_conversation"),
        None,
    )
    if close_tool:
        from api.services.conversation_lifecycle import close_conversation as _close
        close_args = close_tool.get("args", {})
        await _close(
            sb, conv_id, "whatsapp_conversations",
            summary=close_args.get("summary", ""),
            result=close_args.get("result", "other"),
            closed_by="ai",
        )


# ── Helpers ─────────────────────────────────────────────


async def _resolve_contact(
    sb: Client, client_id: str, phone: str
) -> str | None:
    """Busca o crea contacto por teléfono con normalización. Retorna contact_id."""
    from agent.phone_utils import normalize_phone

    normalized = normalize_phone(phone)

    # Buscar por teléfono normalizado
    result = (
        sb.table("contacts")
        .select("id, channels")
        .eq("client_id", client_id)
        .eq("phone", normalized)
        .limit(1)
        .execute()
    )
    if result.data:
        contact = result.data[0]
        _ensure_channel(sb, contact["id"], contact.get("channels") or [], "whatsapp")
        return contact["id"]

    # Crear contacto nuevo con teléfono normalizado
    new_contact = {
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "phone": normalized,
        "source": "whatsapp",
        "channels": ["whatsapp"],
    }
    try:
        sb.table("contacts").insert(new_contact).execute()
        logger.info("WA: contacto creado para +%s", clean)
        return new_contact["id"]
    except Exception as e:
        logger.error("WA: error creando contacto — %s", e)
        return None


async def _get_or_create_conversation(
    sb: Client,
    config_id: str,
    contact_id: str | None,
    remote_phone: str,
    wa_config: dict,
) -> dict:
    """Busca sesión activa o crea una nueva.

    Si last_message_at > session_timeout → cierra sesión anterior y crea nueva.
    """
    timeout_minutes = wa_config.get("session_timeout_minutes", 30)

    # Buscar sesión activa
    result = (
        sb.table("whatsapp_conversations")
        .select("*")
        .eq("config_id", config_id)
        .eq("remote_phone", remote_phone)
        .eq("status", "active")
        .order("last_message_at", desc=True)
        .limit(1)
        .execute()
    )

    if result.data:
        conv = result.data[0]
        last_msg = conv.get("last_message_at")
        if last_msg:
            from datetime import datetime, timezone

            if isinstance(last_msg, str):
                # Parsear ISO string
                last_dt = datetime.fromisoformat(last_msg.replace("Z", "+00:00"))
            else:
                last_dt = last_msg

            now = datetime.now(timezone.utc)
            elapsed_minutes = (now - last_dt).total_seconds() / 60

            if elapsed_minutes > timeout_minutes:
                # Sesión expirada — cerrar y crear nueva
                sb.table("whatsapp_conversations").update(
                    {"status": "expired"}
                ).eq("id", conv["id"]).execute()
                logger.info("WA: sesión %s expirada (%d min)", conv["id"], int(elapsed_minutes))
            else:
                return conv

    # Crear nueva sesión
    greeting = wa_config.get("greeting")
    new_conv = {
        "id": str(uuid.uuid4()),
        "config_id": config_id,
        "contact_id": contact_id,
        "remote_phone": remote_phone,
        "history": [],
        "status": "active",
        "message_count": 0,
    }
    try:
        sb.table("whatsapp_conversations").insert(new_conv).execute()
    except Exception:
        logger.exception("WA: error creando conversación para %s", remote_phone)
        return None
    logger.info("WA: nueva sesión %s para %s", new_conv["id"], remote_phone)

    # Enviar greeting si configurado
    if greeting:
        provider = get_provider(wa_config["provider"])
        try:
            await provider.send_text(wa_config, remote_phone, greeting)
        except Exception:
            logger.exception("WA: error enviando greeting a %s", remote_phone)
        # Guardar greeting como mensaje outbound
        await _save_message(
            sb,
            new_conv["id"],
            InboundMessage(remote_phone=remote_phone, text=greeting),
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
    """Guarda un mensaje en whatsapp_messages."""
    if not conversation_id:
        return

    record = {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "direction": direction,
        "content": msg.text,
        "message_type": msg.message_type,
        "provider_message_id": msg.provider_message_id,
        "status": "sent",
    }
    if tool_calls:
        record["tool_calls"] = tool_calls

    try:
        sb.table("whatsapp_messages").insert(record).execute()
    except Exception as e:
        logger.error("WA: error guardando mensaje — %s", e)


def _ensure_channel(sb: Client, contact_id: str, channels: list, channel: str) -> None:
    """Agrega canal al contacto si no lo tiene."""
    if channel not in channels:
        try:
            new_channels = list(set(channels + [channel]))
            sb.table("contacts").update(
                {"channels": new_channels}
            ).eq("id", contact_id).execute()
        except Exception as e:
            logger.error("Error actualizando channels: %s", e)


def build_whatsapp_system_prompt(
    config: ResolvedConfig,
    api_integrations: list[dict] | None = None,
    mcp_servers: list[dict] | None = None,
) -> str:
    """Construye system prompt adaptado para WhatsApp (sin reglas de voz)."""
    from agent.agent_factory import _build_tool_instructions, _build_api_instructions
    from api.services.chat_service import _build_mcp_prompt_section

    base = config.agent.system_prompt
    tool_instructions = _build_tool_instructions(config.client.enabled_tools)
    api_instructions = _build_api_instructions(api_integrations or [])
    mcp_instructions = _build_mcp_prompt_section(mcp_servers or [])

    prompt = base + tool_instructions + api_instructions + mcp_instructions

    # Ejemplos
    if config.agent.examples:
        prompt += f"\n\n## Ejemplos de conversación\n{config.agent.examples}"

    # Instrucciones específicas WhatsApp
    prompt += (
        "\n\n## Canal: WhatsApp\n"
        "Estás respondiendo por WhatsApp. Reglas importantes:\n"
        "- Sé conciso. Los mensajes largos se ven mal en WhatsApp.\n"
        "- Usa párrafos cortos separados por saltos de línea.\n"
        "- NO uses markdown complejo (headers, tablas). Solo *negritas* y _cursivas_.\n"
        "- Puedes usar emojis con moderación para hacer la conversación amigable.\n"
        "- No menciones que eres una IA a menos que te pregunten directamente.\n"
        "- Responde en el idioma del usuario.\n"
        "- Si necesitas dar una lista, usa viñetas simples con - o •.\n"
    )

    prompt += (
        "\n## Cierre de conversación\n"
        "Cuando el usuario se despida (adiós, gracias, hasta luego), el objetivo se complete "
        "(cita agendada, lead calificado, consulta resuelta), o no haya más que hacer, "
        "usa la herramienta close_conversation con un resumen breve y el resultado apropiado.\n"
    )

    return prompt
