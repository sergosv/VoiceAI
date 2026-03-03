"""Rutas para historial de llamadas."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.cost_rates import build_cost_breakdown
from api.deps import get_supabase
from api.middleware.auth import CurrentUser, get_current_user
from api.schemas import CallDetailOut, CallOut, CallStatsOut, CostBreakdown, CostLineItem

router = APIRouter()


@router.get("", response_model=list[CallOut])
async def list_calls(
    user: CurrentUser = Depends(get_current_user),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    direction: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    client_id: str | None = None,
) -> list[CallOut]:
    """Lista llamadas con filtros. Client ve solo las suyas."""
    sb = get_supabase()
    query = sb.table("calls").select(
        "id, client_id, agent_id, direction, caller_number, callee_number, "
        "duration_seconds, cost_total, status, summary, sentimiento, resumen_ia, "
        "started_at, ended_at, metadata"
    ).order("started_at", desc=True)

    # Multi-tenancy
    if user.role == "client":
        if not user.client_id:
            return []
        query = query.eq("client_id", user.client_id)
    elif client_id:
        query = query.eq("client_id", client_id)

    if status_filter:
        query = query.eq("status", status_filter)
    if direction:
        query = query.eq("direction", direction)
    if date_from:
        query = query.gte("started_at", date_from.isoformat())
    if date_to:
        # Incluir todo el día
        end = datetime.combine(date_to, datetime.max.time()).isoformat()
        query = query.lte("started_at", end)

    offset = (page - 1) * per_page
    query = query.range(offset, offset + per_page - 1)

    result = query.execute()
    calls = []
    for row in result.data:
        # Extraer agent_name de metadata si está disponible
        meta = row.get("metadata") or {}
        row["agent_name"] = meta.get("agent_name")
        calls.append(CallOut(**row))
    return calls


@router.get("/stats", response_model=CallStatsOut)
async def get_call_stats(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = None,
) -> CallStatsOut:
    """Estadísticas de llamadas."""
    sb = get_supabase()

    # Determinar el client_id efectivo
    effective_client_id = user.client_id if user.role == "client" else client_id

    query = sb.table("calls").select(
        "duration_seconds, cost_total, started_at"
    )
    if effective_client_id:
        query = query.eq("client_id", effective_client_id)

    result = query.execute()
    rows = result.data

    if not rows:
        return CallStatsOut()

    today = datetime.now(timezone.utc).date()
    total_seconds = sum(r.get("duration_seconds", 0) for r in rows)
    total_cost = sum(float(r.get("cost_total", 0)) for r in rows)

    today_rows = [
        r for r in rows
        if r.get("started_at") and r["started_at"][:10] == today.isoformat()
    ]
    today_seconds = sum(r.get("duration_seconds", 0) for r in today_rows)

    return CallStatsOut(
        total_calls=len(rows),
        total_minutes=round(total_seconds / 60, 2),
        total_cost=round(total_cost, 4),
        avg_duration_seconds=round(total_seconds / len(rows), 1) if rows else 0,
        calls_today=len(today_rows),
        minutes_today=round(today_seconds / 60, 2),
    )


@router.get("/{call_id}", response_model=CallDetailOut)
async def get_call_detail(
    call_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> CallDetailOut:
    """Detalle de una llamada con transcript."""
    sb = get_supabase()
    result = sb.table("calls").select("*").eq("id", call_id).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Llamada no encontrada")

    call = result.data[0]

    # Multi-tenancy
    if user.role == "client" and call.get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    # Extraer agent_name de metadata
    meta = call.get("metadata") or {}
    call["agent_name"] = meta.get("agent_name")

    # Construir desglose de costos con clasificación plataforma/externo
    bd = build_cost_breakdown(call)
    call["cost_breakdown"] = CostBreakdown(
        platform_cost=bd["platform_cost"],
        external_cost_estimate=bd["external_cost_estimate"],
        total=bd["total"],
        lines=[CostLineItem(**line) for line in bd["lines"]],
    )

    return CallDetailOut(**call)
