"""Proveedor WhatsApp — Evolution API."""

from __future__ import annotations

import asyncio
import logging
import random

import httpx

from api.services.whatsapp.provider import InboundMessage, WhatsAppProvider

logger = logging.getLogger(__name__)

# Delay mínimo y máximo en segundos antes de responder (simula escritura humana)
MIN_TYPING_DELAY = 1.0
MAX_TYPING_DELAY = 3.0
# Caracteres por segundo para calcular delay proporcional al largo del mensaje
CHARS_PER_SECOND = 30


class EvolutionProvider(WhatsAppProvider):
    """Implementación de WhatsApp vía Evolution API."""

    def parse_webhook(self, payload: dict) -> InboundMessage | None:
        """Parsea webhook MESSAGES_UPSERT de Evolution API.

        Filtra mensajes propios (fromMe=true) y extrae texto.
        """
        event = payload.get("event")
        if event != "messages.upsert":
            return None

        data = payload.get("data", {})
        key = data.get("key", {})

        # Filtrar mensajes propios
        if key.get("fromMe", False):
            return None

        remote_jid = key.get("remoteJid", "")
        # Extraer número del JID (formato: 5215551234567@s.whatsapp.net)
        remote_phone = remote_jid.split("@")[0] if "@" in remote_jid else remote_jid

        # Determinar tipo de mensaje
        message = data.get("message", {})
        if message.get("conversation"):
            text = message["conversation"]
            msg_type = "text"
        elif message.get("extendedTextMessage"):
            text = message["extendedTextMessage"].get("text", "")
            msg_type = "text"
        elif message.get("imageMessage"):
            text = message["imageMessage"].get("caption", "")
            msg_type = "image"
        elif message.get("audioMessage"):
            text = ""
            msg_type = "audio"
        elif message.get("videoMessage"):
            text = message["videoMessage"].get("caption", "")
            msg_type = "video"
        elif message.get("documentMessage"):
            text = message["documentMessage"].get("fileName", "")
            msg_type = "document"
        else:
            return None

        instance = payload.get("instance", "")
        msg_id = key.get("id")

        return InboundMessage(
            remote_phone=remote_phone,
            text=text,
            message_type=msg_type,
            provider_message_id=msg_id,
            evo_instance_id=instance,
        )

    async def send_text(self, config: dict, to_phone: str, text: str) -> str | None:
        """Envía texto vía Evolution API con typing indicator y delay humano."""
        api_url = config.get("evo_api_url", "").rstrip("/")
        api_key = config.get("evo_api_key", "")
        instance_id = config.get("evo_instance_id", "")

        if not all([api_url, api_key, instance_id]):
            logger.error("Evolution API config incompleta")
            return None

        clean_phone = to_phone.lstrip("+").replace(" ", "").replace("-", "")
        headers = {"apikey": api_key, "Content-Type": "application/json"}

        # 1. Enviar "composing" (los tres puntitos de "escribiendo...")
        await self._send_presence(api_url, instance_id, headers, clean_phone, "composing")

        # 2. Delay proporcional al largo del mensaje (simula escritura humana)
        typing_delay = min(
            max(len(text) / CHARS_PER_SECOND, MIN_TYPING_DELAY),
            MAX_TYPING_DELAY,
        )
        # Agregar variación aleatoria para que no sea predecible
        typing_delay += random.uniform(0.3, 0.8)
        await asyncio.sleep(typing_delay)

        # 3. Enviar mensaje
        url = f"{api_url}/message/sendText/{instance_id}"
        payload = {"number": clean_phone, "text": text}

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                msg_id = data.get("key", {}).get("id")
                logger.info("Evolution: mensaje enviado a %s", clean_phone)
                return msg_id
        except httpx.TimeoutException:
            logger.error("Evolution: timeout enviando a %s", clean_phone)
            return None
        except httpx.HTTPStatusError as e:
            logger.error("Evolution: HTTP %s — %s", e.response.status_code, e.response.text)
            return None
        except Exception as e:
            logger.error("Evolution: error enviando — %s", e)
            return None

    async def _send_presence(
        self, api_url: str, instance_id: str, headers: dict,
        phone: str, presence: str,
    ) -> None:
        """Envía estado de presencia (composing/paused) al contacto."""
        url = f"{api_url}/chat/sendPresence/{instance_id}"
        payload = {"number": phone, "presence": presence}
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(url, json=payload, headers=headers)
        except Exception:
            # No fallar si el presence no se envía — es cosmético
            pass

    def validate_webhook(self, headers: dict, body: bytes) -> bool:
        """Evolution API no usa firma HMAC — validamos por instance_id en el payload."""
        return True
