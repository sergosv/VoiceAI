"""Rutas CRUD de contactos."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import get_supabase
from api.middleware.auth import CurrentUser, get_current_user
from api.schemas import (
    ContactCreateRequest,
    ContactOut,
    ContactUpdateRequest,
    IdentifierCreateRequest,
    IdentifierOut,
    MemoryOut,
    MessageResponse,
)
from agent.phone_utils import normalize_phone

router = APIRouter()


@router.get("", response_model=list[ContactOut])
async def list_contacts(
    user: CurrentUser = Depends(get_current_user),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = None,
    source: str | None = None,
    client_id: str | None = None,
) -> list[ContactOut]:
    """Lista contactos con búsqueda y paginación."""
    sb = get_supabase()
    query = sb.table("contacts").select("*").order("created_at", desc=True)

    # Multi-tenancy
    if user.role == "client":
        if not user.client_id:
            return []
        query = query.eq("client_id", user.client_id)
    elif client_id:
        query = query.eq("client_id", client_id)

    if source:
        query = query.eq("source", source)

    if search:
        query = query.or_(f"name.ilike.%{search}%,phone.ilike.%{search}%,email.ilike.%{search}%")

    offset = (page - 1) * per_page
    query = query.range(offset, offset + per_page - 1)

    result = query.execute()
    return [ContactOut(**row) for row in result.data]


@router.get("/{contact_id}", response_model=ContactOut)
async def get_contact(
    contact_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> ContactOut:
    """Obtiene un contacto por ID."""
    sb = get_supabase()
    result = sb.table("contacts").select("*").eq("id", contact_id).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contacto no encontrado")

    contact = result.data[0]
    if user.role == "client" and contact.get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    return ContactOut(**contact)


@router.post("", response_model=ContactOut, status_code=201)
async def create_contact(
    req: ContactCreateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> ContactOut:
    """Crea un contacto manualmente."""
    effective_client_id = user.client_id
    if user.role == "admin":
        effective_client_id = user.client_id  # Admin usa su propio client o recibe en query
    if not effective_client_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="client_id requerido")

    sb = get_supabase()
    normalized = normalize_phone(req.phone)

    # Check de duplicado
    existing = (
        sb.table("contacts").select("id")
        .eq("client_id", effective_client_id)
        .eq("phone", normalized)
        .limit(1)
        .execute()
    )
    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un contacto con ese teléfono",
        )

    data = {
        "client_id": effective_client_id,
        "phone": normalized,
        "name": req.name,
        "email": req.email,
        "notes": req.notes,
        "tags": req.tags,
        "source": "manual",
        "call_count": 0,
    }
    result = sb.table("contacts").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creando contacto")
    return ContactOut(**result.data[0])


@router.patch("/{contact_id}", response_model=ContactOut)
async def update_contact(
    contact_id: str,
    req: ContactUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> ContactOut:
    """Actualiza un contacto."""
    sb = get_supabase()

    # Verificar acceso
    existing = sb.table("contacts").select("client_id").eq("id", contact_id).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contacto no encontrado")
    if user.role == "client" and existing.data[0].get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    updates = req.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sin cambios")

    result = sb.table("contacts").update(updates).eq("id", contact_id).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contacto no encontrado")
    return ContactOut(**result.data[0])


@router.delete("/{contact_id}", response_model=MessageResponse)
async def delete_contact(
    contact_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> MessageResponse:
    """Elimina un contacto."""
    sb = get_supabase()

    existing = sb.table("contacts").select("client_id").eq("id", contact_id).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contacto no encontrado")
    if user.role == "client" and existing.data[0].get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    sb.table("contacts").delete().eq("id", contact_id).execute()
    return MessageResponse(message="Contacto eliminado")


@router.get("/{contact_id}/calls")
async def get_contact_calls(
    contact_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    """Historial de llamadas de un contacto (por número de teléfono)."""
    sb = get_supabase()

    contact = sb.table("contacts").select("phone, client_id").eq("id", contact_id).limit(1).execute()
    if not contact.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contacto no encontrado")

    row = contact.data[0]
    if user.role == "client" and row.get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    calls = (
        sb.table("calls")
        .select(
            "id, direction, caller_number, callee_number, duration_seconds, "
            "cost_total, status, summary, started_at, sentimiento, resumen_ia, lead_score"
        )
        .eq("client_id", row["client_id"])
        .or_(f"caller_number.eq.{row['phone']},callee_number.eq.{row['phone']}")
        .order("started_at", desc=True)
        .limit(50)
        .execute()
    )
    return calls.data


@router.get("/{contact_id}/timeline")
async def get_contact_timeline(
    contact_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Timeline unificado del contacto: llamadas, citas, campañas."""
    sb = get_supabase()

    contact = sb.table("contacts").select("phone, client_id").eq("id", contact_id).limit(1).execute()
    if not contact.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contacto no encontrado")

    row = contact.data[0]
    if user.role == "client" and row.get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    phone = row["phone"]
    cid = row["client_id"]

    # Llamadas con análisis
    calls = (
        sb.table("calls")
        .select(
            "id, direction, caller_number, callee_number, duration_seconds, "
            "cost_total, status, summary, started_at, sentimiento, resumen_ia, lead_score, intencion"
        )
        .eq("client_id", cid)
        .or_(f"caller_number.eq.{phone},callee_number.eq.{phone}")
        .order("started_at", desc=True)
        .limit(50)
        .execute()
    )

    # Citas del contacto
    appointments = (
        sb.table("appointments")
        .select("id, title, description, start_time, end_time, status, created_at")
        .eq("contact_id", contact_id)
        .order("start_time", desc=True)
        .limit(50)
        .execute()
    )

    # Campaign calls por teléfono
    campaign_calls_raw = (
        sb.table("campaign_calls")
        .select("id, campaign_id, phone, status, result_summary, analysis_data, created_at")
        .eq("phone", phone)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )

    # Enriquecer campaign_calls con nombre de campaña
    campaign_calls = campaign_calls_raw.data or []
    campaign_ids = list({cc["campaign_id"] for cc in campaign_calls if cc.get("campaign_id")})
    campaign_names: dict[str, str] = {}
    if campaign_ids:
        campaigns = (
            sb.table("campaigns")
            .select("id, name")
            .in_("id", campaign_ids)
            .execute()
        )
        campaign_names = {c["id"]: c["name"] for c in (campaigns.data or [])}
    for cc in campaign_calls:
        cc["campaign_name"] = campaign_names.get(cc.get("campaign_id", ""), "")

    # Summary
    total_calls = len(calls.data or [])
    total_appointments = len(appointments.data or [])
    last_contact_date = None
    if calls.data:
        last_contact_date = calls.data[0].get("started_at")

    next_appointment = None
    for apt in reversed(appointments.data or []):
        if apt.get("status") in ("confirmed", "pending"):
            next_appointment = apt.get("start_time")
            break

    return {
        "calls": calls.data or [],
        "appointments": appointments.data or [],
        "campaign_calls": campaign_calls,
        "summary": {
            "total_calls": total_calls,
            "total_appointments": total_appointments,
            "last_contact_date": last_contact_date,
            "next_appointment": next_appointment,
        },
    }


@router.get("/{contact_id}/memories", response_model=list[MemoryOut])
async def get_contact_memories(
    contact_id: str,
    user: CurrentUser = Depends(get_current_user),
    channel: str | None = None,
    limit: int = Query(20, ge=1, le=100),
) -> list[MemoryOut]:
    """Obtiene las memorias de un contacto, opcionalmente filtradas por canal."""
    sb = get_supabase()

    # Verificar acceso
    contact = sb.table("contacts").select("client_id").eq("id", contact_id).limit(1).execute()
    if not contact.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contacto no encontrado")
    if user.role == "client" and contact.data[0].get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    query = (
        sb.table("memories")
        .select("id, summary, channel, agent_name, duration_seconds, sentiment, topics, action_items, extracted_data, created_at")
        .eq("contact_id", contact_id)
        .order("created_at", desc=True)
        .limit(limit)
    )
    if channel:
        query = query.eq("channel", channel)

    result = query.execute()
    return [MemoryOut(**row) for row in (result.data or [])]


@router.get("/{contact_id}/identifiers", response_model=list[IdentifierOut])
async def get_contact_identifiers(
    contact_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> list[IdentifierOut]:
    """Lista todos los identificadores de un contacto."""
    sb = get_supabase()

    contact = sb.table("contacts").select("client_id").eq("id", contact_id).limit(1).execute()
    if not contact.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contacto no encontrado")
    if user.role == "client" and contact.data[0].get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    result = (
        sb.table("contact_identifiers")
        .select("id, identifier_type, identifier_value, is_primary, is_verified, created_at")
        .eq("contact_id", contact_id)
        .order("created_at")
        .execute()
    )
    return [IdentifierOut(**row) for row in (result.data or [])]


@router.post("/{contact_id}/identifiers", response_model=IdentifierOut, status_code=201)
async def add_contact_identifier(
    contact_id: str,
    req: IdentifierCreateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> IdentifierOut:
    """Vincula un nuevo identificador a un contacto."""
    sb = get_supabase()

    contact = sb.table("contacts").select("client_id").eq("id", contact_id).limit(1).execute()
    if not contact.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contacto no encontrado")

    client_id = contact.data[0]["client_id"]
    if user.role == "client" and client_id != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    # Verificar que no exista ya
    existing = (
        sb.table("contact_identifiers")
        .select("id")
        .eq("client_id", client_id)
        .eq("identifier_type", req.identifier_type)
        .eq("identifier_value", req.identifier_value)
        .limit(1)
        .execute()
    )
    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un identificador con ese tipo y valor",
        )

    data = {
        "client_id": client_id,
        "contact_id": contact_id,
        "identifier_type": req.identifier_type,
        "identifier_value": req.identifier_value,
    }
    result = sb.table("contact_identifiers").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creando identificador")
    return IdentifierOut(**result.data[0])
