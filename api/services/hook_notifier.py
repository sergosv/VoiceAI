"""Servicio de notificaciones para lifecycle hooks.

Resuelve el canal de notificación y envía el mensaje:
- webhook: POST a URL externa
- whatsapp: envía mensaje vía Evolution API
- email: envía email vía Resend
"""

from __future__ import annotations

import asyncio
import logging
import os
from string import Template

import httpx

logger = logging.getLogger(__name__)

# Timeout para requests HTTP
_HTTP_TIMEOUT = 10.0


async def send_hook_notification(notif_config: dict) -> None:
    """Envía una notificación generada por un hook.

    Args:
        notif_config: Dict con channel, to, url, template, payload, context.
    """
    channel = notif_config.get("channel", "webhook")
    ctx = notif_config.get("context", {})

    try:
        if channel == "webhook":
            await _send_webhook(notif_config, ctx)
        elif channel == "whatsapp":
            await _send_whatsapp(notif_config, ctx)
        elif channel == "email":
            await _send_email(notif_config, ctx)
        else:
            logger.warning("Canal de notificación desconocido: %s", channel)
    except Exception:
        logger.exception(
            "Error enviando hook notification via %s (hook: %s)",
            channel, notif_config.get("hook_name"),
        )


async def _send_webhook(notif: dict, ctx: dict) -> None:
    """Envía notificación a un webhook externo."""
    url = notif.get("url")
    if not url:
        # Fallback: usar webhook_dispatch del sistema
        try:
            from api.services.webhook_dispatch import dispatch_event
            await dispatch_event(
                "hook.notification",
                {
                    "hook_name": notif.get("hook_name"),
                    "agent_id": ctx.get("agent_id"),
                    "client_id": ctx.get("client_id"),
                    "channel": ctx.get("channel"),
                    "caller_phone": ctx.get("caller_phone"),
                    "template": notif.get("template"),
                },
                client_id=ctx.get("client_id"),
            )
        except Exception:
            logger.exception("Error dispatching hook webhook event")
        return

    # URL explícita — POST directo
    template_str = notif.get("template", "")
    message = _render_template(template_str, ctx)

    payload_fields = notif.get("payload", [])
    payload = {"hook_name": notif.get("hook_name"), "message": message}
    for field in payload_fields:
        if field in ctx:
            payload[field] = ctx[field]

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.post(url, json=payload)
        logger.info(
            "Hook webhook sent to %s — status %d",
            url, resp.status_code,
        )


async def _send_whatsapp(notif: dict, ctx: dict) -> None:
    """Envía notificación por WhatsApp al dueño del negocio."""
    from api.deps import get_supabase

    to = notif.get("to", "owner")
    template_str = notif.get("template", "")
    message = _render_template(template_str, ctx)

    if not message:
        logger.warning("Hook WhatsApp notification sin mensaje — ignorando")
        return

    # Resolver número destino
    phone: str | None = None
    if to == "owner":
        # Buscar owner del cliente
        sb = get_supabase()
        client_data = await asyncio.to_thread(
            lambda: sb.table("clients")
            .select("owner_phone, owner_email")
            .eq("id", ctx.get("client_id"))
            .limit(1)
            .execute()
        )
        if client_data.data:
            phone = client_data.data[0].get("owner_phone")
    else:
        # `to` es directamente un número de teléfono
        phone = to

    if not phone:
        logger.warning("Hook WhatsApp: no se pudo resolver número destino (to=%s)", to)
        return

    # Buscar config de WhatsApp del agente
    from agent.config_loader import load_whatsapp_config_by_agent_id

    agent_id = ctx.get("agent_id")
    if not agent_id:
        logger.warning("Hook WhatsApp: no hay agent_id en contexto")
        return

    wa_config = await load_whatsapp_config_by_agent_id(agent_id)
    if not wa_config:
        logger.warning("Hook WhatsApp: no hay config de WhatsApp para agente %s", agent_id)
        return

    if wa_config.get("provider") == "evolution":
        from agent.tools.whatsapp_tool import send_whatsapp_message
        result = await send_whatsapp_message(
            api_url=wa_config.get("evo_api_url", ""),
            api_key=wa_config.get("evo_api_key", ""),
            instance_id=wa_config.get("evo_instance_id", ""),
            phone_number=phone,
            message=message,
        )
        logger.info("Hook WhatsApp notification sent to %s: %s", phone, result)
    else:
        logger.warning("Hook WhatsApp: provider '%s' no soportado para notificaciones", wa_config.get("provider"))


async def _send_email(notif: dict, ctx: dict) -> None:
    """Envía notificación por email vía Resend."""
    resend_key = os.environ.get("RESEND_API_KEY")
    if not resend_key:
        logger.warning("Hook email: RESEND_API_KEY no configurada")
        return

    to = notif.get("to", "owner")
    template_str = notif.get("template", "")
    message = _render_template(template_str, ctx)

    # Resolver email destino
    email: str | None = None
    if to == "owner":
        from api.deps import get_supabase
        sb = get_supabase()
        client_data = await asyncio.to_thread(
            lambda: sb.table("clients")
            .select("owner_email")
            .eq("id", ctx.get("client_id"))
            .limit(1)
            .execute()
        )
        if client_data.data:
            email = client_data.data[0].get("owner_email")
    elif "@" in to:
        email = to

    if not email:
        logger.warning("Hook email: no se pudo resolver email destino (to=%s)", to)
        return

    hook_name = notif.get("hook_name", "Notificación")
    from_email = os.environ.get("ADMIN_ALERT_EMAIL", "alertas@agentes.innotecnia.app")

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {resend_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": from_email,
                "to": [email],
                "subject": f"[VoiceAI] {hook_name}",
                "text": message,
            },
        )
        if resp.status_code in (200, 201):
            logger.info("Hook email sent to %s", email)
        else:
            logger.warning("Hook email failed (%d): %s", resp.status_code, resp.text)


def _render_template(template_str: str, ctx: dict) -> str:
    """Renderiza un template con variables del contexto.

    Soporta {{variable}} y $variable.
    """
    if not template_str:
        return ""

    # Reemplazar {{var}} por $var para usar Template de Python
    import re
    normalized = re.sub(r"\{\{(\w+)\}\}", r"${\1}", template_str)

    try:
        return Template(normalized).safe_substitute(ctx)
    except Exception:
        return template_str
