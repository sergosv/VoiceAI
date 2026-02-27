"""Tests para rutas de llamadas."""

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

SAMPLE_CALL = {
    "id": "call-uuid-1",
    "client_id": "client-id-123",
    "direction": "inbound",
    "caller_number": "+5219991234567",
    "callee_number": "+529994890531",
    "duration_seconds": 120,
    "cost_total": "0.045",
    "status": "completed",
    "summary": "Consulta sobre horarios",
    "started_at": "2026-02-27T10:00:00+00:00",
    "ended_at": "2026-02-27T10:02:00+00:00",
}

SAMPLE_CALL_DETAIL = {
    **SAMPLE_CALL,
    "livekit_room_id": "room-123",
    "livekit_room_name": "call-abc",
    "cost_livekit": "0.010",
    "cost_stt": "0.005",
    "cost_llm": "0.010",
    "cost_tts": "0.010",
    "cost_telephony": "0.010",
    "transcript": [{"role": "agent", "text": "Hola"}],
    "metadata": {},
}


class TestListCalls:
    @patch("api.routes.calls.get_supabase")
    def test_client_sees_own_calls(self, mock_sb):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        (mock_inst.table.return_value.select.return_value
         .order.return_value.eq.return_value
         .range.return_value.execute.return_value.data) = [SAMPLE_CALL]
        mock_sb.return_value = mock_inst

        resp = client.get("/api/calls")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["direction"] == "inbound"
        app.dependency_overrides.clear()

    @patch("api.routes.calls.get_supabase")
    def test_filter_by_status(self, mock_sb):
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER
        mock_inst = MagicMock()
        (mock_inst.table.return_value.select.return_value
         .order.return_value.eq.return_value
         .range.return_value.execute.return_value.data) = []
        mock_sb.return_value = mock_inst

        resp = client.get("/api/calls?status=failed")
        assert resp.status_code == 200
        app.dependency_overrides.clear()


class TestCallStats:
    @patch("api.routes.calls.get_supabase")
    def test_stats_empty(self, mock_sb):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.execute.return_value.data) = []
        mock_sb.return_value = mock_inst

        resp = client.get("/api/calls/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_calls"] == 0
        app.dependency_overrides.clear()

    @patch("api.routes.calls.get_supabase")
    def test_stats_with_data(self, mock_sb):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.execute.return_value.data) = [
            {"duration_seconds": 120, "cost_total": "0.045", "started_at": "2026-02-27T10:00:00+00:00"},
            {"duration_seconds": 60, "cost_total": "0.025", "started_at": "2026-02-26T10:00:00+00:00"},
        ]
        mock_sb.return_value = mock_inst

        resp = client.get("/api/calls/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_calls"] == 2
        assert data["total_minutes"] == 3.0
        app.dependency_overrides.clear()


class TestCallDetail:
    @patch("api.routes.calls.get_supabase")
    def test_get_own_call(self, mock_sb):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [SAMPLE_CALL_DETAIL]
        mock_sb.return_value = mock_inst

        resp = client.get("/api/calls/call-uuid-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["transcript"] is not None
        app.dependency_overrides.clear()

    @patch("api.routes.calls.get_supabase")
    def test_client_cannot_see_other_call(self, mock_sb):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        other_call = {**SAMPLE_CALL_DETAIL, "client_id": "other-client"}
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [other_call]
        mock_sb.return_value = mock_inst

        resp = client.get("/api/calls/call-uuid-1")
        assert resp.status_code == 403
        app.dependency_overrides.clear()
