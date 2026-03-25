"""Herramienta de email para el Asistente Personal.

Envía emails usando Resend con configuración personalizada por agente PA.
"""

from __future__ import annotations

import asyncio
import logging
import os

from supabase import Client

logger = logging.getLogger(__name__)


async def pa_load_email_config(sb: Client, agent_id: str) -> dict | None:
    """Carga la configuración de email para un agente PA."""
    result = await asyncio.to_thread(
        lambda: sb.table("pa_email_config")
        .select("*")
        .eq("agent_id", agent_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


async def pa_send_email(
    sb: Client,
    *,
    agent_id: str,
    to_email: str,
    subject: str,
    body: str,
) -> str:
    """Envía un email en nombre del dueño del PA usando Resend."""
    config = await pa_load_email_config(sb, agent_id)
    if not config:
        return "Error: No hay configuración de email. Configura tu email en el panel de control."

    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        logger.error("RESEND_API_KEY no configurada")
        return "Error: El servicio de email no está disponible."

    try:
        import resend
        resend.api_key = api_key

        # Construir el body con firma si existe
        full_body = body
        if config.get("signature"):
            full_body += f"\n\n--\n{config['signature']}"

        params: dict = {
            "from": f"{config['from_name']} <{config['from_email']}>",
            "to": [to_email],
            "subject": subject,
            "text": full_body,
        }
        if config.get("reply_to"):
            params["reply_to"] = config["reply_to"]

        result = await asyncio.to_thread(lambda: resend.Emails.send(params))
        logger.info("PA email sent to %s, id=%s", to_email, result.get("id", "?"))
        return f"Email enviado a {to_email}"
    except Exception as e:
        logger.error("Error enviando PA email: %s", e)
        return f"Error enviando email: {e}"
