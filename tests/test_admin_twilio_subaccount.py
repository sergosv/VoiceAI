"""Tests para endpoints admin de Twilio Subaccount (suspend/reactivate)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.middleware.auth import CurrentUser, get_current_user

client = TestClient(app)

ADMIN_USER = CurrentUser(
    id="admin-uuid", auth_user_id="auth-admin", email="admin@test.com",
    role="admin", client_id=None,
)
CLIENT_USER = CurrentUser(
    id="client-uuid", auth_user_id="auth-client", email="cli@test.com",
    role="client", client_id="client-id-xyz",
)


def _mock_sb_with_client(row: dict | None):
    sb = MagicMock()

    def table_side(name):
        t = MagicMock()
        if name == "clients":
            (t.select.return_value.eq.return_value.limit.return_value
             .execute.return_value.data) = [row] if row else []
            t.update.return_value.eq.return_value.execute.return_value.data = [{}]
        return t

    sb.table.side_effect = table_side
    return sb


class TestAuthorization:
    """Verifica que los endpoints requieran rol admin."""

    def test_suspend_rejects_non_admin(self):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        resp = client.post("/api/admin/clients/cid/twilio-subaccount/suspend", json={})
        assert resp.status_code == 403
        app.dependency_overrides.clear()

    def test_suspend_rejects_unauthenticated(self):
        resp = client.post("/api/admin/clients/cid/twilio-subaccount/suspend", json={})
        assert resp.status_code in (401, 403)

    def test_reactivate_rejects_non_admin(self):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        resp = client.post("/api/admin/clients/cid/twilio-subaccount/reactivate")
        assert resp.status_code == 403
        app.dependency_overrides.clear()


class TestSuspend:
    @patch("api.routes.admin.log_audit")
    @patch("api.services.phone_service.update_subaccount_twilio_status")
    @patch("api.routes.admin.get_supabase")
    def test_suspends_active_subaccount(self, mock_sb_fn, mock_update, mock_audit):
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER
        mock_sb_fn.return_value = _mock_sb_with_client({
            "twilio_subaccount_sid": "AC_SUB",
            "twilio_subaccount_status": "active",
            "name": "Dr. García",
        })
        mock_update.return_value = "suspended"

        resp = client.post(
            "/api/admin/clients/cid/twilio-subaccount/suspend",
            json={"reason": "Cliente solicitó pausa"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "suspended"
        assert resp.json()["subaccount_sid"] == "AC_SUB"
        mock_update.assert_called_once_with("AC_SUB", "suspended")

        # Audit log debe incluir motivo y nombre del cliente
        mock_audit.assert_called_once()
        kwargs = mock_audit.call_args.kwargs
        assert kwargs["action"] == "twilio_subaccount.suspended"
        assert kwargs["user_id"] == ADMIN_USER.id
        assert kwargs["client_id"] == "cid"
        assert kwargs["details"]["reason"] == "Cliente solicitó pausa"
        assert kwargs["details"]["client_name"] == "Dr. García"
        assert kwargs["details"]["previous_status"] == "active"
        app.dependency_overrides.clear()

    @patch("api.routes.admin.get_supabase")
    def test_returns_404_when_client_not_found(self, mock_sb_fn):
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER
        mock_sb_fn.return_value = _mock_sb_with_client(None)
        resp = client.post(
            "/api/admin/clients/missing/twilio-subaccount/suspend", json={},
        )
        assert resp.status_code == 404
        app.dependency_overrides.clear()

    @patch("api.routes.admin.get_supabase")
    def test_returns_400_when_no_subaccount(self, mock_sb_fn):
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER
        mock_sb_fn.return_value = _mock_sb_with_client({
            "twilio_subaccount_sid": None,
            "twilio_subaccount_status": None,
            "name": "X",
        })
        resp = client.post(
            "/api/admin/clients/cid/twilio-subaccount/suspend", json={},
        )
        assert resp.status_code == 400
        assert "subaccount" in resp.json()["detail"].lower()
        app.dependency_overrides.clear()

    @patch("api.routes.admin.get_supabase")
    def test_returns_409_when_closed(self, mock_sb_fn):
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER
        mock_sb_fn.return_value = _mock_sb_with_client({
            "twilio_subaccount_sid": "AC_SUB",
            "twilio_subaccount_status": "closed",
            "name": "X",
        })
        resp = client.post(
            "/api/admin/clients/cid/twilio-subaccount/suspend", json={},
        )
        assert resp.status_code == 409
        app.dependency_overrides.clear()

    @patch("api.services.phone_service.update_subaccount_twilio_status")
    @patch("api.routes.admin.get_supabase")
    def test_idempotent_when_already_suspended(self, mock_sb_fn, mock_update):
        """Suspender una subaccount ya suspendida no debe llamar a Twilio."""
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER
        mock_sb_fn.return_value = _mock_sb_with_client({
            "twilio_subaccount_sid": "AC_SUB",
            "twilio_subaccount_status": "suspended",
            "name": "X",
        })
        resp = client.post(
            "/api/admin/clients/cid/twilio-subaccount/suspend", json={},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "suspended"
        mock_update.assert_not_called()
        app.dependency_overrides.clear()


class TestReactivate:
    @patch("api.routes.admin.log_audit")
    @patch("api.services.phone_service.update_subaccount_twilio_status")
    @patch("api.routes.admin.get_supabase")
    def test_reactivates_suspended_subaccount(self, mock_sb_fn, mock_update, mock_audit):
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER
        mock_sb_fn.return_value = _mock_sb_with_client({
            "twilio_subaccount_sid": "AC_SUB",
            "twilio_subaccount_status": "suspended",
            "name": "Dr. García",
        })
        mock_update.return_value = "active"

        resp = client.post("/api/admin/clients/cid/twilio-subaccount/reactivate")
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"
        mock_update.assert_called_once_with("AC_SUB", "active")
        mock_audit.assert_called_once()
        assert mock_audit.call_args.kwargs["action"] == "twilio_subaccount.reactivated"
        app.dependency_overrides.clear()

    @patch("api.routes.admin.get_supabase")
    def test_returns_409_when_closed(self, mock_sb_fn):
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER
        mock_sb_fn.return_value = _mock_sb_with_client({
            "twilio_subaccount_sid": "AC_SUB",
            "twilio_subaccount_status": "closed",
            "name": "X",
        })
        resp = client.post("/api/admin/clients/cid/twilio-subaccount/reactivate")
        assert resp.status_code == 409
        app.dependency_overrides.clear()

    @patch("api.services.phone_service.update_subaccount_twilio_status")
    @patch("api.routes.admin.get_supabase")
    def test_idempotent_when_already_active(self, mock_sb_fn, mock_update):
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER
        mock_sb_fn.return_value = _mock_sb_with_client({
            "twilio_subaccount_sid": "AC_SUB",
            "twilio_subaccount_status": "active",
            "name": "X",
        })
        resp = client.post("/api/admin/clients/cid/twilio-subaccount/reactivate")
        assert resp.status_code == 200
        mock_update.assert_not_called()
        app.dependency_overrides.clear()

    @patch("api.services.phone_service.update_subaccount_twilio_status")
    @patch("api.routes.admin.get_supabase")
    def test_502_when_twilio_api_fails(self, mock_sb_fn, mock_update):
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER
        mock_sb_fn.return_value = _mock_sb_with_client({
            "twilio_subaccount_sid": "AC_SUB",
            "twilio_subaccount_status": "suspended",
            "name": "X",
        })
        mock_update.side_effect = RuntimeError("Twilio API 500")
        resp = client.post("/api/admin/clients/cid/twilio-subaccount/reactivate")
        assert resp.status_code == 502
        app.dependency_overrides.clear()
