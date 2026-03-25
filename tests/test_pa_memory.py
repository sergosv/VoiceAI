"""Tests para herramientas de memoria del Asistente Personal."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestPaRemember:
    @pytest.mark.asyncio
    async def test_remember_inserts_with_embedding(self):
        from agent.tools.pa_memory_tool import pa_remember

        sb = MagicMock()
        mock_result = MagicMock(data=[{"id": "mem-1"}])
        sb.table.return_value.insert.return_value.execute.return_value = mock_result

        with patch("agent.tools.pa_memory_tool.generate_embedding", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 768
            result = await pa_remember(
                sb, agent_id="a1", client_id="c1",
                content="Tengo junta el viernes", item_type="fact",
            )
        assert result == "mem-1"
        mock_embed.assert_called_once_with("Tengo junta el viernes")
        insert_call = sb.table.return_value.insert.call_args[0][0]
        assert insert_call["content"] == "Tengo junta el viernes"
        assert insert_call["item_type"] == "fact"
        assert insert_call["embedding"] == [0.1] * 768

    @pytest.mark.asyncio
    async def test_remember_works_without_embedding(self):
        from agent.tools.pa_memory_tool import pa_remember

        sb = MagicMock()
        mock_result = MagicMock(data=[{"id": "mem-2"}])
        sb.table.return_value.insert.return_value.execute.return_value = mock_result

        with patch("agent.tools.pa_memory_tool.generate_embedding", new_callable=AsyncMock) as mock_embed:
            mock_embed.side_effect = Exception("API error")
            result = await pa_remember(
                sb, agent_id="a1", client_id="c1",
                content="Algo", item_type="fact",
            )
        assert result == "mem-2"
        insert_call = sb.table.return_value.insert.call_args[0][0]
        assert "embedding" not in insert_call


class TestPaForget:
    @pytest.mark.asyncio
    async def test_forget_marks_deleted(self):
        from agent.tools.pa_memory_tool import pa_forget

        sb = MagicMock()
        sb.rpc.return_value.execute.return_value = MagicMock(
            data=[{"id": "mem-1", "content": "dentista"}]
        )
        sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        with patch("agent.tools.pa_memory_tool.generate_embedding", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 768
            count = await pa_forget(sb, agent_id="a1", query="dentista")

        assert count == 1
        sb.table.return_value.update.assert_called_once_with({"is_deleted": True})

    @pytest.mark.asyncio
    async def test_forget_returns_zero_when_not_found(self):
        from agent.tools.pa_memory_tool import pa_forget

        sb = MagicMock()
        sb.rpc.return_value.execute.return_value = MagicMock(data=[])

        with patch("agent.tools.pa_memory_tool.generate_embedding", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 768
            count = await pa_forget(sb, agent_id="a1", query="nada")

        assert count == 0


class TestPaSearchMemory:
    @pytest.mark.asyncio
    async def test_search_returns_results(self):
        from agent.tools.pa_memory_tool import pa_search_memory

        sb = MagicMock()
        sb.rpc.return_value.execute.return_value = MagicMock(
            data=[
                {"id": "m1", "item_type": "fact", "content": "Junta viernes", "similarity": 0.85},
                {"id": "m2", "item_type": "note", "content": "Precio $500", "similarity": 0.72},
            ]
        )

        with patch("agent.tools.pa_memory_tool.generate_embedding", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 768
            results = await pa_search_memory(
                sb, agent_id="a1", query="junta", limit=5,
            )

        assert len(results) == 2
        assert results[0]["content"] == "Junta viernes"

    @pytest.mark.asyncio
    async def test_search_with_type_filter(self):
        from agent.tools.pa_memory_tool import pa_search_memory

        sb = MagicMock()
        sb.rpc.return_value.execute.return_value = MagicMock(data=[])

        with patch("agent.tools.pa_memory_tool.generate_embedding", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 768
            await pa_search_memory(
                sb, agent_id="a1", query="test",
                item_types=["task", "note"],
            )

        rpc_call = sb.rpc.call_args
        assert rpc_call[0][1]["p_item_types"] == ["task", "note"]
