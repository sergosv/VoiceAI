"""Rutas para evaluación de calidad de llamadas."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import get_supabase
from api.middleware.auth import CurrentUser, get_current_user

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


def _apply_tenant_filter(query, user: CurrentUser, client_id: str | None = None):
    """Aplica filtro multi-tenancy (soporta impersonación admin)."""
    if user.client_id:
        return query.eq("client_id", user.client_id)
    elif client_id:
        return query.eq("client_id", client_id)
    return query


@router.get("")
async def list_evaluations(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = None,
    agent_id: str | None = None,
    min_score: int | None = Query(None, ge=0, le=100),
    max_score: int | None = Query(None, ge=0, le=100),
    has_critical: bool | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """Lista evaluaciones con filtros."""
    sb = get_supabase()
    query = (
        sb.table("call_evaluations")
        .select(
            "id, call_id, client_id, agent_id, overall_score, failures_found, "
            "critical_failures, status, created_at"
        )
        .order("created_at", desc=True)
    )

    query = _apply_tenant_filter(query, user, client_id)
    if query is None:
        return []

    if agent_id:
        query = query.eq("agent_id", agent_id)
    if min_score is not None:
        query = query.gte("overall_score", min_score)
    if max_score is not None:
        query = query.lte("overall_score", max_score)
    if has_critical is True:
        query = query.gt("critical_failures", 0)
    elif has_critical is False:
        query = query.eq("critical_failures", 0)

    query = query.range(offset, offset + limit - 1)
    result = query.execute()
    return result.data or []


@router.get("/stats")
async def get_evaluation_stats(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = None,
    agent_id: str | None = None,
    days: int = Query(7, ge=1, le=90),
) -> dict:
    """Estadísticas agregadas de evaluaciones."""
    sb = get_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    # Evaluaciones en el periodo
    query = (
        sb.table("call_evaluations")
        .select(
            "id, overall_score, failures_found, critical_failures, created_at, "
            "evaluation_data"
        )
        .gte("created_at", cutoff)
        .eq("status", "completed")
    )

    query = _apply_tenant_filter(query, user, client_id)
    if query is None:
        return {
            "total_evaluated": 0,
            "avg_score": 0,
            "failure_distribution": {},
            "severity_distribution": {},
            "trend": [],
        }

    if agent_id:
        query = query.eq("agent_id", agent_id)

    evals = query.execute().data or []

    if not evals:
        return {
            "total_evaluated": 0,
            "avg_score": 0,
            "failure_distribution": {},
            "severity_distribution": {},
            "trend": [],
        }

    # Calcular promedios
    scores = [e["overall_score"] for e in evals if e.get("overall_score") is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0

    # Distribución de failures por tipo y severidad
    failure_distribution: dict[str, int] = {}
    severity_distribution: dict[str, int] = {}

    # Consultar failures individuales para distribución
    effective_client_id = (
        user.client_id if user.role == "client" else client_id
    )
    fail_query = (
        sb.table("evaluation_failures")
        .select("failure_type, severity")
        .gte("created_at", cutoff)
    )
    if effective_client_id:
        fail_query = fail_query.eq("client_id", effective_client_id)
    failures = fail_query.execute().data or []

    for f in failures:
        ft = f.get("failure_type", "unknown")
        sev = f.get("severity", "unknown")
        failure_distribution[ft] = failure_distribution.get(ft, 0) + 1
        severity_distribution[sev] = severity_distribution.get(sev, 0) + 1

    # Trend: agrupar por día
    trend_map: dict[str, list[int]] = {}
    for e in evals:
        day = e["created_at"][:10] if e.get("created_at") else None
        if day and e.get("overall_score") is not None:
            trend_map.setdefault(day, []).append(e["overall_score"])

    trend = sorted(
        [
            {
                "date": day,
                "avg_score": round(sum(s) / len(s), 1),
                "count": len(s),
            }
            for day, s in trend_map.items()
        ],
        key=lambda x: x["date"],
    )

    return {
        "total_evaluated": len(evals),
        "avg_score": avg_score,
        "failure_distribution": failure_distribution,
        "severity_distribution": severity_distribution,
        "trend": trend,
    }


@router.get("/alerts")
async def list_alerts(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = None,
    severity: str | None = None,
    acknowledged: bool | None = None,
    limit: int = Query(20, ge=1, le=100),
) -> list[dict]:
    """Lista alertas de calidad recientes."""
    sb = get_supabase()
    query = (
        sb.table("quality_alerts")
        .select(
            "id, client_id, agent_id, call_id, evaluation_id, alert_type, severity, "
            "title, description, metadata, acknowledged, acknowledged_by, "
            "acknowledged_at, created_at"
        )
        .order("created_at", desc=True)
    )

    query = _apply_tenant_filter(query, user, client_id)
    if query is None:
        return []

    if severity:
        query = query.eq("severity", severity)
    if acknowledged is True:
        query = query.eq("acknowledged", True)
    elif acknowledged is False:
        query = query.eq("acknowledged", False)

    query = query.limit(limit)
    result = query.execute()
    return result.data or []


@router.patch("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Marca una alerta como reconocida."""
    sb = get_supabase()

    # Verificar que la alerta existe y el usuario tiene acceso
    alert = (
        sb.table("quality_alerts").select("id, client_id").eq("id", alert_id).execute()
    )
    if not alert.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alerta no encontrada"
        )

    alert_row = alert.data[0]
    if user.role == "client" and alert_row.get("client_id") != user.client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado"
        )

    updated = (
        sb.table("quality_alerts")
        .update(
            {
                "acknowledged": True,
                "acknowledged_by": user.id,
                "acknowledged_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .eq("id", alert_id)
        .execute()
    )
    if not updated.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error actualizando alerta",
        )
    return updated.data[0]


@router.post("/evaluate/{call_id}")
async def evaluate_single_call(
    call_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Evaluar manualmente una llamada específica."""
    sb = get_supabase()

    # Verificar que la llamada existe y el usuario tiene acceso
    call = sb.table("calls").select("id, client_id").eq("id", call_id).execute()
    if not call.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Llamada no encontrada"
        )

    call_row = call.data[0]
    if user.role == "client" and call_row.get("client_id") != user.client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado"
        )

    from api.services.call_evaluator import evaluate_call

    result = await evaluate_call(call_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Llamada sin transcript suficiente para evaluar",
        )
    return result


@router.post("/sweep")
async def trigger_sweep(
    user: CurrentUser = Depends(get_current_user),
    sample_size: int = Query(10, ge=1, le=50),
) -> dict:
    """Ejecutar manualmente un sweep de evaluación."""
    # Solo admin puede lanzar sweeps
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden ejecutar sweeps",
        )

    from api.services.call_evaluator import run_evaluation_sweep

    results = await run_evaluation_sweep(sample_size=sample_size)
    return results


@router.get("/failures")
async def list_failures(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = None,
    failure_type: str | None = None,
    severity: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """Lista todos los fallos detectados con filtros."""
    sb = get_supabase()
    query = (
        sb.table("evaluation_failures")
        .select(
            "id, evaluation_id, call_id, client_id, failure_type, severity, "
            "description, evidence, turn_index, recommendation, created_at"
        )
        .order("created_at", desc=True)
    )

    query = _apply_tenant_filter(query, user, client_id)
    if query is None:
        return []

    if failure_type:
        query = query.eq("failure_type", failure_type)
    if severity:
        query = query.eq("severity", severity)

    query = query.range(offset, offset + limit - 1)
    result = query.execute()
    return result.data or []
