"""Tool para búsqueda semántica en memorias del contacto mid-call."""

from __future__ import annotations

import asyncio
import logging
import os

from google import genai
from agent.embeddings import generate_embedding

logger = logging.getLogger(__name__)

# Timeout agresivo para que Gemini Live no cancele el tool call.
# Si embeddings + RPC tarda más de esto, retornamos sin datos y el agente continúa.
_RECALL_TIMEOUT_S = 2.5


async def recall_memory_search(
    query: str,
    client_id: str,
    contact_id: str,
    limit: int = 3,
) -> str:
    """Busca en memorias pasadas del contacto usando similitud semántica.

    Args:
        query: Pregunta o tema a buscar en el historial.
        client_id: ID del cliente/negocio.
        contact_id: ID del contacto.
        limit: Máximo de memorias a retornar.

    Returns:
        Texto con memorias relevantes encontradas.
    """
    if not contact_id:
        return "No hay contacto identificado para buscar memorias."

    try:
        # Envolver todo en un timeout agresivo. Si tarda mucho, Gemini Live
        # cancela el tool y el modelo queda en estado roto.
        return await asyncio.wait_for(
            _do_recall(query, client_id, contact_id, limit),
            timeout=_RECALL_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.warning("recall_memory timeout (%ss), retornando sin datos", _RECALL_TIMEOUT_S)
        return "No pude buscar en el historial ahora, continúa la conversación normalmente."
    except Exception:
        logger.exception("Error en recall_memory_search")
        return "No pude buscar en el historial ahora, continúa la conversación normalmente."


async def _do_recall(
    query: str,
    client_id: str,
    contact_id: str,
    limit: int,
) -> str:
    """Implementación real de la búsqueda (sin manejo de timeout)."""
    # Generar embedding de la query
    query_embedding = await generate_embedding(query)
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    # Buscar memorias similares via RPC
    from agent.db import get_supabase

    sb = get_supabase()
    result = await asyncio.to_thread(
        lambda: sb.rpc(
            "search_memories_by_embedding",
            {
                "p_client_id": client_id,
                "p_contact_id": contact_id,
                "p_embedding": embedding_str,
                "p_limit": limit,
                "p_min_similarity": 0.3,
            },
        ).execute()
    )

    memories = result.data if isinstance(result.data, list) else []

    if not memories:
        return "No encontré información relevante en el historial del contacto."

    # Formatear resultados
    lines = []
    for mem in memories:
        summary = mem.get("summary", "")
        channel = mem.get("channel", "")
        created = mem.get("created_at", "")[:10]
        similarity = mem.get("similarity", 0)
        recency_score = mem.get("recency_score", similarity)
        relevance_label = (
            "alta" if recency_score >= 0.7
            else "media" if recency_score >= 0.4
            else "baja"
        )
        lines.append(
            f"- [{created}] ({channel}, relevancia: {relevance_label}): {summary}"
        )
        # Incluir action_items si hay
        action_items = mem.get("action_items") or []
        if action_items:
            items_str = "; ".join(str(a) for a in action_items[:3])
            lines.append(f"  Pendientes: {items_str}")

    return "Historial del contacto:\n" + "\n".join(lines)
