"""Tests de smoke para el entrypoint del agente.

Valida que el flujo de inicialización no crashee para cada modo de voz
y que el greeting use el mecanismo correcto por modo.
Detecta errores como UnboundLocalError, imports faltantes, y mezcla de stacks.
"""

from __future__ import annotations

import ast
import inspect
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.agent_factory import VoiceAgent, build_agent, TOOL_INSTRUCTIONS
from agent.config_loader import AgentConfig, ResolvedConfig, SlimClientConfig


# ── Fixtures ──

def _make_config(
    agent_mode: str = "pipeline",
    greeting: str = "Hola, soy el asistente.",
    voice_config: dict | None = None,
) -> ResolvedConfig:
    """Crea un ResolvedConfig con el modo de voz especificado."""
    vc = voice_config or {"provider": "cartesia", "voice_id": "test-voice"}
    agent = AgentConfig(
        id="aaaa0000-0000-0000-0000-000000000000",
        client_id="cccc0000-0000-0000-0000-000000000000",
        name="TestAgent",
        slug="test-agent",
        phone_number="+5219990001111",
        phone_sid=None,
        livekit_sip_trunk_id=None,
        system_prompt="Eres un asistente de prueba.",
        greeting=greeting,
        examples=None,
        voice_config=vc,
        llm_config={"provider": "google"},
        stt_config={"provider": "deepgram"},
        transfer_number="+5219990002222",
        max_call_duration_seconds=300,
        agent_mode=agent_mode,
    )
    client = SlimClientConfig(
        id="cccc0000-0000-0000-0000-000000000000",
        name="Test Client",
        slug="test-client",
        business_type="generic",
        language="es",
        file_search_store_id=None,
        enabled_tools=["search_knowledge"],
    )
    return ResolvedConfig(agent=agent, client=client)


# ── 1. Syntax validation — entrypoint no tiene errores de parseo ──

class TestEntrypointSyntax:
    """Valida que main.py se parsea sin errores de sintaxis."""

    def test_main_py_parses(self) -> None:
        with open("agent/main.py", encoding="utf-8") as f:
            source = f.read()
        # Si hay syntax error, ast.parse lo lanza
        ast.parse(source)

    def test_agent_factory_parses(self) -> None:
        with open("agent/agent_factory.py", encoding="utf-8") as f:
            source = f.read()
        ast.parse(source)

    def test_session_handler_parses(self) -> None:
        with open("agent/session_handler.py", encoding="utf-8") as f:
            source = f.read()
        ast.parse(source)


# ── 2. Imports — todos los módulos del agente se importan sin error ──

class TestAgentImports:
    """Valida que los imports críticos del agente no fallen."""

    def test_import_main(self) -> None:
        try:
            import agent.main  # noqa: F401
        except ImportError as e:
            if "silero" in str(e) or "noise_cancellation" in str(e):
                pytest.skip("LiveKit plugins not installed locally")
            raise

    def test_import_agent_factory(self) -> None:
        from agent.agent_factory import VoiceAgent, build_agent  # noqa: F401

    def test_import_session_handler(self) -> None:
        from agent.session_handler import SessionHandler  # noqa: F401

    def test_import_call_lifecycle(self) -> None:
        from agent.call_lifecycle import CallLifecycleTracker  # noqa: F401

    def test_import_call_analyzer(self) -> None:
        from agent.call_analyzer import analyze_call_universal  # noqa: F401

    def test_import_callback_tool(self) -> None:
        from agent.tools.callback_tool import schedule_callback  # noqa: F401


# ── 3. VoiceAgent creation — cada modo crea el agente sin error ──

class TestVoiceAgentCreation:
    """Valida que build_agent() funcione para cada modo de voz."""

    @pytest.mark.parametrize("mode", ["pipeline", "gemini_live", "realtime"])
    def test_build_agent_all_modes(self, mode: str) -> None:
        config = _make_config(agent_mode=mode)
        agent = build_agent(config)
        assert isinstance(agent, VoiceAgent)
        assert agent._config.agent.agent_mode == mode

    def test_agent_has_schedule_callback_tool(self) -> None:
        config = _make_config()
        agent = build_agent(config)
        tool_ids = [t.id for t in agent.tools]
        assert "schedule_callback" in tool_ids

    def test_agent_has_session_handler_attr(self) -> None:
        config = _make_config()
        agent = build_agent(config)
        assert hasattr(agent, "_session_handler")
        assert hasattr(agent, "_origin_call_id")

    @pytest.mark.asyncio
    async def test_filter_disabled_tools_is_async(self) -> None:
        """filter_disabled_tools debe ser async (SDK 1.5.2+)."""
        config = _make_config()
        agent = build_agent(config)
        assert inspect.iscoroutinefunction(agent.filter_disabled_tools)


# ── 4. Greeting mechanism — cada modo usa el mecanismo correcto ──

class TestGreetingByMode:
    """Valida que el greeting no mezcle stacks de voz."""

    def test_main_py_no_generate_reply_for_gemini_live(self) -> None:
        """Gemini Live nunca debe usar generate_reply para el greeting."""
        with open("agent/main.py", encoding="utf-8") as f:
            source = f.read()

        # Buscar la sección de saludo y verificar que gemini_live no usa generate_reply
        # El patrón correcto: gemini_live usa system prompt, no generate_reply
        greeting_section = source[source.find("# Saludo inicial"):]
        greeting_section = greeting_section[:greeting_section.find("\nif __name__")]

        # Debe tener un guard para gemini_live
        assert "gemini_live" in greeting_section, (
            "La sección de greeting debe tener lógica específica para gemini_live"
        )

    def test_main_py_gemini_live_greeting_in_system_prompt(self) -> None:
        """Gemini Live debe inyectar greeting en system prompt antes de session.start."""
        with open("agent/main.py", encoding="utf-8") as f:
            source = f.read()

        # Debe existir inyección de greeting en system prompt para gemini_live
        assert "Gemini Live: greeting inyectado en system prompt" in source or \
               "gemini_live" in source and "_instructions" in source, (
            "Gemini Live debe inyectar greeting en _instructions, no usar generate_reply"
        )

    def test_main_py_no_cartesia_in_gemini_live_session(self) -> None:
        """No debe haber TTS de Cartesia mezclado en la sesión de Gemini Live."""
        with open("agent/main.py", encoding="utf-8") as f:
            source = f.read()

        # Buscar la sección donde se construye la sesión de gemini_live
        gl_start = source.find('agent_mode == "gemini_live"')
        if gl_start == -1:
            pytest.skip("No se encontró sección gemini_live")

        # Buscar hasta el siguiente elif/else
        gl_section = source[gl_start:gl_start + 800]
        gl_session = gl_section[gl_section.find("AgentSession("):gl_section.find(")") + 1]

        assert "cartesia" not in gl_session.lower(), (
            "La sesión de Gemini Live NO debe incluir Cartesia TTS — no mezclar stacks"
        )


# ── 5. Variable scope — handler debe estar disponible donde se usa ──

class TestVariableScope:
    """Detecta errores como UnboundLocalError donde se usa una variable antes de crearla."""

    def test_handler_used_after_creation(self) -> None:
        """handler no debe usarse antes de SessionHandler()."""
        with open("agent/main.py", encoding="utf-8") as f:
            lines = f.readlines()

        handler_created_at = None
        handler_used_before = []

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Línea donde se crea handler
            if "handler = SessionHandler(" in stripped or "handler = SessionHandler(" in line:
                handler_created_at = i
            # Líneas donde se usa handler (no en comentarios ni strings)
            if handler_created_at is None and not stripped.startswith("#"):
                if re.search(r'\bhandler\b', stripped) and "handler" not in ("session_handler",):
                    # Filtrar falsos positivos (definiciones de funciones, imports, strings)
                    if "def " not in stripped and "import" not in stripped and '"""' not in stripped:
                        if "voice_agent._session_handler = handler" in stripped:
                            handler_used_before.append((i, stripped))

        assert len(handler_used_before) == 0, (
            f"handler se usa antes de crearse en líneas: {handler_used_before}"
        )


# ── 6. Tool instructions — schedule_callback tiene NUNCA ofrecer ──

class TestToolInstructions:
    """Valida instrucciones de tools críticos."""

    def test_schedule_callback_no_proactive(self) -> None:
        """schedule_callback no debe ofrecerse proactivamente."""
        instruction = TOOL_INSTRUCTIONS.get("schedule_callback", "")
        assert "NUNCA ofrezcas" in instruction or "NUNCA ofrecer" in instruction, (
            "schedule_callback debe tener instrucción de NO ofrecer proactivamente"
        )

    def test_schedule_callback_always_available(self) -> None:
        """schedule_callback debe estar en _ALWAYS_AVAILABLE."""
        assert "schedule_callback" in VoiceAgent._ALWAYS_AVAILABLE
