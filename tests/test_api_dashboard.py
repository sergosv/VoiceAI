"""Tests para rutas del dashboard."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.middleware.auth import CurrentUser, get_current_user

client = TestClient(app)

CLIENT_USER = CurrentUser(
    id="client-uuid", auth_user_id="auth-client", email="cli@test.com",
    role="client", client_id="client-id-123",
)

ADMIN_USER = CurrentUser(
    id="admin-uuid", auth_user_id="auth-admin", email="admin@test.com",
    role="admin", client_id=None,
)


class TestDashboardOverview:
    @patch("api.routes.dashboard.get_supabase")
    def test_client_overview(self, mock_sb):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER

        # Crear mocks separados por tabla
        calls_table = MagicMock()
        calls_exec = MagicMock()
        calls_exec.data = [
            {"duration_seconds": 120, "cost_total": "0.045", "started_at": "2026-02-27T10:00:00+00:00"},
        ]
        calls_table.select.return_value.eq.return_value.execute.return_value = calls_exec

        docs_table = MagicMock()
        docs_exec = MagicMock()
        docs_exec.count = 3
        docs_exec.data = []
        docs_table.select.return_value.eq.return_value.execute.return_value = docs_exec

        clients_table = MagicMock()
        clients_exec = MagicMock()
        clients_exec.data = [{"name": "Dr. García"}]
        clients_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = clients_exec

        def _table(name):
            if name == "calls":
                return calls_table
            elif name == "documents":
                return docs_table
            elif name == "clients":
                return clients_table
            return MagicMock()

        mock_inst = MagicMock()
        mock_inst.table.side_effect = _table
        mock_sb.return_value = mock_inst

        resp = client.get("/api/dashboard/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_calls"] == 1
        assert data["active_documents"] == 3
        assert data["client_name"] == "Dr. García"
        app.dependency_overrides.clear()


class TestDashboardUsage:
    @patch("api.routes.dashboard.get_supabase")
    def test_usage_data(self, mock_sb):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        (mock_inst.table.return_value.select.return_value
         .gte.return_value.order.return_value
         .eq.return_value.execute.return_value.data) = [
            {"date": "2026-02-26", "total_calls": 5, "total_minutes": "12.50", "total_cost": "0.5000"},
            {"date": "2026-02-27", "total_calls": 3, "total_minutes": "8.00", "total_cost": "0.3200"},
        ]
        mock_sb.return_value = mock_inst

        resp = client.get("/api/dashboard/usage?days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert data["period_days"] == 7
        assert len(data["data"]) == 2
        app.dependency_overrides.clear()
