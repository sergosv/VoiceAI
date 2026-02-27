"""Servicio de llamadas outbound — motor de campañas."""

from __future__ import annotations

import asyncio
import json
import logging
import os

from livekit.api import LiveKitAPI
from livekit.api.sip_service import CreateSIPParticipantRequest
from livekit.protocol.agent_dispatch import RoomAgentDispatch
from livekit.protocol.room import CreateRoomRequest

from api.deps import get_supabase

logger = logging.getLogger(__name__)


async def start_campaign(campaign_id: str) -> dict:
    """Inicia una campaña: actualiza status y lanza el runner en background."""
    sb = get_supabase()

    campaign = sb.table("campaigns").select("*").eq("id", campaign_id).limit(1).execute()
    if not campaign.data:
        raise ValueError("Campaña no encontrada")

    camp = campaign.data[0]
    if camp["status"] == "running":
        raise ValueError("La campaña ya está en ejecución")

    # Contar contactos pendientes
    pending = (
        sb.table("campaign_calls")
        .select("id", count="exact")
        .eq("campaign_id", campaign_id)
        .in_("status", ["pending", "retry"])
        .execute()
    )
    if not pending.count:
        raise ValueError("No hay contactos pendientes en esta campaña")

    # Actualizar status
    result = (
        sb.table("campaigns")
        .update({"status": "running"})
        .eq("id", campaign_id)
        .execute()
    )

    # Lanzar runner async
    asyncio.create_task(_campaign_runner(campaign_id, camp["max_concurrent"]))

    return result.data[0] if result.data else camp


async def pause_campaign(campaign_id: str) -> dict:
    """Pausa una campaña en ejecución."""
    sb = get_supabase()
    result = (
        sb.table("campaigns")
        .update({"status": "paused"})
        .eq("id", campaign_id)
        .eq("status", "running")
        .execute()
    )
    if not result.data:
        raise ValueError("Campaña no encontrada o no está en ejecución")
    return result.data[0]


async def restart_campaign(campaign_id: str) -> dict:
    """Resetea una campaña completada/fallida para poder relanzarla."""
    sb = get_supabase()

    campaign = sb.table("campaigns").select("*").eq("id", campaign_id).limit(1).execute()
    if not campaign.data:
        raise ValueError("Campaña no encontrada")

    camp = campaign.data[0]
    if camp["status"] == "running":
        raise ValueError("No se puede reiniciar una campaña en ejecución")

    # Resetear campaign_calls fallidos/completados a pending
    sb.table("campaign_calls").update({
        "status": "pending",
        "attempt": 0,
        "result_summary": None,
        "next_retry_at": None,
    }).eq("campaign_id", campaign_id).in_(
        "status", ["completed", "failed", "no_answer", "busy"]
    ).execute()

    # Resetear contadores de la campaña
    total = (
        sb.table("campaign_calls")
        .select("id", count="exact")
        .eq("campaign_id", campaign_id)
        .execute()
    )
    result = sb.table("campaigns").update({
        "status": "draft",
        "completed_contacts": 0,
        "successful_contacts": 0,
        "completed_at": None,
        "total_contacts": total.count or 0,
    }).eq("id", campaign_id).execute()

    if not result.data:
        raise ValueError("Error reiniciando campaña")

    logger.info("Campaña %s reiniciada", campaign_id)
    return result.data[0]


async def _campaign_runner(campaign_id: str, max_concurrent: int) -> None:
    """Procesa las llamadas pendientes de una campaña."""
    sb = get_supabase()
    logger.info("Campaign runner iniciado: %s (max_concurrent=%d)", campaign_id, max_concurrent)

    semaphore = asyncio.Semaphore(max_concurrent)

    while True:
        # Verificar que la campaña sigue running
        camp = sb.table("campaigns").select("status").eq("id", campaign_id).limit(1).execute()
        if not camp.data or camp.data[0]["status"] != "running":
            logger.info("Campaña %s ya no está running, deteniendo", campaign_id)
            break

        # Obtener siguiente batch de llamadas pendientes
        pending = (
            sb.table("campaign_calls")
            .select("*")
            .eq("campaign_id", campaign_id)
            .in_("status", ["pending", "retry"])
            .order("created_at")
            .limit(max_concurrent)
            .execute()
        )

        if not pending.data:
            logger.info("Campaña %s completada: no quedan llamadas pendientes", campaign_id)
            _complete_campaign(sb, campaign_id)
            break

        # Lanzar llamadas concurrentes
        tasks = []
        for call_entry in pending.data:
            tasks.append(_place_outbound_call(sb, campaign_id, call_entry, semaphore))

        await asyncio.gather(*tasks, return_exceptions=True)

        # Pausa entre batches
        await asyncio.sleep(2)


async def _place_outbound_call(
    sb,
    campaign_id: str,
    call_entry: dict,
    semaphore: asyncio.Semaphore,
) -> None:
    """Coloca una llamada outbound individual vía LiveKit SIP."""
    async with semaphore:
        call_entry_id = call_entry["id"]
        phone = call_entry["phone"]

        # Marcar como calling
        sb.table("campaign_calls").update({
            "status": "calling",
            "attempt": call_entry.get("attempt", 0) + 1,
        }).eq("id", call_entry_id).execute()

        try:
            lk_api = LiveKitAPI(
                url=os.environ["LIVEKIT_URL"],
                api_key=os.environ["LIVEKIT_API_KEY"],
                api_secret=os.environ["LIVEKIT_API_SECRET"],
            )

            # Obtener la campaña para el script
            camp = sb.table("campaigns").select("client_id, script").eq("id", campaign_id).limit(1).execute()
            if not camp.data:
                raise ValueError("Campaña no encontrada")

            client_id = camp.data[0]["client_id"]
            script = camp.data[0]["script"]

            # Obtener trunk del cliente
            client = sb.table("clients").select("phone_number, livekit_sip_trunk_id").eq("id", client_id).limit(1).execute()
            if not client.data or not client.data[0].get("livekit_sip_trunk_id"):
                raise ValueError("Cliente sin SIP trunk configurado")

            trunk_id = client.data[0]["livekit_sip_trunk_id"]
            from_number = client.data[0].get("phone_number", "")

            room_name = f"campaign-{campaign_id[:8]}-{call_entry_id[:8]}"

            # Metadata de la room para que el agente sepa que es outbound
            room_metadata = json.dumps({
                "type": "outbound",
                "campaign_id": campaign_id,
                "client_id": client_id,
                "script": script,
            })

            # 1. Crear room con agent dispatch para que el agente se conecte
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
            await lk_api.room.create_room(create_room_req)
            logger.info("Room creada con agent dispatch: %s", room_name)

            # 2. Crear participante SIP (llamada outbound)
            request = CreateSIPParticipantRequest(
                sip_trunk_id=trunk_id,
                sip_call_to=phone,
                room_name=room_name,
                participant_identity=f"outbound-{call_entry_id[:8]}",
                participant_name=f"Outbound to {phone}",
                participant_metadata=json.dumps({
                    "type": "outbound",
                    "campaign_id": campaign_id,
                }),
            )
            await lk_api.sip.create_sip_participant(request)

            logger.info("Llamada outbound colocada: %s -> %s (room: %s)", from_number, phone, room_name)

            # Marcar como completed (el SessionHandler guardará los detalles)
            sb.table("campaign_calls").update({
                "status": "completed",
            }).eq("id", call_entry_id).execute()

            # Actualizar contadores
            _increment_campaign_counter(sb, campaign_id, "completed_contacts")
            _increment_campaign_counter(sb, campaign_id, "successful_contacts")

            await lk_api.aclose()

        except Exception as e:
            logger.error("Error en llamada outbound %s: %s", call_entry_id, e)

            # Verificar si puede reintentar
            camp_data = sb.table("campaigns").select("retry_attempts, retry_delay_minutes").eq("id", campaign_id).limit(1).execute()
            max_retries = camp_data.data[0]["retry_attempts"] if camp_data.data else 2
            current_attempt = call_entry.get("attempt", 0) + 1

            if current_attempt < max_retries:
                from datetime import datetime, timedelta, timezone
                delay = camp_data.data[0]["retry_delay_minutes"] if camp_data.data else 30
                next_retry = datetime.now(timezone.utc) + timedelta(minutes=delay)
                sb.table("campaign_calls").update({
                    "status": "retry",
                    "next_retry_at": next_retry.isoformat(),
                    "result_summary": str(e)[:500],
                }).eq("id", call_entry_id).execute()
            else:
                sb.table("campaign_calls").update({
                    "status": "failed",
                    "result_summary": str(e)[:500],
                }).eq("id", call_entry_id).execute()
                _increment_campaign_counter(sb, campaign_id, "completed_contacts")


def _increment_campaign_counter(sb, campaign_id: str, field: str) -> None:
    """Incrementa un contador en la campaña."""
    camp = sb.table("campaigns").select(field).eq("id", campaign_id).limit(1).execute()
    if camp.data:
        current = camp.data[0].get(field, 0)
        sb.table("campaigns").update({field: current + 1}).eq("id", campaign_id).execute()


def _complete_campaign(sb, campaign_id: str) -> None:
    """Marca una campaña como completada."""
    from datetime import datetime, timezone
    sb.table("campaigns").update({
        "status": "completed",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", campaign_id).execute()
    logger.info("Campaña %s completada", campaign_id)
