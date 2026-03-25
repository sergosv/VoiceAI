"""Herramientas de tareas y notas para el Asistente Personal."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from supabase import Client

from agent.embeddings import generate_embedding

logger = logging.getLogger(__name__)


async def pa_create_task(
    sb: Client,
    *,
    agent_id: str,
    client_id: str,
    description: str,
    due_date: str | None = None,
    priority: str = "normal",
    call_id: str | None = None,
) -> dict:
    """Crea una tarea en la memoria del PA."""
    metadata = {"priority": priority}
    if due_date:
        metadata["due_date"] = due_date

    try:
        embedding = await generate_embedding(description)
    except Exception:
        embedding = None

    row = {
        "agent_id": agent_id,
        "client_id": client_id,
        "item_type": "task",
        "content": description,
        "metadata": json.dumps(metadata),
        "is_completed": False,
    }
    if embedding:
        row["embedding"] = embedding
    if call_id:
        row["source_call_id"] = call_id

    result = await asyncio.to_thread(
        lambda: sb.table("pa_memory_items").insert(row).execute()
    )
    return result.data[0] if result.data else {}


async def pa_list_tasks(
    sb: Client,
    *,
    agent_id: str,
    include_completed: bool = False,
) -> list[dict]:
    """Lista tareas del PA, opcionalmente incluyendo completadas."""
    query = (
        sb.table("pa_memory_items")
        .select("id, content, metadata, is_completed, created_at, updated_at")
        .eq("agent_id", agent_id)
        .eq("item_type", "task")
        .eq("is_deleted", False)
        .order("created_at", desc=True)
        .limit(50)
    )
    if not include_completed:
        query = query.eq("is_completed", False)

    result = await asyncio.to_thread(lambda: query.execute())
    return result.data or []


async def pa_complete_task(
    sb: Client,
    *,
    agent_id: str,
    task_query: str,
) -> bool:
    """Busca semánticamente una tarea y la marca como completada.
    Retorna True si se completó alguna."""
    try:
        embedding = await generate_embedding(task_query)
    except Exception:
        return False

    result = await asyncio.to_thread(
        lambda: sb.rpc("search_pa_memory", {
            "p_agent_id": agent_id,
            "p_query_embedding": embedding,
            "p_item_types": ["task"],
            "p_limit": 1,
            "p_min_similarity": 0.4,
        }).execute()
    )
    if not result.data:
        return False

    item = result.data[0]
    if item.get("is_completed"):
        return False  # Ya estaba completada

    now = datetime.utcnow().isoformat()
    metadata = item.get("metadata") or {}
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    metadata["completed_at"] = now

    await asyncio.to_thread(
        lambda: sb.table("pa_memory_items")
        .update({"is_completed": True, "metadata": json.dumps(metadata)})
        .eq("id", item["id"])
        .execute()
    )
    logger.info("PA task '%s' marked as completed", item["id"])
    return True


async def pa_create_note(
    sb: Client,
    *,
    agent_id: str,
    client_id: str,
    content: str,
    title: str | None = None,
    category: str | None = None,
    call_id: str | None = None,
) -> dict:
    """Crea una nota en la memoria del PA."""
    metadata: dict = {}
    if title:
        metadata["title"] = title
    if category:
        metadata["category"] = category

    try:
        embedding = await generate_embedding(content)
    except Exception:
        embedding = None

    row = {
        "agent_id": agent_id,
        "client_id": client_id,
        "item_type": "note",
        "content": content,
        "metadata": json.dumps(metadata),
    }
    if embedding:
        row["embedding"] = embedding
    if call_id:
        row["source_call_id"] = call_id

    result = await asyncio.to_thread(
        lambda: sb.table("pa_memory_items").insert(row).execute()
    )
    return result.data[0] if result.data else {}


async def pa_search_notes(
    sb: Client,
    *,
    agent_id: str,
    query: str,
    limit: int = 10,
) -> list[dict]:
    """Busca notas por similitud semántica."""
    from agent.tools.pa_memory_tool import pa_search_memory
    return await pa_search_memory(
        sb, agent_id=agent_id, query=query,
        item_types=["note"], limit=limit,
    )
