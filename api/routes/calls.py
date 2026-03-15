"""Rutas para historial de llamadas."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse

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
    agent_id: str | None = Query(None, alias="agent_id"),
    date_from: date | None = None,
    date_to: date | None = None,
    client_id: str | None = None,
) -> list[CallOut]:
    """Lista llamadas con filtros. Client ve solo las suyas."""
    sb = get_supabase()
    query = sb.table("calls").select(
        "id, client_id, agent_id, direction, caller_number, callee_number, "
        "duration_seconds, cost_total, status, summary, sentimiento, resumen_ia, "
        "started_at, ended_at, metadata, recording_url, recording_key"
    ).order("started_at", desc=True)

    # Multi-tenancy (soporta impersonación admin)
    if user.client_id:
        query = query.eq("client_id", user.client_id)
    elif client_id:
        query = query.eq("client_id", client_id)

    if status_filter:
        query = query.eq("status", status_filter)
    if direction:
        query = query.eq("direction", direction)
    if agent_id:
        query = query.eq("agent_id", agent_id)
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
        row["has_recording"] = bool(row.get("recording_key") or row.get("recording_url"))
        row.pop("recording_url", None)
        row.pop("recording_key", None)
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
    effective_client_id = user.client_id or client_id

    # Obtener el total real usando count="exact"
    count_query = sb.table("calls").select("id", count="exact")
    if effective_client_id:
        count_query = count_query.eq("client_id", effective_client_id)
    count_result = count_query.limit(0).execute()
    real_total = count_result.count if count_result.count is not None else 0

    query = sb.table("calls").select(
        "duration_seconds, cost_total, started_at"
    )
    if effective_client_id:
        query = query.eq("client_id", effective_client_id)

    # Limitar para evitar cargar millones de filas en memoria
    query = query.limit(10000)

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
        total_calls=real_total,
        total_minutes=round(total_seconds / 60, 2),
        total_cost=round(total_cost, 4),
        avg_duration_seconds=round(total_seconds / len(rows), 1) if rows else 0,
        calls_today=len(today_rows),
        minutes_today=round(today_seconds / 60, 2),
    )


@router.get("/export/csv")
async def export_calls_csv(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    status_filter: str | None = Query(None, alias="status"),
) -> Response:
    """Exporta llamadas a CSV."""
    sb = get_supabase()
    query = sb.table("calls").select(
        "id, direction, caller_number, callee_number, duration_seconds, "
        "cost_total, status, summary, sentimiento, resumen_ia, started_at, metadata"
    ).order("started_at", desc=True)

    if user.client_id:
        query = query.eq("client_id", user.client_id)
    elif client_id:
        query = query.eq("client_id", client_id)

    if status_filter:
        query = query.eq("status", status_filter)
    if date_from:
        query = query.gte("started_at", date_from.isoformat())
    if date_to:
        end = datetime.combine(date_to, datetime.max.time()).isoformat()
        query = query.lte("started_at", end)

    query = query.limit(5000)
    result = query.execute()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Fecha", "Dirección", "Número origen", "Número destino",
        "Duración (s)", "Costo", "Estado", "Sentimiento", "Resumen", "Agente",
    ])
    for row in result.data:
        meta = row.get("metadata") or {}
        writer.writerow([
            row.get("started_at", ""),
            row.get("direction", ""),
            row.get("caller_number", ""),
            row.get("callee_number", ""),
            row.get("duration_seconds", 0),
            row.get("cost_total", 0),
            row.get("status", ""),
            row.get("sentimiento", ""),
            row.get("resumen_ia") or row.get("summary") or "",
            meta.get("agent_name", ""),
        ])

    output.seek(0)
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=llamadas_{today_str}.csv"},
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
    call["has_recording"] = bool(call.get("recording_key") or call.get("recording_url"))

    # Generar presigned URL si hay recording_key
    if call.get("recording_key"):
        from api.services.recording_service import generate_presigned_url

        url = generate_presigned_url(call["recording_key"])
        if url:
            call["recording_url"] = url

    # Construir desglose de costos con clasificación plataforma/externo
    bd = build_cost_breakdown(call)
    call["cost_breakdown"] = CostBreakdown(
        platform_cost=bd["platform_cost"],
        external_cost_estimate=bd["external_cost_estimate"],
        total=bd["total"],
        lines=[CostLineItem(**line) for line in bd["lines"]],
    )

    return CallDetailOut(**call)


@router.get("/{call_id}/recording")
async def get_recording_url(
    call_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Obtiene una URL pre-firmada para descargar la grabación de una llamada."""
    sb = get_supabase()
    result = (
        sb.table("calls")
        .select("id, client_id, recording_key, recording_url")
        .eq("id", call_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Llamada no encontrada"
        )

    call = result.data[0]

    # Multi-tenancy
    if user.role == "client" and call.get("client_id") != user.client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado"
        )

    # Preferir recording_key (R2), fallback a recording_url legacy
    if call.get("recording_key"):
        from api.services.recording_service import generate_presigned_url

        url = generate_presigned_url(call["recording_key"])
        if not url:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Error generando URL de grabación",
            )
        return {"url": url, "expires_in": 3600}
    elif call.get("recording_url"):
        return {"url": call["recording_url"], "expires_in": None}

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="No hay grabación disponible"
    )


@router.delete("/{call_id}/recording", status_code=status.HTTP_204_NO_CONTENT)
async def delete_call_recording(
    call_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> None:
    """Elimina la grabación de una llamada de R2 y limpia la referencia en DB (GDPR)."""
    sb = get_supabase()
    result = (
        sb.table("calls")
        .select("id, client_id, recording_key, recording_url")
        .eq("id", call_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Llamada no encontrada"
        )

    call = result.data[0]

    # Multi-tenancy
    if user.role == "client" and call.get("client_id") != user.client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado"
        )

    if not call.get("recording_key") and not call.get("recording_url"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No hay grabación"
        )

    # Eliminar archivo de R2 si existe recording_key
    if call.get("recording_key"):
        from api.services.recording_service import delete_recording

        delete_recording(call["recording_key"])

    # Limpiar referencias en DB y marcar como eliminada
    sb.table("calls").update({
        "recording_key": None,
        "recording_url": None,
        "recording_duration_seconds": None,
        "recording_status": "deleted",
    }).eq("id", call_id).execute()
    return None
