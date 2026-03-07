"""Worker background para ejecutar acciones proactivas programadas.

Cada 60 segundos consulta `scheduled_actions` con `status='pending'` y
`scheduled_at <= now()`, y ejecuta la acción correspondiente (call o whatsapp).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone

from api.deps import get_supabase

logger = logging.getLogger(__name__)

# Intervalo de polling en segundos
POLL_INTERVAL_S = 60
# Max acciones por batch
BATCH_SIZE = 10
# Semáforo para limitar concurrencia
MAX_CONCURRENT = 3

_worker_task: asyncio.Task | None = None


def start_proactive_worker() -> None:
    """Inicia el worker de acciones proactivas como task async."""
    global _worker_task
    if _worker_task and not _worker_task.done():
        logger.warning("Proactive worker ya está corriendo")
        return
    _worker_task = asyncio.create_task(_worker_loop())
    logger.info("Proactive worker iniciado (poll=%ds, max_concurrent=%d)", POLL_INTERVAL_S, MAX_CONCURRENT)


def stop_proactive_worker() -> None:
    """Detiene el worker de acciones proactivas."""
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        _worker_task = None
        logger.info("Proactive worker detenido")


async def _worker_loop() -> None:
    """Loop principal del worker."""
    while True:
        try:
            await _process_pending_actions()
        except asyncio.CancelledError:
            logger.info("Proactive worker cancelado")
            return
        except Exception:
            logger.exception("Error en proactive worker loop")
        await asyncio.sleep(POLL_INTERVAL_S)


async def _process_pending_actions() -> None:
    """Procesa acciones pendientes cuyo scheduled_at ya pasó."""
    sb = get_supabase()
    now_iso = datetime.now(timezone.utc).isoformat()

    result = (
        sb.table("scheduled_actions")
        .select("*")
        .eq("status", "pending")
        .lte("scheduled_at", now_iso)
        .order("scheduled_at")
        .limit(BATCH_SIZE)
        .execute()
    )

    if not result.data:
        return

    logger.info("Proactive worker: %d acciones pendientes", len(result.data))

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    tasks = [_execute_action(sb, action, semaphore) for action in result.data]
    await asyncio.gather(*tasks, return_exceptions=True)


async def _execute_action(
    sb,
    action: dict,
    semaphore: asyncio.Semaphore,
) -> None:
    """Ejecuta una acción proactiva individual."""
    async with semaphore:
        action_id = action["id"]
        channel = action["channel"]
        target = action["target_number"]
        attempts = action.get("attempts", 0) + 1
        max_attempts = action.get("max_attempts", 2)

        # Marcar como executing
        sb.table("scheduled_actions").update({
            "status": "executing",
            "attempts": attempts,
            "last_attempt_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", action_id).execute()

        try:
            if channel == "call":
                await _execute_outbound_call(action)
            elif channel == "whatsapp":
                await _execute_whatsapp(action)
            elif channel == "sms":
                logger.warning("Canal SMS no implementado aún para acción %s", action_id)
                sb.table("scheduled_actions").update({
                    "status": "failed",
                    "result": "Canal SMS no implementado",
                }).eq("id", action_id).execute()
                return

            # Marcar como completada
            sb.table("scheduled_actions").update({
                "status": "completed",
                "result": f"Ejecutada exitosamente vía {channel}",
            }).eq("id", action_id).execute()
            logger.info(
                "Acción proactiva completada: %s -> %s vía %s",
                action_id, target, channel,
            )

        except Exception as e:
            logger.error("Error ejecutando acción proactiva %s: %s", action_id, e)
            if attempts >= max_attempts:
                sb.table("scheduled_actions").update({
                    "status": "failed",
                    "result": str(e)[:500],
                }).eq("id", action_id).execute()
            else:
                # Reintentar: volver a pending
                sb.table("scheduled_actions").update({
                    "status": "pending",
                    "result": f"Intento {attempts} falló: {str(e)[:200]}",
                }).eq("id", action_id).execute()


async def _execute_outbound_call(action: dict) -> None:
    """Ejecuta una llamada outbound proactiva vía LiveKit SIP."""
    from livekit.api import LiveKitAPI
    from livekit.api.sip_service import CreateSIPParticipantRequest
    from livekit.protocol.agent_dispatch import RoomAgentDispatch
    from livekit.protocol.room import CreateRoomRequest

    agent_id = action["agent_id"]
    client_id = action["client_id"]
    target = action["target_number"]
    message = action.get("message", "")

    sb = get_supabase()

    # Resolver trunk
    agent_row = (
        sb.table("agents")
        .select("phone_number, livekit_sip_trunk_id")
        .eq("id", agent_id)
        .limit(1)
        .execute()
    )
    trunk_id = None
    from_number = ""
    if agent_row.data and agent_row.data[0].get("livekit_sip_trunk_id"):
        trunk_id = agent_row.data[0]["livekit_sip_trunk_id"]
        from_number = agent_row.data[0].get("phone_number", "")

    if not trunk_id:
        client_row = (
            sb.table("clients")
            .select("phone_number, livekit_sip_trunk_id")
            .eq("id", client_id)
            .limit(1)
            .execute()
        )
        if client_row.data and client_row.data[0].get("livekit_sip_trunk_id"):
            trunk_id = client_row.data[0]["livekit_sip_trunk_id"]
            from_number = client_row.data[0].get("phone_number", "")

    if not trunk_id:
        raise ValueError("No hay SIP trunk configurado para este agente/cliente")

    lk = LiveKitAPI(
        url=os.environ["LIVEKIT_URL"],
        api_key=os.environ["LIVEKIT_API_KEY"],
        api_secret=os.environ["LIVEKIT_API_SECRET"],
    )

    room_name = f"proactive-{action['id'][:8]}"
    room_metadata = json.dumps({
        "type": "outbound",
        "proactive": True,
        "action_id": action["id"],
        "client_id": client_id,
        "agent_id": agent_id,
        "script": message or "Saluda y explica el motivo de la llamada proactiva.",
        "rule_type": action.get("rule_type", "manual"),
    })

    create_room_req = CreateRoomRequest(
        name=room_name,
        metadata=room_metadata,
        empty_timeout=60,
        agents=[
            RoomAgentDispatch(
                agent_name="voice-ai-platform",
                metadata=room_metadata,
            )
        ],
    )
    await lk.room.create_room(create_room_req)

    request = CreateSIPParticipantRequest(
        sip_trunk_id=trunk_id,
        sip_call_to=target,
        sip_number=from_number,
        room_name=room_name,
        participant_identity=f"proactive-{action['id'][:8]}",
        participant_name=f"Proactive to {target}",
        participant_metadata=json.dumps({
            "type": "proactive",
            "action_id": action["id"],
            "rule_type": action.get("rule_type"),
        }),
    )
    await lk.sip.create_sip_participant(request)
    await lk.aclose()

    logger.info("Llamada proactiva colocada: %s -> %s", from_number, target)


async def _execute_whatsapp(action: dict) -> None:
    """Envía un mensaje de WhatsApp proactivo."""
    agent_id = action["agent_id"]
    target = action["target_number"]
    message = action.get("message", "")

    if not message:
        raise ValueError("Mensaje vacío para WhatsApp proactivo")

    sb = get_supabase()

    # Cargar config de WhatsApp del agente
    wa_config = (
        sb.table("whatsapp_configs")
        .select("*")
        .eq("agent_id", agent_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )

    if not wa_config.data:
        raise ValueError(f"No hay WhatsApp configurado para agente {agent_id}")

    cfg = wa_config.data[0]
    api_url = cfg.get("evo_api_url") or cfg.get("api_url")
    api_key = cfg.get("evo_api_key") or cfg.get("api_key")
    instance_id = cfg.get("evo_instance_id") or cfg.get("instance_id")

    if not all([api_url, api_key, instance_id]):
        raise ValueError("Config de WhatsApp incompleta para envío proactivo")

    from agent.tools.whatsapp_tool import send_whatsapp_message
    result = await send_whatsapp_message(
        api_url=api_url,
        api_key=api_key,
        instance_id=instance_id,
        phone_number=target,
        message=message,
    )

    if "error" in result.lower():
        raise ValueError(result)

    logger.info("WhatsApp proactivo enviado: %s", target)


# ── Utilidades para crear acciones programadas ──


def create_scheduled_action(
    agent_id: str,
    client_id: str,
    rule_type: str,
    channel: str,
    target_number: str,
    message: str | None,
    scheduled_at: str,
    source: str = "rule",
    source_call_id: str | None = None,
    target_contact_id: str | None = None,
    max_attempts: int = 2,
    metadata: dict | None = None,
) -> dict:
    """Crea una acción programada en la DB."""
    sb = get_supabase()
    data = {
        "agent_id": agent_id,
        "client_id": client_id,
        "rule_type": rule_type,
        "channel": channel,
        "target_number": target_number,
        "message": message,
        "scheduled_at": scheduled_at,
        "source": source,
        "source_call_id": source_call_id,
        "target_contact_id": target_contact_id,
        "max_attempts": max_attempts,
        "metadata": metadata or {},
        "status": "pending",
    }
    result = sb.table("scheduled_actions").insert(data).execute()
    if result.data:
        logger.info(
            "Acción programada creada: %s -> %s @ %s vía %s",
            rule_type, target_number, scheduled_at, channel,
        )
        return result.data[0]
    raise ValueError("Error creando acción programada")
