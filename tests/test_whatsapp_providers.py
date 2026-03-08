"""Tests para los providers de WhatsApp (Evolution + GHL)."""

from __future__ import annotations

import pytest

from api.services.whatsapp.evolution import EvolutionProvider
from api.services.whatsapp.gohighlevel import GoHighLevelProvider
from api.services.whatsapp.router import get_provider


# ── Evolution Provider ─────────────────────────────────


class TestEvolutionProvider:
    """Tests para EvolutionProvider.parse_webhook."""

    def setup_method(self):
        self.provider = EvolutionProvider()

    def test_parse_text_message(self):
        payload = {
            "event": "messages.upsert",
            "instance": "mi-instancia",
            "data": {
                "key": {
                    "remoteJid": "5215551234567@s.whatsapp.net",
                    "fromMe": False,
                    "id": "MSG001",
                },
                "message": {
                    "conversation": "Hola, quiero información",
                },
            },
        }
        msg = self.provider.parse_webhook(payload)
        assert msg is not None
        assert msg.remote_phone == "5215551234567"
        assert msg.text == "Hola, quiero información"
        assert msg.message_type == "text"
        assert msg.provider_message_id == "MSG001"
        assert msg.evo_instance_id == "mi-instancia"

    def test_parse_extended_text_message(self):
        payload = {
            "event": "messages.upsert",
            "instance": "test",
            "data": {
                "key": {
                    "remoteJid": "5215559876543@s.whatsapp.net",
                    "fromMe": False,
                    "id": "MSG002",
                },
                "message": {
                    "extendedTextMessage": {
                        "text": "Mensaje extendido con link",
                    },
                },
            },
        }
        msg = self.provider.parse_webhook(payload)
        assert msg is not None
        assert msg.text == "Mensaje extendido con link"
        assert msg.message_type == "text"

    def test_parse_image_message(self):
        payload = {
            "event": "messages.upsert",
            "instance": "test",
            "data": {
                "key": {
                    "remoteJid": "5215551234567@s.whatsapp.net",
                    "fromMe": False,
                    "id": "MSG003",
                },
                "message": {
                    "imageMessage": {"caption": "Mi foto"},
                },
            },
        }
        msg = self.provider.parse_webhook(payload)
        assert msg is not None
        assert msg.message_type == "image"
        assert msg.text == "Mi foto"

    def test_filter_own_messages(self):
        payload = {
            "event": "messages.upsert",
            "instance": "test",
            "data": {
                "key": {
                    "remoteJid": "5215551234567@s.whatsapp.net",
                    "fromMe": True,
                    "id": "MSG004",
                },
                "message": {"conversation": "Hola"},
            },
        }
        msg = self.provider.parse_webhook(payload)
        assert msg is None

    def test_filter_non_messages_event(self):
        payload = {
            "event": "connection.update",
            "instance": "test",
            "data": {},
        }
        msg = self.provider.parse_webhook(payload)
        assert msg is None

    def test_audio_message(self):
        payload = {
            "event": "messages.upsert",
            "instance": "test",
            "data": {
                "key": {
                    "remoteJid": "5215551234567@s.whatsapp.net",
                    "fromMe": False,
                    "id": "MSG005",
                },
                "message": {
                    "audioMessage": {"mimetype": "audio/ogg"},
                },
            },
        }
        msg = self.provider.parse_webhook(payload)
        assert msg is not None
        assert msg.message_type == "audio"
        assert msg.text == ""

    def test_validate_webhook_always_true(self):
        assert self.provider.validate_webhook({}, b"") is True


# ── GoHighLevel Provider ──────────────────────────────


class TestGoHighLevelProvider:
    """Tests para GoHighLevelProvider.parse_webhook."""

    def setup_method(self):
        self.provider = GoHighLevelProvider()

    def test_parse_inbound_whatsapp(self):
        payload = {
            "direction": "inbound",
            "messageType": "TYPE_WHATSAPP",
            "body": "Quiero agendar una cita",
            "phone": "+5215551234567",
            "locationId": "loc123",
            "messageId": "ghl-msg-001",
        }
        msg = self.provider.parse_webhook(payload)
        assert msg is not None
        assert msg.remote_phone == "5215551234567"
        assert msg.text == "Quiero agendar una cita"
        assert msg.message_type == "text"
        assert msg.channel == "whatsapp"
        assert msg.ghl_location_id == "loc123"
        assert msg.ghl_contact_id is None  # No contactId in payload
        assert msg.provider_message_id == "ghl-msg-001"

    def test_parse_inbound_with_contact_id(self):
        """GHL contactId se propaga para enviar respuestas."""
        payload = {
            "direction": "inbound",
            "messageType": "TYPE_LIVE_CHAT",
            "body": "Hola",
            "phone": "",
            "contactId": "ghl-contact-abc123",
            "locationId": "loc123",
        }
        msg = self.provider.parse_webhook(payload)
        assert msg is not None
        assert msg.ghl_contact_id == "ghl-contact-abc123"
        assert msg.remote_phone == "ghl-contact-abc123"  # Fallback cuando no hay phone

    def test_filter_outbound(self):
        payload = {
            "direction": "outbound",
            "messageType": "TYPE_WHATSAPP",
            "body": "Respuesta",
            "phone": "+5215551234567",
        }
        msg = self.provider.parse_webhook(payload)
        assert msg is None

    def test_parse_sms(self):
        """GHL acepta SMS como canal."""
        payload = {
            "direction": "inbound",
            "messageType": "TYPE_SMS",
            "body": "Texto SMS",
            "phone": "+5215551234567",
            "locationId": "loc123",
        }
        msg = self.provider.parse_webhook(payload)
        assert msg is not None
        assert msg.channel == "sms"
        assert msg.text == "Texto SMS"

    def test_parse_webchat(self):
        """GHL acepta Live Chat / Web Chat."""
        payload = {
            "direction": "inbound",
            "messageType": "TYPE_LIVE_CHAT",
            "body": "Hola desde el widget",
            "phone": "",
            "locationId": "loc123",
        }
        msg = self.provider.parse_webhook(payload)
        assert msg is not None
        assert msg.channel == "webchat"

    def test_parse_facebook(self):
        """GHL acepta Facebook Messenger."""
        payload = {
            "direction": "inbound",
            "messageType": "TYPE_FACEBOOK",
            "body": "Mensaje de Facebook",
            "phone": "+5215551234567",
            "locationId": "loc123",
        }
        msg = self.provider.parse_webhook(payload)
        assert msg is not None
        assert msg.channel == "facebook"

    def test_parse_instagram(self):
        """GHL acepta Instagram DM."""
        payload = {
            "direction": "inbound",
            "messageType": "TYPE_INSTAGRAM",
            "body": "DM de Instagram",
            "phone": "",
            "locationId": "loc123",
        }
        msg = self.provider.parse_webhook(payload)
        assert msg is not None
        assert msg.channel == "instagram"

    def test_parse_with_channel_field(self):
        """GHL puede enviar el canal en un campo diferente."""
        payload = {
            "direction": "inbound",
            "messageType": "chat",
            "channel": "whatsapp",
            "body": "Hola desde WhatsApp",
            "phone": "5215559876543",
            "locationId": "loc456",
        }
        msg = self.provider.parse_webhook(payload)
        assert msg is not None
        assert msg.text == "Hola desde WhatsApp"
        assert msg.channel == "whatsapp"

    def test_filter_no_phone_non_digital(self):
        """Sin phone y canal que requiere phone → None."""
        payload = {
            "direction": "inbound",
            "messageType": "TYPE_SMS",
            "body": "Sin phone",
        }
        msg = self.provider.parse_webhook(payload)
        assert msg is None

    def test_no_phone_ok_for_webchat(self):
        """Web chat no necesita phone."""
        payload = {
            "direction": "inbound",
            "messageType": "TYPE_LIVE_CHAT",
            "body": "Hola",
            "locationId": "loc123",
        }
        msg = self.provider.parse_webhook(payload)
        assert msg is not None

    def test_parse_with_attachments(self):
        payload = {
            "direction": "inbound",
            "messageType": "TYPE_WHATSAPP",
            "body": "",
            "phone": "+5215551234567",
            "locationId": "loc789",
            "attachments": [{"type": "image/jpeg", "url": "https://..."}],
        }
        msg = self.provider.parse_webhook(payload)
        assert msg is not None
        assert msg.message_type == "image"

    def test_validate_webhook_no_secret(self, monkeypatch):
        """Sin GHL_WEBHOOK_SECRET, acepta todo."""
        monkeypatch.delenv("GHL_WEBHOOK_SECRET", raising=False)
        assert self.provider.validate_webhook({}, b"{}") is True

    def test_resolve_channel_unknown_defaults_whatsapp(self):
        """Canal desconocido → default 'whatsapp'."""
        payload = {
            "direction": "inbound",
            "messageType": "SOME_NEW_TYPE",
            "body": "Nuevo canal",
            "phone": "+5215551234567",
            "locationId": "loc123",
        }
        msg = self.provider.parse_webhook(payload)
        assert msg is not None
        assert msg.channel == "whatsapp"


# ── Router ─────────────────────────────────────────────


class TestRouter:
    def test_get_evolution_provider(self):
        p = get_provider("evolution")
        assert isinstance(p, EvolutionProvider)

    def test_get_ghl_provider(self):
        p = get_provider("gohighlevel")
        assert isinstance(p, GoHighLevelProvider)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="desconocido"):
            get_provider("telegram")
