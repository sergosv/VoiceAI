"""Rutas para agent insights — análisis cross-call."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_supabase
from api.middleware.auth import CurrentUser, get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


def _check_access(user: CurrentUser, client_id: str) -> None:
    if user.role == "client" and user.client_id != client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")


@router.get("/{client_id}/agents/{agent_id}/insights")
async def list_insights(
    client_id: str,
    agent_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    """Lista insights activos de un agente."""
    _check_access(user, client_id)
    from api.services.agent_insights import get_active_insights
    return await get_active_insights(agent_id)


@router.post("/{client_id}/agents/{agent_id}/insights/generate")
async def generate_insights(
    client_id: str,
    agent_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Genera insights analizando las llamadas recientes del agente."""
    _check_access(user, client_id)
    from api.services.agent_insights import generate_insights_for_agent
    insights = await generate_insights_for_agent(agent_id, client_id, force=True)
    return {"generated": len(insights), "insights": insights}


@router.put("/{client_id}/agents/{agent_id}/insights/{insight_id}/dismiss")
async def dismiss_insight(
    client_id: str,
    agent_id: str,
    insight_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Descarta un insight (no lo quiere)."""
    _check_access(user, client_id)
    sb = get_supabase()
    sb.table("agent_insights").update({"status": "dismissed"}).eq("id", insight_id).execute()
    return {"ok": True}


@router.get("/{client_id}/agents/{agent_id}/prompt-suggestions")
async def get_prompt_suggestions(
    client_id: str,
    agent_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    """Genera sugerencias de mejora al system prompt basadas en métricas."""
    _check_access(user, client_id)
    from api.services.prompt_tuner import generate_prompt_suggestions
    return await generate_prompt_suggestions(agent_id, client_id)


@router.put("/{client_id}/agents/{agent_id}/insights/{insight_id}/apply")
async def apply_insight(
    client_id: str,
    agent_id: str,
    insight_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Marca un insight como aplicado."""
    _check_access(user, client_id)
    sb = get_supabase()
    sb.table("agent_insights").update({"status": "applied"}).eq("id", insight_id).execute()
    return {"ok": True}
