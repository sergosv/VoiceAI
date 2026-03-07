"""Tests para api/routes/looptalk.py — LoopTalk AI Test Personas."""

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
def client_user():
    mock_user = MagicMock()
    mock_user.id = "u2"
    mock_user.role = "client"
    mock_user.client_id = "c1"
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture()
def mock_sb():
    with patch("api.routes.looptalk.get_supabase") as m:
        sb = MagicMock()
        m.return_value = sb
        yield sb


class TestListPersonas:
    def test_admin_sees_all(self, client, mock_sb):
        mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value.data = [
            {"id": "p1", "name": "Lead", "is_template": True, "tags": []},
            {"id": "p2", "name": "Custom", "is_template": False, "tags": []},
        ]
        resp = client.get("/api/looptalk/personas")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_client_sees_templates_and_own(self, client_user, mock_sb):
        mock_sb.table.return_value.select.return_value.order.return_value.or_.return_value.execute.return_value.data = [
            {"id": "p1", "name": "Lead", "is_template": True, "tags": []},
        ]
        resp = client_user.get("/api/looptalk/personas")
        assert resp.status_code == 200


class TestCreatePersona:
    def test_create_success(self, client, mock_sb):
        mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": "p3", "name": "Test Persona", "personality": "Amable", "objective": "Probar"}
        ]
        resp = client.post("/api/looptalk/personas", json={
            "name": "Test Persona",
            "personality": "Amable y directa",
            "objective": "Probar el agente",
        })
        assert resp.status_code == 201
        assert resp.json()["name"] == "Test Persona"

    def test_missing_fields(self, client, mock_sb):
        resp = client.post("/api/looptalk/personas", json={"name": "X"})
        assert resp.status_code == 422  # Pydantic validation


class TestUpdatePersona:
    def test_update_own(self, client, mock_sb):
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"id": "p1", "is_template": False, "client_id": None}
        ]
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
            {"id": "p1", "name": "Updated"}
        ]
        resp = client.patch("/api/looptalk/personas/p1", json={"name": "Updated"})
        assert resp.status_code == 200

    def test_cannot_edit_template(self, client, mock_sb):
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"id": "p1", "is_template": True, "client_id": None}
        ]
        resp = client.patch("/api/looptalk/personas/p1", json={"name": "Hacked"})
        assert resp.status_code == 403


class TestDeletePersona:
    def test_delete_own(self, client, mock_sb):
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"id": "p1", "is_template": False, "client_id": None}
        ]
        mock_sb.table.return_value.delete.return_value.eq.return_value.execute.return_value.data = []
        resp = client.delete("/api/looptalk/personas/p1")
        assert resp.status_code == 200

    def test_cannot_delete_template(self, client, mock_sb):
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"id": "p1", "is_template": True, "client_id": None}
        ]
        resp = client.delete("/api/looptalk/personas/p1")
        assert resp.status_code == 403


class TestStartRun:
    def test_start_success(self, client, mock_sb):
        # Agent lookup
        def table_side_effect(name):
            mock = MagicMock()
            if name == "agents":
                mock.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
                    {"id": "a1", "client_id": "c1", "name": "Agent 1"}
                ]
            elif name == "test_personas":
                mock.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
                    {"id": "p1"}
                ]
            elif name == "test_runs":
                mock.insert.return_value.execute.return_value.data = [
                    {"id": "r1", "status": "pending"}
                ]
            return mock
        mock_sb.table.side_effect = table_side_effect

        with patch("api.routes.looptalk.run_test"):
            resp = client.post("/api/looptalk/run", json={
                "agent_id": "a1",
                "persona_id": "p1",
                "max_turns": 15,
            })
        assert resp.status_code == 201
        assert resp.json()["status"] == "pending"

    def test_missing_agent(self, client, mock_sb):
        resp = client.post("/api/looptalk/run", json={"persona_id": "p1"})
        assert resp.status_code == 422


class TestListRuns:
    def test_returns_data(self, client, mock_sb):
        mock_sb.table.return_value.select.return_value.order.return_value.range.return_value.execute.return_value.data = [
            {
                "id": "r1", "status": "completed", "score": 85, "persona_id": "p1",
                "agent_id": "a1", "test_personas": {"name": "Lead", "difficulty": "easy"},
                "agents": {"name": "Agent 1"},
            }
        ]
        resp = client.get("/api/looptalk/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["persona_name"] == "Lead"
        assert data[0]["agent_name"] == "Agent 1"


class TestStats:
    def test_empty(self, client, mock_sb):
        mock_sb.table.return_value.select.return_value.execute.return_value.data = []
        resp = client.get("/api/looptalk/stats")
        assert resp.status_code == 200
        assert resp.json()["total_runs"] == 0

    def test_with_data(self, client, mock_sb):
        mock_sb.table.return_value.select.return_value.execute.return_value.data = [
            {"id": "r1", "status": "completed", "score": 80, "persona_id": "p1", "test_personas": {"name": "Lead"}},
            {"id": "r2", "status": "completed", "score": 60, "persona_id": "p2", "test_personas": {"name": "Enojado"}},
            {"id": "r3", "status": "failed", "score": None, "persona_id": "p1", "test_personas": {"name": "Lead"}},
        ]
        resp = client.get("/api/looptalk/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_runs"] == 3
        assert data["avg_score"] == 70.0
        assert data["completed_runs"] == 2


class TestSuites:
    def test_create_suite(self, client, mock_sb):
        mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": "s1", "name": "Suite Ventas", "persona_ids": ["p1", "p2"]}
        ]
        resp = client.post("/api/looptalk/suites", json={
            "name": "Suite Ventas",
            "persona_ids": ["p1", "p2"],
        })
        assert resp.status_code == 201
        assert resp.json()["name"] == "Suite Ventas"

    def test_list_suites(self, client, mock_sb):
        mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value.data = [
            {"id": "s1", "name": "Suite Ventas", "persona_ids": ["p1", "p2"]}
        ]
        resp = client.get("/api/looptalk/suites")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
