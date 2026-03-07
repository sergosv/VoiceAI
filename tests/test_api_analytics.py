"""Tests para api/routes/analytics.py — métricas avanzadas."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.middleware.auth import get_current_user


@pytest.fixture()
def client():
    mock_user = MagicMock()
    mock_user.id = "u1"
    mock_user.role = "admin"
    mock_user.client_id = None
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture()
def mock_sb():
    with patch("api.routes.analytics.get_supabase") as m:
        sb = MagicMock()
        m.return_value = sb
        yield sb


class TestSummary:
    def test_empty(self, client, mock_sb):
        mock_sb.table.return_value.select.return_value.gte.return_value.execute.return_value.data = []
        resp = client.get("/api/analytics/summary?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_calls"] == 0
        assert data["period_days"] == 30

    def test_with_calls(self, client, mock_sb):
        calls = [
            {"id": "1", "duration_seconds": 120, "status": "completed",
             "direction": "inbound", "started_at": "2026-03-06T10:00:00Z",
             "cost_total": "0.50", "caller_number": "+521234", "callee_number": None, "agent_id": "a1"},
            {"id": "2", "duration_seconds": 60, "status": "failed",
             "direction": "outbound", "started_at": "2026-03-06T14:30:00Z",
             "cost_total": "0.25", "caller_number": "+525678", "callee_number": "+521111", "agent_id": "a1"},
        ]
        mock_sb.table.return_value.select.return_value.gte.return_value.execute.return_value.data = calls
        resp = client.get("/api/analytics/summary?days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_calls"] == 2
        assert data["inbound"] == 1
        assert data["outbound"] == 1
        assert data["completed"] == 1
        assert data["failed"] == 1
        assert data["unique_callers"] == 2
        assert data["completion_rate"] == 50.0


class TestVolume:
    def test_returns_data(self, client, mock_sb):
        rows = [
            {"date": "2026-03-05", "total_calls": 5, "total_minutes": "10.0",
             "total_cost": "1.50", "inbound_calls": 3, "outbound_calls": 2},
        ]
        mock_sb.table.return_value.select.return_value.gte.return_value.order.return_value.execute.return_value.data = rows
        resp = client.get("/api/analytics/volume?days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["calls"] == 5


class TestByStatus:
    def test_distribution(self, client, mock_sb):
        calls = [
            {"status": "completed"}, {"status": "completed"},
            {"status": "failed"}, {"status": "transferred"},
        ]
        mock_sb.table.return_value.select.return_value.gte.return_value.execute.return_value.data = calls
        resp = client.get("/api/analytics/by-status?days=30")
        assert resp.status_code == 200
        data = resp.json()
        statuses = {d["status"]: d["count"] for d in data}
        assert statuses["completed"] == 2
        assert statuses["failed"] == 1


class TestByHour:
    def test_24_hours(self, client, mock_sb):
        calls = [
            {"started_at": "2026-03-06T09:15:00Z"},
            {"started_at": "2026-03-06T09:45:00Z"},
            {"started_at": "2026-03-06T14:00:00Z"},
        ]
        mock_sb.table.return_value.select.return_value.gte.return_value.execute.return_value.data = calls
        resp = client.get("/api/analytics/by-hour?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 24
        hour_map = {d["hour"]: d["calls"] for d in data}
        assert hour_map[9] == 2
        assert hour_map[14] == 1
        assert hour_map[0] == 0


class TestByAgent:
    def test_groups_by_agent(self, client, mock_sb):
        calls = [
            {"agent_id": "a1", "duration_seconds": 60, "status": "completed", "cost_total": "0.50"},
            {"agent_id": "a1", "duration_seconds": 120, "status": "completed", "cost_total": "1.00"},
            {"agent_id": "a2", "duration_seconds": 30, "status": "failed", "cost_total": "0.10"},
        ]
        agents_rows = [{"id": "a1", "name": "María"}, {"id": "a2", "name": "Carlos"}]

        # Mock chained calls
        def table_side_effect(name):
            mock = MagicMock()
            if name == "calls":
                mock.select.return_value.gte.return_value.execute.return_value.data = calls
            elif name == "agents":
                mock.select.return_value.in_.return_value.execute.return_value.data = agents_rows
            return mock

        mock_sb.table.side_effect = table_side_effect

        resp = client.get("/api/analytics/by-agent?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        maria = next(a for a in data if a["name"] == "María")
        assert maria["calls"] == 2
        assert maria["completion_rate"] == 100.0


class TestDurationDistribution:
    def test_buckets(self, client, mock_sb):
        calls = [
            {"duration_seconds": 10},   # 0-30s
            {"duration_seconds": 45},   # 30s-1m
            {"duration_seconds": 90},   # 1-2m
            {"duration_seconds": 200},  # 2-5m
            {"duration_seconds": 500},  # 5-10m
            {"duration_seconds": 700},  # 10m+
        ]
        mock_sb.table.return_value.select.return_value.gte.return_value.execute.return_value.data = calls
        resp = client.get("/api/analytics/duration-distribution?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 6
        counts = {d["range"]: d["count"] for d in data}
        assert counts["0-30s"] == 1
        assert counts["10m+"] == 1
