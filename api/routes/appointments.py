"""Rutas CRUD de citas."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import get_supabase
from api.middleware.auth import CurrentUser, get_current_user
from api.schemas import (
    AppointmentCreateRequest,
    AppointmentOut,
    AppointmentUpdateRequest,
    MessageResponse,
)

router = APIRouter()


@router.get("", response_model=list[AppointmentOut])
async def list_appointments(
    user: CurrentUser = Depends(get_current_user),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    date_from: date | None = None,
    date_to: date | None = None,
    client_id: str | None = None,
) -> list[AppointmentOut]:
    """Lista citas con filtros de fecha y estado."""
    sb = get_supabase()
    query = sb.table("appointments").select("*").order("start_time", desc=False)

    # Multi-tenancy
    if user.role == "client":
        if not user.client_id:
            return []
        query = query.eq("client_id", user.client_id)
    elif client_id:
        query = query.eq("client_id", client_id)

    if status_filter:
        query = query.eq("status", status_filter)
    if date_from:
        query = query.gte("start_time", date_from.isoformat())
    if date_to:
        end = datetime.combine(date_to, datetime.max.time()).isoformat()
        query = query.lte("start_time", end)

    offset = (page - 1) * per_page
    query = query.range(offset, offset + per_page - 1)

    result = query.execute()
    return [AppointmentOut(**row) for row in result.data]


@router.get("/{appointment_id}", response_model=AppointmentOut)
async def get_appointment(
    appointment_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> AppointmentOut:
    """Obtiene una cita por ID."""
    sb = get_supabase()
    result = sb.table("appointments").select("*").eq("id", appointment_id).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cita no encontrada")

    appointment = result.data[0]
    if user.role == "client" and appointment.get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    return AppointmentOut(**appointment)


@router.post("", response_model=AppointmentOut, status_code=201)
async def create_appointment(
    req: AppointmentCreateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> AppointmentOut:
    """Crea una cita manualmente."""
    effective_client_id = user.client_id
    if not effective_client_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="client_id requerido")

    sb = get_supabase()

    # Verificar conflictos
    conflicts = (
        sb.table("appointments")
        .select("id")
        .eq("client_id", effective_client_id)
        .eq("status", "confirmed")
        .lt("start_time", req.end_time.isoformat())
        .gt("end_time", req.start_time.isoformat())
        .execute()
    )
    if conflicts.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una cita en ese horario",
        )

    data = {
        "client_id": effective_client_id,
        "contact_id": req.contact_id,
        "title": req.title,
        "description": req.description,
        "start_time": req.start_time.isoformat(),
        "end_time": req.end_time.isoformat(),
        "status": "confirmed",
    }
    result = sb.table("appointments").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creando cita")
    return AppointmentOut(**result.data[0])


@router.patch("/{appointment_id}", response_model=AppointmentOut)
async def update_appointment(
    appointment_id: str,
    req: AppointmentUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> AppointmentOut:
    """Actualiza una cita (status, horario, etc)."""
    sb = get_supabase()

    existing = sb.table("appointments").select("client_id").eq("id", appointment_id).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cita no encontrada")
    if user.role == "client" and existing.data[0].get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    updates = req.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sin cambios")

    # Serializar datetimes
    for key in ("start_time", "end_time"):
        if key in updates and isinstance(updates[key], datetime):
            updates[key] = updates[key].isoformat()

    result = sb.table("appointments").update(updates).eq("id", appointment_id).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cita no encontrada")
    return AppointmentOut(**result.data[0])


@router.delete("/{appointment_id}", response_model=MessageResponse)
async def delete_appointment(
    appointment_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> MessageResponse:
    """Elimina una cita."""
    sb = get_supabase()

    existing = sb.table("appointments").select("client_id").eq("id", appointment_id).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cita no encontrada")
    if user.role == "client" and existing.data[0].get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    sb.table("appointments").delete().eq("id", appointment_id).execute()
    return MessageResponse(message="Cita eliminada")
