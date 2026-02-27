"""Herramienta para agendar citas desde el agente de voz."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from supabase import create_client, Client

logger = logging.getLogger(__name__)


def _get_supabase() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


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
) -> str:
    """Agenda una cita en la base de datos y opcionalmente en Google Calendar.

    Valida disponibilidad, crea/actualiza contacto, y crea la cita.
    """
    try:
        # Parsear fecha y hora
        start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        start_dt = start_dt.replace(tzinfo=timezone(timedelta(hours=-6)))  # CST México
        end_dt = start_dt + timedelta(minutes=duration_minutes)
    except ValueError:
        return (
            "No pude interpretar la fecha/hora. "
            "Necesito el formato: fecha YYYY-MM-DD y hora HH:MM (24h)."
        )

    sb = _get_supabase()

    # Verificar conflictos
    conflicts = (
        sb.table("appointments")
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
        contact_result = (
            sb.table("contacts")
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

    # Crear cita
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
    result = sb.table("appointments").insert(appointment_data).execute()
    if not result.data:
        return "Hubo un error al guardar la cita. Por favor intenta de nuevo."

    # Google Calendar (opcional)
    google_event_id = None
    if google_calendar_id and google_service_account_key:
        google_event_id = _create_google_event(
            calendar_id=google_calendar_id,
            service_account_key=google_service_account_key,
            title=title,
            description=description or f"Cita agendada por teléfono para {patient_name}",
            start_time=start_dt,
            end_time=end_dt,
        )
        if google_event_id:
            sb.table("appointments").update(
                {"google_event_id": google_event_id}
            ).eq("id", result.data[0]["id"]).execute()

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
            "start": {"dateTime": start_time.isoformat(), "timeZone": "America/Mexico_City"},
            "end": {"dateTime": end_time.isoformat(), "timeZone": "America/Mexico_City"},
        }
        created = service.events().insert(calendarId=calendar_id, body=event).execute()
        logger.info("Google Calendar event creado: %s", created.get("id"))
        return created.get("id")
    except Exception as e:
        logger.error("Error creando evento en Google Calendar: %s", e)
        return None
