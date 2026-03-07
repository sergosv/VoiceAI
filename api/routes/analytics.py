"""Rutas de analytics — métricas avanzadas de llamadas y rendimiento."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query

from api.deps import get_supabase
from api.middleware.auth import CurrentUser, get_current_user

router = APIRouter()
logger = logging.getLogger("analytics")


def _effective_cid(user: CurrentUser, client_id: str | None) -> str | None:
    return user.client_id if user.role == "client" else client_id


@router.get("/summary")
async def analytics_summary(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = None,
    days: int = Query(30, ge=1, le=365),
) -> dict[str, Any]:
    """Resumen de métricas para el período seleccionado."""
    sb = get_supabase()
    cid = _effective_cid(user, client_id)
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    query = sb.table("calls").select(
        "id, duration_seconds, status, direction, started_at, "
        "cost_total, caller_number, callee_number, agent_id"
    ).gte("started_at", since)
    if cid:
        query = query.eq("client_id", cid)
    calls = query.execute().data

    if not calls:
        return {
            "total_calls": 0, "total_minutes": 0, "avg_duration_seconds": 0,
            "inbound": 0, "outbound": 0, "completed": 0, "failed": 0,
            "transferred": 0, "total_cost": 0, "unique_callers": 0,
            "avg_calls_per_day": 0, "busiest_hour": None,
            "completion_rate": 0, "period_days": days,
        }

    total = len(calls)
    total_seconds = sum(c.get("duration_seconds", 0) or 0 for c in calls)
    inbound = sum(1 for c in calls if c.get("direction") == "inbound")
    outbound = sum(1 for c in calls if c.get("direction") == "outbound")
    completed = sum(1 for c in calls if c.get("status") == "completed")
    failed = sum(1 for c in calls if c.get("status") == "failed")
    transferred = sum(1 for c in calls if c.get("status") == "transferred")
    total_cost = sum(float(c.get("cost_total", 0) or 0) for c in calls)

    # Unique callers
    callers = {c.get("caller_number") for c in calls if c.get("caller_number")}
    callers.discard(None)

    # Busiest hour
    hour_counts: dict[int, int] = {}
    for c in calls:
        sa = c.get("started_at")
        if sa:
            try:
                h = datetime.fromisoformat(sa.replace("Z", "+00:00")).hour
                hour_counts[h] = hour_counts.get(h, 0) + 1
            except (ValueError, AttributeError):
                pass
    busiest_hour = max(hour_counts, key=hour_counts.get) if hour_counts else None

    return {
        "total_calls": total,
        "total_minutes": round(total_seconds / 60, 1),
        "avg_duration_seconds": round(total_seconds / total, 0) if total else 0,
        "inbound": inbound,
        "outbound": outbound,
        "completed": completed,
        "failed": failed,
        "transferred": transferred,
        "total_cost": round(total_cost, 2),
        "unique_callers": len(callers),
        "avg_calls_per_day": round(total / max(days, 1), 1),
        "busiest_hour": busiest_hour,
        "completion_rate": round(completed / total * 100, 1) if total else 0,
        "period_days": days,
    }


@router.get("/volume")
async def analytics_volume(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = None,
    days: int = Query(30, ge=1, le=365),
) -> list[dict[str, Any]]:
    """Volumen de llamadas por día (para gráfica de barras/línea)."""
    sb = get_supabase()
    cid = _effective_cid(user, client_id)
    since = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()

    query = (
        sb.table("usage_daily")
        .select("date, total_calls, total_minutes, total_cost, inbound_calls, outbound_calls")
        .gte("date", since)
        .order("date")
    )
    if cid:
        query = query.eq("client_id", cid)

    rows = query.execute().data
    return [
        {
            "date": r["date"],
            "calls": r.get("total_calls", 0),
            "minutes": float(r.get("total_minutes", 0) or 0),
            "cost": float(r.get("total_cost", 0) or 0),
            "inbound": r.get("inbound_calls", 0),
            "outbound": r.get("outbound_calls", 0),
        }
        for r in rows
    ]


@router.get("/by-status")
async def analytics_by_status(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = None,
    days: int = Query(30, ge=1, le=365),
) -> list[dict[str, Any]]:
    """Distribución de llamadas por status (para gráfica de pie/donut)."""
    sb = get_supabase()
    cid = _effective_cid(user, client_id)
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    query = sb.table("calls").select("status").gte("started_at", since)
    if cid:
        query = query.eq("client_id", cid)
    calls = query.execute().data

    counts: dict[str, int] = {}
    for c in calls:
        s = c.get("status", "unknown")
        counts[s] = counts.get(s, 0) + 1

    return [{"status": k, "count": v} for k, v in sorted(counts.items())]


@router.get("/by-hour")
async def analytics_by_hour(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = None,
    days: int = Query(30, ge=1, le=365),
) -> list[dict[str, Any]]:
    """Distribución de llamadas por hora del día (para heatmap/bar)."""
    sb = get_supabase()
    cid = _effective_cid(user, client_id)
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    query = sb.table("calls").select("started_at").gte("started_at", since)
    if cid:
        query = query.eq("client_id", cid)
    calls = query.execute().data

    hours: dict[int, int] = {h: 0 for h in range(24)}
    for c in calls:
        sa = c.get("started_at")
        if sa:
            try:
                h = datetime.fromisoformat(sa.replace("Z", "+00:00")).hour
                hours[h] += 1
            except (ValueError, AttributeError):
                pass

    return [{"hour": h, "calls": cnt} for h, cnt in sorted(hours.items())]


@router.get("/by-agent")
async def analytics_by_agent(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = None,
    days: int = Query(30, ge=1, le=365),
) -> list[dict[str, Any]]:
    """Métricas por agente (para comparar rendimiento entre agentes)."""
    sb = get_supabase()
    cid = _effective_cid(user, client_id)
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    query = sb.table("calls").select(
        "agent_id, duration_seconds, status, cost_total"
    ).gte("started_at", since)
    if cid:
        query = query.eq("client_id", cid)
    calls = query.execute().data

    # Agrupar por agente
    agents: dict[str, dict] = {}
    for c in calls:
        aid = c.get("agent_id") or "unknown"
        if aid not in agents:
            agents[aid] = {"agent_id": aid, "calls": 0, "minutes": 0, "completed": 0, "cost": 0}
        agents[aid]["calls"] += 1
        agents[aid]["minutes"] += (c.get("duration_seconds", 0) or 0) / 60
        agents[aid]["cost"] += float(c.get("cost_total", 0) or 0)
        if c.get("status") == "completed":
            agents[aid]["completed"] += 1

    # Resolver nombres de agentes
    agent_ids = [a for a in agents if a != "unknown"]
    if agent_ids:
        agent_rows = (
            sb.table("agents").select("id, name").in_("id", agent_ids).execute().data
        )
        name_map = {r["id"]: r["name"] for r in agent_rows}
    else:
        name_map = {}

    result = []
    for a in agents.values():
        a["name"] = name_map.get(a["agent_id"], "Sin agente")
        a["minutes"] = round(a["minutes"], 1)
        a["cost"] = round(a["cost"], 2)
        a["completion_rate"] = round(a["completed"] / a["calls"] * 100, 1) if a["calls"] else 0
        result.append(a)

    return sorted(result, key=lambda x: x["calls"], reverse=True)


@router.get("/duration-distribution")
async def analytics_duration_distribution(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = None,
    days: int = Query(30, ge=1, le=365),
) -> list[dict[str, Any]]:
    """Distribución de duración de llamadas en rangos."""
    sb = get_supabase()
    cid = _effective_cid(user, client_id)
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    query = sb.table("calls").select("duration_seconds").gte("started_at", since)
    if cid:
        query = query.eq("client_id", cid)
    calls = query.execute().data

    buckets = [
        ("0-30s", 0, 30),
        ("30s-1m", 30, 60),
        ("1-2m", 60, 120),
        ("2-5m", 120, 300),
        ("5-10m", 300, 600),
        ("10m+", 600, 999999),
    ]
    result = []
    for label, lo, hi in buckets:
        count = sum(
            1 for c in calls
            if lo <= (c.get("duration_seconds", 0) or 0) < hi
        )
        result.append({"range": label, "count": count})

    return result
