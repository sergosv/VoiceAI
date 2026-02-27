"""Rutas del dashboard (overview y usage)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query

from api.deps import get_supabase
from api.middleware.auth import CurrentUser, get_current_user
from api.schemas import DashboardOverview, DashboardUsage, UsageDataPoint

router = APIRouter()


@router.get("/overview", response_model=DashboardOverview)
async def get_overview(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = None,
) -> DashboardOverview:
    """Overview del dashboard: totales y datos de hoy."""
    sb = get_supabase()
    effective_client_id = user.client_id if user.role == "client" else client_id

    # Datos de llamadas
    query = sb.table("calls").select("duration_seconds, cost_total, started_at")
    if effective_client_id:
        query = query.eq("client_id", effective_client_id)
    calls = query.execute().data

    today = datetime.now(timezone.utc).date().isoformat()

    total_seconds = sum(r.get("duration_seconds", 0) for r in calls)
    total_cost = sum(float(r.get("cost_total", 0)) for r in calls)

    today_calls = [
        r for r in calls
        if r.get("started_at") and r["started_at"][:10] == today
    ]
    today_seconds = sum(r.get("duration_seconds", 0) for r in today_calls)
    today_cost = sum(float(r.get("cost_total", 0)) for r in today_calls)

    # Documentos activos
    doc_query = sb.table("documents").select("id", count="exact")
    if effective_client_id:
        doc_query = doc_query.eq("client_id", effective_client_id)
    doc_result = doc_query.execute()
    active_docs = doc_result.count or 0

    # Nombre del cliente
    client_name = None
    if effective_client_id:
        client_result = (
            sb.table("clients")
            .select("name")
            .eq("id", effective_client_id)
            .limit(1)
            .execute()
        )
        if client_result.data:
            client_name = client_result.data[0]["name"]

    return DashboardOverview(
        total_calls=len(calls),
        total_minutes=round(total_seconds / 60, 2),
        total_cost=round(total_cost, 4),
        calls_today=len(today_calls),
        minutes_today=round(today_seconds / 60, 2),
        cost_today=round(today_cost, 4),
        active_documents=active_docs,
        client_name=client_name,
    )


@router.get("/usage", response_model=DashboardUsage)
async def get_usage(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = None,
    days: int = Query(30, ge=1, le=90),
) -> DashboardUsage:
    """Datos de uso diario para gráficas."""
    sb = get_supabase()
    effective_client_id = user.client_id if user.role == "client" else client_id

    since = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()

    query = (
        sb.table("usage_daily")
        .select("date, total_calls, total_minutes, total_cost")
        .gte("date", since)
        .order("date")
    )
    if effective_client_id:
        query = query.eq("client_id", effective_client_id)

    result = query.execute()

    data = [
        UsageDataPoint(
            date=row["date"],
            calls=row.get("total_calls", 0),
            minutes=float(row.get("total_minutes", 0)),
            cost=float(row.get("total_cost", 0)),
        )
        for row in result.data
    ]

    return DashboardUsage(data=data, period_days=days)
