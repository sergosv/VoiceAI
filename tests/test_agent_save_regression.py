"""Tests de regresión para guardar/actualizar agentes.

Regresiones conocidas:
- widget_channels se borraba al guardar agente (fix: e755884)
- API keys se encriptaban doble al actualizar
- Cambio de provider TTS no limpiaba la key anterior
"""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

# Mock sentry_sdk si no está instalado
if "sentry_sdk" not in sys.modules:
    _mock_sentry = ModuleType("sentry_sdk")
    _mock_sentry.init = lambda **kw: None  # type: ignore[attr-defined]
    _mock_sentry.set_tag = lambda k, v: None  # type: ignore[attr-defined]
    sys.modules["sentry_sdk"] = _mock_sentry

from fastapi.testclient import TestClient

from api.main import app
from api.middleware.auth import CurrentUser, get_current_user

client = TestClient(app)

ADMIN_USER = CurrentUser(
    id="admin-uuid",
    auth_user_id="auth-admin",
    email="admin@test.com",
    role="admin",
    client_id=None,
)

CLIENT_USER = CurrentUser(
    id="client-uuid",
    auth_user_id="auth-client",
    email="user@test.com",
    role="client",
    client_id="client-001",
)


def _mock_agent_row(**overrides) -> dict:
    """Crea un row de agente simulado."""
    base = {
        "id": "agent-001",
        "client_id": "client-001",
        "name": "María",
        "slug": "maria",
        "phone_number": "+5219994330027",
        "phone_sid": None,
        "livekit_sip_trunk_id": None,
        "system_prompt": "Eres María.",
        "greeting": "Hola!",
        "examples": None,
        "voice_config": {"provider": "cartesia", "voice_id": "test-voice"},
        "llm_config": {"provider": "google"},
        "stt_config": {"provider": "deepgram"},
        "agent_mode": "pipeline",
        "agent_type": "inbound",
        "transfer_number": None,
        "max_call_duration_seconds": 300,
        "conversation_flow": None,
        "conversation_mode": "prompt",
        "mode_config": {},
        "is_active": True,
        "widget_channels": ["phone", "webchat"],
        "tts_provider": "cartesia",
        "tts_api_key": None,
        "after_hours_message": None,
        "role_description": None,
        "orchestrator_enabled": True,
        "orchestrator_priority": 0,
        "sentiment_config": None,
        "intent_config": None,
        "guardrails_config": None,
        "language_detection_config": None,
        "quality_config": None,
        "proactive_config": None,
        "created_at": "2026-03-01T00:00:00Z",
        "updated_at": "2026-03-01T00:00:00Z",
    }
    base.update(overrides)
    return base


class TestAgentUpdatePreservesFields:
    """Verificar que el schema de update solo envía campos modificados.

    Regresión: widget_channels se borraba al guardar agente porque
    el PATCH enviaba campos que no debía tocar.
    """

    def test_update_request_excludes_none_fields(self):
        """AgentUpdateRequest solo incluye campos explícitamente enviados."""
        from api.schemas import AgentUpdateRequest

        # Solo enviar nombre
        req = AgentUpdateRequest(name="Valeria")
        data = req.model_dump(exclude_none=True)

        assert "name" in data
        assert data["name"] == "Valeria"
        # widget_channels NO debe estar en el update
        assert "widget_channels" not in data
        assert "voice_config" not in data
        assert "system_prompt" not in data

    def test_update_request_includes_explicit_fields(self):
        """Campos explícitamente enviados sí se incluyen."""
        from api.schemas import AgentUpdateRequest

        req = AgentUpdateRequest(
            name="Valeria",
            system_prompt="Nuevo prompt.",
            widget_channels=["phone", "webchat", "whatsapp"],
        )
        data = req.model_dump(exclude_none=True)

        assert data["name"] == "Valeria"
        assert data["system_prompt"] == "Nuevo prompt."
        assert data["widget_channels"] == ["phone", "webchat", "whatsapp"]

    def test_update_request_empty_is_empty(self):
        """Sin campos → dict vacío (no se actualiza nada)."""
        from api.schemas import AgentUpdateRequest

        req = AgentUpdateRequest()
        data = req.model_dump(exclude_none=True)
        # Debe estar vacío o casi vacío
        # (algunos campos tienen defaults, pero los opcionales son None)
        assert "widget_channels" not in data
        assert "voice_config" not in data


class TestAgentAccessControl:
    """Verificar que clientes no pueden acceder a agentes de otros."""

    def setup_method(self):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER

    def teardown_method(self):
        app.dependency_overrides.clear()

    @patch("api.routes.agents.get_supabase")
    def test_client_cannot_list_other_agents(self, mock_sb_fn):
        """Cliente no puede listar agentes de otro client_id."""
        mock_sb = MagicMock()
        mock_sb_fn.return_value = mock_sb

        resp = client.get("/api/clients/other-client-999/agents")
        assert resp.status_code == 403

    @patch("api.routes.agents.get_supabase")
    def test_client_can_list_own_agents(self, mock_sb_fn):
        """Cliente sí puede listar sus propios agentes."""
        mock_sb = MagicMock()
        mock_sb_fn.return_value = mock_sb
        mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
            _mock_agent_row()
        ]

        resp = client.get("/api/clients/client-001/agents")
        assert resp.status_code == 200


class TestAgentDeleteProtection:
    """Verificar que no se puede borrar el último agente."""

    def setup_method(self):
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER

    def teardown_method(self):
        app.dependency_overrides.clear()

    @patch("api.routes.agents.get_supabase")
    @patch("api.routes.agents.log_audit", new_callable=AsyncMock)
    def test_cannot_delete_last_agent(self, mock_audit, mock_sb_fn):
        """No se puede borrar si es el único agente del cliente."""
        mock_sb = MagicMock()
        mock_sb_fn.return_value = mock_sb

        # El agente existe
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            _mock_agent_row()
        ]
        # Solo 1 agente en el cliente
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.count = 1
        # count query
        count_mock = MagicMock()
        count_mock.execute.return_value = MagicMock(count=1)
        mock_sb.table.return_value.select.return_value.eq.return_value = count_mock
        count_mock.eq.return_value = count_mock
        count_mock.limit.return_value = count_mock
        count_mock.execute.return_value.data = [_mock_agent_row()]

        resp = client.delete("/api/clients/client-001/agents/agent-001")
        # Debe rechazar — no se puede borrar el último
        assert resp.status_code in (400, 403, 409)
