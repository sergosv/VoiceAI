"""Tests para rutas de campañas outbound."""

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

SAMPLE_CAMPAIGN = {
    "id": "camp-1",
    "client_id": "client-id-123",
    "agent_id": "agent-1",
    "name": "Test Campaign",
    "description": None,
    "script": "Hola {nombre}",
    "status": "draft",
    "scheduled_at": None,
    "completed_at": None,
    "max_concurrent": 1,
    "retry_attempts": 2,
    "retry_delay_minutes": 30,
    "total_contacts": 0,
    "completed_contacts": 0,
    "successful_contacts": 0,
    "created_at": "2026-01-01T00:00:00",
    "updated_at": None,
}

SAMPLE_CAMPAIGN_CALL = {
    "id": "cc-1",
    "campaign_id": "camp-1",
    "contact_id": None,
    "call_id": None,
    "phone": "+5219991234567",
    "status": "pending",
    "attempt": 0,
    "result_summary": None,
    "analysis_data": None,
    "created_at": "2026-01-01T00:00:00",
}


class TestListCampaigns:
    @patch("api.routes.campaigns.get_supabase")
    def test_list_campaigns_client(self, mock_sb):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        (mock_inst.table.return_value.select.return_value
         .order.return_value.eq.return_value.execute.return_value.data) = [SAMPLE_CAMPAIGN]
        mock_sb.return_value = mock_inst

        resp = client.get("/api/campaigns")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test Campaign"
        assert data[0]["status"] == "draft"
        app.dependency_overrides.clear()


class TestCreateCampaign:
    @patch("api.routes.campaigns.get_supabase")
    def test_create_campaign(self, mock_sb):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        # Mock para resolver agent_id default
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.eq.return_value
         .order.return_value.limit.return_value.execute.return_value.data) = [{"id": "agent-1"}]
        # Mock para insert
        (mock_inst.table.return_value.insert.return_value
         .execute.return_value.data) = [SAMPLE_CAMPAIGN]
        mock_sb.return_value = mock_inst

        resp = client.post("/api/campaigns", json={
            "name": "Test Campaign",
            "script": "Hola {nombre}",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Campaign"
        assert data["script"] == "Hola {nombre}"
        app.dependency_overrides.clear()


class TestGetCampaign:
    @patch("api.routes.campaigns.get_supabase")
    def test_get_campaign(self, mock_sb):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [SAMPLE_CAMPAIGN]
        mock_sb.return_value = mock_inst

        resp = client.get("/api/campaigns/camp-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "camp-1"
        app.dependency_overrides.clear()

    @patch("api.routes.campaigns.get_supabase")
    def test_get_campaign_forbidden(self, mock_sb):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        other_campaign = {**SAMPLE_CAMPAIGN, "client_id": "other-client"}
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [other_campaign]
        mock_sb.return_value = mock_inst

        resp = client.get("/api/campaigns/camp-1")
        assert resp.status_code == 403
        app.dependency_overrides.clear()


class TestUpdateCampaign:
    @patch("api.routes.campaigns.get_supabase")
    def test_update_campaign_draft(self, mock_sb):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        # Mock para select existing
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [
            {"client_id": "client-id-123", "status": "draft"}
        ]
        # Mock para update
        updated = {**SAMPLE_CAMPAIGN, "name": "Updated Campaign"}
        (mock_inst.table.return_value.update.return_value
         .eq.return_value.execute.return_value.data) = [updated]
        mock_sb.return_value = mock_inst

        resp = client.patch("/api/campaigns/camp-1", json={"name": "Updated Campaign"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Campaign"
        app.dependency_overrides.clear()

    @patch("api.routes.campaigns.get_supabase")
    def test_update_campaign_running_blocked(self, mock_sb):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [
            {"client_id": "client-id-123", "status": "running"}
        ]
        mock_sb.return_value = mock_inst

        resp = client.patch("/api/campaigns/camp-1", json={"name": "Nope"})
        assert resp.status_code == 400
        app.dependency_overrides.clear()


class TestDeleteCampaign:
    @patch("api.routes.campaigns.get_supabase")
    def test_delete_campaign(self, mock_sb):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [
            {"client_id": "client-id-123", "status": "draft"}
        ]
        (mock_inst.table.return_value.delete.return_value
         .eq.return_value.execute.return_value.data) = []
        mock_sb.return_value = mock_inst

        resp = client.delete("/api/campaigns/camp-1")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Campaña eliminada"
        app.dependency_overrides.clear()

    @patch("api.routes.campaigns.get_supabase")
    def test_delete_running_blocked(self, mock_sb):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [
            {"client_id": "client-id-123", "status": "running"}
        ]
        mock_sb.return_value = mock_inst

        resp = client.delete("/api/campaigns/camp-1")
        assert resp.status_code == 400
        app.dependency_overrides.clear()


class TestListCampaignCalls:
    @patch("api.routes.campaigns.get_supabase")
    def test_list_campaign_calls(self, mock_sb):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        # Mock para select existing campaign
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [
            {"client_id": "client-id-123"}
        ]
        # Mock para select campaign_calls
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.order.return_value.execute.return_value.data) = [SAMPLE_CAMPAIGN_CALL]
        mock_sb.return_value = mock_inst

        resp = client.get("/api/campaigns/camp-1/calls")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["phone"] == "+5219991234567"
        assert data[0]["status"] == "pending"
        app.dependency_overrides.clear()
