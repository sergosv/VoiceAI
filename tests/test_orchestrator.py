"""Tests para agent/orchestrator.py — Orquestación multi-agente."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.config_loader import AgentConfig, ResolvedConfig, SlimClientConfig
from agent.orchestrator import (
    OrchestratorAgent,
    SubAgent,
    _parse_agent_id,
    decide_agent,
)


# ── Fixtures ────────────────────────────────────────────


def _make_resolved_config(
    agent_id: str = "aaaa",
    agent_name: str = "Agente Test",
    client_id: str = "cccc",
    role_description: str | None = None,
    orchestrator_priority: int = 0,
    system_prompt: str = "Eres un agente de prueba.",
) -> ResolvedConfig:
    agent = AgentConfig(
        id=agent_id,
        client_id=client_id,
        name=agent_name,
        slug=agent_name.lower().replace(" ", "-"),
        phone_number=None,
        phone_sid=None,
        livekit_sip_trunk_id=None,
        system_prompt=system_prompt,
        greeting="Hola, soy " + agent_name,
        examples=None,
        role_description=role_description,
        orchestrator_enabled=True,
        orchestrator_priority=orchestrator_priority,
    )
    client = SlimClientConfig(
        id=client_id,
        name="Test Client",
        slug="test-client",
        business_type="generic",
        language="es",
        file_search_store_id=None,
        orchestration_mode="intelligent",
        orchestrator_model="gemini-2.0-flash",
    )
    return ResolvedConfig(agent=agent, client=client)


def _make_sub_agent(
    agent_id: str,
    name: str,
    role_description: str = "Agente genérico",
) -> SubAgent:
    return SubAgent(
        id=agent_id,
        name=name,
        instructions=f"Eres {name}, asistente virtual.",
        role_description=role_description,
        llm_instance=MagicMock(),
        tts_instance=MagicMock(),
        tools=[],
        config=_make_resolved_config(agent_id=agent_id, agent_name=name),
        priority=0,
    )


@pytest.fixture
def sample_agents_metadata() -> list[dict]:
    return [
        {"id": "agent-1", "name": "Recepcionista", "role_description": "Recepción y citas"},
        {"id": "agent-2", "name": "Ventas", "role_description": "Ventas y cotizaciones"},
    ]


@pytest.fixture
def sample_sub_agents() -> dict[str, SubAgent]:
    return {
        "agent-1": _make_sub_agent("agent-1", "Recepcionista", "Recepción y citas"),
        "agent-2": _make_sub_agent("agent-2", "Ventas", "Ventas y cotizaciones"),
    }


@pytest.fixture
def orchestrator(sample_sub_agents, sample_agents_metadata) -> OrchestratorAgent:
    primary = _make_resolved_config(agent_id="agent-1", agent_name="Recepcionista")
    return OrchestratorAgent(
        primary_config=primary,
        sub_agents=sample_sub_agents,
        agents_metadata=sample_agents_metadata,
        default_agent_id="agent-1",
        coordinator_model="gemini-2.0-flash",
    )


# ── Tests para _parse_agent_id ─────────────────────────


class TestParseAgentId:

    def test_exact_match(self) -> None:
        result = _parse_agent_id("agent-1", ["agent-1", "agent-2"])
        assert result == "agent-1"

    def test_uuid_match(self) -> None:
        uuid = "550e8400-e29b-41d4-a716-446655440000"
        result = _parse_agent_id(f"El agente es {uuid}", [uuid, "other-id"])
        assert result == uuid

    def test_stripped_quotes(self) -> None:
        result = _parse_agent_id('"agent-2"', ["agent-1", "agent-2"])
        assert result == "agent-2"

    def test_returns_none_for_invalid(self) -> None:
        result = _parse_agent_id("unknown", ["agent-1", "agent-2"])
        assert result is None

    def test_returns_none_for_empty(self) -> None:
        result = _parse_agent_id("", ["agent-1"])
        assert result is None


# ── Tests para decide_agent ────────────────────────────


class TestDecideAgent:

    @pytest.mark.asyncio
    async def test_returns_agent_id_on_success(self, sample_agents_metadata) -> None:
        """Simula respuesta exitosa del coordinador."""
        mock_response = MagicMock()
        mock_response.text = "agent-2"

        mock_model = MagicMock()
        mock_model.generate_content = AsyncMock(return_value=mock_response)

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch("agent.orchestrator.genai.Client", return_value=mock_client):
            result = await decide_agent(
                user_message="Quiero una cotización",
                agents_metadata=sample_agents_metadata,
                coordinator_model="gemini-2.0-flash",
            )

        assert result == "agent-2"

    @pytest.mark.asyncio
    async def test_returns_none_on_error(self, sample_agents_metadata) -> None:
        """Retorna None si el coordinador falla."""
        with patch("agent.orchestrator.genai.Client", side_effect=Exception("API error")):
            result = await decide_agent(
                user_message="Hola",
                agents_metadata=sample_agents_metadata,
                coordinator_model="gemini-2.0-flash",
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_invalid_response(self, sample_agents_metadata) -> None:
        """Retorna None si la respuesta no contiene un ID válido."""
        mock_response = MagicMock()
        mock_response.text = "No sé qué agente elegir"

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch("agent.orchestrator.genai.Client", return_value=mock_client):
            result = await decide_agent(
                user_message="Hola",
                agents_metadata=sample_agents_metadata,
                coordinator_model="gemini-2.0-flash",
            )

        assert result is None


# ── Tests para OrchestratorAgent ───────────────────────


class TestOrchestratorAgent:

    def test_initializes_with_default_agent(self, orchestrator) -> None:
        assert orchestrator.current_agent_id == "agent-1"
        assert orchestrator._turn_count == 0
        assert len(orchestrator.agent_turns) == 0

    def test_config_returns_primary(self, orchestrator) -> None:
        assert orchestrator.config.agent.id == "agent-1"

    def test_get_current_sub(self, orchestrator) -> None:
        sub = orchestrator._get_current_sub()
        assert sub.name == "Recepcionista"

    def test_swap_system_prompt(self, orchestrator) -> None:
        """Verifica que se puede reemplazar el system prompt."""
        # Crear un chat context mock con un system message
        system_msg = MagicMock()
        system_msg.role = "system"
        system_msg.content = "Prompt original"

        chat_ctx = MagicMock()
        chat_ctx.items = [system_msg]

        orchestrator._swap_system_prompt(chat_ctx, "Prompt nuevo")
        assert system_msg.content == "Prompt nuevo"

    def test_extract_last_user_message(self, orchestrator) -> None:
        """Verifica extracción del último mensaje del usuario."""
        user_msg = MagicMock()
        user_msg.role = "user"
        user_msg.text_content = "Quiero agendar una cita"

        assistant_msg = MagicMock()
        assistant_msg.role = "assistant"
        assistant_msg.text_content = "Claro, ¿qué día le queda bien?"

        chat_ctx = MagicMock()
        chat_ctx.items = [user_msg, assistant_msg]

        result = orchestrator._extract_last_user_message(chat_ctx)
        # Debería devolver el último user message (recorre en reversa)
        assert result == "Quiero agendar una cita"

    def test_extract_last_user_message_none(self, orchestrator) -> None:
        """Retorna None si no hay mensajes de usuario."""
        chat_ctx = MagicMock()
        chat_ctx.items = []
        result = orchestrator._extract_last_user_message(chat_ctx)
        assert result is None


# ── Tests para build_orchestrated_agent ─────────────────


class TestBuildOrchestratedAgent:

    @patch("agent.pipeline_builder.build_llm")
    @patch("agent.pipeline_builder.build_tts")
    def test_creates_orchestrator(self, mock_tts, mock_llm) -> None:
        from agent.agent_factory import build_orchestrated_agent

        mock_llm.return_value = MagicMock()
        mock_tts.return_value = MagicMock()

        configs = [
            _make_resolved_config(
                agent_id="a1", agent_name="Recepción",
                role_description="Recibe llamadas", orchestrator_priority=10,
            ),
            _make_resolved_config(
                agent_id="a2", agent_name="Ventas",
                role_description="Vende productos", orchestrator_priority=5,
            ),
        ]

        result = build_orchestrated_agent(configs, configs[0])

        assert isinstance(result, OrchestratorAgent)
        assert len(result._sub_agents) == 2
        assert result._default_agent_id == "a1"  # Mayor prioridad primero
        assert "a1" in result._sub_agents
        assert "a2" in result._sub_agents

    @patch("agent.pipeline_builder.build_llm")
    @patch("agent.pipeline_builder.build_tts")
    def test_raises_on_empty_configs(self, mock_tts, mock_llm) -> None:
        from agent.agent_factory import build_orchestrated_agent

        primary = _make_resolved_config()
        with pytest.raises(ValueError, match="No hay agentes"):
            build_orchestrated_agent([], primary)


# ── Tests para load_orchestrated_configs ─────────────────


class TestLoadOrchestratedConfigs:

    @pytest.mark.asyncio
    async def test_loads_configs_ordered_by_priority(self) -> None:
        from agent.config_loader import load_orchestrated_configs

        mock_data = [
            {
                "id": "a1", "client_id": "c1", "name": "A1", "slug": "a1",
                "system_prompt": "p1", "greeting": "g1", "is_active": True,
                "orchestrator_enabled": True, "orchestrator_priority": 10,
                "clients": {
                    "id": "c1", "name": "C1", "slug": "c1",
                    "business_type": "generic", "language": "es",
                },
            },
            {
                "id": "a2", "client_id": "c1", "name": "A2", "slug": "a2",
                "system_prompt": "p2", "greeting": "g2", "is_active": True,
                "orchestrator_enabled": True, "orchestrator_priority": 5,
                "clients": {
                    "id": "c1", "name": "C1", "slug": "c1",
                    "business_type": "generic", "language": "es",
                },
            },
        ]

        mock_response = MagicMock()
        mock_response.data = mock_data

        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = mock_response

        with patch("agent.config_loader._get_supabase", return_value=mock_sb):
            configs = await load_orchestrated_configs("c1")

        assert len(configs) == 2
        assert configs[0].agent.id == "a1"
        assert configs[1].agent.id == "a2"
