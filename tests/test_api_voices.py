"""Tests para rutas de voces."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, mock_open, patch

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

SAMPLE_VOICES_JSON = json.dumps({
    "voices": {
        "es_female_warm": {
            "id": "voice-1",
            "name": "María",
            "language": "es",
            "gender": "female",
            "description": "Cálida y amigable",
        }
    }
})


class TestListVoices:
    @patch("builtins.open", mock_open(read_data=SAMPLE_VOICES_JSON))
    def test_list_voices(self):
        resp = client.get("/api/voices")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "María"
        assert data[0]["id"] == "voice-1"

    @patch("builtins.open", mock_open(read_data=SAMPLE_VOICES_JSON))
    def test_list_voices_structure(self):
        resp = client.get("/api/voices")
        assert resp.status_code == 200
        data = resp.json()
        voice = data[0]
        assert "key" in voice
        assert "id" in voice
        assert "name" in voice
        assert "language" in voice
        assert "gender" in voice
        assert "description" in voice
        assert voice["key"] == "es_female_warm"
        assert voice["language"] == "es"
        assert voice["gender"] == "female"

    @patch("builtins.open", mock_open(read_data=SAMPLE_VOICES_JSON))
    def test_list_voices_no_auth(self):
        # Asegurarse de que no hay override de auth — el endpoint no requiere autenticación
        app.dependency_overrides.pop(get_current_user, None)
        resp = client.get("/api/voices")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        app.dependency_overrides.clear()
