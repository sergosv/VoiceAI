"""Rutas del dashboard (overview, usage, onboarding)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from api.cost_rates import build_cost_breakdown
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
    effective_client_id = user.client_id or client_id

    # Admin sin client_id explícito no debe ver datos de todos los clientes
    if user.role == "admin" and not effective_client_id:
        raise HTTPException(
            status_code=400,
            detail="client_id is required for admin users",
        )

    # Datos de llamadas — limitar a últimos 30 días para evitar cargar filas ilimitadas
    thirty_days_ago = (
        datetime.now(timezone.utc) - timedelta(days=30)
    ).date().isoformat()
    query = (
        sb.table("calls")
        .select(
            "duration_seconds, cost_total, cost_livekit, cost_stt, cost_llm, "
            "cost_tts, cost_telephony, metadata, started_at"
        )
        .gte("started_at", f"{thirty_days_ago}T00:00:00")
        .limit(5000)
    )
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

    # Clasificar costos plataforma vs externo
    platform_today = 0.0
    external_today = 0.0
    platform_total = 0.0
    external_total = 0.0
    for r in calls:
        bd = build_cost_breakdown(r)
        platform_total += bd["platform_cost"]
        external_total += bd["external_cost_estimate"]
        if r.get("started_at") and r["started_at"][:10] == today:
            platform_today += bd["platform_cost"]
            external_today += bd["external_cost_estimate"]

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
        platform_cost_today=round(platform_today, 4),
        external_cost_today=round(external_today, 4),
        platform_cost_total=round(platform_total, 4),
        external_cost_total=round(external_total, 4),
    )


@router.get("/usage", response_model=DashboardUsage)
async def get_usage(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = None,
    days: int = Query(30, ge=1, le=90),
) -> DashboardUsage:
    """Datos de uso diario para gráficas."""
    sb = get_supabase()
    effective_client_id = user.client_id or client_id

    # Admin sin client_id explícito no debe ver datos de todos los clientes
    if user.role == "admin" and not effective_client_id:
        raise HTTPException(
            status_code=400,
            detail="client_id is required for admin users",
        )

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


@router.get("/audit-logs")
async def list_audit_logs(
    user: CurrentUser = Depends(get_current_user),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    action: str | None = None,
) -> dict:
    """Lista de audit logs del cliente, paginada."""
    sb = get_supabase()
    query = (
        sb.table("audit_logs")
        .select("*", count="exact")
        .eq("client_id", user.client_id)
        .order("created_at", desc=True)
    )

    if action:
        query = query.eq("action", action)

    offset = (page - 1) * per_page
    query = query.range(offset, offset + per_page - 1)
    result = query.execute()

    return {
        "data": result.data or [],
        "total": result.count or 0,
        "page": page,
        "per_page": per_page,
    }


# --- Onboarding progress ---

REQUIRED_ONBOARDING_STEPS = [
    "create_agent",
    "configure_voice",
    "upload_docs",
    "test_call",
    "add_credits",
]


@router.get("/onboarding")
async def get_onboarding(
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Obtiene el progreso de onboarding del cliente."""
    sb = get_supabase()
    result = (
        sb.table("clients")
        .select("onboarding_progress, onboarding_completed")
        .eq("id", user.client_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return {"progress": {}, "completed": False}
    row = result.data[0]
    return {
        "progress": row.get("onboarding_progress") or {},
        "completed": row.get("onboarding_completed", False),
    }


@router.patch("/onboarding")
async def update_onboarding(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Marca un paso de onboarding como completado."""
    body = await request.json()
    sb = get_supabase()

    # Obtener progreso actual
    current = (
        sb.table("clients")
        .select("onboarding_progress")
        .eq("id", user.client_id)
        .limit(1)
        .execute()
    )
    progress: dict[str, bool] = (
        (current.data[0].get("onboarding_progress") or {})
        if current.data
        else {}
    )

    # Merge: marcar paso individual o dismiss completo
    step = body.get("step")
    if step and step in REQUIRED_ONBOARDING_STEPS:
        progress[step] = True

    dismiss = body.get("dismiss")
    if dismiss:
        progress["dismissed"] = True

    # Verificar si todos los pasos requeridos estan completos
    all_done = all(progress.get(s) for s in REQUIRED_ONBOARDING_STEPS)

    sb.table("clients").update({
        "onboarding_progress": progress,
        "onboarding_completed": all_done,
    }).eq("id", user.client_id).execute()

    return {"progress": progress, "completed": all_done}
