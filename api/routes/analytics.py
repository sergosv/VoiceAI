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
    return user.client_id or client_id


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


@router.get("/sentiment-distribution")
async def analytics_sentiment_distribution(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = None,
    days: int = Query(30, ge=1, le=365),
) -> list[dict[str, Any]]:
    """Distribución de sentimiento en llamadas del período."""
    sb = get_supabase()
    cid = _effective_cid(user, client_id)
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    query = sb.table("calls").select(
        "sentiment_realtime"
    ).gte("started_at", since).not_.is_("sentiment_realtime", "null")
    if cid:
        query = query.eq("client_id", cid)
    calls = query.execute().data

    counts: dict[str, int] = {}
    for c in calls:
        sr = c.get("sentiment_realtime")
        if isinstance(sr, dict):
            sentiment = sr.get("dominant_sentiment", "unknown")
        else:
            sentiment = "unknown"
        counts[sentiment] = counts.get(sentiment, 0) + 1

    return [{"sentiment": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])]


@router.get("/quality-distribution")
async def analytics_quality_distribution(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = None,
    days: int = Query(30, ge=1, le=365),
) -> dict[str, Any]:
    """Distribución de calidad de llamadas en rangos."""
    sb = get_supabase()
    cid = _effective_cid(user, client_id)
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    query = sb.table("calls").select(
        "quality_score"
    ).gte("started_at", since).not_.is_("quality_score", "null")
    if cid:
        query = query.eq("client_id", cid)
    calls = query.execute().data

    buckets = [
        ("Excelente", 80, 101),
        ("Bueno", 60, 80),
        ("Regular", 40, 60),
        ("Bajo", 0, 40),
    ]

    scores = [float(c.get("quality_score", 0) or 0) for c in calls]
    overall_avg = round(sum(scores) / len(scores), 1) if scores else 0

    distribution = []
    for label, lo, hi in buckets:
        bucket_scores = [s for s in scores if lo <= s < hi]
        count = len(bucket_scores)
        avg = round(sum(bucket_scores) / count, 1) if count else 0
        distribution.append({
            "range": label, "min": lo, "max": hi, "count": count, "avg": avg,
        })

    return {"overall_avg": overall_avg, "distribution": distribution}


@router.get("/top-intents")
async def analytics_top_intents(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = None,
    days: int = Query(30, ge=1, le=365),
) -> list[dict[str, Any]]:
    """Intents más comunes en llamadas del período."""
    sb = get_supabase()
    cid = _effective_cid(user, client_id)
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    query = sb.table("calls").select(
        "intent_realtime"
    ).gte("started_at", since).not_.is_("intent_realtime", "null")
    if cid:
        query = query.eq("client_id", cid)
    calls = query.execute().data

    counts: dict[str, int] = {}
    for c in calls:
        ir = c.get("intent_realtime")
        if isinstance(ir, dict):
            intent = ir.get("primary_intent", "unknown")
        else:
            intent = "unknown"
        counts[intent] = counts.get(intent, 0) + 1

    total = sum(counts.values())
    result = []
    for intent, count in sorted(counts.items(), key=lambda x: -x[1]):
        result.append({
            "intent": intent,
            "count": count,
            "percentage": round(count / total * 100, 1) if total else 0,
        })

    return result


@router.get("/proactive-stats")
async def analytics_proactive_stats(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = None,
    days: int = Query(30, ge=1, le=365),
) -> dict[str, Any]:
    """Estadísticas de acciones proactivas programadas."""
    sb = get_supabase()
    cid = _effective_cid(user, client_id)
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    query = sb.table("scheduled_actions").select(
        "id, status, channel, rule_type"
    ).gte("created_at", since)
    if cid:
        query = query.eq("client_id", cid)
    actions = query.execute().data

    by_status: dict[str, int] = {}
    by_channel: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for a in actions:
        s = a.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
        ch = a.get("channel", "unknown")
        by_channel[ch] = by_channel.get(ch, 0) + 1
        t = a.get("rule_type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    return {
        "total": len(actions),
        "by_status": by_status,
        "by_channel": by_channel,
        "by_type": by_type,
    }


@router.get("/retention-stats")
async def retention_stats(
    user: CurrentUser = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365),
) -> dict[str, Any]:
    """Estadísticas del worker de retención de grabaciones."""
    sb = get_supabase()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    # Grabaciones eliminadas por retención (filtro por fecha real de borrado)
    deleted = sb.table("calls").select("id", count="exact").eq(
        "recording_status", "deleted_retention"
    ).gte("recording_deleted_at", since).execute()

    # Grabaciones activas
    active = sb.table("calls").select("id", count="exact").not_.is_(
        "recording_key", "null"
    ).execute()

    # Config
    import os
    retention_days = int(os.environ.get("RECORDING_RETENTION_DAYS", "90"))

    return {
        "deleted_in_period": deleted.count or 0,
        "active_recordings": active.count or 0,
        "retention_days": retention_days,
        "period_days": days,
    }


@router.get("/escalations")
async def analytics_escalations(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = None,
    days: int = Query(30, ge=1, le=365),
) -> dict[str, Any]:
    """Escalaciones de molestia detectadas en el período."""
    sb = get_supabase()
    cid = _effective_cid(user, client_id)
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    # Buscar call_events tipo escalation_detected
    query = sb.table("call_events").select(
        "call_id, event, timestamp, details"
    ).eq("event", "escalation_detected").gte("timestamp", since)
    events = query.execute().data or []

    # Si hay client_id, filtrar por calls de ese cliente
    if cid and events:
        call_ids = list({e["call_id"] for e in events if e.get("call_id")})
        if call_ids:
            calls = sb.table("calls").select("id").eq("client_id", cid).in_(
                "id", call_ids
            ).execute()
            valid_ids = {c["id"] for c in calls.data or []}
            events = [e for e in events if e.get("call_id") in valid_ids]

    # Agrupar por día
    by_day: dict[str, int] = {}
    for e in events:
        ts = e.get("timestamp", "")[:10]
        if ts:
            by_day[ts] = by_day.get(ts, 0) + 1

    return {
        "total": len(events),
        "period_days": days,
        "by_day": [{"date": d, "count": c} for d, c in sorted(by_day.items())],
        "recent": [
            {
                "call_id": e.get("call_id"),
                "timestamp": e.get("timestamp"),
                "text": (e.get("details") or {}).get("user_text", ""),
                "violations": (e.get("details") or {}).get("violations", []),
            }
            for e in events[:20]
        ],
    }


@router.get("/sales-funnel")
async def analytics_sales_funnel(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = None,
    agent_id: str | None = None,
    campaign_id: str | None = None,
    days: int = Query(30, ge=1, le=365),
) -> dict[str, Any]:
    """Funnel de ventas outbound con tasas de conversión por etapa.

    Calcula: conexión → conversación → interés → cierre (cita/callback).
    También: objeciones top-5 y duración promedio por resultado.
    """
    sb = get_supabase()
    cid = _effective_cid(user, client_id)
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    # Si se filtra por campaign_id, obtener los room_names de esa campaña
    campaign_room_prefix = None
    if campaign_id:
        campaign_room_prefix = f"campaign-{campaign_id[:8]}"

    # Obtener todas las llamadas outbound del período
    query = sb.table("calls").select(
        "id, direction, duration_seconds, status, sentimiento, intencion, "
        "lead_score, siguiente_accion, disposition, transcript, livekit_room_name"
    ).eq("direction", "outbound").gte("started_at", since)
    if cid:
        query = query.eq("client_id", cid)
    if agent_id:
        query = query.eq("agent_id", agent_id)
    if campaign_room_prefix:
        query = query.like("livekit_room_name", f"{campaign_room_prefix}%")
    calls = query.execute().data or []

    # También obtener análisis de campañas
    camp_query = sb.table("campaign_calls").select(
        "id, status, analysis_data, result_summary"
    ).gte("created_at", since)
    if campaign_id:
        camp_query = camp_query.eq("campaign_id", campaign_id)
    elif cid:
        camp_query = camp_query.in_(
            "campaign_id",
            [c["id"] for c in sb.table("campaigns").select("id").eq("client_id", cid).execute().data or []]
        )
    campaign_calls = camp_query.execute().data or []

    # ── Funnel metrics ──
    total_dialed = len(calls) + len([c for c in campaign_calls if c["status"] != "pending"])
    connected = [c for c in calls if c["status"] == "completed" and c["duration_seconds"] and c["duration_seconds"] > 5]
    had_conversation = [c for c in connected if c.get("transcript") and len(c["transcript"]) >= 4]
    showed_interest = [c for c in connected if (c.get("lead_score") or 0) >= 50]
    high_interest = [c for c in connected if (c.get("lead_score") or 0) >= 75]

    # Cierres: siguiente_accion indica acción concreta
    closed = [c for c in connected if c.get("siguiente_accion") in ("agendar_cita", "enviar_info", "seguimiento")]
    appointments = [c for c in connected if c.get("siguiente_accion") == "agendar_cita"]

    # Campaign-specific results
    camp_completed = [c for c in campaign_calls if c["status"] == "completed"]
    camp_no_answer = [c for c in campaign_calls if c["status"] == "no_answer"]
    camp_failed = [c for c in campaign_calls if c["status"] == "failed"]

    # ── Objeciones (del análisis de campañas) ──
    objection_counts: dict[str, int] = {}
    for cc in camp_completed:
        ad = cc.get("analysis_data") or {}
        for obj in ad.get("objections", []):
            obj_text = obj if isinstance(obj, str) else str(obj)
            objection_counts[obj_text] = objection_counts.get(obj_text, 0) + 1
    top_objections = sorted(objection_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    # ── Duración promedio por resultado ──
    duration_by_sentiment: dict[str, list[int]] = {}
    for c in connected:
        s = c.get("sentimiento") or "sin_analisis"
        duration_by_sentiment.setdefault(s, []).append(c["duration_seconds"])
    avg_duration_by_sentiment = {
        k: round(sum(v) / len(v)) for k, v in duration_by_sentiment.items()
    }

    # ── Sentimiento distribution de outbound ──
    sentiment_dist = {"positivo": 0, "neutral": 0, "negativo": 0, "sin_analisis": 0}
    for c in connected:
        s = c.get("sentimiento") or "sin_analisis"
        sentiment_dist[s] = sentiment_dist.get(s, 0) + 1

    # ── Calcular tasas ──
    def _rate(num: int, den: int) -> float:
        return round(num / den * 100, 1) if den > 0 else 0

    return {
        "period_days": days,
        "funnel": {
            "total_dialed": total_dialed,
            "connected": len(connected),
            "connection_rate": _rate(len(connected), total_dialed),
            "had_conversation": len(had_conversation),
            "conversation_rate": _rate(len(had_conversation), len(connected)),
            "showed_interest": len(showed_interest),
            "interest_rate": _rate(len(showed_interest), len(had_conversation)),
            "high_interest": len(high_interest),
            "closed": len(closed),
            "close_rate": _rate(len(closed), len(had_conversation)),
            "appointments": len(appointments),
            "appointment_rate": _rate(len(appointments), len(had_conversation)),
        },
        "campaign_results": {
            "completed": len(camp_completed),
            "no_answer": len(camp_no_answer),
            "failed": len(camp_failed),
            "answer_rate": _rate(len(camp_completed), len(camp_completed) + len(camp_no_answer)),
        },
        "top_objections": [{"objection": o, "count": c} for o, c in top_objections],
        "avg_duration_by_sentiment": avg_duration_by_sentiment,
        "sentiment_distribution": sentiment_dist,
    }
