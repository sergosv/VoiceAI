"""Tests para rutas CRUD de agentes."""

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

SAMPLE_AGENT_ROW = {
    "id": "agent-1",
    "client_id": "client-id-123",
    "name": "María",
    "slug": "maria",
    "phone_number": None,
    "system_prompt": "test",
    "greeting": "Hola",
    "examples": None,
    "voice_config": {"provider": "cartesia", "voice_id": "v1"},
    "llm_config": {"provider": "google"},
    "stt_config": {"provider": "deepgram"},
    "agent_mode": "pipeline",
    "agent_type": "inbound",
    "transfer_number": None,
    "after_hours_message": None,
    "max_call_duration_seconds": 300,
    "is_active": True,
    "role_description": None,
    "orchestrator_enabled": True,
    "orchestrator_priority": 0,
    "conversation_mode": "prompt",
    "conversation_flow": None,
    "mode_config": {},
    "sentiment_config": None,
    "intent_config": None,
    "guardrails_config": None,
    "language_detection_config": None,
    "quality_config": None,
    "proactive_config": None,
    "widget_channels": ["voice", "chat"],
    "created_at": "2026-01-01T00:00:00",
    "updated_at": None,
}


class TestAgentOutSchemaConsistency:
    """Verifica que AgentOut incluye todos los campos que retorna la DB."""

    def test_sample_row_roundtrips_through_agent_out(self):
        """Si un campo existe en SAMPLE_AGENT_ROW, AgentOut debe aceptarlo sin perderlo."""
        from api.schemas import agent_out_from_row

        result = agent_out_from_row(SAMPLE_AGENT_ROW)
        out = result.model_dump()

        # Campos que se transforman (API keys se stripean) — no comparar directamente
        skip = {"voice_config", "llm_config", "stt_config"}
        for key in SAMPLE_AGENT_ROW:
            if key in skip:
                continue
            assert key in out, (
                f"Campo '{key}' existe en la DB pero falta en AgentOut schema. "
                f"Agrega '{key}' a la clase AgentOut en api/schemas.py"
            )

    def test_widget_channels_preserved(self):
        """widget_channels debe sobrevivir el roundtrip por AgentOut."""
        from api.schemas import agent_out_from_row

        row = {**SAMPLE_AGENT_ROW, "widget_channels": ["voice", "chat"]}
        result = agent_out_from_row(row)
        assert result.widget_channels == ["voice", "chat"]

        row2 = {**SAMPLE_AGENT_ROW, "widget_channels": ["voice"]}
        result2 = agent_out_from_row(row2)
        assert result2.widget_channels == ["voice"]


class TestListAgents:
    @patch("api.routes.agents.get_supabase")
    def test_list_agents_client(self, mock_sb):
        """Client lista sus propios agentes."""
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.order.return_value.execute.return_value.data) = [SAMPLE_AGENT_ROW]
        mock_sb.return_value = mock_inst

        resp = client.get("/api/clients/client-id-123/agents")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "María"
        app.dependency_overrides.clear()

    def test_list_agents_forbidden(self):
        """Client no puede listar agentes de otro cliente."""
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        resp = client.get("/api/clients/other-client-id/agents")
        assert resp.status_code == 403
        app.dependency_overrides.clear()


class TestCreateAgent:
    @patch("api.services.client_service.load_voice_id", return_value="voice-id-123")
    @patch("api.routes.agents.get_supabase")
    def test_create_agent(self, mock_sb, mock_voice):
        """Crea un agente con nombre, retorna 201."""
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        # Mock: verificar que el cliente existe
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [
            {"name": "Test Client", "business_type": "dental", "language": "es"}
        ]
        # Mock: insert del agente
        mock_inst.table.return_value.insert.return_value.execute.return_value.data = [SAMPLE_AGENT_ROW]
        mock_sb.return_value = mock_inst

        resp = client.post(
            "/api/clients/client-id-123/agents",
            json={"name": "María"},
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "María"
        app.dependency_overrides.clear()


class TestGetAgent:
    @patch("api.routes.agents.get_supabase")
    def test_get_agent(self, mock_sb):
        """Obtiene un agente por ID."""
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.eq.return_value.limit.return_value
         .execute.return_value.data) = [SAMPLE_AGENT_ROW]
        mock_sb.return_value = mock_inst

        resp = client.get("/api/clients/client-id-123/agents/agent-1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "agent-1"
        app.dependency_overrides.clear()

    @patch("api.routes.agents.get_supabase")
    def test_get_agent_not_found(self, mock_sb):
        """404 cuando el agente no existe."""
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.eq.return_value.limit.return_value
         .execute.return_value.data) = []
        mock_sb.return_value = mock_inst

        resp = client.get("/api/clients/client-id-123/agents/nonexistent")
        assert resp.status_code == 404
        app.dependency_overrides.clear()


class TestUpdateAgent:
    @patch("api.routes.agents.get_supabase")
    def test_update_agent(self, mock_sb):
        """Actualiza nombre y greeting de un agente."""
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        updated_row = {**SAMPLE_AGENT_ROW, "name": "Ana", "greeting": "Buenos días"}
        mock_inst = MagicMock()
        # Mock: leer agente actual (select → eq → eq → limit → execute)
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.eq.return_value.limit.return_value
         .execute.return_value.data) = [SAMPLE_AGENT_ROW]
        # Mock: update → eq → eq → execute
        (mock_inst.table.return_value.update.return_value
         .eq.return_value.eq.return_value.execute.return_value.data) = [updated_row]
        mock_sb.return_value = mock_inst

        resp = client.patch(
            "/api/clients/client-id-123/agents/agent-1",
            json={"name": "Ana", "greeting": "Buenos días"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Ana"
        assert resp.json()["greeting"] == "Buenos días"
        app.dependency_overrides.clear()


class TestDeleteAgent:
    @patch("api.routes.agents.get_supabase")
    def test_delete_agent(self, mock_sb):
        """Elimina un agente cuando hay más de uno."""
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        # Mock: count de agentes > 1
        count_result = MagicMock()
        count_result.count = 2
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.execute.return_value) = count_result
        # Mock: delete
        (mock_inst.table.return_value.delete.return_value
         .eq.return_value.eq.return_value.execute.return_value.data) = [SAMPLE_AGENT_ROW]
        mock_sb.return_value = mock_inst

        resp = client.delete("/api/clients/client-id-123/agents/agent-1")
        assert resp.status_code == 200
        assert "eliminado" in resp.json()["message"].lower()
        app.dependency_overrides.clear()

    @patch("api.routes.agents.get_supabase")
    def test_delete_last_agent_forbidden(self, mock_sb):
        """No se puede eliminar el último agente."""
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        # Mock: count de agentes = 1
        count_result = MagicMock()
        count_result.count = 1
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.execute.return_value) = count_result
        mock_sb.return_value = mock_inst

        resp = client.delete("/api/clients/client-id-123/agents/agent-1")
        assert resp.status_code == 400
        assert "último" in resp.json()["detail"].lower()
        app.dependency_overrides.clear()
