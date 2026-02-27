"""Tests para agent/config_loader.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agent.config_loader import (
    ClientConfig,
    _row_to_config,
    load_client_config_by_id,
    load_client_config_by_phone,
    load_client_config_by_slug,
)


class TestRowToConfig:
    """Tests para conversión de DB row a ClientConfig."""

    def test_converts_full_row(self, sample_db_row: dict) -> None:
        config = _row_to_config(sample_db_row)
        assert isinstance(config, ClientConfig)
        assert config.id == "11111111-1111-1111-1111-111111111111"
        assert config.name == "Consultorio Dr. García"
        assert config.slug == "dr-garcia"
        assert config.business_type == "dental"
        assert config.voice_id == "test-voice-id-123"
        assert config.file_search_store_id == "stores/test-store-123"
        assert config.transfer_number == "+5219991234567"

    def test_uses_defaults_for_missing_fields(self) -> None:
        """Campos opcionales usan valores por defecto."""
        minimal_row = {
            "id": "aaa",
            "name": "Test",
            "slug": "test",
            "agent_name": "Bot",
            "voice_id": "v1",
            "greeting": "Hola",
            "system_prompt": "Eres un bot.",
        }
        config = _row_to_config(minimal_row)
        assert config.business_type == "generic"
        assert config.language == "es"
        assert config.tools_enabled == ["search_knowledge"]
        assert config.max_call_duration_seconds == 300
        assert config.file_search_store_id is None
        assert config.transfer_number is None

    def test_tools_enabled_none_uses_default(self) -> None:
        row = {
            "id": "x",
            "name": "X",
            "slug": "x",
            "agent_name": "X",
            "voice_id": "x",
            "greeting": "x",
            "system_prompt": "x",
            "tools_enabled": None,
        }
        config = _row_to_config(row)
        assert config.tools_enabled == ["search_knowledge"]


class TestLoadByPhone:
    """Tests para load_client_config_by_phone."""

    @pytest.mark.asyncio
    async def test_exact_match(self, sample_db_row, mock_supabase_response) -> None:
        mock_table = MagicMock()
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.limit.return_value = mock_table
        mock_table.execute.return_value = mock_supabase_response([sample_db_row])

        mock_sb = MagicMock()
        mock_sb.table.return_value = mock_table

        with patch("agent.config_loader._get_supabase", return_value=mock_sb):
            config = await load_client_config_by_phone("+5219991112233")

        assert config is not None
        assert config.slug == "dr-garcia"

    @pytest.mark.asyncio
    async def test_flexible_match_without_prefix(
        self, sample_db_row, mock_supabase_response
    ) -> None:
        """Encuentra cliente quitando prefijo +52."""
        # Primera búsqueda exacta: sin resultados
        mock_table_exact = MagicMock()
        mock_table_exact.select.return_value = mock_table_exact
        mock_table_exact.eq.return_value = mock_table_exact
        mock_table_exact.limit.return_value = mock_table_exact
        mock_table_exact.execute.return_value = mock_supabase_response([])

        # Segunda búsqueda flexible: retorna todos los clientes activos
        mock_table_all = MagicMock()
        mock_table_all.select.return_value = mock_table_all
        mock_table_all.eq.return_value = mock_table_all
        mock_table_all.execute.return_value = mock_supabase_response([sample_db_row])

        call_count = 0

        def mock_table_side_effect(_table_name):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_table_exact
            return mock_table_all

        mock_sb = MagicMock()
        mock_sb.table.side_effect = mock_table_side_effect

        with patch("agent.config_loader._get_supabase", return_value=mock_sb):
            config = await load_client_config_by_phone("9991112233")

        assert config is not None
        assert config.slug == "dr-garcia"

    @pytest.mark.asyncio
    async def test_no_match_returns_none(self, mock_supabase_response) -> None:
        mock_table = MagicMock()
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.limit.return_value = mock_table
        mock_table.execute.return_value = mock_supabase_response([])

        mock_sb = MagicMock()
        mock_sb.table.return_value = mock_table

        with patch("agent.config_loader._get_supabase", return_value=mock_sb):
            config = await load_client_config_by_phone("+0000000000")

        assert config is None


class TestLoadBySlug:
    """Tests para load_client_config_by_slug."""

    @pytest.mark.asyncio
    async def test_found(self, sample_db_row, mock_supabase_response) -> None:
        mock_table = MagicMock()
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.limit.return_value = mock_table
        mock_table.execute.return_value = mock_supabase_response([sample_db_row])

        mock_sb = MagicMock()
        mock_sb.table.return_value = mock_table

        with patch("agent.config_loader._get_supabase", return_value=mock_sb):
            config = await load_client_config_by_slug("dr-garcia")

        assert config is not None
        assert config.name == "Consultorio Dr. García"

    @pytest.mark.asyncio
    async def test_not_found(self, mock_supabase_response) -> None:
        mock_table = MagicMock()
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.limit.return_value = mock_table
        mock_table.execute.return_value = mock_supabase_response([])

        mock_sb = MagicMock()
        mock_sb.table.return_value = mock_table

        with patch("agent.config_loader._get_supabase", return_value=mock_sb):
            config = await load_client_config_by_slug("no-existe")

        assert config is None


class TestLoadById:
    """Tests para load_client_config_by_id."""

    @pytest.mark.asyncio
    async def test_found(self, sample_db_row, mock_supabase_response) -> None:
        mock_table = MagicMock()
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.limit.return_value = mock_table
        mock_table.execute.return_value = mock_supabase_response([sample_db_row])

        mock_sb = MagicMock()
        mock_sb.table.return_value = mock_table

        with patch("agent.config_loader._get_supabase", return_value=mock_sb):
            config = await load_client_config_by_id("11111111-1111-1111-1111-111111111111")

        assert config is not None
        assert config.id == "11111111-1111-1111-1111-111111111111"

    @pytest.mark.asyncio
    async def test_not_found(self, mock_supabase_response) -> None:
        mock_table = MagicMock()
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.limit.return_value = mock_table
        mock_table.execute.return_value = mock_supabase_response([])

        mock_sb = MagicMock()
        mock_sb.table.return_value = mock_table

        with patch("agent.config_loader._get_supabase", return_value=mock_sb):
            config = await load_client_config_by_id("99999999-9999-9999-9999-999999999999")

        assert config is None
