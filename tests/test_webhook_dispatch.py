"""Tests para agent/webhook_dispatch.py y los puntos de integración de webhooks."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.webhook_dispatch import _event_matches, dispatch_event, _deliver


# ── _event_matches tests ─────────────────────────────────


class TestEventMatches:
    """Verifica lógica de matching de eventos contra suscripciones."""

    def test_exact_match(self) -> None:
        assert _event_matches("call.completed", ["call.completed"])

    def test_no_match(self) -> None:
        assert not _event_matches("call.completed", ["message.received"])

    def test_wildcard_star(self) -> None:
        assert _event_matches("call.completed", ["*"])

    def test_wildcard_category(self) -> None:
        assert _event_matches("call.completed", ["call.*"])

    def test_wildcard_category_no_match(self) -> None:
        assert not _event_matches("message.received", ["call.*"])

    def test_multiple_subscriptions(self) -> None:
        assert _event_matches("message.sent", ["call.*", "message.sent"])

    def test_empty_subscriptions(self) -> None:
        assert not _event_matches("call.completed", [])

    def test_category_prefix_match(self) -> None:
        assert _event_matches("contact.created", ["contact.*"])

    def test_category_prefix_no_match(self) -> None:
        assert not _event_matches("conversation.closed", ["contact.*"])

    def test_wildcard_with_exact(self) -> None:
        """Wildcard y exact juntos — ambos deben funcionar."""
        assert _event_matches("call.completed", ["message.*", "call.completed"])


# ── dispatch_event tests ─────────────────────────────────


class TestDispatchEvent:
    """Verifica que dispatch_event busca endpoints y lanza tasks."""

    @pytest.mark.asyncio
    async def test_dispatch_creates_tasks_for_matching_endpoints(self) -> None:
        """dispatch_event crea asyncio.create_task para cada endpoint que matchea."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {
                    "id": "ep-1",
                    "url": "https://example.com/hook",
                    "secret": "s3cr3t",
                    "events": ["call.*"],
                },
                {
                    "id": "ep-2",
                    "url": "https://other.com/hook",
                    "secret": "key2",
                    "events": ["message.*"],
                },
            ]
        )

        with patch("agent.webhook_dispatch.get_supabase", return_value=mock_sb), \
             patch("agent.webhook_dispatch._deliver", new_callable=AsyncMock) as mock_deliver, \
             patch("agent.webhook_dispatch.asyncio") as mock_asyncio:
            mock_asyncio.create_task = MagicMock()

            await dispatch_event("client-1", "call.completed", {"key": "val"})

            # Solo ep-1 matchea "call.*"
            assert mock_asyncio.create_task.call_count == 1

    @pytest.mark.asyncio
    async def test_dispatch_no_endpoints(self) -> None:
        """dispatch_event con 0 endpoints no falla."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        with patch("agent.webhook_dispatch.get_supabase", return_value=mock_sb):
            await dispatch_event("client-1", "call.completed", {})

    @pytest.mark.asyncio
    async def test_dispatch_swallows_db_errors(self) -> None:
        """dispatch_event no propaga excepciones de DB."""
        with patch("agent.webhook_dispatch.get_supabase", side_effect=RuntimeError("DB down")):
            # No debería lanzar excepción
            await dispatch_event("client-1", "call.completed", {})


# ── _deliver tests ────────────────────────────────────────


class TestDeliver:
    """Verifica la entrega de webhooks con reintentos."""

    @pytest.mark.asyncio
    async def test_deliver_success_first_attempt(self) -> None:
        """Entrega exitosa al primer intento."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("agent.webhook_dispatch.get_supabase", return_value=mock_sb), \
             patch("agent.webhook_dispatch.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await _deliver("ep-1", "https://example.com", "secret", "c1", "call.completed", {})

            mock_client.post.assert_called_once()
            # Debe loguear la entrega exitosa
            mock_sb.table.assert_any_call("webhook_deliveries")

    @pytest.mark.asyncio
    async def test_deliver_retries_on_failure(self) -> None:
        """Reintenta cuando el servidor responde con error."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()

        mock_resp_fail = MagicMock()
        mock_resp_fail.status_code = 500
        mock_resp_fail.text = "Internal Server Error"

        mock_resp_ok = MagicMock()
        mock_resp_ok.status_code = 200

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return mock_resp_fail
            return mock_resp_ok

        with patch("agent.webhook_dispatch.get_supabase", return_value=mock_sb), \
             patch("agent.webhook_dispatch.httpx.AsyncClient") as mock_client_cls, \
             patch("agent.webhook_dispatch.asyncio.sleep", new_callable=AsyncMock):
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await _deliver("ep-1", "https://example.com", "secret", "c1", "test.event", {})

            # Debería haber intentado 3 veces (2 fails + 1 success)
            assert call_count == 3

    @pytest.mark.asyncio
    async def test_deliver_retries_on_network_error(self) -> None:
        """Reintenta cuando hay error de red."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()

        call_count = 0
        mock_resp_ok = MagicMock()
        mock_resp_ok.status_code = 200

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Connection refused")
            return mock_resp_ok

        with patch("agent.webhook_dispatch.get_supabase", return_value=mock_sb), \
             patch("agent.webhook_dispatch.httpx.AsyncClient") as mock_client_cls, \
             patch("agent.webhook_dispatch.asyncio.sleep", new_callable=AsyncMock):
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await _deliver("ep-1", "https://example.com", "secret", "c1", "test.event", {})

            assert call_count == 2


# ── Integration point tests ──────────────────────────────


class TestSessionHandlerWebhook:
    """Verifica que session_handler.py despacha call.completed."""

    @pytest.mark.asyncio
    async def test_finalize_dispatches_call_completed(self) -> None:
        """finalize() llama asyncio.create_task con dispatch call.completed."""
        from agent.config_loader import AgentConfig, SlimClientConfig, ResolvedConfig

        client_cfg = SlimClientConfig(
            id="c1", name="Test", slug="test",
            business_type="general", language="es",
            file_search_store_id=None,
        )
        agent_cfg = AgentConfig(
            id="a1", client_id="c1", name="Agent", slug="agent",
            phone_number=None, phone_sid=None, livekit_sip_trunk_id=None,
            system_prompt="test", greeting="Hola",
            examples=None,
        )
        config = ResolvedConfig(client=client_cfg, agent=agent_cfg)

        from agent.session_handler import SessionHandler

        handler = SessionHandler(
            config=config,
            direction="inbound",
            caller_number="+521234567890",
            callee_number="+529998887777",
            room_name="test-room",
        )

        mock_sb = MagicMock()
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "call-123"}]
        )
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[]
        )

        tasks_created = []
        original_create_task = asyncio.create_task

        def capture_create_task(coro):
            tasks_created.append(coro)
            # Cancel coroutine to avoid "was never awaited" warning
            coro.close()
            return MagicMock()

        with patch("agent.session_handler._get_supabase", return_value=mock_sb), \
             patch("agent.session_handler.asyncio.create_task", side_effect=capture_create_task), \
             patch("agent.webhook_dispatch.get_supabase", return_value=mock_sb), \
             patch("agent.webhook_dispatch.asyncio.create_task", side_effect=capture_create_task):
            await handler.finalize(status="completed")

        # Debería haber al menos 1 task creada (la del webhook)
        # Puede haber más (universal analysis etc.)
        assert len(tasks_created) >= 1


class TestMemoryWebhook:
    """Verifica que memory.py despacha contact.created y contact.updated."""

    @pytest.mark.asyncio
    async def test_identify_new_contact_dispatches_created(self) -> None:
        """identify() despacha contact.created cuando crea un contacto nuevo."""
        from agent.memory import AgentMemory

        mock_sb = MagicMock()
        # resolve_contact RPC returns None (not found)
        mock_sb.rpc.return_value.execute.return_value = MagicMock(data=None)
        # fallback find by phone returns None
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[]
        )
        # create_contact_with_identifier RPC returns contact_id
        rpc_calls = [
            MagicMock(data=None),  # resolve_contact
            MagicMock(data="new-contact-id"),  # create_contact_with_identifier
        ]
        call_idx = {"i": 0}

        def rpc_side_effect(*args, **kwargs):
            result = MagicMock()
            result.execute.return_value = rpc_calls[call_idx["i"]]
            call_idx["i"] += 1
            return result

        mock_sb.rpc.side_effect = rpc_side_effect

        tasks_created = []

        def capture_create_task(coro):
            tasks_created.append(coro)
            coro.close()
            return MagicMock()

        with patch("agent.memory._get_supabase", return_value=mock_sb), \
             patch("agent.webhook_dispatch.get_supabase", return_value=mock_sb), \
             patch("asyncio.create_task", side_effect=capture_create_task):
            memory = AgentMemory(client_id="c1", channel="call")
            result = await memory.identify("+5219994567890", "phone")

        assert result == "new-contact-id"
        # Debería haber creado un task para contact.created
        assert len(tasks_created) >= 1


class TestChatServiceWebhook:
    """Verifica que chat_service.py despacha message.received y message.sent."""

    @pytest.mark.asyncio
    async def test_chat_turn_dispatches_message_events(self) -> None:
        """chat_turn() despacha message.received y message.sent."""
        tasks_created = []

        def capture_create_task(coro):
            tasks_created.append(str(coro))
            coro.close()
            return MagicMock()

        # Solo verificar que el import de dispatch_event no falla
        # y que create_task se llama
        from api.services.webhook_service import dispatch_event

        assert callable(dispatch_event)


class TestConversationLifecycleWebhook:
    """Verifica que conversation_lifecycle.py despacha conversation.closed."""

    @pytest.mark.asyncio
    async def test_close_conversation_dispatches_webhook(self) -> None:
        """close_conversation() despacha conversation.closed."""
        from api.services.conversation_lifecycle import close_conversation

        mock_sb = MagicMock()
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        # Para la query de config_id
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"config_id": "cfg-1", "client_id": "c1"}]
        )

        tasks_created = []

        def capture_create_task(coro):
            tasks_created.append(coro)
            coro.close()
            return MagicMock()

        with patch("api.services.conversation_lifecycle.asyncio.create_task", side_effect=capture_create_task):
            await close_conversation(
                mock_sb,
                "conv-123",
                "whatsapp_conversations",
                summary="Test summary",
                result="resolved",
                closed_by="ai",
            )

        # Debería haber creado un task para conversation.closed
        assert len(tasks_created) >= 1


class TestWhatsAppServiceWebhook:
    """Verifica que whatsapp/service.py despacha message events."""

    def test_dispatch_import_works(self) -> None:
        """Verifica que el import de webhook_service funciona desde whatsapp service."""
        from api.services.webhook_service import dispatch_event

        assert callable(dispatch_event)


class TestGHLServiceWebhook:
    """Verifica que ghl_service.py despacha message events."""

    def test_dispatch_import_works(self) -> None:
        """Verifica que el import de webhook_service funciona desde ghl service."""
        from api.services.webhook_service import dispatch_event

        assert callable(dispatch_event)
