"""Tests para BYOT (Bring Your Own Twilio)."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from api.schemas import SaveTwilioCredentialsRequest, client_out_from_row

# Stub twilio si no está instalado (entorno de test ligero)
if "twilio" not in sys.modules:
    twilio_mock = MagicMock()
    sys.modules["twilio"] = twilio_mock
    sys.modules["twilio.rest"] = twilio_mock.rest


# ── Validación de credenciales ──────────────────────────


class TestSaveTwilioCredentialsRequest:
    def test_valid_credentials(self):
        req = SaveTwilioCredentialsRequest(
            account_sid="AC12345678901234567890123456789012",
            auth_token="abcdef01234567890abcdef012345678",
        )
        assert req.account_sid.startswith("AC")
        assert len(req.account_sid) == 34
        assert len(req.auth_token) == 32

    def test_invalid_sid_prefix(self):
        with pytest.raises(ValidationError, match="AC"):
            SaveTwilioCredentialsRequest(
                account_sid="XX12345678901234567890123456789012",
                auth_token="abcdef01234567890abcdef012345678",
            )

    def test_invalid_sid_length(self):
        with pytest.raises(ValidationError, match="34"):
            SaveTwilioCredentialsRequest(
                account_sid="AC1234567890",
                auth_token="abcdef01234567890abcdef012345678",
            )

    def test_invalid_token_length(self):
        with pytest.raises(ValidationError, match="32"):
            SaveTwilioCredentialsRequest(
                account_sid="AC12345678901234567890123456789012",
                auth_token="short",
            )

    def test_strips_whitespace(self):
        req = SaveTwilioCredentialsRequest(
            account_sid="  AC12345678901234567890123456789012  ",
            auth_token="  abcdef01234567890abcdef012345678  ",
        )
        assert not req.account_sid.startswith(" ")
        assert not req.auth_token.startswith(" ")


# ── ClientOut con has_twilio_credentials ─────────────────


class TestClientOutByot:
    BASE_ROW = {
        "id": "c1", "name": "Test", "slug": "test", "business_type": "generic",
        "agent_name": "María", "language": "es", "voice_id": "v1",
        "greeting": "Hola", "system_prompt": "Eres un asistente",
    }

    def test_has_twilio_credentials_true(self):
        row = {
            **self.BASE_ROW,
            "twilio_account_sid": "AC12345678901234567890123456789012",
            "twilio_auth_token": "enc:encrypted_token_here",
        }
        out = client_out_from_row(row)
        assert out.has_twilio_credentials is True

    def test_has_twilio_credentials_false_when_missing(self):
        row = {**self.BASE_ROW}
        out = client_out_from_row(row)
        assert out.has_twilio_credentials is False

    def test_has_twilio_credentials_false_when_partial(self):
        row = {
            **self.BASE_ROW,
            "twilio_account_sid": "AC12345678901234567890123456789012",
            "twilio_auth_token": None,
        }
        out = client_out_from_row(row)
        assert out.has_twilio_credentials is False

    def test_credentials_not_exposed_in_output(self):
        row = {
            **self.BASE_ROW,
            "twilio_account_sid": "AC12345678901234567890123456789012",
            "twilio_auth_token": "enc:secret",
        }
        out = client_out_from_row(row)
        out_dict = out.model_dump()
        assert "twilio_account_sid" not in out_dict
        assert "twilio_auth_token" not in out_dict


# ── Phone Service: _get_twilio_client ────────────────────


class TestGetTwilioClient:
    @patch.dict("os.environ", {
        "TWILIO_ACCOUNT_SID": "ACplatform000000000000000000000000",
        "TWILIO_AUTH_TOKEN": "platformtoken00000000000000000000",
    })
    def test_uses_env_when_no_byot(self):
        # Reimportar para que use el mock de twilio
        from importlib import reload
        import api.services.phone_service as ps
        reload(ps)

        mock_client_cls = MagicMock()
        with patch.object(ps, "_get_twilio_client") as mock_get:
            # Simular el comportamiento real
            pass
        # Testeamos directamente la lógica
        with patch("twilio.rest.Client", new=mock_client_cls):
            result = ps._get_twilio_client()
            mock_client_cls.assert_called_once_with(
                "ACplatform000000000000000000000000",
                "platformtoken00000000000000000000",
            )

    def test_uses_byot_when_provided(self):
        from importlib import reload
        import api.services.phone_service as ps
        reload(ps)

        mock_client_cls = MagicMock()
        with patch("twilio.rest.Client", new=mock_client_cls):
            ps._get_twilio_client(
                "ACbyot00000000000000000000000000",
                "byottoken000000000000000000000000",
            )
            mock_client_cls.assert_called_once_with(
                "ACbyot00000000000000000000000000",
                "byottoken000000000000000000000000",
            )


# ── Phone Service: validate_twilio_credentials ──────────


class TestValidateTwilioCredentials:
    def test_valid_credentials(self):
        from importlib import reload
        import api.services.phone_service as ps
        reload(ps)

        mock_client_cls = MagicMock()
        mock_account = MagicMock()
        mock_account.status = "active"
        mock_client_cls.return_value.api.v2010.accounts.return_value.fetch.return_value = mock_account

        with patch("twilio.rest.Client", new=mock_client_cls):
            assert ps.validate_twilio_credentials("ACtest0000000000000000000000000000", "token00000000000000000000000000") is True

    def test_invalid_credentials(self):
        from importlib import reload
        import api.services.phone_service as ps
        reload(ps)

        mock_client_cls = MagicMock()
        mock_client_cls.return_value.api.v2010.accounts.return_value.fetch.side_effect = Exception("Auth failed")

        with patch("twilio.rest.Client", new=mock_client_cls):
            assert ps.validate_twilio_credentials("ACbad", "bad") is False


# ── Phone Service: get_client_twilio_creds ───────────────


class TestGetClientTwilioCreds:
    def test_returns_none_when_no_creds(self):
        from api.services.phone_service import get_client_twilio_creds
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"twilio_account_sid": None, "twilio_auth_token": None}]
        )
        sid, token = get_client_twilio_creds(sb, "client-1")
        assert sid is None
        assert token is None

    def test_returns_decrypted_creds(self):
        from api.services.phone_service import get_client_twilio_creds
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{
                "twilio_account_sid": "AC12345678901234567890123456789012",
                "twilio_auth_token": "enc:encrypted_value",
            }]
        )
        with patch("api.crypto.decrypt_value", return_value="decrypted_token"):
            sid, token = get_client_twilio_creds(sb, "client-1")
        assert sid == "AC12345678901234567890123456789012"
        assert token == "decrypted_token"


# ── Phone Service: search/purchase con BYOT ─────────────


class TestPhoneServiceByotThreading:
    def test_search_with_byot_creds(self):
        from importlib import reload
        import api.services.phone_service as ps
        reload(ps)

        mock_client_cls = MagicMock()
        mock_instance = mock_client_cls.return_value
        mock_instance.available_phone_numbers.return_value.local.list.return_value = []
        mock_instance.available_phone_numbers.return_value.mobile.list.return_value = []

        with patch("twilio.rest.Client", new=mock_client_cls):
            ps.search_available_numbers(
                "MX", account_sid="ACbyot00000000000000000000000000",
                auth_token="byottoken000000000000000000000000",
            )
            mock_client_cls.assert_called_once_with(
                "ACbyot00000000000000000000000000",
                "byottoken000000000000000000000000",
            )

    def test_purchase_with_byot_creds(self):
        from importlib import reload
        import api.services.phone_service as ps
        reload(ps)

        mock_client_cls = MagicMock()
        mock_incoming = MagicMock()
        mock_incoming.sid = "PN123"
        mock_incoming.phone_number = "+5215551234567"
        mock_client_cls.return_value.incoming_phone_numbers.create.return_value = mock_incoming

        with patch("twilio.rest.Client", new=mock_client_cls):
            sid, num = ps.purchase_phone_number(
                "+5215551234567",
                account_sid="ACbyot00000000000000000000000000",
                auth_token="byottoken000000000000000000000000",
            )
            assert sid == "PN123"
            mock_client_cls.assert_called_once_with(
                "ACbyot00000000000000000000000000",
                "byottoken000000000000000000000000",
            )
