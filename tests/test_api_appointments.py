"""Tests para rutas CRUD de citas."""

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

SAMPLE_APPOINTMENT_ROW = {
    "id": "apt-1",
    "client_id": "client-id-123",
    "contact_id": None,
    "call_id": None,
    "title": "Cita - Juan",
    "description": "Checkup",
    "start_time": "2026-03-10T10:00:00",
    "end_time": "2026-03-10T11:00:00",
    "status": "confirmed",
    "google_event_id": None,
    "created_at": "2026-01-01T00:00:00",
    "updated_at": None,
}


class TestListAppointments:
    @patch("api.routes.appointments.get_supabase")
    def test_list_appointments(self, mock_sb):
        """Client lista sus citas."""
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        (mock_inst.table.return_value.select.return_value
         .order.return_value.eq.return_value.range.return_value
         .execute.return_value.data) = [SAMPLE_APPOINTMENT_ROW]
        mock_sb.return_value = mock_inst

        resp = client.get("/api/appointments")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["title"] == "Cita - Juan"
        app.dependency_overrides.clear()


class TestCreateAppointment:
    @patch("api.routes.appointments.get_supabase")
    def test_create_appointment(self, mock_sb):
        """Crea una cita, retorna 201."""
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        # Mock: check de conflictos (sin conflictos)
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.eq.return_value.lt.return_value
         .gt.return_value.execute.return_value.data) = []
        # Mock: insert
        mock_inst.table.return_value.insert.return_value.execute.return_value.data = [
            SAMPLE_APPOINTMENT_ROW
        ]
        mock_sb.return_value = mock_inst

        resp = client.post(
            "/api/appointments",
            json={
                "title": "Cita - Juan",
                "description": "Checkup",
                "start_time": "2026-03-10T10:00:00",
                "end_time": "2026-03-10T11:00:00",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["title"] == "Cita - Juan"
        app.dependency_overrides.clear()

    @patch("api.routes.appointments.get_supabase")
    def test_create_appointment_conflict(self, mock_sb):
        """Retorna 409 si hay conflicto de horario."""
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        # Mock: check de conflictos (hay conflicto)
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.eq.return_value.lt.return_value
         .gt.return_value.execute.return_value.data) = [{"id": "existing-apt"}]
        mock_sb.return_value = mock_inst

        resp = client.post(
            "/api/appointments",
            json={
                "title": "Otra cita",
                "start_time": "2026-03-10T10:30:00",
                "end_time": "2026-03-10T11:30:00",
            },
        )
        assert resp.status_code == 409
        app.dependency_overrides.clear()


class TestGetAppointment:
    @patch("api.routes.appointments.get_supabase")
    def test_get_appointment(self, mock_sb):
        """Obtiene una cita por ID."""
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [
            SAMPLE_APPOINTMENT_ROW
        ]
        mock_sb.return_value = mock_inst

        resp = client.get("/api/appointments/apt-1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "apt-1"
        app.dependency_overrides.clear()

    @patch("api.routes.appointments.get_supabase")
    def test_get_appointment_forbidden(self, mock_sb):
        """403 si la cita es de otro cliente."""
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        other_apt = {**SAMPLE_APPOINTMENT_ROW, "client_id": "other-client-id"}
        mock_inst = MagicMock()
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [other_apt]
        mock_sb.return_value = mock_inst

        resp = client.get("/api/appointments/apt-1")
        assert resp.status_code == 403
        app.dependency_overrides.clear()


class TestUpdateAppointment:
    @patch("api.routes.appointments.get_supabase")
    def test_update_appointment(self, mock_sb):
        """Actualiza el status de una cita."""
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        updated_row = {**SAMPLE_APPOINTMENT_ROW, "status": "cancelled"}
        mock_inst = MagicMock()
        # Mock: verificar acceso
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [
            {"client_id": "client-id-123"}
        ]
        # Mock: update
        (mock_inst.table.return_value.update.return_value
         .eq.return_value.execute.return_value.data) = [updated_row]
        mock_sb.return_value = mock_inst

        resp = client.patch(
            "/api/appointments/apt-1",
            json={"status": "cancelled"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"
        app.dependency_overrides.clear()


class TestDeleteAppointment:
    @patch("api.routes.appointments.get_supabase")
    def test_delete_appointment(self, mock_sb):
        """Elimina una cita."""
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        # Mock: verificar que existe y acceso
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [
            {"client_id": "client-id-123"}
        ]
        # Mock: delete
        mock_inst.table.return_value.delete.return_value.eq.return_value.execute.return_value.data = []
        mock_sb.return_value = mock_inst

        resp = client.delete("/api/appointments/apt-1")
        assert resp.status_code == 200
        assert "eliminada" in resp.json()["message"].lower()
        app.dependency_overrides.clear()
