"""Tests para agent/tools/file_search.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agent.tools.file_search import search_knowledge_base


class TestSearchKnowledgeBase:
    """Tests para search_knowledge_base()."""

    @pytest.mark.asyncio
    async def test_returns_response_text(self) -> None:
        mock_response = MagicMock()
        mock_response.text = "Los horarios son lunes a viernes 9am-6pm."

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch("agent.tools.file_search._get_gemini", return_value=mock_client):
            result = await search_knowledge_base("¿horarios?", "stores/test-123")

        assert "horarios" in result
        assert "lunes a viernes" in result
        mock_client.models.generate_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_store_id_returns_message(self) -> None:
        result = await search_knowledge_base("pregunta", "")
        assert "No hay base de conocimientos" in result

    @pytest.mark.asyncio
    async def test_none_store_id_returns_message(self) -> None:
        # store_id vacío se evalúa como falsy
        result = await search_knowledge_base("pregunta", "")
        assert "No hay base de conocimientos" in result

    @pytest.mark.asyncio
    async def test_handles_api_exception(self) -> None:
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("API error")

        with patch("agent.tools.file_search._get_gemini", return_value=mock_client):
            result = await search_knowledge_base("¿algo?", "stores/test-123")

        assert "No pude consultar" in result

    @pytest.mark.asyncio
    async def test_handles_none_response_text(self) -> None:
        mock_response = MagicMock()
        mock_response.text = None

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch("agent.tools.file_search._get_gemini", return_value=mock_client):
            result = await search_knowledge_base("¿algo?", "stores/test-123")

        assert "No se encontró información relevante" in result

    @pytest.mark.asyncio
    async def test_passes_correct_model_and_store(self) -> None:
        mock_response = MagicMock()
        mock_response.text = "resultado"

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch("agent.tools.file_search._get_gemini", return_value=mock_client):
            await search_knowledge_base("consulta", "stores/my-store")

        call_kwargs = mock_client.models.generate_content.call_args
        assert call_kwargs.kwargs["model"] == "gemini-2.5-flash"
