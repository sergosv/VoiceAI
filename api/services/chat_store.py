"""Store en memoria para conversaciones de chat tester."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field

from agent.config_loader import ResolvedConfig

logger = logging.getLogger(__name__)

MAX_TURNS = 50
MAX_TTL = 1800  # 30 minutos


@dataclass
class Conversation:
    """Una conversación de chat tester."""

    id: str
    config: ResolvedConfig
    system_prompt: str
    history: list  # list[google.genai.types.Content]
    created_at: float
    turn_count: int = 0
    contact_name: str | None = None
    client_id: str = ""


# Store global en memoria
_store: dict[str, Conversation] = {}
_cleanup_task: asyncio.Task | None = None


def create_conversation(
    config: ResolvedConfig,
    system_prompt: str,
    contact_name: str | None = None,
) -> Conversation:
    """Crea una nueva conversación y la guarda en el store."""
    conv = Conversation(
        id=str(uuid.uuid4()),
        config=config,
        system_prompt=system_prompt,
        history=[],
        created_at=time.time(),
        contact_name=contact_name,
        client_id=config.client.id,
    )
    _store[conv.id] = conv
    logger.info("Chat conversation created: %s (agent=%s)", conv.id, config.agent.name)
    return conv


def get_conversation(conversation_id: str) -> Conversation | None:
    """Obtiene una conversación del store."""
    conv = _store.get(conversation_id)
    if conv and (time.time() - conv.created_at) > MAX_TTL:
        # Expirada
        del _store[conversation_id]
        return None
    return conv


def delete_conversation(conversation_id: str) -> bool:
    """Elimina una conversación del store."""
    if conversation_id in _store:
        del _store[conversation_id]
        return True
    return False


def _cleanup_expired() -> int:
    """Limpia conversaciones expiradas. Retorna cantidad eliminada."""
    now = time.time()
    expired = [cid for cid, conv in _store.items() if (now - conv.created_at) > MAX_TTL]
    for cid in expired:
        del _store[cid]
    if expired:
        logger.info("Cleaned up %d expired chat conversations", len(expired))
    return len(expired)


async def _cleanup_loop() -> None:
    """Loop de limpieza que corre cada 60 segundos."""
    while True:
        await asyncio.sleep(60)
        try:
            _cleanup_expired()
        except Exception as e:
            logger.error("Error in chat cleanup loop: %s", e)


def start_cleanup_loop() -> None:
    """Inicia el loop de limpieza de conversaciones."""
    global _cleanup_task
    if _cleanup_task is None or _cleanup_task.done():
        _cleanup_task = asyncio.create_task(_cleanup_loop())
        logger.info("Chat cleanup loop started")
