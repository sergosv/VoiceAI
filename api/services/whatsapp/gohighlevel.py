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

    # Mapeo de messageType de GHL a canal normalizado
    _CHANNEL_MAP: dict[str, str] = {
        "type_whatsapp": "whatsapp",
        "whatsapp": "whatsapp",
        "type_sms": "sms",
        "sms": "sms",
        "type_live_chat": "webchat",
        "live_chat": "webchat",
        "type_facebook": "facebook",
        "facebook": "facebook",
        "type_instagram": "instagram",
        "instagram": "instagram",
        "type_email": "email",
        "email": "email",
        "type_google_my_business": "google",
        "gmb": "google",
    }

    def _resolve_channel(self, payload: dict) -> str:
        """Resuelve el canal normalizado del mensaje GHL."""
        msg_type = payload.get("messageType", "").lower().strip()
        if msg_type in self._CHANNEL_MAP:
            return self._CHANNEL_MAP[msg_type]

        channel = payload.get("channel", "").lower().strip()
        if channel in self._CHANNEL_MAP:
            return self._CHANNEL_MAP[channel]

        # Fallback: buscar por substring
        for key, value in self._CHANNEL_MAP.items():
            if key in msg_type or key in channel:
                return value

        return "whatsapp"  # Default a whatsapp si no se puede determinar

    def parse_webhook(self, payload: dict) -> InboundMessage | None:
        """Parsea webhook InboundMessage de GHL.

        Acepta todos los canales: WhatsApp, SMS, Web Chat, Facebook, Instagram, etc.
        Filtra: solo direction=inbound.
        """
        direction = payload.get("direction")
        if direction != "inbound":
            return None

        channel = self._resolve_channel(payload)

        text = payload.get("body", "") or payload.get("message", "")
        phone = payload.get("phone", "") or payload.get("contactPhone", "")
        location_id = payload.get("locationId", "")
        msg_id = payload.get("messageId") or payload.get("id")

        contact_id = payload.get("contactId", "")
        if not phone and not contact_id and channel not in ("webchat", "facebook", "instagram"):
            return None

        # Limpiar phone (si no hay phone, usar contactId como identificador)
        clean_phone = (phone or "").lstrip("+").replace(" ", "").replace("-", "")
        if not clean_phone:
            clean_phone = contact_id or "unknown"

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
            channel=channel,
            provider_message_id=msg_id,
            ghl_location_id=location_id,
            ghl_contact_id=contact_id or None,
        )

    # Mapeo de canal normalizado a tipo de mensaje GHL para enviar
    _GHL_TYPE_MAP: dict[str, str] = {
        "whatsapp": "WhatsApp",
        "sms": "SMS",
        "webchat": "Live_Chat",
        "facebook": "FB",
        "instagram": "IG",
        "email": "Email",
        "google": "GMB",
    }

    async def send_text(self, config: dict, to_phone: str, text: str) -> str | None:
        """Envía mensaje vía GHL POST /conversations/messages."""
        api_key = config.get("ghl_api_key", "")
        contact_id = config.get("_ghl_contact_id")  # Debe resolverse antes
        channel = config.get("_ghl_channel", "whatsapp")

        if not api_key:
            logger.error("GHL: api_key no configurada")
            return None

        url = f"{GHL_API_BASE}/conversations/messages"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Version": "2021-07-28",
        }

        ghl_type = self._GHL_TYPE_MAP.get(channel, "WhatsApp")
        clean_phone = to_phone.lstrip("+").replace(" ", "").replace("-", "")

        payload: dict = {
            "type": ghl_type,
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
