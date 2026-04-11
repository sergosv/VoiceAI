"""Servicio para ejecutar scheduled callbacks — devoluciones de llamada programadas."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone

from livekit.api import (
    CreateRoomRequest,
    CreateSIPParticipantRequest,
    LiveKitAPI,
    RoomAgentDispatch,
)

from api.deps import get_supabase

logger = logging.getLogger(__name__)


async def process_pending_callbacks() -> dict:
    """Busca callbacks pendientes cuya hora ya llegó y los ejecuta.

    Retorna estadísticas de ejecución.
    """
    sb = get_supabase()
    now = datetime.now(timezone.utc).isoformat()

    # Buscar callbacks pendientes cuya hora ya pasó
    result = sb.table("scheduled_callbacks").select(
        "*, agents!inner(slug, name, client_id), clients!scheduled_callbacks_client_id_fkey(slug)"
    ).eq("status", "pending").lte("scheduled_at", now).order(
        "scheduled_at"
    ).limit(20).execute()

    if not result.data:
        return {"processed": 0, "succeeded": 0, "failed": 0}

    stats = {"processed": 0, "succeeded": 0, "failed": 0}

    for cb in result.data:
        stats["processed"] += 1
        try:
            await _execute_callback(sb, cb)
            stats["succeeded"] += 1
        except Exception:
            logger.exception("Error ejecutando callback %s", cb["id"])
            stats["failed"] += 1

    return stats


async def _execute_callback(sb, cb: dict) -> None:
    """Ejecuta un callback individual: crea room + SIP participant."""
    cb_id = cb["id"]
    phone = cb["phone"]
    agent_id = cb["agent_id"]
    client_id = cb["client_id"]
    context = cb.get("context", "")
    attempts = cb.get("attempts", 0) + 1
    max_attempts = cb.get("max_attempts", 3)

    # DNC check: si el número fue agregado a la lista entre el momento de programar
    # y el de ejecutar, NO llamar
    try:
        dnc = sb.table("dnc_entries").select("id").eq(
            "client_id", client_id
        ).eq("phone", phone).limit(1).execute()
        if dnc.data:
            logger.warning(
                "Callback %s cancelado: número %s en DNC",
                cb_id, phone,
            )
            sb.table("scheduled_callbacks").update({
                "status": "cancelled",
                "failure_reason": "Número en lista Do-Not-Call al momento de ejecutar",
            }).eq("id", cb_id).execute()
            return
    except Exception:
        logger.exception("Error verificando DNC para callback %s", cb_id)

    # Marcar como in_progress
    sb.table("scheduled_callbacks").update({
        "status": "in_progress",
        "attempts": attempts,
        "last_attempt_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", cb_id).execute()

    lk_api: LiveKitAPI | None = None
    try:
        lk_api = LiveKitAPI(
            url=os.environ["LIVEKIT_URL"],
            api_key=os.environ["LIVEKIT_API_KEY"],
            api_secret=os.environ["LIVEKIT_API_SECRET"],
        )

        # Resolver trunk SIP
        from api.services.outbound_service import _resolve_sip_trunk
        trunk_id, from_number = await _resolve_sip_trunk(
            sb, lk_api, agent_id, client_id
        )

        room_name = f"callback-{cb_id[:8]}"

        # Si el callback vino de una campaña, recuperar el script para usarlo
        origin_type = cb.get("origin_type")
        callback_campaign_id = cb.get("campaign_id")
        campaign_script = None
        if origin_type == "campaign" and callback_campaign_id:
            try:
                camp = sb.table("campaigns").select("script").eq(
                    "id", callback_campaign_id
                ).limit(1).execute()
                if camp.data and camp.data[0].get("script"):
                    campaign_script = camp.data[0]["script"]
                    logger.info(
                        "Callback %s usará campaign script (%d chars) de campaña %s",
                        cb_id, len(campaign_script), callback_campaign_id,
                    )
            except Exception:
                logger.exception("Error recuperando campaign script para callback %s", cb_id)

        # Metadata para que el agente sepa que es un callback
        meta_dict = {
            "type": "callback",
            "callback_id": cb_id,
            "client_id": client_id,
            "agent_id": agent_id,
            "callback_context": context[:500] if context else "",
            "origin_type": origin_type or "inbound",
        }
        if campaign_script:
            meta_dict["campaign_script"] = campaign_script
            meta_dict["campaign_id"] = callback_campaign_id
        room_metadata = json.dumps(meta_dict)

        # Crear room con agent dispatch
        await lk_api.room.create_room(CreateRoomRequest(
            name=room_name,
            metadata=room_metadata,
            empty_timeout=60,
            agents=[
                RoomAgentDispatch(
                    agent_name="voice-ai-platform",
                    metadata=room_metadata,
                )
            ],
        ))

        # Crear participante SIP (llamada outbound)
        await lk_api.sip.create_sip_participant(CreateSIPParticipantRequest(
            sip_trunk_id=trunk_id,
            sip_call_to=phone,
            sip_number=from_number,
            room_name=room_name,
            participant_identity=f"callback-{cb_id[:8]}",
            participant_name=f"Callback to {phone}",
            participant_metadata=json.dumps({
                "type": "callback",
                "callback_id": cb_id,
            }),
        ))

        logger.info(
            "Callback ejecutado: %s -> %s (room: %s)",
            from_number, phone, room_name,
        )

        # Marcar como completado (el resultado real se actualiza cuando la llamada termine)
        sb.table("scheduled_callbacks").update({
            "status": "completed",
        }).eq("id", cb_id).execute()

    except Exception as e:
        logger.error("Error en callback %s: %s", cb_id, e)

        if attempts >= max_attempts:
            sb.table("scheduled_callbacks").update({
                "status": "failed",
                "failure_reason": str(e)[:500],
            }).eq("id", cb_id).execute()
        else:
            # Reintentar en 10 minutos
            retry_at = datetime.now(timezone.utc) + timedelta(minutes=10)
            sb.table("scheduled_callbacks").update({
                "status": "pending",
                "scheduled_at": retry_at.isoformat(),
                "failure_reason": f"Intento {attempts}/{max_attempts}: {str(e)[:300]}",
            }).eq("id", cb_id).execute()
            logger.info("Callback %s re-programado para %s", cb_id, retry_at)

        raise
    finally:
        if lk_api:
            await lk_api.aclose()
