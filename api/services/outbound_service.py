"""Servicio de llamadas outbound — motor de campañas con controles anti-abuso."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone

from livekit.api import LiveKitAPI
from livekit.api.sip_service import CreateSIPParticipantRequest
from livekit.protocol.agent_dispatch import RoomAgentDispatch
from livekit.protocol.room import CreateRoomRequest

from api.deps import get_supabase

logger = logging.getLogger(__name__)

# ── Outbound safety limits ─────────────────────────────────────────
# Configurables via env vars para ajustar sin redeploy
DAILY_OUTBOUND_LIMIT = int(os.environ.get("OUTBOUND_DAILY_LIMIT", "200"))
MIN_ANSWER_RATE = float(os.environ.get("OUTBOUND_MIN_ANSWER_RATE", "0.20"))
MIN_CALLS_FOR_RATE_CHECK = int(os.environ.get("OUTBOUND_MIN_CALLS_RATE_CHECK", "15"))
MIN_AVG_DURATION_SECONDS = int(os.environ.get("OUTBOUND_MIN_AVG_DURATION", "10"))
# Timeout para llamadas stuck en "calling" (minutos)
# Debe ser mayor que la duración máxima esperada de una llamada (15min por defecto)
CALLING_TIMEOUT_MINUTES = int(os.environ.get("OUTBOUND_CALLING_TIMEOUT_MINUTES", "15"))

# Mantener referencias a tasks de campañas para evitar GC prematuro
_running_campaigns: set[asyncio.Task] = set()


def _check_daily_outbound_limit(sb, client_id: str) -> None:
    """Verifica que el cliente no exceda el límite diario de llamadas outbound."""
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()

    result = (
        sb.table("calls")
        .select("id", count="exact")
        .eq("client_id", client_id)
        .eq("direction", "outbound")
        .gte("started_at", today_start)
        .execute()
    )
    count = result.count or 0
    if count >= DAILY_OUTBOUND_LIMIT:
        raise ValueError(
            f"Límite diario de llamadas outbound alcanzado ({count}/{DAILY_OUTBOUND_LIMIT}). "
            f"Intenta mañana o contacta al administrador."
        )


def _check_campaign_health(sb, campaign_id: str) -> str | None:
    """Analiza la salud de una campaña en curso. Retorna razón de pausa o None si OK."""
    calls = (
        sb.table("campaign_calls")
        .select("status, result_summary")
        .eq("campaign_id", campaign_id)
        .in_("status", ["completed", "failed", "no_answer", "busy"])
        .execute()
    )
    finished = calls.data or []
    total = len(finished)

    if total < MIN_CALLS_FOR_RATE_CHECK:
        return None  # Muy pocas llamadas para evaluar

    # 1. Tasa de contestación — si nadie contesta, parece spam
    answered = sum(1 for c in finished if c["status"] == "completed")
    answer_rate = answered / total if total > 0 else 0

    if answer_rate < MIN_ANSWER_RATE:
        return (
            f"Tasa de contestación muy baja ({answer_rate:.0%}, mínimo {MIN_ANSWER_RATE:.0%}). "
            f"Solo {answered} de {total} llamadas fueron contestadas. "
            f"Verifica que los contactos sean válidos."
        )

    # 2. Alta tasa de no_answer + busy — base de contactos de mala calidad
    no_answer = sum(1 for c in finished if c["status"] in ("no_answer", "busy"))
    no_answer_rate = no_answer / total if total > 0 else 0
    if no_answer_rate > 0.70:
        return (
            f"Demasiadas llamadas sin respuesta ({no_answer_rate:.0%}). "
            f"{no_answer} de {total} llamadas no fueron contestadas o estaban ocupadas."
        )

    return None


def _cleanup_stale_calls(sb, campaign_id: str) -> int:
    """Marca como failed las llamadas stuck en 'calling' por más de CALLING_TIMEOUT_MINUTES.

    Retorna cantidad de llamadas limpiadas.
    """
    cutoff = (
        datetime.now(timezone.utc) - timedelta(minutes=CALLING_TIMEOUT_MINUTES)
    ).isoformat()

    # Buscar llamadas en "calling" cuyo último update fue antes del cutoff
    stale = (
        sb.table("campaign_calls")
        .select("id")
        .eq("campaign_id", campaign_id)
        .eq("status", "calling")
        .lt("updated_at", cutoff)
        .execute()
    )
    if not stale.data:
        return 0

    stale_ids = [row["id"] for row in stale.data]
    for sid in stale_ids:
        sb.table("campaign_calls").update({
            "status": "failed",
            "result_summary": f"Error técnico: la llamada no se procesó correctamente (sin respuesta del agente en {CALLING_TIMEOUT_MINUTES}min)",
        }).eq("id", sid).execute()

    logger.warning(
        "Campaign %s: %d llamadas stuck en 'calling' marcadas como failed",
        campaign_id, len(stale_ids),
    )
    _update_campaign_counters(sb, campaign_id)
    return len(stale_ids)


async def start_campaign(campaign_id: str) -> dict:
    """Inicia una campaña: actualiza status y lanza el runner en background."""
    sb = get_supabase()

    campaign = sb.table("campaigns").select("*").eq("id", campaign_id).limit(1).execute()
    if not campaign.data:
        raise ValueError("Campaña no encontrada")

    camp = campaign.data[0]
    if camp["status"] == "running":
        raise ValueError("La campaña ya está en ejecución")

    # No reset "calling" to "pending" — in-flight calls will complete on their own
    # and update to "completed"/"failed" naturally.

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

    client_id = camp["client_id"]

    # Verificar límite diario de outbound (protección anti-abuso)
    _check_daily_outbound_limit(sb, client_id)

    # Verificar créditos suficientes (estimado: 2 min por contacto)
    balance = sb.table("credit_balances").select("balance").eq("client_id", client_id).limit(1).execute()
    current_balance = float((balance.data[0]["balance"]) if balance.data else 0)
    estimated_cost = (pending.count or 0) * 2  # 2 créditos por contacto estimado
    if current_balance < min(estimated_cost, 5):
        raise ValueError(
            f"Créditos insuficientes ({current_balance:.0f}) para campaña "
            f"de {pending.count} contactos (estimado: {estimated_cost})"
        )

    # Actualizar status atómicamente (solo si está en draft/paused/completed)
    result = (
        sb.table("campaigns")
        .update({"status": "running"})
        .eq("id", campaign_id)
        .in_("status", ["draft", "paused", "completed"])
        .execute()
    )
    if not result.data:
        raise ValueError("La campaña ya está en ejecución o no se puede iniciar")

    # Lanzar runner async con referencia para evitar GC
    task = asyncio.create_task(_campaign_runner(campaign_id, camp["max_concurrent"]))
    _running_campaigns.add(task)
    task.add_done_callback(_running_campaigns.discard)

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

    # Si está running, primero pausarla para detener el runner
    if camp["status"] == "running":
        sb.table("campaigns").update({"status": "paused"}).eq("id", campaign_id).execute()
        logger.info("Campaña %s pausada antes de reiniciar", campaign_id)

    # Resetear campaign_calls fallidos/completados/calling a pending
    sb.table("campaign_calls").update({
        "status": "pending",
        "attempt": 0,
        "result_summary": None,
        "analysis_data": None,
        "next_retry_at": None,
    }).eq("campaign_id", campaign_id).in_(
        "status", ["completed", "failed", "no_answer", "busy", "calling"]
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
    current_max = max_concurrent

    while True:
        # Verificar que la campaña sigue running + leer max_concurrent dinámico
        camp = (
            sb.table("campaigns")
            .select("status, max_concurrent")
            .eq("id", campaign_id)
            .limit(1)
            .execute()
        )
        # Limpiar llamadas stuck en "calling" que excedieron el timeout
        _cleanup_stale_calls(sb, campaign_id)

        if not camp.data or camp.data[0]["status"] != "running":
            logger.info("Campaña %s ya no está running, deteniendo", campaign_id)
            break

        # Health check: verificar tasa de contestación cada iteración
        pause_reason = _check_campaign_health(sb, campaign_id)
        if pause_reason:
            logger.warning(
                "Campaign %s auto-paused: %s", campaign_id, pause_reason
            )
            sb.table("campaigns").update({
                "status": "paused",
            }).eq("id", campaign_id).execute()
            # Intentar notificar por email
            try:
                from api.services.email_service import send_email
                # Obtener email del admin/owner del cliente
                camp_full = (
                    sb.table("campaigns")
                    .select("client_id")
                    .eq("id", campaign_id)
                    .limit(1)
                    .execute()
                )
                if camp_full.data:
                    cid = camp_full.data[0]["client_id"]
                    client_row = (
                        sb.table("clients")
                        .select("owner_email, name")
                        .eq("id", cid)
                        .limit(1)
                        .execute()
                    )
                    owner_email = (client_row.data[0].get("owner_email") if client_row.data else None)
                    admin_email = os.environ.get("ADMIN_ALERT_EMAIL")
                    to_email = owner_email or admin_email
                    if to_email:
                        import asyncio as _aio
                        _aio.create_task(send_email(
                            to=to_email,
                            subject=f"Campaña pausada automáticamente",
                            html=f"<p>La campaña fue pausada por controles de seguridad:</p>"
                                 f"<p><strong>{pause_reason}</strong></p>"
                                 f"<p>Revisa los contactos y reanuda desde el dashboard.</p>",
                        ))
            except Exception:
                pass  # No bloquear el flujo por fallo de email
            break

        # Actualizar max_concurrent si cambió en DB
        new_max = camp.data[0].get("max_concurrent", current_max)
        if new_max != current_max:
            logger.info(
                "Campaign %s: max_concurrent cambiado %d → %d",
                campaign_id, current_max, new_max,
            )
            # Recrear semáforo con nuevo límite
            semaphore = asyncio.Semaphore(new_max)
            current_max = new_max

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
        slots_available = max(current_max - active_count, 0)

        if slots_available <= 0:
            await asyncio.sleep(5)
            continue

        now_iso = datetime.now(timezone.utc).isoformat()

        # Fetch pending calls OR retry calls whose retry time has passed
        pending = (
            sb.table("campaign_calls")
            .select("*")
            .eq("campaign_id", campaign_id)
            .or_(f"status.eq.pending,and(status.eq.retry,next_retry_at.lte.{now_iso})")
            .order("created_at")
            .limit(slots_available)
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

    # Validar trunk del agente (fuente de verdad para routing)
    if agent_trunk_id:
        if await _validate_trunk_exists(lk, agent_trunk_id):
            if client_phone and agent_phone and client_phone != agent_phone:
                logger.info(
                    "Agent phone (%s) differs from client phone (%s) — using agent phone",
                    agent_phone, client_phone,
                )
            return agent_trunk_id, agent_phone
        logger.warning(
            "Trunk del agente '%s' no existe en LiveKit, usando fallback del cliente",
            agent_trunk_id,
        )

    # Fallback: trunk del cliente (legacy, solo si agente no tiene trunk propio)
    if client_trunk_id:
        logger.info(
            "Agent %s sin trunk propio, usando trunk del cliente como fallback",
            agent_id or "N/A",
        )
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

        lk_api: LiveKitAPI | None = None
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

        except Exception as e:
            logger.error("Error en llamada outbound %s: %s", call_entry_id, e)

            # Verificar si puede reintentar
            camp_data = sb.table("campaigns").select("retry_attempts, retry_delay_minutes").eq("id", campaign_id).limit(1).execute()
            max_retries = camp_data.data[0]["retry_attempts"] if camp_data.data else 2
            current_attempt = call_entry.get("attempt", 0) + 1

            # Mensaje de error legible
            err_str = str(e)
            if "trunk" in err_str.lower():
                friendly_error = f"Error de telefonía: no se pudo conectar con el trunk SIP ({err_str[:200]})"
            elif "room" in err_str.lower():
                friendly_error = f"Error creando sala de llamada ({err_str[:200]})"
            elif "credit" in err_str.lower() or "balance" in err_str.lower():
                friendly_error = f"Créditos insuficientes para realizar la llamada"
            else:
                friendly_error = f"Error al iniciar llamada: {err_str[:300]}"

            if current_attempt < max_retries:
                delay = camp_data.data[0]["retry_delay_minutes"] if camp_data.data else 30
                next_retry = datetime.now(timezone.utc) + timedelta(minutes=delay)
                sb.table("campaign_calls").update({
                    "status": "retry",
                    "next_retry_at": next_retry.isoformat(),
                    "result_summary": f"Reintentando ({current_attempt}/{max_retries}): {friendly_error}",
                }).eq("id", call_entry_id).execute()
            else:
                sb.table("campaign_calls").update({
                    "status": "failed",
                    "result_summary": f"Falló después de {current_attempt} intentos: {friendly_error}",
                }).eq("id", call_entry_id).execute()
        finally:
            if lk_api is not None:
                await lk_api.aclose()


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
    _update_campaign_counters(sb, campaign_id)
    sb.table("campaigns").update({
        "status": "completed",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", campaign_id).execute()
    logger.info("Campaña %s completada", campaign_id)
