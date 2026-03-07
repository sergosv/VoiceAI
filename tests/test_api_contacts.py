"""Tests para rutas CRUD de contactos."""

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

SAMPLE_CONTACT_ROW = {
    "id": "contact-1",
    "client_id": "client-id-123",
    "name": "Juan",
    "phone": "+5219991234567",
    "email": None,
    "source": "manual",
    "notes": None,
    "tags": [],
    "call_count": 0,
    "last_call_at": None,
    "lead_score": 0,
    "summary": None,
    "preferences": {},
    "key_facts": [],
    "last_interaction_channel": None,
    "average_sentiment": None,
    "first_interaction_at": None,
    "created_at": "2026-01-01T00:00:00",
    "updated_at": None,
}


class TestListContacts:
    @patch("api.routes.contacts.get_supabase")
    def test_list_contacts_client(self, mock_sb):
        """Client lista sus contactos."""
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        (mock_inst.table.return_value.select.return_value
         .order.return_value.eq.return_value.range.return_value
         .execute.return_value.data) = [SAMPLE_CONTACT_ROW]
        mock_sb.return_value = mock_inst

        resp = client.get("/api/contacts")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "Juan"
        app.dependency_overrides.clear()


class TestCreateContact:
    @patch("agent.phone_utils.normalize_phone", side_effect=lambda x: x)
    @patch("api.routes.contacts.get_supabase")
    def test_create_contact(self, mock_sb, mock_phone):
        """Crea un contacto con teléfono, retorna 201."""
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        # Mock: check de duplicado (no existe)
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.eq.return_value.limit.return_value
         .execute.return_value.data) = []
        # Mock: insert
        mock_inst.table.return_value.insert.return_value.execute.return_value.data = [
            SAMPLE_CONTACT_ROW
        ]
        mock_sb.return_value = mock_inst

        resp = client.post(
            "/api/contacts",
            json={"phone": "+5219991234567", "name": "Juan"},
        )
        assert resp.status_code == 201
        assert resp.json()["phone"] == "+5219991234567"
        app.dependency_overrides.clear()

    @patch("agent.phone_utils.normalize_phone", side_effect=lambda x: x)
    @patch("api.routes.contacts.get_supabase")
    def test_create_contact_duplicate(self, mock_sb, mock_phone):
        """Retorna 409 si el contacto ya existe."""
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        # Mock: check de duplicado (ya existe)
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.eq.return_value.limit.return_value
         .execute.return_value.data) = [{"id": "existing-contact"}]
        mock_sb.return_value = mock_inst

        resp = client.post(
            "/api/contacts",
            json={"phone": "+5219991234567", "name": "Juan"},
        )
        assert resp.status_code == 409
        app.dependency_overrides.clear()


class TestGetContact:
    @patch("api.routes.contacts.get_supabase")
    def test_get_contact(self, mock_sb):
        """Obtiene un contacto por ID."""
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [SAMPLE_CONTACT_ROW]
        mock_sb.return_value = mock_inst

        resp = client.get("/api/contacts/contact-1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "contact-1"
        app.dependency_overrides.clear()

    @patch("api.routes.contacts.get_supabase")
    def test_get_contact_forbidden(self, mock_sb):
        """403 si el contacto es de otro cliente."""
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        other_contact = {**SAMPLE_CONTACT_ROW, "client_id": "other-client-id"}
        mock_inst = MagicMock()
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [other_contact]
        mock_sb.return_value = mock_inst

        resp = client.get("/api/contacts/contact-1")
        assert resp.status_code == 403
        app.dependency_overrides.clear()


class TestUpdateContact:
    @patch("api.routes.contacts.get_supabase")
    def test_update_contact(self, mock_sb):
        """Actualiza el nombre de un contacto."""
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        updated_row = {**SAMPLE_CONTACT_ROW, "name": "Juan Carlos"}
        mock_inst = MagicMock()
        # Mock: verificar acceso (select client_id)
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [
            {"client_id": "client-id-123"}
        ]
        # Mock: update
        (mock_inst.table.return_value.update.return_value
         .eq.return_value.execute.return_value.data) = [updated_row]
        mock_sb.return_value = mock_inst

        resp = client.patch(
            "/api/contacts/contact-1",
            json={"name": "Juan Carlos"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Juan Carlos"
        app.dependency_overrides.clear()


class TestDeleteContact:
    @patch("api.routes.contacts.get_supabase")
    def test_delete_contact(self, mock_sb):
        """Elimina un contacto."""
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        # Mock: verificar que existe y acceso
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [
            {"client_id": "client-id-123", "phone": "+5219991234567"}
        ]
        # Mock: delete cascades (calls, appointments, campaign_calls, contacts)
        mock_inst.table.return_value.delete.return_value.eq.return_value.or_.return_value.execute.return_value.data = []
        mock_inst.table.return_value.delete.return_value.eq.return_value.execute.return_value.data = []
        mock_sb.return_value = mock_inst

        resp = client.delete("/api/contacts/contact-1")
        assert resp.status_code == 200
        assert "eliminado" in resp.json()["message"].lower()
        app.dependency_overrides.clear()

    @patch("api.routes.contacts.get_supabase")
    def test_delete_contact_not_found(self, mock_sb):
        """404 si el contacto no existe."""
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = []
        mock_sb.return_value = mock_inst

        resp = client.delete("/api/contacts/nonexistent")
        assert resp.status_code == 404
        app.dependency_overrides.clear()
