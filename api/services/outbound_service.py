"""Servicio de llamadas outbound — motor de campañas."""

from __future__ import annotations

import asyncio
import logging
import os

from livekit.api import LiveKitAPI
from livekit.api.sip_service import CreateSIPParticipantRequest

from api.deps import get_supabase

logger = logging.getLogger(__name__)


async def start_campaign(campaign_id: str) -> dict:
    """Inicia una campaña: actualiza status y lanza el runner en background."""
    sb = get_supabase()

    campaign = sb.table("campaigns").select("*").eq("id", campaign_id).limit(1).execute()
    if not campaign.data:
        raise ValueError("Campaña no encontrada")

    camp = campaign.data[0]
    if camp["status"] not in ("draft", "scheduled", "paused"):
        raise ValueError(f"No se puede iniciar una campaña con status '{camp['status']}'")

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

            # Obtener trunk del cliente
            client = sb.table("clients").select("phone_number, livekit_sip_trunk_id").eq("id", client_id).limit(1).execute()
            if not client.data or not client.data[0].get("livekit_sip_trunk_id"):
                raise ValueError("Cliente sin SIP trunk configurado")

            trunk_id = client.data[0]["livekit_sip_trunk_id"]
            from_number = client.data[0].get("phone_number", "")

            room_name = f"campaign-{campaign_id[:8]}-{call_entry_id[:8]}"

            # Crear participante SIP (llamada outbound)
            request = CreateSIPParticipantRequest(
                sip_trunk_id=trunk_id,
                sip_call_to=phone,
                room_name=room_name,
                participant_identity=f"outbound-{call_entry_id[:8]}",
                participant_name=f"Outbound to {phone}",
                participant_metadata='{"type": "outbound", "campaign_id": "' + campaign_id + '"}',
            )
            await lk_api.sip.create_sip_participant(request)

            logger.info("Llamada outbound colocada: %s → %s (room: %s)", from_number, phone, room_name)

            # Marcar como completed (el SessionHandler guardará los detalles de la llamada)
            sb.table("campaign_calls").update({
                "status": "completed",
            }).eq("id", call_entry_id).execute()

            # Actualizar contadores
            _increment_campaign_counter(sb, campaign_id, "completed_contacts")
            _increment_campaign_counter(sb, campaign_id, "successful_contacts")

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
