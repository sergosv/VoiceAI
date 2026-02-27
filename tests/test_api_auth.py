"""Tests para rutas de autenticación."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.middleware.auth import CurrentUser, get_current_user

client = TestClient(app)

ADMIN_USER = CurrentUser(
    id="admin-uuid",
    auth_user_id="auth-admin-uuid",
    email="admin@test.com",
    role="admin",
    client_id=None,
)

CLIENT_USER = CurrentUser(
    id="client-uuid",
    auth_user_id="auth-client-uuid",
    email="cliente@test.com",
    role="client",
    client_id="client-id-123",
)


def _override_admin():
    async def _dep():
        return ADMIN_USER
    return _dep


def _override_client():
    async def _dep():
        return CLIENT_USER
    return _dep


class TestAuthMe:
    def test_get_me_admin(self):
        app.dependency_overrides[get_current_user] = _override_admin()
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "admin@test.com"
        assert data["role"] == "admin"
        assert data["client_id"] is None
        app.dependency_overrides.clear()

    def test_get_me_client(self):
        app.dependency_overrides[get_current_user] = _override_client()
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "client"
        assert data["client_id"] == "client-id-123"
        app.dependency_overrides.clear()

    def test_get_me_no_auth(self):
        app.dependency_overrides.clear()
        resp = client.get("/api/auth/me")
        assert resp.status_code in (401, 403)


class TestRegisterUser:
    @patch("api.routes.auth.create_supabase_client")
    @patch("api.routes.auth.get_supabase")
    def test_register_user_as_admin(self, mock_sb, mock_create_sb):
        app.dependency_overrides[get_current_user] = _override_admin()

        # Mock Supabase Auth admin.create_user
        mock_auth_response = MagicMock()
        mock_auth_response.user.id = "new-auth-uid"
        mock_admin_client = MagicMock()
        mock_admin_client.auth.admin.create_user.return_value = mock_auth_response
        mock_create_sb.return_value = mock_admin_client

        # Mock insert en tabla users
        mock_sb_inst = MagicMock()
        mock_sb_inst.table.return_value.insert.return_value.execute.return_value.data = [{
            "id": "new-user-id",
            "auth_user_id": "new-auth-uid",
            "email": "nuevo@test.com",
            "role": "client",
            "client_id": "client-abc",
            "display_name": "Nuevo User",
        }]
        mock_sb.return_value = mock_sb_inst

        resp = client.post("/api/auth/register-user", json={
            "email": "nuevo@test.com",
            "password": "SecurePass123!",
            "role": "client",
            "client_id": "client-abc",
            "display_name": "Nuevo User",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "nuevo@test.com"
        assert data["role"] == "client"
        app.dependency_overrides.clear()

    def test_register_user_as_client_forbidden(self):
        app.dependency_overrides[get_current_user] = _override_client()
        resp = client.post("/api/auth/register-user", json={
            "email": "hack@test.com",
            "password": "pass",
        })
        assert resp.status_code == 403
        app.dependency_overrides.clear()
