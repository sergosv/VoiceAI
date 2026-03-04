"""Proveedor WhatsApp — GoHighLevel."""

from __future__ import annotations

import hashlib
import hmac
import logging

import httpx

from api.services.whatsapp.provider import InboundMessage, WhatsAppProvider

logger = logging.getLogger(__name__)

GHL_API_BASE = "https://services.leadconnectorhq.com"


class GoHighLevelProvider(WhatsAppProvider):
    """Implementación de WhatsApp vía GoHighLevel API."""

    def parse_webhook(self, payload: dict) -> InboundMessage | None:
        """Parsea webhook InboundMessage de GHL.

        Filtra: direction=inbound + messageType que incluya WhatsApp.
        """
        # GHL envía el tipo de evento en el campo 'type'
        direction = payload.get("direction")
        if direction != "inbound":
            return None

        # Verificar que es un mensaje de WhatsApp
        msg_type = payload.get("messageType", "")
        if "whatsapp" not in msg_type.lower() and msg_type.upper() != "TYPE_WHATSAPP":
            # GHL puede enviar como TYPE_WHATSAPP o WhatsApp
            # También aceptar si el canal es whatsapp
            channel = payload.get("channel", "")
            if "whatsapp" not in channel.lower():
                return None

        text = payload.get("body", "") or payload.get("message", "")
        phone = payload.get("phone", "") or payload.get("contactPhone", "")
        location_id = payload.get("locationId", "")
        msg_id = payload.get("messageId") or payload.get("id")

        if not phone:
            return None

        # Limpiar phone
        clean_phone = phone.lstrip("+").replace(" ", "").replace("-", "")

        # Detectar tipo de contenido
        content_type = "text"
        attachments = payload.get("attachments", [])
        if attachments:
            first = attachments[0] if isinstance(attachments, list) else {}
            att_type = first.get("type", "") if isinstance(first, dict) else ""
            if "image" in att_type:
                content_type = "image"
            elif "audio" in att_type:
                content_type = "audio"
            elif "video" in att_type:
                content_type = "video"
            elif att_type:
                content_type = "document"

        return InboundMessage(
            remote_phone=clean_phone,
            text=text,
            message_type=content_type,
            provider_message_id=msg_id,
            ghl_location_id=location_id,
        )

    async def send_text(self, config: dict, to_phone: str, text: str) -> str | None:
        """Envía mensaje vía GHL POST /conversations/messages."""
        api_key = config.get("ghl_api_key", "")
        contact_id = config.get("_ghl_contact_id")  # Debe resolverse antes

        if not api_key:
            logger.error("GHL: api_key no configurada")
            return None

        # GHL requiere conversationId o contactId
        # Enviamos creando un mensaje en la conversación del contacto
        url = f"{GHL_API_BASE}/conversations/messages"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Version": "2021-07-28",
        }

        clean_phone = to_phone.lstrip("+").replace(" ", "").replace("-", "")

        payload: dict = {
            "type": "WhatsApp",
            "message": text,
        }

        if contact_id:
            payload["contactId"] = contact_id
        else:
            payload["phone"] = f"+{clean_phone}"

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                msg_id = data.get("messageId") or data.get("id")
                logger.info("GHL: mensaje enviado a %s", clean_phone)
                return msg_id
        except httpx.TimeoutException:
            logger.error("GHL: timeout enviando a %s", clean_phone)
            return None
        except httpx.HTTPStatusError as e:
            logger.error("GHL: HTTP %s — %s", e.response.status_code, e.response.text)
            return None
        except Exception as e:
            logger.error("GHL: error enviando — %s", e)
            return None

    def validate_webhook(self, headers: dict, body: bytes) -> bool:
        """Valida firma HMAC-SHA256 del webhook de GHL.

        GHL envía la firma en x-wh-signature.
        Si no hay secret configurado, se acepta (dev mode).
        """
        import os

        secret = os.environ.get("GHL_WEBHOOK_SECRET", "")
        if not secret:
            return True

        signature = headers.get("x-wh-signature", "")
        if not signature:
            return False

        expected = hmac.new(
            secret.encode(), body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
