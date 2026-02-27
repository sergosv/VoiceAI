"""Construye agentes de voz dinámicos según la configuración del cliente."""

from __future__ import annotations

import logging

from livekit.agents import Agent, RunContext
from livekit.agents.llm import function_tool

from agent.config_loader import ClientConfig
from agent.tools.file_search import search_knowledge_base

logger = logging.getLogger(__name__)


class VoiceAgent(Agent):
    """Agente de voz personalizado por cliente.

    Cada instancia se configura dinámicamente según el ClientConfig
    del negocio al que pertenece la llamada.
    """

    def __init__(self, config: ClientConfig) -> None:
        super().__init__(instructions=config.system_prompt)
        self._config = config

    @property
    def config(self) -> ClientConfig:
        return self._config

    @function_tool()
    async def search_knowledge(self, context: RunContext, query: str) -> str:
        """Busca información en la base de conocimientos del negocio.

        Usa esta herramienta cuando el usuario pregunte sobre servicios,
        precios, horarios, menú, o cualquier información específica del negocio.

        Args:
            query: La pregunta o tema a buscar en los documentos del negocio.
        """
        store_id = self._config.file_search_store_id
        if not store_id:
            return "No hay base de conocimientos configurada."

        logger.info(
            "File Search query para '%s': %s",
            self._config.slug,
            query,
        )
        return await search_knowledge_base(query, store_id)

    @function_tool()
    async def transfer_to_human(self, context: RunContext, reason: str) -> str:
        """Transfiere la llamada a un agente humano.

        Usa esta herramienta cuando el cliente lo solicite explícitamente
        o cuando no puedas resolver su consulta.

        Args:
            reason: Motivo de la transferencia.
        """
        transfer_number = self._config.transfer_number
        if not transfer_number:
            return (
                "No hay número de transferencia configurado. "
                "Informa al cliente que el equipo se comunicará con él."
            )

        # TODO: Implementar transferencia SIP real en Fase 2
        logger.info(
            "Solicitud de transferencia para '%s': %s",
            self._config.slug,
            reason,
        )
        return (
            f"Transferencia solicitada al número {transfer_number}. "
            f"Motivo: {reason}. "
            "Informa al cliente que lo estás transfiriendo."
        )


def build_agent(config: ClientConfig) -> VoiceAgent:
    """Construye un VoiceAgent configurado para un cliente específico."""
    agent = VoiceAgent(config)
    logger.info(
        "Agente creado para '%s' (%s) — voz: %s, idioma: %s",
        config.name,
        config.slug,
        config.voice_id,
        config.language,
    )
    return agent
