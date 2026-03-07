"""Tests de integración para proactive_worker — flujo completo con mocks de DB."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_supabase_table(data_map: dict | None = None) -> MagicMock:
    """Crea un mock de Supabase con respuestas configurables por tabla."""
    sb = MagicMock()
    tables: dict[str, MagicMock] = {}

    def table_factory(name: str) -> MagicMock:
        if name not in tables:
            tables[name] = MagicMock()
        return tables[name]

    sb.table.side_effect = table_factory

    if data_map:
        for tbl_name, config in data_map.items():
            tables[tbl_name] = config

    return sb, tables


class TestProcessPendingIntegration:
    """Test el flujo completo: query pending → execute → update status."""

    @pytest.mark.asyncio
    @patch("api.services.proactive_worker.get_supabase")
    async def test_full_call_flow(self, mock_sb_fn: MagicMock) -> None:
        """Acción call pending → executing → completed."""
        action = {
            "id": "act-001",
            "agent_id": "agent-1",
            "client_id": "client-1",
            "channel": "call",
            "target_number": "+521234567890",
            "message": "Hola, seguimiento",
            "rule_type": "callback_missed_call",
            "attempts": 0,
            "max_attempts": 2,
        }

        sb = MagicMock()
        mock_sb_fn.return_value = sb

        # scheduled_actions table
        sa_table = MagicMock()
        # SELECT pending
        sa_table.select.return_value.eq.return_value.lte.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[action]
        )
        # UPDATE calls
        sa_table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[action])

        # agents table (para resolver trunk)
        agents_table = MagicMock()
        agents_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"phone_number": "+525551234567", "livekit_sip_trunk_id": "trunk-1"}]
        )

        def route_table(name: str) -> MagicMock:
            if name == "scheduled_actions":
                return sa_table
            if name == "agents":
                return agents_table
            return MagicMock()

        sb.table.side_effect = route_table

        # Mock LiveKit API
        with patch("api.services.proactive_worker._execute_outbound_call", new_callable=AsyncMock) as mock_call:
            from api.services.proactive_worker import _process_pending_actions

            await _process_pending_actions()

            # Debe haber marcado como executing y luego completed
            updates = [call.args[0] for call in sa_table.update.call_args_list]
            statuses = [u.get("status") for u in updates]
            assert "executing" in statuses
            assert "completed" in statuses

            mock_call.assert_called_once_with(action)

    @pytest.mark.asyncio
    @patch("api.services.proactive_worker.get_supabase")
    async def test_full_whatsapp_flow(self, mock_sb_fn: MagicMock) -> None:
        """Acción whatsapp pending → executing → completed."""
        action = {
            "id": "act-002",
            "agent_id": "agent-1",
            "client_id": "client-1",
            "channel": "whatsapp",
            "target_number": "+521234567890",
            "message": "Recordatorio de cita manana a las 10am",
            "rule_type": "reminder_appointment",
            "attempts": 0,
            "max_attempts": 2,
        }

        sb = MagicMock()
        mock_sb_fn.return_value = sb

        sa_table = MagicMock()
        sa_table.select.return_value.eq.return_value.lte.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[action]
        )
        sa_table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[action])

        sb.table.return_value = sa_table

        with patch("api.services.proactive_worker._execute_whatsapp", new_callable=AsyncMock) as mock_wa:
            from api.services.proactive_worker import _process_pending_actions

            await _process_pending_actions()

            updates = [call.args[0] for call in sa_table.update.call_args_list]
            statuses = [u.get("status") for u in updates]
            assert "executing" in statuses
            assert "completed" in statuses

            mock_wa.assert_called_once_with(action)

    @pytest.mark.asyncio
    @patch("api.services.proactive_worker.get_supabase")
    async def test_failed_action_retries(self, mock_sb_fn: MagicMock) -> None:
        """Acción falla en intento 1 de 2 → vuelve a pending."""
        action = {
            "id": "act-003",
            "agent_id": "agent-1",
            "client_id": "client-1",
            "channel": "call",
            "target_number": "+521234567890",
            "message": "Seguimiento",
            "rule_type": "followup_no_conversion",
            "attempts": 0,
            "max_attempts": 2,
        }

        sb = MagicMock()
        mock_sb_fn.return_value = sb

        sa_table = MagicMock()
        sa_table.select.return_value.eq.return_value.lte.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[action]
        )
        sa_table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[action])

        sb.table.return_value = sa_table

        with patch(
            "api.services.proactive_worker._execute_outbound_call",
            new_callable=AsyncMock,
            side_effect=ValueError("SIP trunk no disponible"),
        ):
            from api.services.proactive_worker import _process_pending_actions

            await _process_pending_actions()

            updates = [call.args[0] for call in sa_table.update.call_args_list]
            statuses = [u.get("status") for u in updates]
            # Intento 1 de 2 → debe volver a pending (no failed)
            assert "executing" in statuses
            assert "pending" in statuses
            assert "failed" not in statuses

    @pytest.mark.asyncio
    @patch("api.services.proactive_worker.get_supabase")
    async def test_failed_action_max_attempts(self, mock_sb_fn: MagicMock) -> None:
        """Acción falla en ultimo intento → queda como failed."""
        action = {
            "id": "act-004",
            "agent_id": "agent-1",
            "client_id": "client-1",
            "channel": "call",
            "target_number": "+521234567890",
            "message": "Ultimo intento",
            "rule_type": "callback_missed_call",
            "attempts": 1,  # Ya intentó 1 vez
            "max_attempts": 2,
        }

        sb = MagicMock()
        mock_sb_fn.return_value = sb

        sa_table = MagicMock()
        sa_table.select.return_value.eq.return_value.lte.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[action]
        )
        sa_table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[action])

        sb.table.return_value = sa_table

        with patch(
            "api.services.proactive_worker._execute_outbound_call",
            new_callable=AsyncMock,
            side_effect=ConnectionError("No se pudo conectar"),
        ):
            from api.services.proactive_worker import _process_pending_actions

            await _process_pending_actions()

            updates = [call.args[0] for call in sa_table.update.call_args_list]
            statuses = [u.get("status") for u in updates]
            assert "executing" in statuses
            assert "failed" in statuses

    @pytest.mark.asyncio
    @patch("api.services.proactive_worker.get_supabase")
    async def test_sms_channel_not_implemented(self, mock_sb_fn: MagicMock) -> None:
        """Canal SMS marca como failed con mensaje descriptivo."""
        action = {
            "id": "act-005",
            "agent_id": "agent-1",
            "client_id": "client-1",
            "channel": "sms",
            "target_number": "+521234567890",
            "message": "Recordatorio por SMS",
            "rule_type": "reminder",
            "attempts": 0,
            "max_attempts": 2,
        }

        sb = MagicMock()
        mock_sb_fn.return_value = sb

        sa_table = MagicMock()
        sa_table.select.return_value.eq.return_value.lte.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[action]
        )
        sa_table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[action])

        sb.table.return_value = sa_table

        from api.services.proactive_worker import _process_pending_actions

        await _process_pending_actions()

        updates = [call.args[0] for call in sa_table.update.call_args_list]
        statuses = [u.get("status") for u in updates]
        assert "failed" in statuses
        results = [u.get("result", "") for u in updates if u.get("result")]
        assert any("SMS" in r for r in results)

    @pytest.mark.asyncio
    @patch("api.services.proactive_worker.get_supabase")
    async def test_multiple_actions_concurrent(self, mock_sb_fn: MagicMock) -> None:
        """Multiples acciones se procesan con semáforo de concurrencia."""
        actions = [
            {
                "id": f"act-{i:03d}",
                "agent_id": "agent-1",
                "client_id": "client-1",
                "channel": "call",
                "target_number": f"+5212345678{i:02d}",
                "message": f"Msg {i}",
                "rule_type": "callback_missed_call",
                "attempts": 0,
                "max_attempts": 2,
            }
            for i in range(5)
        ]

        sb = MagicMock()
        mock_sb_fn.return_value = sb

        sa_table = MagicMock()
        sa_table.select.return_value.eq.return_value.lte.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
            data=actions
        )
        sa_table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])

        sb.table.return_value = sa_table

        call_count = 0

        async def mock_call(action: dict) -> None:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)

        with patch("api.services.proactive_worker._execute_outbound_call", side_effect=mock_call):
            from api.services.proactive_worker import _process_pending_actions

            await _process_pending_actions()

            assert call_count == 5
            # 5 executing + 5 completed = 10 updates
            assert sa_table.update.call_count == 10


class TestWorkerLifecycle:
    """Tests para start/stop del worker."""

    @pytest.mark.asyncio
    async def test_worker_loop_handles_errors(self) -> None:
        """Worker loop no muere por errores en _process_pending_actions."""
        call_count = 0

        async def failing_process() -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("DB connection lost")

        with (
            patch("api.services.proactive_worker._process_pending_actions", side_effect=failing_process),
            patch("api.services.proactive_worker.POLL_INTERVAL_S", 0.01),
        ):
            import api.services.proactive_worker as pw

            task = asyncio.create_task(pw._worker_loop())
            await asyncio.sleep(0.05)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

            # Debe haber llamado más de una vez (sobrevivió al error)
            assert call_count >= 2

    @pytest.mark.asyncio
    async def test_worker_cancellation(self) -> None:
        """Worker se cancela limpiamente."""
        with patch(
            "api.services.proactive_worker._process_pending_actions",
            new_callable=AsyncMock,
        ):
            import api.services.proactive_worker as pw

            task = asyncio.create_task(pw._worker_loop())
            await asyncio.sleep(0.01)
            task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await task


class TestOutboundCallExecution:
    """Tests para _execute_outbound_call con mocks de LiveKit."""

    @pytest.mark.asyncio
    @patch.dict("os.environ", {
        "LIVEKIT_URL": "wss://test.livekit.cloud",
        "LIVEKIT_API_KEY": "test-key",
        "LIVEKIT_API_SECRET": "test-secret",
    })
    @patch("api.services.proactive_worker.get_supabase")
    async def test_outbound_call_creates_room_and_participant(self, mock_sb_fn: MagicMock) -> None:
        """Verifica que se crea room y SIP participant."""
        sb = MagicMock()
        mock_sb_fn.return_value = sb

        agents_table = MagicMock()
        agents_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"phone_number": "+525551234567", "livekit_sip_trunk_id": "trunk-1"}]
        )
        sb.table.return_value = agents_table

        mock_lk = MagicMock()
        mock_lk.room.create_room = AsyncMock()
        mock_lk.sip.create_sip_participant = AsyncMock()
        mock_lk.aclose = AsyncMock()

        with patch("livekit.api.LiveKitAPI", return_value=mock_lk):
            from api.services.proactive_worker import _execute_outbound_call

            await _execute_outbound_call({
                "id": "act-010",
                "agent_id": "agent-1",
                "client_id": "client-1",
                "target_number": "+521234567890",
                "message": "Seguimiento proactivo",
                "rule_type": "callback_missed_call",
            })

            mock_lk.room.create_room.assert_called_once()
            mock_lk.sip.create_sip_participant.assert_called_once()
            mock_lk.aclose.assert_called_once()

    @pytest.mark.asyncio
    @patch("api.services.proactive_worker.get_supabase")
    async def test_outbound_call_no_trunk_raises(self, mock_sb_fn: MagicMock) -> None:
        """Sin SIP trunk configurado lanza ValueError."""
        sb = MagicMock()
        mock_sb_fn.return_value = sb

        # Ni agente ni cliente tienen trunk
        empty_table = MagicMock()
        empty_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"phone_number": None, "livekit_sip_trunk_id": None}]
        )
        sb.table.return_value = empty_table

        from api.services.proactive_worker import _execute_outbound_call

        with pytest.raises(ValueError, match="No hay SIP trunk"):
            await _execute_outbound_call({
                "id": "act-011",
                "agent_id": "agent-1",
                "client_id": "client-1",
                "target_number": "+521234567890",
                "message": "Test",
                "rule_type": "test",
            })

    @pytest.mark.asyncio
    @patch.dict("os.environ", {
        "LIVEKIT_URL": "wss://test.livekit.cloud",
        "LIVEKIT_API_KEY": "test-key",
        "LIVEKIT_API_SECRET": "test-secret",
    })
    @patch("api.services.proactive_worker.get_supabase")
    async def test_outbound_call_falls_back_to_client_trunk(self, mock_sb_fn: MagicMock) -> None:
        """Si agente no tiene trunk, usa el del cliente."""
        sb = MagicMock()
        mock_sb_fn.return_value = sb

        call_count = {"n": 0}

        def route_table(name: str) -> MagicMock:
            t = MagicMock()
            if name == "agents":
                t.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                    data=[{"phone_number": None, "livekit_sip_trunk_id": None}]
                )
            elif name == "clients":
                t.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                    data=[{"phone_number": "+525559999999", "livekit_sip_trunk_id": "client-trunk-1"}]
                )
            return t

        sb.table.side_effect = route_table

        mock_lk = MagicMock()
        mock_lk.room.create_room = AsyncMock()
        mock_lk.sip.create_sip_participant = AsyncMock()
        mock_lk.aclose = AsyncMock()

        with patch("livekit.api.LiveKitAPI", return_value=mock_lk):
            from api.services.proactive_worker import _execute_outbound_call

            await _execute_outbound_call({
                "id": "act-012",
                "agent_id": "agent-1",
                "client_id": "client-1",
                "target_number": "+521234567890",
                "message": "Test fallback",
                "rule_type": "test",
            })

            # Debe haber consultado clients table
            sb.table.assert_any_call("clients")
            mock_lk.sip.create_sip_participant.assert_called_once()
