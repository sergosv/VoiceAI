"""Rutas CRUD de campañas outbound."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.deps import get_supabase
from api.middleware.auth import CurrentUser, get_current_user
from api.schemas import MessageResponse
from api.services.outbound_service import start_campaign, pause_campaign, restart_campaign

router = APIRouter()


# ── Schemas ──────────────────────────────────────────

class CampaignOut(BaseModel):
    id: str
    client_id: str
    agent_id: str | None = None
    name: str
    description: str | None = None
    script: str
    status: str = "draft"
    scheduled_at: str | None = None
    completed_at: str | None = None
    max_concurrent: int = 1
    retry_attempts: int = 2
    retry_delay_minutes: int = 30
    total_contacts: int = 0
    completed_contacts: int = 0
    successful_contacts: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class CampaignCreateRequest(BaseModel):
    name: str
    description: str | None = None
    script: str
    agent_id: str | None = None
    max_concurrent: int = 1
    retry_attempts: int = 2
    retry_delay_minutes: int = 30


class CampaignUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    script: str | None = None
    max_concurrent: int | None = None
    retry_attempts: int | None = None
    retry_delay_minutes: int | None = None


class CampaignCallOut(BaseModel):
    id: str
    campaign_id: str
    contact_id: str | None = None
    call_id: str | None = None
    phone: str
    status: str = "pending"
    attempt: int = 0
    result_summary: str | None = None
    analysis_data: dict | None = None
    created_at: str | None = None


class BulkContactsRequest(BaseModel):
    contact_ids: list[str] = Field(default_factory=list)
    phone_numbers: list[str] = Field(default_factory=list)


# ── Routes ───────────────────────────────────────────

@router.get("", response_model=list[CampaignOut])
async def list_campaigns(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = None,
) -> list[CampaignOut]:
    """Lista campañas."""
    sb = get_supabase()
    query = sb.table("campaigns").select("*").order("created_at", desc=True)

    if user.role == "client":
        if not user.client_id:
            return []
        query = query.eq("client_id", user.client_id)
    elif client_id:
        query = query.eq("client_id", client_id)

    result = query.execute()
    return [CampaignOut(**row) for row in result.data]


@router.get("/{campaign_id}", response_model=CampaignOut)
async def get_campaign(
    campaign_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> CampaignOut:
    """Obtiene una campaña por ID."""
    sb = get_supabase()
    result = sb.table("campaigns").select("*").eq("id", campaign_id).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaña no encontrada")

    camp = result.data[0]
    if user.role == "client" and camp.get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    return CampaignOut(**camp)


@router.post("", response_model=CampaignOut, status_code=201)
async def create_campaign(
    req: CampaignCreateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> CampaignOut:
    """Crea una nueva campaña."""
    effective_client_id = user.client_id
    if not effective_client_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="client_id requerido")

    sb = get_supabase()

    # Resolver agent_id: si no viene, usar el default del client
    agent_id = req.agent_id
    if not agent_id:
        default_agent = (
            sb.table("agents")
            .select("id")
            .eq("client_id", effective_client_id)
            .eq("is_active", True)
            .order("created_at")
            .limit(1)
            .execute()
        )
        if default_agent.data:
            agent_id = default_agent.data[0]["id"]

    data = {
        "client_id": effective_client_id,
        "agent_id": agent_id,
        "name": req.name,
        "description": req.description,
        "script": req.script,
        "max_concurrent": req.max_concurrent,
        "retry_attempts": req.retry_attempts,
        "retry_delay_minutes": req.retry_delay_minutes,
    }
    result = sb.table("campaigns").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creando campaña")
    return CampaignOut(**result.data[0])


@router.patch("/{campaign_id}", response_model=CampaignOut)
async def update_campaign(
    campaign_id: str,
    req: CampaignUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> CampaignOut:
    """Actualiza una campaña (solo en draft o paused)."""
    sb = get_supabase()

    existing = sb.table("campaigns").select("client_id, status").eq("id", campaign_id).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaña no encontrada")
    if user.role == "client" and existing.data[0].get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")
    if existing.data[0]["status"] == "running":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pausa la campaña antes de editarla")

    updates = req.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sin cambios")

    result = sb.table("campaigns").update(updates).eq("id", campaign_id).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaña no encontrada")
    return CampaignOut(**result.data[0])


@router.delete("/{campaign_id}", response_model=MessageResponse)
async def delete_campaign(
    campaign_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> MessageResponse:
    """Elimina una campaña (no se puede si está running)."""
    sb = get_supabase()

    existing = sb.table("campaigns").select("client_id, status").eq("id", campaign_id).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaña no encontrada")
    if user.role == "client" and existing.data[0].get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")
    if existing.data[0]["status"] == "running":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pausa la campaña antes de eliminarla")

    sb.table("campaign_calls").delete().eq("campaign_id", campaign_id).execute()
    sb.table("campaigns").delete().eq("id", campaign_id).execute()
    return MessageResponse(message="Campaña eliminada")


@router.post("/{campaign_id}/start", response_model=CampaignOut)
async def start_campaign_route(
    campaign_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> CampaignOut:
    """Inicia una campaña."""
    sb = get_supabase()

    existing = sb.table("campaigns").select("client_id").eq("id", campaign_id).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaña no encontrada")
    if user.role == "client" and existing.data[0].get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    try:
        result = await start_campaign(campaign_id)
        return CampaignOut(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{campaign_id}/pause", response_model=CampaignOut)
async def pause_campaign_route(
    campaign_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> CampaignOut:
    """Pausa una campaña en ejecución."""
    sb = get_supabase()

    existing = sb.table("campaigns").select("client_id").eq("id", campaign_id).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaña no encontrada")
    if user.role == "client" and existing.data[0].get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    try:
        result = await pause_campaign(campaign_id)
        return CampaignOut(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{campaign_id}/restart", response_model=CampaignOut)
async def restart_campaign_route(
    campaign_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> CampaignOut:
    """Reinicia una campaña: resetea llamadas fallidas/completadas a pending."""
    sb = get_supabase()

    existing = sb.table("campaigns").select("client_id").eq("id", campaign_id).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaña no encontrada")
    if user.role == "client" and existing.data[0].get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    try:
        result = await restart_campaign(campaign_id)
        return CampaignOut(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{campaign_id}/calls", response_model=list[CampaignCallOut])
async def list_campaign_calls(
    campaign_id: str,
    user: CurrentUser = Depends(get_current_user),
    status_filter: str | None = Query(None, alias="status"),
) -> list[CampaignCallOut]:
    """Lista las llamadas de una campaña."""
    sb = get_supabase()

    existing = sb.table("campaigns").select("client_id").eq("id", campaign_id).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaña no encontrada")
    if user.role == "client" and existing.data[0].get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    query = (
        sb.table("campaign_calls")
        .select("*")
        .eq("campaign_id", campaign_id)
        .order("created_at")
    )
    if status_filter:
        query = query.eq("status", status_filter)

    result = query.execute()
    return [CampaignCallOut(**row) for row in result.data]


@router.post("/{campaign_id}/contacts", response_model=MessageResponse)
async def add_campaign_contacts(
    campaign_id: str,
    req: BulkContactsRequest,
    user: CurrentUser = Depends(get_current_user),
) -> MessageResponse:
    """Agrega contactos a una campaña (por IDs o números directos)."""
    sb = get_supabase()

    existing = sb.table("campaigns").select("client_id, status").eq("id", campaign_id).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaña no encontrada")
    if user.role == "client" and existing.data[0].get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")
    if existing.data[0]["status"] == "running":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pausa la campaña antes de agregar contactos")

    entries = []

    # Agregar por contact_id
    if req.contact_ids:
        contacts = sb.table("contacts").select("id, phone").in_("id", req.contact_ids).execute()
        for c in contacts.data:
            entries.append({
                "campaign_id": campaign_id,
                "contact_id": c["id"],
                "phone": c["phone"],
                "status": "pending",
            })

    # Agregar por número directo
    for phone in req.phone_numbers:
        entries.append({
            "campaign_id": campaign_id,
            "phone": phone,
            "status": "pending",
        })

    if not entries:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sin contactos para agregar")

    sb.table("campaign_calls").insert(entries).execute()

    # Actualizar total_contacts
    total = (
        sb.table("campaign_calls")
        .select("id", count="exact")
        .eq("campaign_id", campaign_id)
        .execute()
    )
    sb.table("campaigns").update({"total_contacts": total.count or 0}).eq("id", campaign_id).execute()

    return MessageResponse(message=f"{len(entries)} contactos agregados a la campaña")


class UpdateCampaignCallRequest(BaseModel):
    phone: str


@router.patch("/{campaign_id}/calls/{call_id}", response_model=CampaignCallOut)
async def update_campaign_call(
    campaign_id: str,
    call_id: str,
    req: UpdateCampaignCallRequest,
    user: CurrentUser = Depends(get_current_user),
) -> CampaignCallOut:
    """Actualiza el teléfono de un contacto en la campaña."""
    sb = get_supabase()

    existing = sb.table("campaigns").select("client_id, status").eq("id", campaign_id).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaña no encontrada")
    if user.role == "client" and existing.data[0].get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")
    if existing.data[0]["status"] == "running":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pausa la campaña antes de editar contactos")

    phone = req.phone.strip()
    if not phone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El teléfono no puede estar vacío")

    result = (
        sb.table("campaign_calls")
        .update({"phone": phone})
        .eq("id", call_id)
        .eq("campaign_id", campaign_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contacto no encontrado")

    return CampaignCallOut(**result.data[0])


@router.delete("/{campaign_id}/calls/{call_id}", response_model=MessageResponse)
async def delete_campaign_call(
    campaign_id: str,
    call_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> MessageResponse:
    """Elimina un contacto/llamada de una campaña."""
    sb = get_supabase()

    existing = sb.table("campaigns").select("client_id, status").eq("id", campaign_id).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaña no encontrada")
    if user.role == "client" and existing.data[0].get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")
    if existing.data[0]["status"] == "running":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pausa la campaña antes de eliminar contactos")

    sb.table("campaign_calls").delete().eq("id", call_id).eq("campaign_id", campaign_id).execute()

    # Recalcular total_contacts
    total = (
        sb.table("campaign_calls")
        .select("id", count="exact")
        .eq("campaign_id", campaign_id)
        .execute()
    )
    sb.table("campaigns").update({"total_contacts": total.count or 0}).eq("id", campaign_id).execute()

    return MessageResponse(message="Contacto eliminado de la campaña")
