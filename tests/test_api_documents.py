"""Tests para rutas de documentos."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.middleware.auth import CurrentUser, get_current_user

client = TestClient(app)

CLIENT_USER = CurrentUser(
    id="client-uuid", auth_user_id="auth-client", email="cli@test.com",
    role="client", client_id="client-id-123",
)

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


class TestListDocuments:
    @patch("api.routes.documents.get_supabase")
    def test_client_lists_own_docs(self, mock_sb):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        (mock_inst.table.return_value.select.return_value
         .order.return_value.eq.return_value.execute.return_value.data) = [SAMPLE_DOC]
        mock_sb.return_value = mock_inst

        resp = client.get("/api/documents")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["filename"] == "servicios.pdf"
        app.dependency_overrides.clear()


class TestDeleteDocument:
    @patch("api.routes.documents.delete_document_record")
    @patch("api.routes.documents.get_supabase")
    def test_client_can_delete_own_doc(self, mock_sb, mock_delete):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_inst = MagicMock()
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [SAMPLE_DOC]
        mock_sb.return_value = mock_inst

        resp = client.delete("/api/documents/doc-uuid-1")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Documento eliminado"
        app.dependency_overrides.clear()

    @patch("api.routes.documents.get_supabase")
    def test_client_cannot_delete_other_doc(self, mock_sb):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        other_doc = {**SAMPLE_DOC, "client_id": "other-client"}
        mock_inst = MagicMock()
        (mock_inst.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [other_doc]
        mock_sb.return_value = mock_inst

        resp = client.delete("/api/documents/doc-uuid-1")
        assert resp.status_code == 403
        app.dependency_overrides.clear()
