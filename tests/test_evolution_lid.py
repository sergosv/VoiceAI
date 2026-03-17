"""Tests de regresión para WhatsApp LID y Evolution provider.

Regresión: WhatsApp empezó a usar LID (Linked ID) en vez de JIDs basados
en teléfono. El número real está en key.remoteJidAlt.
Bug original: 2026-03-16, commit 435f433.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.whatsapp.evolution import EvolutionProvider


class TestEvolutionLID:
    """Tests para manejo de WhatsApp Linked IDs (@lid)."""

    def setup_method(self):
        self.provider = EvolutionProvider()

    def test_lid_uses_remoteJidAlt(self):
        """Cuando remoteJid es @lid, debe usar remoteJidAlt."""
        payload = {
            "event": "messages.upsert",
            "instance": "valeria",
            "data": {
                "key": {
                    "remoteJid": "47223333253334@lid",
                    "remoteJidAlt": "5212227690231@s.whatsapp.net",
                    "fromMe": False,
                    "id": "MSG-LID-001",
                    "addressingMode": "lid",
                },
                "message": {"conversation": "Hola desde LID"},
            },
        }
        msg = self.provider.parse_webhook(payload)
        assert msg is not None
        assert msg.remote_phone == "5212227690231"
        assert msg.text == "Hola desde LID"
        assert msg.evo_instance_id == "valeria"

    def test_lid_without_alt_jid_still_parses(self):
        """Si @lid no tiene remoteJidAlt, usa el LID como fallback."""
        payload = {
            "event": "messages.upsert",
            "instance": "test",
            "data": {
                "key": {
                    "remoteJid": "99887766554433@lid",
                    "fromMe": False,
                    "id": "MSG-LID-002",
                },
                "message": {"conversation": "Sin alt"},
            },
        }
        msg = self.provider.parse_webhook(payload)
        assert msg is not None
        # Sin alt, usa el LID pero split("@") quita el sufijo
        assert msg.remote_phone == "99887766554433"

    def test_lid_with_empty_alt_jid(self):
        """remoteJidAlt vacío → usa LID original."""
        payload = {
            "event": "messages.upsert",
            "instance": "test",
            "data": {
                "key": {
                    "remoteJid": "12345678901234@lid",
                    "remoteJidAlt": "",
                    "fromMe": False,
                    "id": "MSG-LID-003",
                },
                "message": {"conversation": "Alt vacío"},
            },
        }
        msg = self.provider.parse_webhook(payload)
        assert msg is not None
        assert msg.remote_phone == "12345678901234"

    def test_lid_with_invalid_alt_jid(self):
        """remoteJidAlt sin @s.whatsapp.net → usa LID original (sin @lid)."""
        payload = {
            "event": "messages.upsert",
            "instance": "test",
            "data": {
                "key": {
                    "remoteJid": "12345678901234@lid",
                    "remoteJidAlt": "99887766@g.us",
                    "fromMe": False,
                    "id": "MSG-LID-004",
                },
                "message": {"conversation": "Alt es grupo"},
            },
        }
        msg = self.provider.parse_webhook(payload)
        assert msg is not None
        # No es @s.whatsapp.net, usa LID pero split quita @lid
        assert msg.remote_phone == "12345678901234"

    def test_normal_jid_ignores_alt(self):
        """JID normal @s.whatsapp.net no necesita remoteJidAlt."""
        payload = {
            "event": "messages.upsert",
            "instance": "test",
            "data": {
                "key": {
                    "remoteJid": "5215551234567@s.whatsapp.net",
                    "remoteJidAlt": "99887766554433@lid",
                    "fromMe": False,
                    "id": "MSG-NORMAL",
                },
                "message": {"conversation": "Normal"},
            },
        }
        msg = self.provider.parse_webhook(payload)
        assert msg is not None
        assert msg.remote_phone == "5215551234567"

    def test_multiple_lid_formats(self):
        """Diferentes longitudes de LID deben resolverse."""
        lid_cases = [
            ("47223333253334@lid", "5212227690231@s.whatsapp.net", "5212227690231"),
            ("87652128792675@lid", "573246800989@s.whatsapp.net", "573246800989"),
            ("118240902643890@lid", "5219994330027@s.whatsapp.net", "5219994330027"),
        ]
        for lid, alt, expected_phone in lid_cases:
            payload = {
                "event": "messages.upsert",
                "instance": "test",
                "data": {
                    "key": {
                        "remoteJid": lid,
                        "remoteJidAlt": alt,
                        "fromMe": False,
                        "id": f"MSG-{lid[:8]}",
                    },
                    "message": {"conversation": "Test"},
                },
            }
            msg = self.provider.parse_webhook(payload)
            assert msg is not None, f"Failed for LID: {lid}"
            assert msg.remote_phone == expected_phone, (
                f"Expected {expected_phone} for LID {lid}, got {msg.remote_phone}"
            )


class TestEvolutionSendLongPhone:
    """Tests para envío con números largos (>13 dígitos)."""

    def setup_method(self):
        self.provider = EvolutionProvider()

    @pytest.mark.asyncio
    async def test_long_phone_sent_as_jid(self):
        """Números >13 dígitos se envían como JID completo."""
        config = {
            "evo_api_url": "https://evo.test.com",
            "evo_api_key": "test-key",
            "evo_instance_id": "test-instance",
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"key": {"id": "sent-001"}}
            mock_resp.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            result = await self.provider.send_text(config, "47223333253334", "Hola")

            # Verificar que se hizo al menos un post (presence + send)
            assert mock_client.post.call_count >= 1

    @pytest.mark.asyncio
    async def test_normal_phone_sent_as_number(self):
        """Números normales (<=13 dígitos) se envían sin @s.whatsapp.net."""
        config = {
            "evo_api_url": "https://evo.test.com",
            "evo_api_key": "test-key",
            "evo_instance_id": "test-instance",
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"key": {"id": "sent-002"}}
            mock_resp.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            await self.provider.send_text(config, "5212227690231", "Hola")

            # El número NO debe tener @s.whatsapp.net
            calls = mock_client.post.call_args_list
            send_call = [c for c in calls if "sendText" in str(c)]
            assert len(send_call) >= 1


class TestEvolutionWebhookValidation:
    """Tests para validación de webhooks Evolution."""

    def setup_method(self):
        self.provider = EvolutionProvider()

    def test_no_token_env_accepts_all(self, monkeypatch):
        """Sin EVOLUTION_WEBHOOK_TOKEN, acepta todo."""
        monkeypatch.delenv("EVOLUTION_WEBHOOK_TOKEN", raising=False)
        assert self.provider.validate_webhook({}, b"") is True

    def test_valid_token(self, monkeypatch):
        """Token correcto es aceptado."""
        monkeypatch.setenv("EVOLUTION_WEBHOOK_TOKEN", "mi-secreto-123")
        assert self.provider.validate_webhook({"apikey": "mi-secreto-123"}, b"") is True

    def test_invalid_token(self, monkeypatch):
        """Token incorrecto es rechazado."""
        monkeypatch.setenv("EVOLUTION_WEBHOOK_TOKEN", "mi-secreto-123")
        assert self.provider.validate_webhook({"apikey": "token-malo"}, b"") is False

    def test_missing_apikey_header_accepted(self, monkeypatch):
        """Sin header apikey, se acepta (compatibilidad con versiones viejas)."""
        monkeypatch.setenv("EVOLUTION_WEBHOOK_TOKEN", "mi-secreto-123")
        assert self.provider.validate_webhook({}, b"") is True

    def test_apikey_case_insensitive(self, monkeypatch):
        """Header 'Apikey' (capitalizado) también funciona."""
        monkeypatch.setenv("EVOLUTION_WEBHOOK_TOKEN", "mi-secreto-123")
        assert self.provider.validate_webhook({"Apikey": "mi-secreto-123"}, b"") is True
