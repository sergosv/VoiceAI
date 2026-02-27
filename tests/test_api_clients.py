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
