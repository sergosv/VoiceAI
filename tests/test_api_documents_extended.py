"""Tests extendidos para api/routes/documents.py — upload, permisos admin, etc."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.middleware.auth import CurrentUser, get_current_user


SAMPLE_DOC = {
    "id": "doc-uuid-1",
    "client_id": "client-id-123",
    "filename": "servicios.pdf",
    "file_type": "pdf",
    "file_size_bytes": 5120,
    "indexing_status": "indexed",
    "description": "Lista de servicios",
    "uploaded_at": "2026-02-27T10:00:00+00:00",
}


@pytest.fixture()
def admin_client():
    mock_user = CurrentUser(
        id="admin-uuid", auth_user_id="auth-admin", email="admin@test.com",
        role="admin", client_id=None,
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture()
def client_user():
    mock_user = CurrentUser(
        id="client-uuid", auth_user_id="auth-client", email="cli@test.com",
        role="client", client_id="client-id-123",
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture()
def mock_sb():
    with patch("api.routes.documents.get_supabase") as m:
        sb = MagicMock()
        m.return_value = sb
        yield sb


class TestListDocumentsExtended:
    def test_admin_lists_all(self, admin_client, mock_sb):
        (mock_sb.table.return_value
         .select.return_value
         .order.return_value
         .execute.return_value.data) = [SAMPLE_DOC]

        resp = admin_client.get("/api/documents")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_admin_filters_by_client(self, admin_client, mock_sb):
        (mock_sb.table.return_value
         .select.return_value
         .order.return_value
         .eq.return_value
         .execute.return_value.data) = [SAMPLE_DOC]

        resp = admin_client.get("/api/documents?client_id=client-id-123")
        assert resp.status_code == 200

    def test_client_no_client_id_returns_empty(self, mock_sb):
        mock_user = CurrentUser(
            id="x", auth_user_id="ax", email="x@t.com",
            role="client", client_id=None,
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user
        tc = TestClient(app, raise_server_exceptions=False)

        resp = tc.get("/api/documents")
        assert resp.status_code == 200
        assert resp.json() == []
        app.dependency_overrides.clear()

    def test_empty_documents(self, admin_client, mock_sb):
        (mock_sb.table.return_value
         .select.return_value
         .order.return_value
         .execute.return_value.data) = []

        resp = admin_client.get("/api/documents")
        assert resp.status_code == 200
        assert resp.json() == []


class TestUploadDocument:
    @patch("api.routes.documents.save_document_record")
    @patch("api.routes.documents.upload_document_to_gemini")
    def test_upload_success(self, mock_gemini, mock_save, client_user, mock_sb):
        (mock_sb.table.return_value
         .select.return_value
         .eq.return_value
         .limit.return_value
         .execute.return_value.data) = [{"file_search_store_id": "store-123"}]

        mock_save.return_value = SAMPLE_DOC

        file_content = b"PDF content here for testing purposes"
        resp = client_user.post(
            "/api/documents",
            files={"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")},
            data={"description": "Test doc"},
        )
        assert resp.status_code == 201
        assert resp.json()["filename"] == "servicios.pdf"

    def test_upload_no_client_id(self, admin_client, mock_sb):
        """Admin sin client_id y sin pasar client_id en form -> 400."""
        file_content = b"some content"
        resp = admin_client.post(
            "/api/documents",
            files={"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")},
            data={"description": "Test"},
        )
        assert resp.status_code == 400

    def test_upload_client_not_found(self, client_user, mock_sb):
        (mock_sb.table.return_value
         .select.return_value
         .eq.return_value
         .limit.return_value
         .execute.return_value.data) = []

        file_content = b"some content"
        resp = client_user.post(
            "/api/documents",
            files={"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")},
        )
        assert resp.status_code == 404

    def test_upload_no_store_id(self, client_user, mock_sb):
        (mock_sb.table.return_value
         .select.return_value
         .eq.return_value
         .limit.return_value
         .execute.return_value.data) = [{"file_search_store_id": None}]

        file_content = b"some content"
        resp = client_user.post(
            "/api/documents",
            files={"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")},
        )
        assert resp.status_code == 400

    def test_upload_empty_file(self, client_user, mock_sb):
        (mock_sb.table.return_value
         .select.return_value
         .eq.return_value
         .limit.return_value
         .execute.return_value.data) = [{"file_search_store_id": "store-123"}]

        resp = client_user.post(
            "/api/documents",
            files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
        )
        assert resp.status_code == 400

    @patch("api.routes.documents.upload_document_to_gemini", side_effect=Exception("Gemini error"))
    def test_upload_gemini_failure(self, mock_gemini, client_user, mock_sb):
        (mock_sb.table.return_value
         .select.return_value
         .eq.return_value
         .limit.return_value
         .execute.return_value.data) = [{"file_search_store_id": "store-123"}]

        file_content = b"some valid content"
        resp = client_user.post(
            "/api/documents",
            files={"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")},
        )
        assert resp.status_code == 502


class TestDeleteDocumentExtended:
    @patch("api.routes.documents.delete_document_record")
    def test_admin_deletes_any(self, mock_delete, admin_client, mock_sb):
        (mock_sb.table.return_value
         .select.return_value
         .eq.return_value
         .limit.return_value
         .execute.return_value.data) = [SAMPLE_DOC]

        resp = admin_client.delete("/api/documents/doc-uuid-1")
        assert resp.status_code == 200
        mock_delete.assert_called_once()

    def test_delete_not_found(self, admin_client, mock_sb):
        (mock_sb.table.return_value
         .select.return_value
         .eq.return_value
         .limit.return_value
         .execute.return_value.data) = []

        resp = admin_client.delete("/api/documents/nonexistent")
        assert resp.status_code == 404
