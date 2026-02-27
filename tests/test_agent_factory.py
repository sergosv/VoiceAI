"""Tests para agent/agent_factory.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.agent_factory import VoiceAgent, build_agent
from agent.config_loader import ClientConfig


class TestBuildAgent:
    """Tests para build_agent()."""

    def test_returns_voice_agent(self, sample_config: ClientConfig) -> None:
        agent = build_agent(sample_config)
        assert isinstance(agent, VoiceAgent)

    def test_agent_has_correct_instructions(self, sample_config: ClientConfig) -> None:
        agent = build_agent(sample_config)
        assert agent._instructions == sample_config.system_prompt

    def test_agent_stores_config(self, sample_config: ClientConfig) -> None:
        agent = build_agent(sample_config)
        assert agent.config is sample_config
        assert agent.config.slug == "dr-garcia"


class TestVoiceAgentSearchKnowledge:
    """Tests para VoiceAgent.search_knowledge()."""

    @pytest.mark.asyncio
    async def test_calls_file_search_with_store_id(
        self, sample_config: ClientConfig
    ) -> None:
        agent = VoiceAgent(sample_config)
        mock_context = MagicMock()

        with patch(
            "agent.agent_factory.search_knowledge_base",
            new_callable=AsyncMock,
            return_value="Los horarios son lunes a viernes 9-18h.",
        ) as mock_search:
            result = await agent.search_knowledge(mock_context, "¿Cuáles son los horarios?")

        mock_search.assert_called_once_with("¿Cuáles son los horarios?", "stores/test-store-123")
        assert "horarios" in result

    @pytest.mark.asyncio
    async def test_returns_message_when_no_store(
        self, sample_config_no_store: ClientConfig
    ) -> None:
        agent = VoiceAgent(sample_config_no_store)
        mock_context = MagicMock()

        result = await agent.search_knowledge(mock_context, "pregunta")

        assert "No hay base de conocimientos" in result


class TestVoiceAgentTransfer:
    """Tests para VoiceAgent.transfer_to_human()."""

    @pytest.mark.asyncio
    async def test_transfer_with_number(self, sample_config: ClientConfig) -> None:
        agent = VoiceAgent(sample_config)
        mock_context = MagicMock()

        result = await agent.transfer_to_human(mock_context, "Cliente quiere hablar con humano")

        assert "+5219991234567" in result
        assert "Transferencia solicitada" in result

    @pytest.mark.asyncio
    async def test_transfer_without_number(
        self, sample_config_no_store: ClientConfig
    ) -> None:
        agent = VoiceAgent(sample_config_no_store)
        mock_context = MagicMock()

        result = await agent.transfer_to_human(mock_context, "Quiero hablar con alguien")

        assert "No hay número de transferencia" in result
        assert "el equipo se comunicará" in result
