"""Function tool para que el agente programe recordatorios durante la llamada.

Permite al usuario decir cosas como:
- "Recuérdame mañana a las 2 de mi cita con el doctor"
- "Mándame un WhatsApp el viernes con el resumen"
- "Llámame la próxima semana para darme seguimiento"
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def schedule_reminder_action(
    description: str,
    datetime_str: str,
    channel: str,
    agent_id: str,
    client_id: str,
    target_number: str,
    target_contact_id: str | None = None,
    source_call_id: str | None = None,
) -> str:
    """Programa un recordatorio para ejecutarse en la fecha indicada.

    Args:
        description: Descripción del recordatorio (ej: "Cita con el doctor").
        datetime_str: Fecha y hora en formato ISO 8601 (ej: "2026-03-08T14:00:00").
        channel: Canal de envío: "call" o "whatsapp".
        agent_id: UUID del agente que programa.
        client_id: UUID del cliente.
        target_number: Número del contacto destino.
        target_contact_id: UUID del contacto (opcional).
        source_call_id: UUID de la llamada origen (opcional).

    Returns:
        Mensaje de confirmación para el usuario.
    """
    try:
        # Validar datetime
        try:
            scheduled = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
        except ValueError:
            return f"No pude entender la fecha '{datetime_str}'. Por favor indícame la fecha y hora de forma clara."

        # Validar que sea en el futuro
        now = datetime.now(timezone.utc)
        if scheduled.tzinfo is None:
            # Asumir UTC si no tiene timezone
            scheduled = scheduled.replace(tzinfo=timezone.utc)
        if scheduled <= now:
            return "La fecha indicada ya pasó. Por favor indícame una fecha futura."

        # Validar channel
        if channel not in ("call", "whatsapp"):
            channel = "call"

        # Construir mensaje basado en la descripción
        message = f"Hola, te llamo para recordarte: {description}"
        if channel == "whatsapp":
            message = f"Recordatorio: {description}"

        from api.services.proactive_worker import create_scheduled_action
        create_scheduled_action(
            agent_id=agent_id,
            client_id=client_id,
            rule_type="reminder",
            channel=channel,
            target_number=target_number,
            message=message,
            scheduled_at=scheduled.isoformat(),
            source="conversation",
            source_call_id=source_call_id,
            target_contact_id=target_contact_id,
            max_attempts=2,
            metadata={"description": description, "original_datetime": datetime_str},
        )

        # Formatear fecha para confirmación
        formatted = scheduled.strftime("%d de %B de %Y a las %H:%M")
        channel_text = "una llamada" if channel == "call" else "un mensaje de WhatsApp"
        return f"Listo, te enviaré {channel_text} el {formatted} para recordarte: {description}."

    except Exception as e:
        logger.error("Error programando recordatorio: %s", e)
        return "Hubo un problema programando el recordatorio. Por favor intenta de nuevo."
