"""Herramienta para enviar mensajes de WhatsApp vía Evolution API."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


async def send_whatsapp_message(
    api_url: str,
    api_key: str,
    instance_id: str,
    phone_number: str,
    message: str,
) -> str:
    """Envía un mensaje de WhatsApp vía Evolution API.

    Args:
        api_url: URL base de Evolution API.
        api_key: API key de la instancia.
        instance_id: ID de la instancia de WhatsApp.
        phone_number: Número destino (con código de país, sin +).
        message: Texto del mensaje.
    """
    # Limpiar número
    clean_phone = phone_number.lstrip("+").replace(" ", "").replace("-", "")

    url = f"{api_url.rstrip('/')}/message/sendText/{instance_id}"
    headers = {"apikey": api_key, "Content-Type": "application/json"}
    payload = {
        "number": clean_phone,
        "text": message,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()

        logger.info("WhatsApp enviado a %s vía instancia %s", clean_phone, instance_id)
        return f"Mensaje de WhatsApp enviado exitosamente al número {phone_number}."

    except httpx.TimeoutException:
        logger.error("Timeout enviando WhatsApp a %s", clean_phone)
        return "No pude enviar el mensaje de WhatsApp: tiempo de espera agotado."
    except httpx.HTTPStatusError as e:
        logger.error("Error HTTP enviando WhatsApp: %s %s", e.response.status_code, e.response.text)
        return f"Error al enviar WhatsApp: {e.response.status_code}."
    except Exception as e:
        logger.error("Error enviando WhatsApp: %s", e)
        return "No pude enviar el mensaje de WhatsApp en este momento."
