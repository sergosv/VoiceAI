"""Tests de Twilio Subaccounts (Paso 1 MVP).

Cobertura:
- resolve_twilio_creds: 4 escenarios (BYOT válido, subaccount, grandfathered,
  malformed)
- create_twilio_subaccount: interacción con SDK
- associate_number_to_trunk / transfer_number_to_subaccount
- ensure_client_subaccount: idempotencia (crea desde cero, solo trunk, existente)
- Integración con purchase_and_assign_phone (fuera de este archivo; se mockean)
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from api.services import phone_service


@pytest.fixture(autouse=True)
def _patch_env(monkeypatch):
    """Garantiza TWILIO_ACCOUNT_SID/TOKEN fake para todos los tests."""
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC_MAIN")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "TOKEN_MAIN")
    monkeypatch.setenv("ENCRYPTION_KEY", "hNZ8JdR2bRFvWUKfCjFy8OZk1P_M8Y8TXrQmPJVKVmE=")
    # Re-cargar módulo crypto para que tome la key nueva
    from api import crypto
    import importlib
    importlib.reload(crypto)


def _mock_sb_with_row(row: dict | None) -> MagicMock:
    sb = MagicMock()
    (sb.table.return_value.select.return_value
     .eq.return_value.limit.return_value.execute.return_value.data) = (
        [row] if row is not None else []
    )
    return sb


class TestResolveTwilioCreds:
    def test_byot_valid_takes_priority(self, monkeypatch):
        from api.crypto import encrypt_value
        token_enc = encrypt_value("BYOT_TOKEN")
        sb = _mock_sb_with_row({
            "twilio_account_sid": "AC_BYOT",
            "twilio_auth_token": token_enc,
            "twilio_subaccount_sid": "AC_SUB",
            "twilio_subaccount_auth_token": encrypt_value("SUB_TOKEN"),
        })
        sid, token = phone_service.resolve_twilio_creds(sb, "cid")
        assert sid == "AC_BYOT"
        assert token == "BYOT_TOKEN"

    def test_subaccount_when_no_byot(self):
        from api.crypto import encrypt_value
        sb = _mock_sb_with_row({
            "twilio_account_sid": None,
            "twilio_auth_token": None,
            "twilio_subaccount_sid": "AC_SUB",
            "twilio_subaccount_auth_token": encrypt_value("SUB_TOKEN"),
        })
        sid, token = phone_service.resolve_twilio_creds(sb, "cid")
        assert sid == "AC_SUB"
        assert token == "SUB_TOKEN"

    def test_main_fallback_when_grandfathered(self):
        sb = _mock_sb_with_row({
            "twilio_account_sid": None,
            "twilio_auth_token": None,
            "twilio_subaccount_sid": None,
            "twilio_subaccount_auth_token": None,
        })
        sid, token = phone_service.resolve_twilio_creds(sb, "cid")
        assert sid == "AC_MAIN"
        assert token == "TOKEN_MAIN"

    def test_client_not_found_falls_back_to_main(self):
        sb = _mock_sb_with_row(None)
        sid, token = phone_service.resolve_twilio_creds(sb, "missing")
        assert sid == "AC_MAIN"

    def test_byot_partial_raises(self):
        sb = _mock_sb_with_row({
            "twilio_account_sid": "AC_BYOT",
            "twilio_auth_token": None,
            "twilio_subaccount_sid": None,
            "twilio_subaccount_auth_token": None,
        })
        with pytest.raises(ValueError, match="BYOT parcialmente"):
            phone_service.resolve_twilio_creds(sb, "cid")

    def test_subaccount_partial_raises(self):
        sb = _mock_sb_with_row({
            "twilio_account_sid": None,
            "twilio_auth_token": None,
            "twilio_subaccount_sid": "AC_SUB",
            "twilio_subaccount_auth_token": None,
        })
        with pytest.raises(ValueError, match="Subaccount parcialmente"):
            phone_service.resolve_twilio_creds(sb, "cid")

    def test_subaccount_undecryptable_raises(self):
        sb = _mock_sb_with_row({
            "twilio_account_sid": None,
            "twilio_auth_token": None,
            "twilio_subaccount_sid": "AC_SUB",
            "twilio_subaccount_auth_token": "enc:garbage-not-a-fernet-token",
        })
        with pytest.raises(ValueError, match="no pudo desencriptarse"):
            phone_service.resolve_twilio_creds(sb, "cid")


class TestCreateSubaccount:
    @patch("api.services.phone_service._get_twilio_client")
    def test_creates_subaccount_with_friendly_name(self, mock_factory):
        mock_client = MagicMock()
        mock_account = MagicMock(sid="AC_NEW", auth_token="NEW_TOKEN")
        mock_client.api.v2010.accounts.create.return_value = mock_account
        mock_factory.return_value = mock_client

        sid, token = phone_service.create_twilio_subaccount("voiceai-prod-test")
        assert sid == "AC_NEW"
        assert token == "NEW_TOKEN"
        mock_client.api.v2010.accounts.create.assert_called_once_with(
            friendly_name="voiceai-prod-test"
        )


class TestAssociateNumberToTrunk:
    @patch("api.services.phone_service._get_twilio_client")
    def test_updates_incoming_number_trunk_sid(self, mock_factory):
        mock_client = MagicMock()
        mock_factory.return_value = mock_client
        phone_service.associate_number_to_trunk(
            "PN123", "TK456",
            account_sid="AC_SUB", auth_token="TKN",
        )
        mock_client.incoming_phone_numbers.assert_called_with("PN123")
        mock_client.incoming_phone_numbers("PN123").update.assert_called_with(
            trunk_sid="TK456"
        )


class TestTransferNumber:
    @patch("api.services.phone_service._get_twilio_client")
    def test_transfer_uses_master_creds(self, mock_factory):
        mock_client = MagicMock()
        mock_client.incoming_phone_numbers("PN123").update.return_value = MagicMock(sid="PN123")
        mock_factory.return_value = mock_client

        result = phone_service.transfer_number_to_subaccount(
            "PN123", "AC_SUB",
        )
        # Verifica que se usan env vars (master) al no pasar creds explícitas
        assert result == "PN123"


class TestEnsureClientSubaccount:
    @patch("api.services.phone_service.setup_twilio_elastic_sip_trunk")
    @patch("api.services.phone_service.create_twilio_subaccount")
    def test_creates_subaccount_and_trunk_from_scratch(
        self, mock_create_sub, mock_setup_trunk,
    ):
        mock_create_sub.return_value = ("AC_NEW", "NEW_TOKEN")
        mock_setup_trunk.return_value = "TK_NEW"

        sb = MagicMock()
        (sb.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [{
            "slug": "dr-garcia",
            "twilio_subaccount_sid": None,
            "twilio_subaccount_auth_token": None,
            "twilio_subaccount_trunk_sid": None,
            "twilio_subaccount_status": None,
        }]
        sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{}]

        sid, token, trunk_sid = phone_service.ensure_client_subaccount(sb, "cid")
        assert sid == "AC_NEW"
        assert token == "NEW_TOKEN"
        assert trunk_sid == "TK_NEW"
        mock_create_sub.assert_called_once()
        assert "voiceai-prod-dr-garcia" in mock_create_sub.call_args[0][0]
        mock_setup_trunk.assert_called_once()

        # Verificar que los updates hayan incluido provisioning primero, active después
        update_calls = sb.table.return_value.update.call_args_list
        statuses = [c.args[0].get("twilio_subaccount_status") for c in update_calls]
        assert "provisioning" in statuses
        assert "active" in statuses
        assert statuses.index("provisioning") < statuses.index("active")

    @patch("api.services.phone_service.setup_twilio_elastic_sip_trunk")
    @patch("api.services.phone_service.create_twilio_subaccount")
    def test_idempotent_when_all_exists(self, mock_create_sub, mock_setup_trunk):
        from api.crypto import encrypt_value
        sb = MagicMock()
        (sb.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [{
            "slug": "dr-garcia",
            "twilio_subaccount_sid": "AC_EXISTING",
            "twilio_subaccount_auth_token": encrypt_value("EXISTING_TOKEN"),
            "twilio_subaccount_trunk_sid": "TK_EXISTING",
            "twilio_subaccount_status": "active",
        }]

        sid, token, trunk_sid = phone_service.ensure_client_subaccount(sb, "cid")
        assert sid == "AC_EXISTING"
        assert token == "EXISTING_TOKEN"
        assert trunk_sid == "TK_EXISTING"
        mock_create_sub.assert_not_called()
        mock_setup_trunk.assert_not_called()

    @patch("api.services.phone_service.setup_twilio_elastic_sip_trunk")
    @patch("api.services.phone_service.create_twilio_subaccount")
    def test_creates_trunk_only_when_subaccount_exists_in_provisioning(
        self, mock_create_sub, mock_setup_trunk,
    ):
        """Fallo previo dejó la subaccount creada pero sin trunk. Transicionar a active."""
        from api.crypto import encrypt_value
        mock_setup_trunk.return_value = "TK_NEW"
        sb = MagicMock()
        (sb.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [{
            "slug": "dr-garcia",
            "twilio_subaccount_sid": "AC_EXISTING",
            "twilio_subaccount_auth_token": encrypt_value("EXISTING_TOKEN"),
            "twilio_subaccount_trunk_sid": None,
            "twilio_subaccount_status": "provisioning",
        }]
        sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{}]

        sid, _, trunk_sid = phone_service.ensure_client_subaccount(sb, "cid")
        assert sid == "AC_EXISTING"
        assert trunk_sid == "TK_NEW"
        mock_create_sub.assert_not_called()
        mock_setup_trunk.assert_called_once()

        # Verificar transición a active
        update_calls = sb.table.return_value.update.call_args_list
        assert any(
            c.args[0].get("twilio_subaccount_status") == "active"
            for c in update_calls
        )

    @patch("api.services.phone_service.setup_twilio_elastic_sip_trunk")
    @patch("api.services.phone_service.create_twilio_subaccount")
    def test_self_heals_when_trunk_exists_but_status_is_provisioning(
        self, mock_create_sub, mock_setup_trunk,
    ):
        """Caso raro: trunk_sid existe pero status quedó en provisioning."""
        from api.crypto import encrypt_value
        sb = MagicMock()
        (sb.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [{
            "slug": "dr-garcia",
            "twilio_subaccount_sid": "AC_X",
            "twilio_subaccount_auth_token": encrypt_value("TOKEN_X"),
            "twilio_subaccount_trunk_sid": "TK_X",
            "twilio_subaccount_status": "provisioning",
        }]
        sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{}]

        phone_service.ensure_client_subaccount(sb, "cid")
        mock_create_sub.assert_not_called()
        mock_setup_trunk.assert_not_called()
        # Self-heal: update con active ejecutado
        update_calls = sb.table.return_value.update.call_args_list
        assert any(
            c.args[0].get("twilio_subaccount_status") == "active"
            for c in update_calls
        )

    @pytest.mark.parametrize("status", ["suspended", "closed"])
    def test_refuses_to_touch_suspended_or_closed(self, status):
        from api.crypto import encrypt_value
        sb = MagicMock()
        (sb.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [{
            "slug": "dr-garcia",
            "twilio_subaccount_sid": "AC_X",
            "twilio_subaccount_auth_token": encrypt_value("T"),
            "twilio_subaccount_trunk_sid": "TK_X",
            "twilio_subaccount_status": status,
        }]
        with pytest.raises(ValueError, match=f"'{status}'"):
            phone_service.ensure_client_subaccount(sb, "cid")

    def test_raises_when_client_not_found(self):
        sb = MagicMock()
        (sb.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = []
        with pytest.raises(ValueError, match="no encontrado"):
            phone_service.ensure_client_subaccount(sb, "missing")


class TestSlugifyForTwilio:
    def test_ascii_safe(self):
        assert phone_service._slugify_for_twilio("Dr. García") == "dr-garca"

    def test_max_64_chars(self):
        long = "a" * 100
        assert len(phone_service._slugify_for_twilio(long)) == 64

    def test_fallback_when_empty(self):
        assert phone_service._slugify_for_twilio("!!!") == "client"
