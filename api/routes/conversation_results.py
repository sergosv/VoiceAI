"""Endpoints para resultados de modos de conversación (survey, quiz, negotiation, interview)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.auth import get_current_user
from api.deps import get_supabase
from api.schemas import ConversationResultOut

router = APIRouter(prefix="/conversation-results", tags=["conversation-results"])


@router.get("/{client_id}", response_model=list[ConversationResultOut])
async def list_results(
    client_id: str,
    mode: str | None = Query(None, description="Filtrar por modo"),
    agent_id: str | None = Query(None, description="Filtrar por agente"),
    completed: bool | None = Query(None, description="Filtrar por completado"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
) -> list[ConversationResultOut]:
    """Lista resultados de conversaciones estructuradas."""
    sb = get_supabase()
    query = (
        sb.table("conversation_results")
        .select("*")
        .eq("client_id", client_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
    )
    if mode:
        query = query.eq("mode", mode)
    if agent_id:
        query = query.eq("agent_id", agent_id)
    if completed is not None:
        query = query.eq("completed", completed)

    result = query.execute()
    return [ConversationResultOut(**r) for r in (result.data or [])]


@router.get("/{client_id}/{result_id}", response_model=ConversationResultOut)
async def get_result(
    client_id: str,
    result_id: str,
    user: dict = Depends(get_current_user),
) -> ConversationResultOut:
    """Obtiene un resultado específico."""
    sb = get_supabase()
    result = (
        sb.table("conversation_results")
        .select("*")
        .eq("id", result_id)
        .eq("client_id", client_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resultado no encontrado")
    return ConversationResultOut(**result.data[0])


@router.get("/{client_id}/stats/{agent_id}")
async def get_mode_stats(
    client_id: str,
    agent_id: str,
    mode: str | None = Query(None),
    user: dict = Depends(get_current_user),
) -> dict:
    """Estadísticas agregadas de resultados por agente."""
    sb = get_supabase()
    query = (
        sb.table("conversation_results")
        .select("mode, completed, score, max_score, passed")
        .eq("client_id", client_id)
        .eq("agent_id", agent_id)
    )
    if mode:
        query = query.eq("mode", mode)
    result = query.execute()
    rows = result.data or []

    total = len(rows)
    completed = sum(1 for r in rows if r.get("completed"))
    passed = sum(1 for r in rows if r.get("passed"))
    avg_score = 0.0
    scored_rows = [r for r in rows if r.get("score") is not None and r.get("max_score")]
    if scored_rows:
        avg_score = sum(
            (r["score"] / r["max_score"]) * 100 for r in scored_rows
        ) / len(scored_rows)

    return {
        "total": total,
        "completed": completed,
        "completion_rate": round(completed / total * 100, 1) if total else 0,
        "passed": passed,
        "pass_rate": round(passed / len(scored_rows) * 100, 1) if scored_rows else None,
        "avg_score_pct": round(avg_score, 1) if scored_rows else None,
    }
