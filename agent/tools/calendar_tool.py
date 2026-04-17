"""Herramienta para agendar citas desde el agente de voz."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo
    TZ_MEXICO = ZoneInfo("America/Mexico_City")
except ImportError:
    try:
        from backports.zoneinfo import ZoneInfo
        TZ_MEXICO = ZoneInfo("America/Mexico_City")
    except ImportError:
        # Fallback estático: UTC-6 sin soporte DST.
        # Para soporte correcto de DST, instalar 'tzdata' (pip install tzdata).
        logger.warning(
            "zoneinfo no disponible y backports.zoneinfo no instalado. "
            "Usando UTC-6 fijo sin soporte de horario de verano (DST)."
        )
        TZ_MEXICO = timezone(timedelta(hours=-6))

from supabase import Client

from agent.db import get_supabase


def _get_supabase() -> Client:
    return get_supabase()


def _resolve_tz(tz_name: str | None) -> datetime.tzinfo:
    """Resuelve timezone por nombre IANA, con fallback a America/Mexico_City."""
    target = tz_name or "America/Mexico_City"
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(target)
    except (ImportError, KeyError):
        try:
            from backports.zoneinfo import ZoneInfo as BZoneInfo
            return BZoneInfo(target)
        except (ImportError, KeyError):
            return TZ_MEXICO


async def schedule_appointment(
    client_id: str,
    caller_phone: str,
    patient_name: str,
    date: str,
    time: str,
    duration_minutes: int = 60,
    description: str | None = None,
    google_calendar_id: str | None = None,
    google_service_account_key: dict | None = None,
    client_timezone: str | None = None,
) -> str:
    """Agenda una cita en la base de datos y opcionalmente en Google Calendar.

    Valida disponibilidad, crea/actualiza contacto, y crea la cita.
    """
    tz = _resolve_tz(client_timezone)
    tz_name = client_timezone or "America/Mexico_City"
    try:
        # Parsear fecha y hora en timezone del cliente
        start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        start_dt = start_dt.replace(tzinfo=tz)
        end_dt = start_dt + timedelta(minutes=duration_minutes)
    except ValueError:
        return (
            "No pude interpretar la fecha/hora. "
            "Necesito el formato: fecha YYYY-MM-DD y hora HH:MM (24h)."
        )

    sb = _get_supabase()

    # Verificar conflictos (pre-check para dar un mensaje rápido y legible;
    # la atomicidad real la garantiza el EXCLUDE constraint de la migración 058
    # que captura el race de dos callers pidiendo el mismo horario simultáneo).
    conflicts = await asyncio.to_thread(
        lambda: sb.table("appointments")
        .select("id, title, start_time, end_time")
        .eq("client_id", client_id)
        .eq("status", "confirmed")
        .lt("start_time", end_dt.isoformat())
        .gt("end_time", start_dt.isoformat())
        .execute()
    )
    if conflicts.data:
        existing = conflicts.data[0]
        return (
            f"Ese horario no está disponible. Ya hay una cita: "
            f"'{existing['title']}' de {existing['start_time'][:16]} a {existing['end_time'][:16]}. "
            "¿Podemos buscar otro horario?"
        )

    # Upsert contacto
    contact_id = None
    if caller_phone:
        contact_result = await asyncio.to_thread(
            lambda: sb.table("contacts")
            .upsert(
                {
                    "client_id": client_id,
                    "phone": caller_phone,
                    "name": patient_name,
                    "source": "inbound_call",
                },
                on_conflict="client_id,phone",
            )
            .execute()
        )
        if contact_result.data:
            contact_id = contact_result.data[0]["id"]

    # Crear cita — envuelto en try/except para capturar el constraint
    # `no_overlapping_appointments` (migración 058) que previene double-booking
    # cuando dos callers llegan al mismo slot al mismo tiempo.
    title = f"Cita - {patient_name}"
    appointment_data = {
        "client_id": client_id,
        "contact_id": contact_id,
        "title": title,
        "description": description or f"Cita agendada por teléfono para {patient_name}",
        "start_time": start_dt.isoformat(),
        "end_time": end_dt.isoformat(),
        "status": "confirmed",
    }
    try:
        result = await asyncio.to_thread(
            lambda: sb.table("appointments").insert(appointment_data).execute()
        )
    except Exception as e:
        err_str = str(e).lower()
        if "no_overlapping_appointments" in err_str or "exclude" in err_str or "conflicting key" in err_str:
            logger.warning(
                "Race detectado: slot %s tomado mientras agendábamos para %s",
                start_dt.isoformat(), patient_name,
            )
            return (
                "Ese horario acaba de ser reservado por alguien más. "
                "¿Podemos buscar otro horario?"
            )
        logger.exception("Error inesperado insertando cita")
        return "Hubo un error al guardar la cita. Por favor intenta de nuevo."
    if not result.data:
        return "Hubo un error al guardar la cita. Por favor intenta de nuevo."

    # Google Calendar (opcional)
    google_event_id = None
    if google_calendar_id and google_service_account_key:
        google_event_id = await asyncio.to_thread(
            _create_google_event,
            google_calendar_id,
            google_service_account_key,
            title,
            description or f"Cita agendada por teléfono para {patient_name}",
            start_dt,
            end_dt,
            tz_name,
        )
        if google_event_id:
            await asyncio.to_thread(
                lambda: sb.table("appointments").update(
                    {"google_event_id": google_event_id}
                ).eq("id", result.data[0]["id"]).execute()
            )

    formatted_date = start_dt.strftime("%d/%m/%Y")
    formatted_time = start_dt.strftime("%H:%M")
    confirmation = (
        f"Cita confirmada para {patient_name} el {formatted_date} a las {formatted_time} "
        f"({duration_minutes} minutos)."
    )
    if google_event_id:
        confirmation += " También se agregó al calendario de Google."

    return confirmation


def _create_google_event(
    calendar_id: str,
    service_account_key: dict,
    title: str,
    description: str,
    start_time: datetime,
    end_time: datetime,
    tz_name: str = "America/Mexico_City",
) -> str | None:
    """Crea un evento en Google Calendar usando service account."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        credentials = service_account.Credentials.from_service_account_info(
            service_account_key,
            scopes=["https://www.googleapis.com/auth/calendar"],
        )
        service = build("calendar", "v3", credentials=credentials)

        event = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start_time.isoformat(), "timeZone": tz_name},
            "end": {"dateTime": end_time.isoformat(), "timeZone": tz_name},
        }
        created = service.events().insert(calendarId=calendar_id, body=event).execute()
        logger.info("Google Calendar event creado: %s", created.get("id"))
        return created.get("id")
    except Exception as e:
        logger.error("Error creando evento en Google Calendar: %s", e)
        return None
