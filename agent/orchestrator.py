"""Orquestador multi-agente con Google ADK.

Permite que múltiples agentes compartan un mismo número telefónico.
Un coordinador (gemini-2.0-flash) decide en tiempo real qué agente
responde cada turno según la intención del usuario.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import AsyncIterator

from google import genai
from google.genai import types as genai_types
from livekit.agents import Agent, llm, tts

from agent.config_loader import ResolvedConfig

logger = logging.getLogger(__name__)

# Timeout para el coordinador (ms); si se excede, se usa el agente default
COORDINATOR_TIMEOUT_S = 3.0


@dataclass
class SubAgent:
    """Contenedor ligero de un sub-agente con sus propios LLM/TTS."""

    id: str
    name: str
    instructions: str
    role_description: str
    llm_instance: llm.LLM
    tts_instance: tts.TTS
    tools: list  # function_tools del agente
    config: ResolvedConfig
    priority: int = 0


async def decide_agent(
    user_message: str,
    agents_metadata: list[dict],
    coordinator_model: str,
    conversation_summary: str | None = None,
) -> str | None:
    """Usa Gemini para clasificar qué agente debe responder.

    Args:
        user_message: Último mensaje del usuario.
        agents_metadata: Lista de dicts con id, name, role_description.
        coordinator_model: Modelo Gemini a usar (ej: gemini-2.0-flash).
        conversation_summary: Resumen breve de la conversación previa.

    Returns:
        agent_id del agente seleccionado, o None si no se pudo decidir.
    """
    import os

    agents_desc = "\n".join(
        f"- ID: {a['id']} | Nombre: {a['name']} | Rol: {a['role_description']}"
        for a in agents_metadata
    )

    prompt = (
        "Eres un coordinador de agentes de voz. Tu ÚNICA tarea es decidir "
        "cuál agente debe responder al usuario.\n\n"
        f"Agentes disponibles:\n{agents_desc}\n\n"
    )
    if conversation_summary:
        prompt += f"Resumen de la conversación:\n{conversation_summary}\n\n"

    prompt += (
        f"El usuario dijo: \"{user_message}\"\n\n"
        "Responde SOLO con el ID del agente más adecuado. "
        "No expliques tu decisión. Solo el ID."
    )

    try:
        client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
        response = await client.aio.models.generate_content(
            model=coordinator_model,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=100,
            ),
        )
        raw = response.text.strip() if response.text else ""
        return _parse_agent_id(raw, [a["id"] for a in agents_metadata])
    except Exception:
        logger.exception("Error en coordinador ADK")
        return None


def _parse_agent_id(raw: str, valid_ids: list[str]) -> str | None:
    """Extrae un agent_id válido de la respuesta del coordinador."""
    # Intentar match exacto primero
    cleaned = raw.strip().strip('"').strip("'").strip()
    if cleaned in valid_ids:
        return cleaned
    # Buscar un UUID en el texto
    for candidate in valid_ids:
        if candidate in raw:
            return candidate
    return None


class OrchestratorAgent(Agent):
    """Agente que rutea dinámicamente entre sub-agentes por turno.

    Overrides llm_node y tts_node para intercambiar el LLM y TTS
    del sub-agente activo en cada turno, según la decisión del
    coordinador ADK.
    """

    def __init__(
        self,
        primary_config: ResolvedConfig,
        sub_agents: dict[str, SubAgent],
        agents_metadata: list[dict],
        default_agent_id: str,
        coordinator_model: str = "gemini-2.0-flash",
        coordinator_prompt: str | None = None,
    ) -> None:
        # Inicializar con el prompt del agente default
        default_sub = sub_agents[default_agent_id]
        super().__init__(instructions=default_sub.instructions)

        self._primary_config = primary_config
        self._sub_agents = sub_agents
        self._agents_metadata = agents_metadata
        self._default_agent_id = default_agent_id
        self._coordinator_model = coordinator_model
        self._coordinator_prompt = coordinator_prompt
        self._current_agent_id: str = default_agent_id
        self._agent_turns: list[dict] = []
        self._turn_count: int = 0
        self._conversation_summary: str = ""

    @property
    def config(self) -> ResolvedConfig:
        """Config del agente primario (para session_handler)."""
        return self._primary_config

    @property
    def current_agent_id(self) -> str:
        return self._current_agent_id

    @property
    def agent_turns(self) -> list[dict]:
        return self._agent_turns

    def _get_current_sub(self) -> SubAgent:
        return self._sub_agents[self._current_agent_id]

    def _extract_last_user_message(self, chat_ctx: llm.ChatContext) -> str | None:
        """Extrae el último mensaje del usuario del chat context."""
        for item in reversed(chat_ctx.items):
            if hasattr(item, "role") and item.role == "user":
                # ChatMessage o similar
                if hasattr(item, "text_content") and item.text_content:
                    return item.text_content
                if hasattr(item, "content"):
                    content = item.content
                    if isinstance(content, str):
                        return content
                    if isinstance(content, list):
                        for part in content:
                            if isinstance(part, str):
                                return part
                            if hasattr(part, "text"):
                                return part.text
        return None

    def _swap_system_prompt(self, chat_ctx: llm.ChatContext, new_instructions: str) -> None:
        """Reemplaza el system prompt en el chat context."""
        for i, item in enumerate(chat_ctx.items):
            if hasattr(item, "role") and item.role == "system":
                # Reemplazar contenido del system message
                if hasattr(item, "content"):
                    item.content = new_instructions
                return
        # Si no hay system message, insertar al inicio
        from livekit.agents.llm import ChatMessage
        chat_ctx.items.insert(0, ChatMessage(role="system", content=new_instructions))

    async def llm_node(
        self,
        chat_ctx: llm.ChatContext,
        tools: list,
        model_settings: llm.ModelSettings,
    ) -> AsyncIterator:
        """Intercepta el LLM para rutear al sub-agente correcto."""
        self._turn_count += 1
        user_msg = self._extract_last_user_message(chat_ctx)

        selected_id = self._current_agent_id

        if self._turn_count == 1:
            # Primer turno: siempre usar default (saludo)
            selected_id = self._default_agent_id
            logger.info("Turno 1: usando agente default '%s'", self._default_agent_id)
        elif user_msg and len(self._sub_agents) > 1:
            # Turno 2+: consultar coordinador
            t0 = time.monotonic()
            decided = await decide_agent(
                user_message=user_msg,
                agents_metadata=self._agents_metadata,
                coordinator_model=self._coordinator_model,
                conversation_summary=self._conversation_summary,
            )
            elapsed_ms = (time.monotonic() - t0) * 1000

            if decided and decided in self._sub_agents:
                selected_id = decided
                if selected_id != self._current_agent_id:
                    logger.info(
                        "Coordinador rutea: '%s' -> '%s' (%.0fms)",
                        self._sub_agents[self._current_agent_id].name,
                        self._sub_agents[selected_id].name,
                        elapsed_ms,
                    )
            else:
                logger.warning(
                    "Coordinador no pudo decidir (%.0fms), manteniendo '%s'",
                    elapsed_ms,
                    self._sub_agents[self._current_agent_id].name,
                )

        # Actualizar agente activo
        previous_id = self._current_agent_id
        self._current_agent_id = selected_id
        selected_sub = self._get_current_sub()

        # Log del turno
        self._agent_turns.append({
            "turn": self._turn_count,
            "user_message": (user_msg or "")[:200],
            "selected_agent_id": selected_id,
            "selected_agent_name": selected_sub.name,
            "previous_agent_id": previous_id,
            "switched": previous_id != selected_id,
            "timestamp": time.time(),
        })

        # Actualizar resumen de conversación (últimos mensajes)
        if user_msg:
            self._conversation_summary += f"\nUsuario: {user_msg[:100]}"
            # Mantener el resumen corto
            lines = self._conversation_summary.strip().split("\n")
            if len(lines) > 10:
                self._conversation_summary = "\n".join(lines[-10:])

        # Swap system prompt al del agente seleccionado
        self._swap_system_prompt(chat_ctx, selected_sub.instructions)

        # Usar el LLM del sub-agente seleccionado
        llm_instance = selected_sub.llm_instance
        stream = llm_instance.chat(
            chat_ctx=chat_ctx,
            tools=tools,
            model_settings=model_settings,
        )
        async for chunk in stream:
            yield chunk

    async def tts_node(
        self,
        text: str | AsyncIterator[str],
        model_settings: tts.ModelSettings,
    ) -> AsyncIterator:
        """Usa el TTS del sub-agente activo (voz diferente por agente)."""
        selected_sub = self._get_current_sub()
        tts_instance = selected_sub.tts_instance

        stream = tts_instance.synthesize(text)
        async for frame in stream:
            yield frame
