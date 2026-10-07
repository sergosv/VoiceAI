"""Tests para rutas de clientes."""

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
    role="client", client_id="client-id-123",
)

SAMPLE_CLIENT_ROW = {
    "id": "client-id-123",
    "name": "Dr. García",
    "slug": "dr-garcia",
    "business_type": "dental",
    "agent_name": "María",
    "language": "es",
    "voice_id": "voice-abc",
    "greeting": "Hola",
    "system_prompt": "Eres María",
    "file_search_store_id": None,
    "file_search_store_name": None,
    "phone_number": "+529994890531",
    "max_call_duration_seconds": 300,
    "tools_enabled": ["search_knowledge"],
    "transfer_number": None,
    "business_hours": None,
    "after_hours_message": None,
    "is_active": True,
    "owner_email": "doc@test.com",
    "monthly_minutes_limit": 500,
    "created_at": "2026-02-01T00:00:00+00:00",
    "updated_at": "2026-02-01T00:00:00+00:00",
}


class TestListClients:
    @patch("api.routes.clients.get_supabase")
    def test_admin_sees_all(self, mock_sb):
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER
        mock_inst = MagicMock()
        mock_inst.table.return_value.select.return_value.order.return_value.execute.return_value.data = [
            SAMPLE_CLIENT_ROW
        ]
        mock_sb.return_value = mock_inst

        resp = client.get("/api/clients")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "Dr. García"
        app.dependency_overrides.clear()

    @patch("api.routes.clients.get_supabase")
    def test_client_sees_own(self, mock_sb):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        (mock_inst.table.return_value.select.return_value
         .order.return_value.eq.return_value.execute.return_value.data) = [SAMPLE_CLIENT_ROW]
        mock_sb.return_value = mock_inst

        resp = client.get("/api/clients")
        assert resp.status_code == 200
        app.dependency_overrides.clear()


class TestGetClient:
    @patch("api.routes.clients.get_supabase")
    def test_get_own_client(self, mock_sb):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [SAMPLE_CLIENT_ROW]
        mock_sb.return_value = mock_inst

        resp = client.get("/api/clients/client-id-123")
        assert resp.status_code == 200
        assert resp.json()["slug"] == "dr-garcia"
        app.dependency_overrides.clear()

    def test_client_cannot_access_other(self):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        resp = client.get("/api/clients/other-client-id")
        assert resp.status_code == 403
        app.dependency_overrides.clear()


class TestUpdateClient:
    @patch("api.routes.clients.get_supabase")
    def test_client_can_update_greeting(self, mock_sb):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        updated_row = {**SAMPLE_CLIENT_ROW, "greeting": "Nuevo saludo"}
        mock_inst = MagicMock()
        (mock_inst.table.return_value.update.return_value
         .eq.return_value.execute.return_value.data) = [updated_row]
        mock_sb.return_value = mock_inst

        resp = client.patch("/api/clients/client-id-123", json={"greeting": "Nuevo saludo"})
        assert resp.status_code == 200
        assert resp.json()["greeting"] == "Nuevo saludo"
        app.dependency_overrides.clear()

    def test_client_cannot_update_is_active(self):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        resp = client.patch("/api/clients/client-id-123", json={"is_active": False})
        assert resp.status_code == 403
        app.dependency_overrides.clear()


class TestCreateClient:
    """Tests del flujo completo de creación de cliente con user Auth + email."""

    def _override_admin(self):
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER

    def _make_sb_mock(
        self,
        *,
        slug_taken: bool = False,
        email_taken: bool = False,
    ):
        """Mock del cliente supabase para pre-validaciones y inserts."""
        sb = MagicMock()

        def table_side(name):
            t = MagicMock()
            if name == "clients":
                chain = t.select.return_value.eq.return_value.limit.return_value.execute
                chain.return_value.data = [{"id": "x"}] if slug_taken else []
                t.delete.return_value.eq.return_value.execute.return_value.data = []
            elif name == "users":
                chain = t.select.return_value.eq.return_value.limit.return_value.execute
                chain.return_value.data = [{"id": "u"}] if email_taken else []
            elif name == "agents":
                t.insert.return_value.execute.return_value.data = [{"id": "agent-id"}]
                t.delete.return_value.eq.return_value.execute.return_value.data = []
            return t

        sb.table.side_effect = table_side
        return sb

    @patch("api.routes.clients.log_audit")
    @patch("api.routes.clients.dispatch_event")
    @patch("api.routes.clients.send_welcome_email")
    @patch("api.routes.clients.create_owner_user")
    @patch("api.routes.clients.create_client_in_db")
    @patch("api.routes.clients.create_gemini_store")
    @patch("api.routes.clients.get_supabase")
    def test_full_flow_creates_user_and_sends_email(
        self, mock_sb, mock_store, mock_create_db, mock_create_user,
        mock_email, mock_dispatch, mock_audit,
    ):
        self._override_admin()
        mock_sb.return_value = self._make_sb_mock()
        mock_store.return_value = ("stores/abc", "store-dr-garcia")
        mock_create_db.return_value = SAMPLE_CLIENT_ROW
        mock_create_user.return_value = {"id": "user-id"}

        async def _noop(*a, **kw): return None
        mock_email.side_effect = _noop
        mock_dispatch.side_effect = _noop

        resp = client.post("/api/clients", json={
            "name": "Dr. García",
            "slug": "dr-garcia",
            "business_type": "dental",
            "agent_name": "María",
            "voice_key": "es_female_warm",
            "language": "es",
            "owner_email": "doc@test.com",
            "send_welcome_email": True,
        })
        assert resp.status_code == 201, resp.text
        mock_create_user.assert_called_once()
        mock_email.assert_awaited_once()
        mock_audit.assert_called_once()
        assert mock_audit.call_args.kwargs["action"] == "client.created"
        app.dependency_overrides.clear()

    @patch("api.routes.clients.get_supabase")
    def test_slug_collision_returns_409(self, mock_sb):
        self._override_admin()
        mock_sb.return_value = self._make_sb_mock(slug_taken=True)
        resp = client.post("/api/clients", json={
            "name": "Otro", "slug": "dr-garcia",
        })
        assert resp.status_code == 409
        assert "slug" in resp.json()["detail"].lower()
        app.dependency_overrides.clear()

    @patch("api.routes.clients.get_supabase")
    def test_email_collision_returns_409(self, mock_sb):
        self._override_admin()
        mock_sb.return_value = self._make_sb_mock(email_taken=True)
        resp = client.post("/api/clients", json={
            "name": "Nuevo", "slug": "nuevo",
            "owner_email": "doc@test.com",
        })
        assert resp.status_code == 409
        assert "email" in resp.json()["detail"].lower()
        app.dependency_overrides.clear()

    @patch("api.routes.clients.delete_gemini_store")
    @patch("api.routes.clients.delete_owner_user")
    @patch("api.routes.clients.log_audit")
    @patch("api.routes.clients.dispatch_event")
    @patch("api.routes.clients.send_welcome_email")
    @patch("api.routes.clients.create_owner_user")
    @patch("api.routes.clients.create_client_in_db")
    @patch("api.routes.clients.create_gemini_store")
    @patch("api.routes.clients.get_supabase")
    def test_auth_failure_rolls_back_gemini_and_db(
        self, mock_sb, mock_store, mock_create_db, mock_create_user,
        mock_email, mock_dispatch, mock_audit, mock_del_user, mock_del_store,
    ):
        """Si falla la creación del user Auth, se rollbackea Gemini store + DB.

        El delete_owner_user NO se llama porque create_owner_user ya limpia
        su propio Auth user internamente antes de lanzar.
        """
        self._override_admin()
        mock_sb.return_value = self._make_sb_mock()
        mock_store.return_value = ("stores/abc", "store-x")
        mock_create_db.return_value = SAMPLE_CLIENT_ROW
        mock_create_user.side_effect = ValueError("Auth failed")

        resp = client.post("/api/clients", json={
            "name": "X", "slug": "x-slug",
            "owner_email": "new@test.com",
        })
        assert resp.status_code == 400
        mock_del_store.assert_called_once()
        # delete_owner_user NO se llama porque create_owner_user limpia el suyo
        mock_del_user.assert_not_called()
        app.dependency_overrides.clear()

    @patch("api.routes.clients.log_audit")
    @patch("api.routes.clients.dispatch_event")
    @patch("api.routes.clients.send_welcome_email")
    @patch("api.routes.clients.create_owner_user")
    @patch("api.routes.clients.create_client_in_db")
    @patch("api.routes.clients.create_gemini_store")
    @patch("api.routes.clients.get_supabase")
    def test_skip_email_when_flag_off(
        self, mock_sb, mock_store, mock_create_db, mock_create_user,
        mock_email, mock_dispatch, mock_audit,
    ):
        self._override_admin()
        mock_sb.return_value = self._make_sb_mock()
        mock_store.return_value = ("stores/abc", "store-x")
        mock_create_db.return_value = SAMPLE_CLIENT_ROW
        mock_create_user.return_value = {"id": "user-id"}

        async def _noop(*a, **kw): return None
        mock_dispatch.side_effect = _noop

        resp = client.post("/api/clients", json={
            "name": "X", "slug": "x-slug",
            "owner_email": "silent@test.com",
            "send_welcome_email": False,
        })
        assert resp.status_code == 201
        mock_create_user.assert_called_once()
        mock_email.assert_not_called()
        app.dependency_overrides.clear()

    @patch("api.routes.clients.log_audit")
    @patch("api.routes.clients.dispatch_event")
    @patch("api.routes.clients.create_client_in_db")
    @patch("api.routes.clients.create_gemini_store")
    @patch("api.routes.clients.get_supabase")
    def test_without_owner_email_skips_user_creation(
        self, mock_sb, mock_store, mock_create_db, mock_dispatch, mock_audit,
    ):
        self._override_admin()
        mock_sb.return_value = self._make_sb_mock()
        mock_store.return_value = ("stores/abc", "store-x")
        mock_create_db.return_value = SAMPLE_CLIENT_ROW

        async def _noop(*a, **kw): return None
        mock_dispatch.side_effect = _noop

        resp = client.post("/api/clients", json={
            "name": "No owner", "slug": "no-owner",
        })
        assert resp.status_code == 201
        app.dependency_overrides.clear()


class TestDeleteClient:
    def test_client_cannot_delete(self):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        resp = client.delete("/api/clients/client-id-123")
        assert resp.status_code == 403
        app.dependency_overrides.clear()

    @patch("api.routes.clients.get_supabase")
    def test_admin_can_delete(self, mock_sb):
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER
        mock_inst = MagicMock()
        (mock_inst.table.return_value.delete.return_value
         .eq.return_value.execute.return_value.data) = [SAMPLE_CLIENT_ROW]
        mock_sb.return_value = mock_inst

        resp = client.delete("/api/clients/client-id-123")
        assert resp.status_code == 200
        app.dependency_overrides.clear()
