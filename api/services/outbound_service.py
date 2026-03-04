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

    # Si viene de paused, resetear contactos "calling" que se quedaron colgados
    if camp["status"] == "paused":
        sb.table("campaign_calls").update({
            "status": "pending",
        }).eq("campaign_id", campaign_id).eq("status", "calling").execute()

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
        "analysis_data": None,
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

        # Verificar si hay llamadas activas (calling)
        active = (
            sb.table("campaign_calls")
            .select("id", count="exact")
            .eq("campaign_id", campaign_id)
            .eq("status", "calling")
            .execute()
        )
        active_count = active.count or 0

        # Obtener siguiente batch de llamadas pendientes
        slots_available = max(max_concurrent - active_count, 0)
        pending = (
            sb.table("campaign_calls")
            .select("*")
            .eq("campaign_id", campaign_id)
            .in_("status", ["pending", "retry"])
            .order("created_at")
            .limit(slots_available if slots_available > 0 else 1)
            .execute()
        )

        if not pending.data and active_count == 0:
            logger.info("Campaña %s completada: no quedan llamadas pendientes ni activas", campaign_id)
            _complete_campaign(sb, campaign_id)
            break

        if not pending.data:
            # Hay llamadas activas pero no pendientes, esperar
            logger.info("Campaña %s: %d llamadas activas, esperando...", campaign_id, active_count)
            await asyncio.sleep(5)
            continue

        # Lanzar llamadas concurrentes
        tasks = []
        for call_entry in pending.data:
            if slots_available <= 0:
                break
            tasks.append(_place_outbound_call(sb, campaign_id, call_entry, semaphore))
            slots_available -= 1

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # Pausa entre batches
        await asyncio.sleep(5)


async def _validate_trunk_exists(lk: LiveKitAPI, trunk_id: str) -> bool:
    """Verifica que un SIP trunk exista en LiveKit Cloud."""
    try:
        from livekit.api.sip_service import ListSIPOutboundTrunkRequest
        result = await lk.sip.list_outbound_trunk(
            ListSIPOutboundTrunkRequest()
        )
        return any(t.sip_trunk_id == trunk_id for t in result.items)
    except Exception:
        # Si no podemos verificar, asumimos que existe para no bloquear
        return True


async def _resolve_sip_trunk(
    sb, lk: LiveKitAPI, agent_id: str | None, client_id: str
) -> tuple[str, str]:
    """Resuelve el trunk_id y from_number con validación y fallback.

    1. Intenta con el trunk del agente
    2. Si no existe o es inválido, usa el trunk del cliente
    3. Si ninguno funciona, lanza error claro
    """
    agent_trunk_id = None
    agent_phone = ""
    client_trunk_id = None
    client_phone = ""

    # Leer trunk del agente
    if agent_id:
        agent_row = (
            sb.table("agents")
            .select("phone_number, livekit_sip_trunk_id")
            .eq("id", agent_id)
            .limit(1)
            .execute()
        )
        if agent_row.data and agent_row.data[0].get("livekit_sip_trunk_id"):
            agent_trunk_id = agent_row.data[0]["livekit_sip_trunk_id"]
            agent_phone = agent_row.data[0].get("phone_number", "")

    # Leer trunk del cliente (siempre, como fallback)
    client_row = (
        sb.table("clients")
        .select("phone_number, livekit_sip_trunk_id")
        .eq("id", client_id)
        .limit(1)
        .execute()
    )
    if client_row.data and client_row.data[0].get("livekit_sip_trunk_id"):
        client_trunk_id = client_row.data[0]["livekit_sip_trunk_id"]
        client_phone = client_row.data[0].get("phone_number", "")

    # Validar trunk del agente
    if agent_trunk_id:
        if await _validate_trunk_exists(lk, agent_trunk_id):
            return agent_trunk_id, agent_phone
        logger.warning(
            "Trunk del agente '%s' no existe en LiveKit, usando fallback del cliente",
            agent_trunk_id,
        )

    # Fallback: trunk del cliente
    if client_trunk_id:
        if await _validate_trunk_exists(lk, client_trunk_id):
            return client_trunk_id, client_phone
        logger.error(
            "Trunk del cliente '%s' tampoco existe en LiveKit", client_trunk_id
        )

    raise ValueError(
        "No hay SIP trunk válido configurado. "
        "Verifica la configuración del agente y cliente en el dashboard."
    )


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

            # Obtener la campaña para el script y agent_id
            camp = sb.table("campaigns").select("client_id, agent_id, script").eq("id", campaign_id).limit(1).execute()
            if not camp.data:
                raise ValueError("Campaña no encontrada")

            client_id = camp.data[0]["client_id"]
            agent_id = camp.data[0].get("agent_id")
            script = camp.data[0]["script"]

            # Resolver trunk_id y from_number con fallback
            trunk_id, from_number = await _resolve_sip_trunk(
                sb, lk_api, agent_id, client_id
            )

            room_name = f"campaign-{campaign_id[:8]}-{call_entry_id[:8]}"

            # Metadata de la room para que el agente sepa que es outbound
            room_metadata = json.dumps({
                "type": "outbound",
                "campaign_id": campaign_id,
                "client_id": client_id,
                "agent_id": agent_id,
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
                sip_number=from_number,
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

            # NO marcar como completed aquí — el agent session_handler lo hará
            # cuando la llamada realmente termine. Solo cerramos el API client.
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


def _update_campaign_counters(sb, campaign_id: str) -> None:
    """Recalcula contadores de la campaña basándose en los status reales."""
    completed = (
        sb.table("campaign_calls")
        .select("id", count="exact")
        .eq("campaign_id", campaign_id)
        .in_("status", ["completed", "failed", "no_answer", "busy"])
        .execute()
    )
    successful = (
        sb.table("campaign_calls")
        .select("id", count="exact")
        .eq("campaign_id", campaign_id)
        .eq("status", "completed")
        .execute()
    )
    sb.table("campaigns").update({
        "completed_contacts": completed.count or 0,
        "successful_contacts": successful.count or 0,
    }).eq("id", campaign_id).execute()


def _complete_campaign(sb, campaign_id: str) -> None:
    """Marca una campaña como completada con contadores finales."""
    from datetime import datetime, timezone
    _update_campaign_counters(sb, campaign_id)
    sb.table("campaigns").update({
        "status": "completed",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", campaign_id).execute()
    logger.info("Campaña %s completada", campaign_id)
