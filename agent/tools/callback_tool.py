"""Herramienta para programar callbacks (devolución de llamada) desde el agente de voz."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo
except ImportError:
    try:
        from backports.zoneinfo import ZoneInfo
    except ImportError:
        ZoneInfo = None  # type: ignore[assignment,misc]

from supabase import Client

from agent.db import get_supabase


def _get_supabase() -> Client:
    return get_supabase()


def _resolve_tz(tz_name: str | None) -> datetime.tzinfo:
    """Resuelve timezone por nombre IANA, con fallback a America/Mexico_City."""
    target = tz_name or "America/Mexico_City"
    if ZoneInfo:
        try:
            return ZoneInfo(target)
        except KeyError:
            return ZoneInfo("America/Mexico_City")
    return timezone(timedelta(hours=-6))


_DAY_MAP = {
    0: ("lun", "lun-vie"),
    1: ("mar", "lun-vie"),
    2: ("mie", "lun-vie"),
    3: ("jue", "lun-vie"),
    4: ("vie", "lun-vie"),
    5: ("sab", None),
    6: ("dom", None),
}


def _is_in_business_hours(dt: datetime, business_hours: dict) -> bool:
    """Verifica si un datetime cae dentro del horario laboral.

    business_hours format: {"lun-vie": "09:00-18:00", "sab": "09:00-14:00"}
    """
    weekday = dt.weekday()
    day_key, range_key = _DAY_MAP.get(weekday, (None, None))

    # Buscar entry específica del día primero, luego el rango lun-vie
    entry = business_hours.get(day_key) if day_key else None
    if not entry and range_key:
        entry = business_hours.get(range_key)

    if not entry:
        return False  # No configurado = fuera de horario

    try:
        start_str, end_str = entry.split("-")
        start_h, start_m = map(int, start_str.strip().split(":"))
        end_h, end_m = map(int, end_str.strip().split(":"))
        minutes = dt.hour * 60 + dt.minute
        start_minutes = start_h * 60 + start_m
        end_minutes = end_h * 60 + end_m
        return start_minutes <= minutes <= end_minutes
    except (ValueError, AttributeError):
        return True  # Si el formato es inválido, ser permisivo


def _parse_scheduled_time(
    date_str: str,
    time_str: str,
    tz: datetime.tzinfo,
) -> datetime:
    """Parsea fecha + hora y retorna datetime con timezone.

    Soporta formatos:
    - date: YYYY-MM-DD, DD/MM/YYYY
    - time: HH:MM (24h), h:MMam/pm
    """
    # Normalizar fecha
    date_str = date_str.strip()
    if "/" in date_str:
        parts = date_str.split("/")
        if len(parts) == 3:
            if len(parts[2]) == 4:
                date_str = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"

    # Normalizar hora
    time_str = time_str.strip().lower().replace(" ", "")
    if "pm" in time_str or "am" in time_str:
        is_pm = "pm" in time_str
        time_str = time_str.replace("pm", "").replace("am", "")
        h, m = time_str.split(":")
        h = int(h)
        if is_pm and h != 12:
            h += 12
        elif not is_pm and h == 12:
            h = 0
        time_str = f"{h:02d}:{int(m):02d}"

    dt_str = f"{date_str}T{time_str}:00"
    dt_naive = datetime.fromisoformat(dt_str)
    return dt_naive.replace(tzinfo=tz)


# Tracker en memoria para idempotencia dentro de la misma sesión del agente.
# Si el LLM llama el tool 5 veces en 10 segundos (porque Gemini canceló el call
# y reintenta), solo el primer call hace el insert; los demás devuelven el mismo
# resultado inmediatamente sin tocar la DB.
_recent_schedules: dict[str, tuple[float, str]] = {}
_IDEMPOTENCY_WINDOW_S = 30


def _idempotency_key(client_id: str, phone: str, scheduled_at: datetime) -> str:
    """Key que identifica un schedule único por cliente+phone+hora (al minuto)."""
    minute_key = scheduled_at.strftime("%Y%m%d%H%M")
    return f"{client_id}:{phone}:{minute_key}"


async def schedule_callback(
    client_id: str,
    agent_id: str,
    phone: str,
    date: str,
    time: str,
    context: str | None = None,
    origin_call_id: str | None = None,
    client_timezone: str | None = None,
    max_attempts: int = 3,
    origin_type: str | None = None,
    campaign_id: str | None = None,
    business_hours: dict | None = None,
) -> str:
    """Programa un callback (devolución de llamada) para una hora futura.

    Diseñado para responder en <500ms: validaciones síncronas, insert async
    en background, idempotente para evitar duplicados cuando Gemini cancela
    y reintenta el tool.

    Args:
        client_id: ID del cliente.
        agent_id: ID del agente que hará la llamada.
        phone: Número de teléfono a llamar.
        date: Fecha en formato YYYY-MM-DD.
        time: Hora en formato HH:MM (24h).
        context: Resumen de la conversación para dar contexto al agente.
        origin_call_id: ID de la llamada original.
        client_timezone: Timezone IANA del cliente.
        max_attempts: Intentos máximos si no contesta.
        business_hours: Config ya cargada del cliente (evita query extra).

    Returns:
        Mensaje de confirmación o error.
    """
    tz = _resolve_tz(client_timezone)

    try:
        scheduled_at = _parse_scheduled_time(date, time, tz)
    except (ValueError, IndexError) as e:
        logger.warning("Error parseando fecha/hora para callback: %s %s — %s", date, time, e)
        return (
            "No pude interpretar la fecha u hora. "
            "Confirma con el usuario la fecha (día/mes/año) y hora exacta."
        )

    # Validaciones rápidas (sin DB)
    now = datetime.now(tz)
    if scheduled_at < now - timedelta(minutes=5):
        return (
            "La hora indicada ya pasó. "
            "Pregúntale al usuario una hora futura para la llamada."
        )
    if scheduled_at > now + timedelta(days=30):
        return (
            "Solo puedo programar callbacks hasta 30 días en el futuro. "
            "Confirma una fecha más cercana con el usuario."
        )

    # Validar business_hours si vienen en el argumento (sin query extra)
    if business_hours and not _is_in_business_hours(scheduled_at, business_hours):
        return (
            "Esa hora está fuera del horario de atención. "
            "Pregúntale al usuario otra hora dentro del horario laboral."
        )

    # Normalizar teléfono para consistencia con DNC
    try:
        from agent.phone_utils import normalize_phone as _np
        phone = _np(phone)
    except Exception:
        pass

    # ── Idempotencia: si ya programamos este callback recientemente, devolver
    #    el mismo resultado sin tocar DB (evita duplicados cuando Gemini
    #    cancela el tool call y reintenta).
    import time as _time
    now_ts = _time.time()
    # Limpiar entradas viejas del tracker
    expired = [k for k, (ts, _) in _recent_schedules.items() if now_ts - ts > _IDEMPOTENCY_WINDOW_S]
    for k in expired:
        _recent_schedules.pop(k, None)

    key = _idempotency_key(client_id, phone, scheduled_at)
    if key in _recent_schedules:
        _, cached_msg = _recent_schedules[key]
        logger.info("Idempotencia: callback %s ya en flight, retornando cache", key)
        return cached_msg

    # Formatear confirmación antes de marcar idempotencia
    hora_local = scheduled_at.strftime("%I:%M %p").lstrip("0")
    fecha_local = scheduled_at.strftime("%d/%m/%Y")
    confirmation_msg = (
        f"Callback programado exitosamente para el {fecha_local} a las {hora_local}. "
        f"Confirma al usuario que le llamaremos a esa hora al número {phone}."
    )
    _recent_schedules[key] = (now_ts, confirmation_msg)

    # ── Insert en background (no bloquea al LLM) ──
    async def _do_insert() -> None:
        try:
            sb = _get_supabase()

            # Cifrar context at rest (puede contener PII del transcript)
            from agent.config_loader import _encrypt_value
            encrypted_context = _encrypt_value(context) if context else None

            # Cancelar callbacks pendientes anteriores al mismo número
            try:
                await asyncio.to_thread(
                    lambda: sb.table("scheduled_callbacks")
                    .update({
                        "status": "cancelled",
                        "failure_reason": "Reemplazado por nuevo callback",
                    })
                    .eq("client_id", client_id)
                    .eq("phone", phone)
                    .eq("status", "pending")
                    .execute()
                )
            except Exception:
                logger.exception("Error cancelando callbacks previos (bg)")

            insert_data = {
                "client_id": client_id,
                "agent_id": agent_id,
                "phone": phone,
                "scheduled_at": scheduled_at.isoformat(),
                "timezone": str(tz),
                "context": encrypted_context,
                "origin_call_id": origin_call_id,
                "max_attempts": max_attempts,
            }
            if origin_type:
                insert_data["origin_type"] = origin_type
            if campaign_id:
                insert_data["campaign_id"] = campaign_id

            await asyncio.to_thread(
                lambda: sb.table("scheduled_callbacks").insert(insert_data).execute()
            )
            logger.info(
                "Callback programado (bg): %s → %s a las %s (%s)",
                phone, fecha_local, hora_local, tz,
            )
        except Exception:
            logger.exception("Error insertando callback %s en background", phone)
            # Limpiar la entrada de idempotencia para permitir retry manual
            _recent_schedules.pop(key, None)

    # Fire and forget — el LLM recibe confirmación inmediatamente
    asyncio.create_task(_do_insert())

    return confirmation_msg
