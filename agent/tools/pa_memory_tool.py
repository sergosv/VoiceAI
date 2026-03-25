"""Herramientas de memoria persistente para el Asistente Personal.

Usa pgvector (VECTOR 768) con text-embedding-004 para búsqueda semántica.
Tabla: pa_memory_items (facts, preferences, tasks, notes, reminders).
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from supabase import Client

from agent.embeddings import generate_embedding

logger = logging.getLogger(__name__)


async def pa_remember(
    sb: Client,
    *,
    agent_id: str,
    client_id: str,
    content: str,
    item_type: str = "fact",
    metadata: dict | None = None,
    call_id: str | None = None,
) -> str:
    """Guarda un item en la memoria del PA con embedding para búsqueda semántica."""
    try:
        embedding = await generate_embedding(content)
    except Exception as e:
        logger.warning("Error generando embedding para PA memory: %s", e)
        embedding = None

    row = {
        "agent_id": agent_id,
        "client_id": client_id,
        "item_type": item_type,
        "content": content,
        "metadata": json.dumps(metadata or {}),
    }
    if embedding:
        row["embedding"] = embedding
    if call_id:
        row["source_call_id"] = call_id

    try:
        result = await asyncio.to_thread(
            lambda: sb.table("pa_memory_items").insert(row).execute()
        )
        return result.data[0]["id"] if result.data else ""
    except Exception as e:
        logger.error("Error guardando PA memory: %s", e)
        raise


async def pa_forget(
    sb: Client,
    *,
    agent_id: str,
    query: str,
) -> int:
    """Busca semánticamente y marca como eliminado el item más relevante.
    Retorna cantidad de items eliminados (0 o 1)."""
    try:
        embedding = await generate_embedding(query)
    except Exception as e:
        logger.warning("Error generando embedding para forget: %s", e)
        return 0

    try:
        result = await asyncio.to_thread(
            lambda: sb.rpc("search_pa_memory", {
                "p_agent_id": agent_id,
                "p_query_embedding": embedding,
                "p_limit": 1,
                "p_min_similarity": 0.5,
            }).execute()
        )
        if not result.data:
            return 0

        item_id = result.data[0]["id"]
        await asyncio.to_thread(
            lambda: sb.table("pa_memory_items")
            .update({"is_deleted": True})
            .eq("id", item_id)
            .execute()
        )
        logger.info("PA memory item %s marked as deleted", item_id)
        return 1
    except Exception as e:
        logger.error("Error en pa_forget: %s", e)
        return 0


async def pa_search_memory(
    sb: Client,
    *,
    agent_id: str,
    query: str,
    item_types: list[str] | None = None,
    limit: int = 10,
) -> list[dict]:
    """Búsqueda semántica en la memoria del PA. Retorna items ordenados por relevancia."""
    try:
        embedding = await generate_embedding(query)
    except Exception as e:
        logger.warning("Error generando embedding para search: %s", e)
        return []

    params: dict = {
        "p_agent_id": agent_id,
        "p_query_embedding": embedding,
        "p_limit": limit,
        "p_min_similarity": 0.3,
    }
    if item_types:
        params["p_item_types"] = item_types

    try:
        result = await asyncio.to_thread(
            lambda: sb.rpc("search_pa_memory", params).execute()
        )
        return result.data or []
    except Exception as e:
        logger.error("Error en pa_search_memory: %s", e)
        return []
