"""Tests de integración para endpoints de callbacks y DNC."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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


def _override(user):
    async def _dep():
        return user
    return _dep


# ── DNC ──

class TestDNCEndpoints:
    def setup_method(self) -> None:
        app.dependency_overrides[get_current_user] = _override(CLIENT_USER)

    def teardown_method(self) -> None:
        app.dependency_overrides.clear()

    def test_list_dnc_client_scoped(self) -> None:
        mock_sb = MagicMock()
        mock_table = MagicMock()
        mock_table.range.return_value.execute.return_value.data = []
        mock_table.range.return_value.execute.return_value.count = 0
        mock_sb.table.return_value.select.return_value.order.return_value.eq.return_value = mock_table

        with patch("api.routes.dnc.get_supabase", return_value=mock_sb):
            resp = client.get("/api/dnc?page=1&per_page=10")
            assert resp.status_code == 200
            assert resp.json()["data"] == []

    def test_add_dnc_normalizes_phone(self) -> None:
        mock_sb = MagicMock()
        mock_sb.table.return_value.upsert.return_value.execute.return_value.data = [
            {"id": "dnc-1", "phone": "+529994890531"}
        ]
        with patch("api.routes.dnc.get_supabase", return_value=mock_sb):
            resp = client.post("/api/dnc", json={
                "phone": "+52 (999) 489-0531",
                "reason": "test",
            })
            assert resp.status_code == 200
            # Verificar que se llamó upsert con el phone normalizado
            call_args = mock_sb.table.return_value.upsert.call_args
            assert call_args[0][0]["phone"] == "+529994890531"

    def test_admin_needs_client_id(self) -> None:
        app.dependency_overrides[get_current_user] = _override(ADMIN_USER)
        mock_sb = MagicMock()
        with patch("api.routes.dnc.get_supabase", return_value=mock_sb):
            # Admin sin impersonar + sin client_id en body = error
            resp = client.post("/api/dnc", json={"phone": "+529994890531"})
            assert resp.status_code == 400
            assert "client_id" in resp.json()["detail"].lower()


# ── Callbacks ──

class TestCallbacksEndpoints:
    def setup_method(self) -> None:
        app.dependency_overrides[get_current_user] = _override(CLIENT_USER)

    def teardown_method(self) -> None:
        app.dependency_overrides.clear()

    def test_list_callbacks(self) -> None:
        mock_sb = MagicMock()
        mock_q = MagicMock()
        mock_q.execute.return_value.data = []
        mock_q.execute.return_value.count = 0
        mock_sb.table.return_value.select.return_value.order.return_value.eq.return_value.range.return_value = mock_q

        with patch("api.routes.callbacks.get_supabase", return_value=mock_sb):
            resp = client.get("/api/callbacks?page=1&per_page=10")
            assert resp.status_code == 200
            assert "data" in resp.json()
            assert "total" in resp.json()

    def test_bulk_cancel_requires_client_id_for_admin(self) -> None:
        app.dependency_overrides[get_current_user] = _override(ADMIN_USER)
        mock_sb = MagicMock()
        with patch("api.routes.callbacks.get_supabase", return_value=mock_sb):
            resp = client.post("/api/callbacks/bulk-cancel")
            assert resp.status_code == 400

    def test_bulk_cancel_works_for_client(self) -> None:
        # El MagicMock responde a cualquier cadena de .eq().eq()
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"id": "1"}, {"id": "2"}]
        # Crear mock que retorne mock_result al final de cualquier cadena
        mock_sb.table.return_value = MagicMock()
        chain = mock_sb.table.return_value
        chain.update.return_value = chain
        chain.eq.return_value = chain
        chain.execute.return_value = mock_result
        with patch("api.routes.callbacks.get_supabase", return_value=mock_sb):
            resp = client.post("/api/callbacks/bulk-cancel")
            assert resp.status_code == 200
            assert resp.json()["cancelled"] == 2
