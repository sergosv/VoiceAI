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
) -> str:
    """Programa un callback (devolución de llamada) para una hora futura.

    Args:
        client_id: ID del cliente.
        agent_id: ID del agente que hará la llamada.
        phone: Número de teléfono a llamar.
        date: Fecha en formato YYYY-MM-DD.
        time: Hora en formato HH:MM (24h).
        context: Resumen de la conversación para dar contexto al agente.
        origin_call_id: ID de la llamada original donde se pidió el callback.
        client_timezone: Timezone IANA del cliente.
        max_attempts: Intentos máximos si no contesta.

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

    # Validar que no sea en el pasado
    now = datetime.now(tz)
    if scheduled_at < now - timedelta(minutes=5):
        return (
            "La hora indicada ya pasó. "
            "Pregúntale al usuario una hora futura para la llamada."
        )

    # Validar que no sea demasiado lejos (max 30 días)
    if scheduled_at > now + timedelta(days=30):
        return (
            "Solo puedo programar callbacks hasta 30 días en el futuro. "
            "Confirma una fecha más cercana con el usuario."
        )

    sb = _get_supabase()

    try:
        insert_data = {
            "client_id": client_id,
            "agent_id": agent_id,
            "phone": phone,
            "scheduled_at": scheduled_at.isoformat(),
            "timezone": str(tz),
            "context": context,
            "origin_call_id": origin_call_id,
            "max_attempts": max_attempts,
        }
        if origin_type:
            insert_data["origin_type"] = origin_type
        if campaign_id:
            insert_data["campaign_id"] = campaign_id

        result = await asyncio.to_thread(
            lambda: sb.table("scheduled_callbacks").insert(insert_data).execute()
        )

        if result.data:
            # Formatear hora para confirmación
            hora_local = scheduled_at.strftime("%I:%M %p").lstrip("0")
            fecha_local = scheduled_at.strftime("%d/%m/%Y")
            logger.info(
                "Callback programado: %s → %s a las %s (%s)",
                phone, fecha_local, hora_local, tz,
            )
            return (
                f"Callback programado exitosamente para el {fecha_local} a las {hora_local}. "
                f"Confirma al usuario que le llamaremos a esa hora al número {phone}."
            )
        return "Error al guardar el callback. Pide disculpas e intenta de nuevo."

    except Exception:
        logger.exception("Error programando callback para %s", phone)
        return (
            "Hubo un error al programar la llamada. "
            "Pide disculpas y dile que un asesor lo contactará."
        )
