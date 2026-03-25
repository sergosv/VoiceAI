"""Tests para herramientas de tareas/notas/email del PA."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestPaCreateTask:
    @pytest.mark.asyncio
    async def test_creates_task_with_due_date(self):
        from agent.tools.pa_tasks_tool import pa_create_task

        sb = MagicMock()
        sb.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "t1", "content": "Llamar a Juan", "item_type": "task"}]
        )

        with patch("agent.tools.pa_tasks_tool.generate_embedding", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 768
            result = await pa_create_task(
                sb, agent_id="a1", client_id="c1",
                description="Llamar a Juan", due_date="2026-04-01",
            )

        assert result["id"] == "t1"
        insert_data = sb.table.return_value.insert.call_args[0][0]
        assert insert_data["item_type"] == "task"
        assert insert_data["content"] == "Llamar a Juan"
        meta = json.loads(insert_data["metadata"])
        assert meta["due_date"] == "2026-04-01"


class TestPaListTasks:
    @pytest.mark.asyncio
    async def test_lists_pending_tasks(self):
        from agent.tools.pa_tasks_tool import pa_list_tasks

        sb = MagicMock()
        mock_query = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.eq.return_value = mock_query
        mock_query.execute.return_value = MagicMock(
            data=[{"id": "t1", "content": "Tarea 1", "is_completed": False}]
        )

        result = await pa_list_tasks(sb, agent_id="a1", include_completed=False)
        assert len(result) == 1


class TestPaCompleteTask:
    @pytest.mark.asyncio
    async def test_completes_matching_task(self):
        from agent.tools.pa_tasks_tool import pa_complete_task

        sb = MagicMock()
        sb.rpc.return_value.execute.return_value = MagicMock(
            data=[{"id": "t1", "content": "Llamar a Juan", "is_completed": False, "metadata": "{}"}]
        )
        sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        with patch("agent.tools.pa_tasks_tool.generate_embedding", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 768
            result = await pa_complete_task(sb, agent_id="a1", task_query="Juan")

        assert result is True
        update_call = sb.table.return_value.update.call_args[0][0]
        assert update_call["is_completed"] is True

    @pytest.mark.asyncio
    async def test_returns_false_when_not_found(self):
        from agent.tools.pa_tasks_tool import pa_complete_task

        sb = MagicMock()
        sb.rpc.return_value.execute.return_value = MagicMock(data=[])

        with patch("agent.tools.pa_tasks_tool.generate_embedding", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 768
            result = await pa_complete_task(sb, agent_id="a1", task_query="nada")

        assert result is False


class TestPaCreateNote:
    @pytest.mark.asyncio
    async def test_creates_note_with_title(self):
        from agent.tools.pa_tasks_tool import pa_create_note

        sb = MagicMock()
        sb.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "n1", "content": "Precio $500", "item_type": "note"}]
        )

        with patch("agent.tools.pa_tasks_tool.generate_embedding", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 768
            result = await pa_create_note(
                sb, agent_id="a1", client_id="c1",
                content="Precio $500", title="Proveedor",
            )

        assert result["id"] == "n1"
        insert_data = sb.table.return_value.insert.call_args[0][0]
        meta = json.loads(insert_data["metadata"])
        assert meta["title"] == "Proveedor"


class TestPaSendEmail:
    @pytest.mark.asyncio
    async def test_sends_email_with_config(self):
        from agent.tools.pa_email_tool import pa_send_email

        sb = MagicMock()
        # Mock pa_load_email_config
        sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{
                "from_name": "Asistente",
                "from_email": "asistente@test.com",
                "reply_to": "owner@test.com",
                "signature": "Firma",
            }]
        )

        import sys
        mock_resend = MagicMock()
        mock_resend.Emails.send.return_value = {"id": "email-1"}
        sys.modules["resend"] = mock_resend

        with patch.dict("os.environ", {"RESEND_API_KEY": "re_test_123"}):
            result = await pa_send_email(
                sb, agent_id="a1",
                to_email="pedro@test.com", subject="Hola", body="Texto",
            )

        assert "enviado" in result.lower()
        send_call = mock_resend.Emails.send.call_args[0][0]
        assert send_call["to"] == ["pedro@test.com"]
        assert "Firma" in send_call["text"]
        del sys.modules["resend"]

    @pytest.mark.asyncio
    async def test_returns_error_without_config(self):
        from agent.tools.pa_email_tool import pa_send_email

        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[]
        )

        result = await pa_send_email(
            sb, agent_id="a1",
            to_email="x@x.com", subject="Test", body="Body",
        )
        assert "error" in result.lower() or "configur" in result.lower()
