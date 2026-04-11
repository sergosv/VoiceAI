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


MAX_CONCURRENT_CALLBACKS = 5
_callback_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _callback_semaphore
    if _callback_semaphore is None:
        _callback_semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALLBACKS)
    return _callback_semaphore


async def process_pending_callbacks() -> dict:
    """Busca callbacks pendientes cuya hora ya llegó y los ejecuta.

    Máximo MAX_CONCURRENT_CALLBACKS ejecuciones en paralelo.
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

    sem = _get_semaphore()
    stats = {"processed": 0, "succeeded": 0, "failed": 0}

    async def _run_with_sem(cb):
        async with sem:
            try:
                await _execute_callback(sb, cb)
                return True
            except Exception:
                logger.exception("Error ejecutando callback %s", cb["id"])
                return False

    results = await asyncio.gather(
        *(_run_with_sem(cb) for cb in result.data),
        return_exceptions=True,
    )
    for r in results:
        stats["processed"] += 1
        if r is True:
            stats["succeeded"] += 1
        else:
            stats["failed"] += 1

    return stats


async def _execute_callback(sb, cb: dict) -> None:
    """Ejecuta un callback individual: crea room + SIP participant."""
    cb_id = cb["id"]
    phone = cb["phone"]
    agent_id = cb["agent_id"]
    client_id = cb["client_id"]
    # Descifrar context (puede estar encriptado con Fernet)
    raw_context = cb.get("context", "") or ""
    try:
        from agent.config_loader import _decrypt_key
        context = _decrypt_key(raw_context) or raw_context
    except Exception:
        context = raw_context
    attempts = cb.get("attempts", 0) + 1
    max_attempts = cb.get("max_attempts", 3)

    from agent.phone_utils import normalize_phone as _np
    _normalized = _np(phone)

    # DNC check: si el número fue agregado a la lista entre el momento de programar
    # y el de ejecutar, NO llamar
    try:
        dnc = sb.table("dnc_entries").select("id").eq(
            "client_id", client_id
        ).eq("phone", _normalized).limit(1).execute()
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

    # Transición atómica pending → in_progress. Si otra instancia del worker
    # ya lo tomó, el UPDATE retorna 0 filas y abortamos.
    claim = sb.table("scheduled_callbacks").update({
        "status": "in_progress",
        "attempts": attempts,
        "last_attempt_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", cb_id).eq("status", "pending").execute()

    if not claim.data:
        logger.info("Callback %s ya tomado por otro worker, saltando", cb_id)
        return

    # Active call check: no llamar si ya hay una llamada activa con ese número
    try:
        active = sb.table("active_calls").select("id").eq(
            "client_id", client_id
        ).execute()
        if active.data:
            # Verificar si alguna de las llamadas activas es con este phone
            call_ids = [a["id"] for a in active.data]
            # El active_calls no tiene phone directo, revisar por room_name/metadata
            # Aproximación: postponer 5 min si hay cualquier llamada activa con este client
            active_calls = sb.table("calls").select("id, caller_number, callee_number").in_(
                "livekit_room_name", [a.get("room_name", "") for a in active.data if a.get("room_name")]
            ).execute()
            for ac in active_calls.data or []:
                if ac.get("caller_number") == _normalized or ac.get("callee_number") == _normalized:
                    logger.warning(
                        "Callback %s postponed: número %s tiene llamada activa",
                        cb_id, phone,
                    )
                    # Re-schedule en 5 minutos
                    retry_at = datetime.now(timezone.utc) + timedelta(minutes=5)
                    sb.table("scheduled_callbacks").update({
                        "scheduled_at": retry_at.isoformat(),
                    }).eq("id", cb_id).execute()
                    return
    except Exception:
        logger.exception("Error verificando active_calls para callback %s", cb_id)

    # (status ya se actualizó atómicamente arriba vía claim)

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
            # Notificar al owner del cliente
            try:
                client = sb.table("clients").select("owner_email, name").eq(
                    "id", client_id
                ).limit(1).execute()
                if client.data and client.data[0].get("owner_email"):
                    from api.services.email_service import send_email
                    owner_email = client.data[0]["owner_email"]
                    client_name = client.data[0].get("name", "")
                    await send_email(
                        to=owner_email,
                        subject=f"Callback fallido: {phone}",
                        html=(
                            f"<p>Hola,</p>"
                            f"<p>El callback programado para <strong>{phone}</strong> falló "
                            f"después de {attempts} intentos.</p>"
                            f"<p><strong>Razón:</strong> {str(e)[:300]}</p>"
                            f"<p>Cliente: {client_name}</p>"
                            f"<p>Puedes revisar los detalles en el dashboard de callbacks.</p>"
                        ),
                    )
                    logger.info("Alerta enviada a %s por callback fallido", owner_email)
            except Exception:
                logger.exception("Error enviando alerta de callback fallido")
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
