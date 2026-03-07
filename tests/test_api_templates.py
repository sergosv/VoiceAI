"""Tests para api/routes/templates.py — Template Store y Wizard."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.middleware.auth import get_current_user


@pytest.fixture()
def admin_client():
    mock_user = MagicMock()
    mock_user.id = "u1"
    mock_user.role = "admin"
    mock_user.client_id = None
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture()
def client_user_client():
    mock_user = MagicMock()
    mock_user.id = "u2"
    mock_user.role = "client"
    mock_user.client_id = "client-id-123"
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture()
def mock_sb():
    with patch("api.routes.templates.get_supabase") as m:
        sb = MagicMock()
        m.return_value = sb
        yield sb


SAMPLE_OBJECTIVES = [
    {"id": "1", "slug": "qualify", "name": "Calificar leads", "is_active": True, "sort_order": 1},
    {"id": "2", "slug": "support", "name": "Soporte", "is_active": True, "sort_order": 2},
]

SAMPLE_VERTICALS = [
    {"slug": "real-estate", "name": "Inmobiliaria", "description": "Para inmobiliarias",
     "icon": "🏠", "default_framework_slug": "bant", "sort_order": 1},
]

SAMPLE_FRAMEWORKS = [
    {"slug": "bant", "name": "BANT", "description": "Budget, Authority, Need, Timeline",
     "best_for": "Ventas B2B", "sort_order": 1},
]

SAMPLE_TEMPLATE = {
    "id": "tpl-uuid-1",
    "name": "Inmobiliaria Lead Qualifier",
    "slug": "inmo-qualifier",
    "vertical_slug": "real-estate",
    "framework_slug": "bant",
    "direction": "inbound",
    "objective": "Calificar leads",
    "agent_role": "Asistente de ventas",
    "greeting": "Hola, bienvenido",
    "qualification_steps": [{"step": "presupuesto"}],
    "is_active": True,
    "sort_order": 1,
    "tags": ["qualify"],
    "usage_count": 5,
    "industry_verticals": {"name": "Inmobiliaria", "icon": "🏠"},
    "qualification_frameworks": {"name": "BANT", "slug": "bant"},
}


class TestListObjectives:
    def test_returns_objectives(self, admin_client, mock_sb):
        (mock_sb.table.return_value
         .select.return_value
         .eq.return_value
         .order.return_value
         .execute.return_value.data) = SAMPLE_OBJECTIVES

        resp = admin_client.get("/api/templates/objectives")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["slug"] == "qualify"

    def test_empty(self, admin_client, mock_sb):
        (mock_sb.table.return_value
         .select.return_value
         .eq.return_value
         .order.return_value
         .execute.return_value.data) = []

        resp = admin_client.get("/api/templates/objectives")
        assert resp.status_code == 200
        assert resp.json() == []


class TestListVerticals:
    def test_returns_verticals(self, admin_client, mock_sb):
        (mock_sb.table.return_value
         .select.return_value
         .eq.return_value
         .order.return_value
         .execute.return_value.data) = SAMPLE_VERTICALS

        resp = admin_client.get("/api/templates/verticals")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["slug"] == "real-estate"


class TestListFrameworks:
    def test_returns_frameworks(self, admin_client, mock_sb):
        (mock_sb.table.return_value
         .select.return_value
         .eq.return_value
         .order.return_value
         .execute.return_value.data) = SAMPLE_FRAMEWORKS

        resp = admin_client.get("/api/templates/frameworks")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["slug"] == "bant"


class TestSearchTemplates:
    def test_no_filters(self, admin_client, mock_sb):
        (mock_sb.table.return_value
         .select.return_value
         .eq.return_value
         .order.return_value
         .execute.return_value.data) = [SAMPLE_TEMPLATE]

        resp = admin_client.get("/api/templates/search")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

    def test_filter_by_vertical(self, admin_client, mock_sb):
        (mock_sb.table.return_value
         .select.return_value
         .eq.return_value
         .eq.return_value
         .order.return_value
         .execute.return_value.data) = [SAMPLE_TEMPLATE]

        resp = admin_client.get("/api/templates/search?vertical=real-estate")
        assert resp.status_code == 200

    def test_filter_by_direction(self, admin_client, mock_sb):
        (mock_sb.table.return_value
         .select.return_value
         .eq.return_value
         .in_.return_value
         .order.return_value
         .execute.return_value.data) = [SAMPLE_TEMPLATE]

        resp = admin_client.get("/api/templates/search?direction=inbound")
        assert resp.status_code == 200

    def test_filter_by_objective(self, admin_client, mock_sb):
        (mock_sb.table.return_value
         .select.return_value
         .eq.return_value
         .contains.return_value
         .order.return_value
         .execute.return_value.data) = [SAMPLE_TEMPLATE]

        resp = admin_client.get("/api/templates/search?objective=qualify")
        assert resp.status_code == 200

    def test_empty_results(self, admin_client, mock_sb):
        (mock_sb.table.return_value
         .select.return_value
         .eq.return_value
         .order.return_value
         .execute.return_value.data) = []

        resp = admin_client.get("/api/templates/search")
        assert resp.status_code == 200
        assert resp.json() == []


class TestPreviewTemplate:
    def test_found(self, admin_client, mock_sb):
        (mock_sb.table.return_value
         .select.return_value
         .eq.return_value
         .limit.return_value
         .execute.return_value.data) = [SAMPLE_TEMPLATE]

        resp = admin_client.get("/api/templates/preview/tpl-uuid-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Inmobiliaria Lead Qualifier"

    def test_not_found(self, admin_client, mock_sb):
        (mock_sb.table.return_value
         .select.return_value
         .eq.return_value
         .limit.return_value
         .execute.return_value.data) = []

        resp = admin_client.get("/api/templates/preview/no-existe")
        assert resp.status_code == 404


class TestGenerateAgent:
    @patch("api.routes.templates.generate_agent_from_template", new_callable=AsyncMock)
    def test_generate_system_prompt(self, mock_generate, admin_client, mock_sb):
        mock_generate.return_value = {
            "mode": "system_prompt",
            "result": "Eres un asistente de ventas...",
            "template_info": {"name": "Inmo Qualifier", "vertical": "Inmobiliaria",
                              "framework": "BANT", "direction": "inbound", "objective": "qualify"},
        }

        resp = admin_client.post("/api/templates/generate", json={
            "template_id": "tpl-uuid-1",
            "business_name": "Dental Plus",
            "agent_name": "María",
            "mode": "system_prompt",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "system_prompt"
        assert "result" in data

    @patch("api.routes.templates.generate_agent_from_template", new_callable=AsyncMock)
    def test_generate_builder_flow(self, mock_generate, admin_client, mock_sb):
        mock_generate.return_value = {
            "mode": "builder_flow",
            "result": {"nodes": [], "edges": []},
            "template_info": {"name": "Inmo", "vertical": "Inmobiliaria",
                              "framework": "BANT", "direction": "inbound", "objective": "qualify"},
        }

        resp = admin_client.post("/api/templates/generate", json={
            "template_id": "tpl-uuid-1",
            "business_name": "Dental Plus",
            "mode": "builder_flow",
        })
        assert resp.status_code == 200
        assert resp.json()["mode"] == "builder_flow"

    @patch("api.routes.templates.generate_agent_from_template", new_callable=AsyncMock)
    def test_generate_value_error(self, mock_generate, admin_client, mock_sb):
        mock_generate.side_effect = ValueError("Template no encontrado")

        resp = admin_client.post("/api/templates/generate", json={
            "template_id": "bad-id",
            "business_name": "Test",
        })
        assert resp.status_code == 400


class TestAdminCreateTemplate:
    def test_admin_creates_template(self, admin_client, mock_sb):
        created = {**SAMPLE_TEMPLATE, "id": "new-tpl-id"}
        (mock_sb.table.return_value
         .insert.return_value
         .execute.return_value.data) = [created]

        resp = admin_client.post("/api/templates/admin/templates", json={
            "vertical_slug": "real-estate",
            "framework_slug": "bant",
            "slug": "new-template",
            "name": "New Template",
            "objective": "qualify",
            "direction": "inbound",
            "agent_role": "Asistente",
            "qualification_steps": [{"step": "presupuesto"}],
        })
        assert resp.status_code == 201
        assert resp.json()["id"] == "new-tpl-id"

    def test_non_admin_forbidden(self, client_user_client, mock_sb):
        resp = client_user_client.post("/api/templates/admin/templates", json={
            "vertical_slug": "real-estate",
            "framework_slug": "bant",
            "slug": "new-template",
            "name": "New Template",
            "objective": "qualify",
            "direction": "inbound",
            "agent_role": "Asistente",
            "qualification_steps": [{"step": "presupuesto"}],
        })
        assert resp.status_code == 403


class TestAdminStats:
    def test_admin_gets_stats(self, admin_client, mock_sb):
        templates = [
            {"name": "T1", "vertical_slug": "real-estate", "usage_count": 10, "direction": "inbound"},
            {"name": "T2", "vertical_slug": "health", "usage_count": 5, "direction": "outbound"},
        ]
        (mock_sb.table.return_value
         .select.return_value
         .eq.return_value
         .order.return_value
         .execute.return_value.data) = templates

        resp = admin_client.get("/api/templates/admin/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_uses"] == 15
        assert len(data["templates"]) == 2

    def test_non_admin_forbidden(self, client_user_client, mock_sb):
        resp = client_user_client.get("/api/templates/admin/stats")
        assert resp.status_code == 403


class TestLeadsSummary:
    def test_admin_gets_leads(self, admin_client, mock_sb):
        leads = [
            {"id": "l1", "tier": "hot", "created_at": "2026-03-01T00:00:00Z"},
            {"id": "l2", "tier": "warm", "created_at": "2026-03-01T00:00:00Z"},
            {"id": "l3", "tier": "cold", "created_at": "2026-03-01T00:00:00Z"},
            {"id": "l4", "tier": "hot", "created_at": "2026-03-01T00:00:00Z"},
        ]
        (mock_sb.table.return_value
         .select.return_value
         .eq.return_value
         .gte.return_value
         .order.return_value
         .execute.return_value.data) = leads

        resp = admin_client.get("/api/templates/leads/client-id-123?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        assert data["hot"] == 2
        assert data["warm"] == 1
        assert data["cold"] == 1

    def test_client_forbidden_other_client(self, client_user_client, mock_sb):
        resp = client_user_client.get("/api/templates/leads/other-client-id")
        assert resp.status_code == 403

    def test_client_can_see_own_leads(self, client_user_client, mock_sb):
        (mock_sb.table.return_value
         .select.return_value
         .eq.return_value
         .gte.return_value
         .order.return_value
         .execute.return_value.data) = []

        resp = client_user_client.get("/api/templates/leads/client-id-123")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
