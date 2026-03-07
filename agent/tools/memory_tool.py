"""Tool para búsqueda semántica en memorias del contacto mid-call."""

from __future__ import annotations

import logging
import os

from google import genai
from agent.embeddings import generate_embedding

logger = logging.getLogger(__name__)


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
        # Generar embedding de la query
        query_embedding = await generate_embedding(query)
        embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        # Buscar memorias similares via RPC
        from agent.db import get_supabase

        sb = get_supabase()
        result = sb.rpc(
            "search_memories_by_embedding",
            {
                "p_client_id": client_id,
                "p_contact_id": contact_id,
                "p_embedding": embedding_str,
                "p_limit": limit,
                "p_min_similarity": 0.3,
            },
        ).execute()

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
            lines.append(
                f"- [{created}] ({channel}): {summary}"
            )
            # Incluir action_items si hay
            action_items = mem.get("action_items") or []
            if action_items:
                items_str = "; ".join(str(a) for a in action_items[:3])
                lines.append(f"  Pendientes: {items_str}")

        return "Historial del contacto:\n" + "\n".join(lines)

    except Exception:
        logger.exception("Error en recall_memory_search")
        return "No pude buscar en el historial en este momento."
