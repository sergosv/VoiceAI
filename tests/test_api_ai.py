"""Tests para api/routes/ai.py — asistente IA de prompts."""

from __future__ import annotations

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


class TestGeneratePrompt:
    @patch("api.routes.ai._call_gemini", return_value="Eres Sofia, asistente de Dental Plus...")
    def test_generate_agent_prompt(self, mock_gemini, client):
        resp = client.post("/api/ai/generate-prompt", json={
            "type": "agent",
            "business_name": "Dental Plus",
            "business_type": "dental",
            "agent_name": "Sofia",
            "tone": "amable",
            "main_function": "Agendar citas",
        })
        assert resp.status_code == 200
        assert "Sofia" in resp.json()["prompt"] or "Dental" in resp.json()["prompt"]
        mock_gemini.assert_called_once()

    @patch("api.routes.ai._call_gemini", return_value="Script de campaña generado...")
    def test_generate_campaign_prompt(self, mock_gemini, client):
        resp = client.post("/api/ai/generate-prompt", json={
            "type": "campaign",
            "objective": "Vender seguros",
            "product": "Seguro de vida",
            "hook": "Protege a tu familia",
            "business_name": "Seguros MX",
            "agent_name": "Carlos",
            "data_to_capture": "nombre, telefono",
            "objection_handling": "Es caro -> tenemos planes accesibles",
        })
        assert resp.status_code == 200
        mock_gemini.assert_called_once()

    @patch("api.routes.ai._call_gemini", side_effect=Exception("API error"))
    def test_gemini_error(self, mock_gemini, client):
        resp = client.post("/api/ai/generate-prompt", json={
            "type": "agent",
            "business_name": "Test",
        })
        assert resp.status_code == 502

    @patch("api.routes.ai._call_gemini", return_value="Prompt generado")
    def test_minimal_request(self, mock_gemini, client):
        """Sin campos opcionales, sigue funcionando."""
        resp = client.post("/api/ai/generate-prompt", json={"type": "agent"})
        assert resp.status_code == 200


class TestImprovePrompt:
    @patch("api.routes.ai._call_gemini", return_value="Prompt mejorado con tono mexicano...")
    def test_improve_agent_prompt(self, mock_gemini, client):
        resp = client.post("/api/ai/improve-prompt", json={
            "type": "agent",
            "prompt": "Eres un asistente basico. Responde preguntas.",
        })
        assert resp.status_code == 200
        assert "mejorado" in resp.json()["prompt"]

    @patch("api.routes.ai._call_gemini", return_value="Script mejorado...")
    def test_improve_campaign_prompt(self, mock_gemini, client):
        resp = client.post("/api/ai/improve-prompt", json={
            "type": "campaign",
            "prompt": "Hola llamo de empresa X.",
        })
        assert resp.status_code == 200

    def test_empty_prompt_rejected(self, client):
        resp = client.post("/api/ai/improve-prompt", json={
            "prompt": "   ",
        })
        assert resp.status_code == 400

    @patch("api.routes.ai._call_gemini", side_effect=Exception("Gemini down"))
    def test_gemini_error(self, mock_gemini, client):
        resp = client.post("/api/ai/improve-prompt", json={
            "prompt": "Un prompt existente",
        })
        assert resp.status_code == 502


class TestCallGemini:
    def test_no_api_key(self, client):
        """Sin GOOGLE_API_KEY, retorna 503."""
        from api.routes.ai import _call_gemini
        from fastapi import HTTPException

        with patch.dict("os.environ", {}, clear=False):
            import os
            old = os.environ.pop("GOOGLE_API_KEY", None)
            try:
                with pytest.raises(HTTPException) as exc_info:
                    _call_gemini("system", "user")
                assert exc_info.value.status_code == 503
            finally:
                if old:
                    os.environ["GOOGLE_API_KEY"] = old


class TestLoadTemplateReference:
    def test_loads_or_empty(self):
        from api.routes.ai import _load_template_reference
        result = _load_template_reference()
        # Either loads the file or returns empty string
        assert isinstance(result, str)
