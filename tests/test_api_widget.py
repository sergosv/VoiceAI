"""Tests para api/routes/widget.py — endpoints públicos del web widget."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture()
def client():
    yield TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def mock_sb():
    with patch("api.routes.widget.get_supabase") as m:
        sb = MagicMock()
        m.return_value = sb
        yield sb


SAMPLE_AGENT = {
    "id": "agent-uuid-1",
    "name": "Asistente María",
    "slug": "asistente-maria",
    "greeting": "¡Hola! ¿En qué te puedo ayudar?",
    "client_id": "client-uuid-1",
}

SAMPLE_CLIENT = {
    "id": "client-uuid-1",
    "name": "Dental Plus",
    "slug": "dental-plus",
    "language": "es",
}


class TestWidgetConfig:
    def test_found_agent_and_client(self, client, mock_sb):
        """Retorna config pública cuando agente y cliente están activos."""
        def table_side(name):
            mock = MagicMock()
            if name == "agents":
                (mock.select.return_value
                 .eq.return_value
                 .eq.return_value
                 .limit.return_value
                 .execute.return_value.data) = [SAMPLE_AGENT]
            elif name == "clients":
                (mock.select.return_value
                 .eq.return_value
                 .eq.return_value
                 .limit.return_value
                 .execute.return_value.data) = [SAMPLE_CLIENT]
            return mock

        mock_sb.table.side_effect = table_side

        resp = client.get("/api/widget/config/asistente-maria")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_name"] == "Asistente María"
        assert data["agent_slug"] == "asistente-maria"
        assert data["greeting"] == "¡Hola! ¿En qué te puedo ayudar?"
        assert data["client_name"] == "Dental Plus"
        assert data["language"] == "es"
        assert "livekit_url" in data

    def test_agent_not_found(self, client, mock_sb):
        """404 cuando no se encuentra el agente."""
        (mock_sb.table.return_value
         .select.return_value
         .eq.return_value
         .eq.return_value
         .limit.return_value
         .execute.return_value.data) = []

        resp = client.get("/api/widget/config/no-existe")
        assert resp.status_code == 404

    def test_client_inactive(self, client, mock_sb):
        """404 cuando el cliente del agente no está activo."""
        def table_side(name):
            mock = MagicMock()
            if name == "agents":
                (mock.select.return_value
                 .eq.return_value
                 .eq.return_value
                 .limit.return_value
                 .execute.return_value.data) = [SAMPLE_AGENT]
            elif name == "clients":
                (mock.select.return_value
                 .eq.return_value
                 .eq.return_value
                 .limit.return_value
                 .execute.return_value.data) = []
            return mock

        mock_sb.table.side_effect = table_side

        resp = client.get("/api/widget/config/asistente-maria")
        assert resp.status_code == 404


class TestWidgetToken:
    @patch.dict("os.environ", {
        "LIVEKIT_API_KEY": "test-key",
        "LIVEKIT_API_SECRET": "test-secret-that-is-long-enough-for-jwt",
        "LIVEKIT_URL": "wss://test.livekit.cloud",
    })
    @patch("livekit.api.AccessToken")
    def test_generates_token(self, mock_access_token_cls, client, mock_sb):
        """Genera token LiveKit cuando agente y cliente existen."""
        # Mock AccessToken chain
        mock_token = MagicMock()
        mock_token.with_identity.return_value = mock_token
        mock_token.with_name.return_value = mock_token
        mock_token.with_grants.return_value = mock_token
        mock_token.with_metadata.return_value = mock_token
        mock_token.to_jwt.return_value = "jwt-token-abc"
        mock_access_token_cls.return_value = mock_token

        def table_side(name):
            mock = MagicMock()
            if name == "agents":
                (mock.select.return_value
                 .eq.return_value
                 .eq.return_value
                 .limit.return_value
                 .execute.return_value.data) = [{"id": "a1", "client_id": "c1"}]
            elif name == "clients":
                (mock.select.return_value
                 .eq.return_value
                 .eq.return_value
                 .limit.return_value
                 .execute.return_value.data) = [{"id": "c1"}]
            return mock

        mock_sb.table.side_effect = table_side

        resp = client.post("/api/widget/token/asistente-maria")
        assert resp.status_code == 200
        data = resp.json()
        assert data["token"] == "jwt-token-abc"
        assert "room" in data
        assert data["room"].startswith("widget-")
        assert data["url"] == "wss://test.livekit.cloud"

    def test_agent_not_found(self, client, mock_sb):
        """404 cuando el agente no existe para token."""
        (mock_sb.table.return_value
         .select.return_value
         .eq.return_value
         .eq.return_value
         .limit.return_value
         .execute.return_value.data) = []

        resp = client.post("/api/widget/token/no-existe")
        assert resp.status_code == 404

    @patch.dict("os.environ", {
        "LIVEKIT_API_KEY": "test-key",
        "LIVEKIT_API_SECRET": "test-secret",
        "LIVEKIT_URL": "wss://test.livekit.cloud",
    })
    def test_client_not_found_for_token(self, client, mock_sb):
        """404 cuando el cliente del agente no está activo."""
        def table_side(name):
            mock = MagicMock()
            if name == "agents":
                (mock.select.return_value
                 .eq.return_value
                 .eq.return_value
                 .limit.return_value
                 .execute.return_value.data) = [{"id": "a1", "client_id": "c1"}]
            elif name == "clients":
                (mock.select.return_value
                 .eq.return_value
                 .eq.return_value
                 .limit.return_value
                 .execute.return_value.data) = []
            return mock

        mock_sb.table.side_effect = table_side

        resp = client.post("/api/widget/token/asistente-maria")
        assert resp.status_code == 404

    @patch.dict("os.environ", {
        "LIVEKIT_API_KEY": "",
        "LIVEKIT_API_SECRET": "",
    }, clear=False)
    def test_livekit_not_configured(self, client, mock_sb):
        """500 cuando LIVEKIT_API_KEY/SECRET no están configurados."""
        import os
        # Temporarily remove the env vars
        old_key = os.environ.pop("LIVEKIT_API_KEY", None)
        old_secret = os.environ.pop("LIVEKIT_API_SECRET", None)

        try:
            def table_side(name):
                mock = MagicMock()
                if name == "agents":
                    (mock.select.return_value
                     .eq.return_value
                     .eq.return_value
                     .limit.return_value
                     .execute.return_value.data) = [{"id": "a1", "client_id": "c1"}]
                elif name == "clients":
                    (mock.select.return_value
                     .eq.return_value
                     .eq.return_value
                     .limit.return_value
                     .execute.return_value.data) = [{"id": "c1"}]
                return mock

            mock_sb.table.side_effect = table_side

            resp = client.post("/api/widget/token/asistente-maria")
            assert resp.status_code == 500
        finally:
            if old_key:
                os.environ["LIVEKIT_API_KEY"] = old_key
            if old_secret:
                os.environ["LIVEKIT_API_SECRET"] = old_secret
