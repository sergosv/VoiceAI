"""Tests para agent/session_handler.py."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from agent.config_loader import ResolvedConfig
from agent.session_handler import RATES, SessionHandler


class TestSessionHandlerInit:
    """Tests para inicialización del SessionHandler."""

    def test_initializes_correctly(self, sample_config: ResolvedConfig) -> None:
        handler = SessionHandler(
            config=sample_config,
            direction="inbound",
            caller_number="+5219990001111",
            callee_number="+5219991112233",
            room_name="call-test-room",
        )
        assert handler._config is sample_config
        assert handler._direction == "inbound"
        assert handler._caller_number == "+5219990001111"
        assert handler._callee_number == "+5219991112233"
        assert handler._room_name == "call-test-room"
        assert handler._transcript == []
        assert isinstance(handler._started_at, datetime)


class TestTranscript:
    """Tests para manejo de transcripción."""

    def test_add_entry(self, sample_config: ResolvedConfig) -> None:
        handler = SessionHandler(
            config=sample_config,
            direction="inbound",
            caller_number=None,
            callee_number=None,
        )
        handler.add_transcript_entry("user", "Hola, necesito una cita")
        handler.add_transcript_entry("assistant", "Claro, ¿para cuándo la necesita?")

        assert len(handler._transcript) == 2
        assert handler._transcript[0]["role"] == "user"
        assert handler._transcript[0]["text"] == "Hola, necesito una cita"
        assert handler._transcript[1]["role"] == "assistant"
        assert "timestamp" in handler._transcript[0]


class TestCostCalculation:
    """Tests para cálculo de costos."""

    def test_rates_defined(self) -> None:
        """Verifica que los rates estén definidos para todos los servicios."""
        expected_services = {"livekit", "stt", "llm", "tts", "telephony"}
        assert set(RATES.keys()) == expected_services

    def test_rates_are_decimals(self) -> None:
        for rate in RATES.values():
            assert isinstance(rate, Decimal)

    @pytest.mark.asyncio
    async def test_finalize_calculates_costs(
        self, sample_config: ResolvedConfig, mock_supabase_response
    ) -> None:
        handler = SessionHandler(
            config=sample_config,
            direction="inbound",
            caller_number="+5219990001111",
            callee_number="+5219991112233",
            room_name="call-test-room",
        )
        handler.add_transcript_entry("user", "Hola")
        handler.add_transcript_entry("assistant", "¡Hola!")

        mock_calls_table = MagicMock()
        mock_calls_table.insert.return_value = mock_calls_table
        mock_calls_table.execute.return_value = mock_supabase_response([])

        mock_usage_table = MagicMock()
        mock_usage_table.select.return_value = mock_usage_table
        mock_usage_table.eq.return_value = mock_usage_table
        mock_usage_table.limit.return_value = mock_usage_table
        mock_usage_table.insert.return_value = mock_usage_table
        mock_usage_table.execute.return_value = mock_supabase_response([])

        def table_router(name):
            if name == "calls":
                return mock_calls_table
            return mock_usage_table

        mock_sb = MagicMock()
        mock_sb.table.side_effect = table_router

        with patch("agent.session_handler._get_supabase", return_value=mock_sb):
            await handler.finalize(status="completed")

        # Verificar que se insertó en calls
        assert mock_calls_table.insert.called
        call_data = mock_calls_table.insert.call_args[0][0]
        assert call_data["client_id"] == sample_config.client.id
        assert call_data["direction"] == "inbound"
        assert call_data["status"] == "completed"
        assert call_data["cost_total"] >= 0
        assert len(call_data["transcript"]) == 2

    @pytest.mark.asyncio
    async def test_finalize_creates_usage_daily(
        self, sample_config: ResolvedConfig, mock_supabase_response
    ) -> None:
        handler = SessionHandler(
            config=sample_config,
            direction="inbound",
            caller_number=None,
            callee_number=None,
        )

        # Mock que retorna vacío para usage_daily (insert nuevo)
        mock_calls_table = MagicMock()
        mock_calls_table.insert.return_value = mock_calls_table
        mock_calls_table.execute.return_value = mock_supabase_response([])

        mock_usage_table = MagicMock()
        mock_usage_table.select.return_value = mock_usage_table
        mock_usage_table.eq.return_value = mock_usage_table
        mock_usage_table.limit.return_value = mock_usage_table
        mock_usage_table.insert.return_value = mock_usage_table
        mock_usage_table.execute.return_value = mock_supabase_response([])

        def table_router(name):
            if name == "calls":
                return mock_calls_table
            return mock_usage_table

        mock_sb = MagicMock()
        mock_sb.table.side_effect = table_router

        with patch("agent.session_handler._get_supabase", return_value=mock_sb):
            await handler.finalize()

        # Debe insertar (no update) en usage_daily
        assert mock_usage_table.insert.called
        usage_data = mock_usage_table.insert.call_args[0][0]
        assert usage_data["total_calls"] == 1
        assert usage_data["inbound_calls"] == 1
        assert usage_data["outbound_calls"] == 0

    @pytest.mark.asyncio
    async def test_finalize_updates_existing_usage_daily(
        self, sample_config: ResolvedConfig, mock_supabase_response
    ) -> None:
        handler = SessionHandler(
            config=sample_config,
            direction="outbound",
            caller_number=None,
            callee_number=None,
        )

        existing_usage = {
            "id": "usage-row-id",
            "total_calls": 5,
            "total_minutes": 25.0,
            "total_cost": 1.125,
            "inbound_calls": 3,
            "outbound_calls": 2,
        }

        mock_calls_table = MagicMock()
        mock_calls_table.insert.return_value = mock_calls_table
        mock_calls_table.execute.return_value = mock_supabase_response([])

        mock_usage_table = MagicMock()
        mock_usage_table.select.return_value = mock_usage_table
        mock_usage_table.eq.return_value = mock_usage_table
        mock_usage_table.limit.return_value = mock_usage_table
        mock_usage_table.update.return_value = mock_usage_table
        # Primer execute: retorna row existente, segundo: ok
        mock_usage_table.execute.side_effect = [
            mock_supabase_response([existing_usage]),
            mock_supabase_response([]),
        ]

        def table_router(name):
            if name == "calls":
                return mock_calls_table
            return mock_usage_table

        mock_sb = MagicMock()
        mock_sb.table.side_effect = table_router

        with patch("agent.session_handler._get_supabase", return_value=mock_sb):
            await handler.finalize()

        # Debe actualizar (no insertar) en usage_daily
        assert mock_usage_table.update.called
        update_data = mock_usage_table.update.call_args[0][0]
        assert update_data["total_calls"] == 6
        assert update_data["outbound_calls"] == 3
        assert update_data["inbound_calls"] == 3  # Sin cambio
