"""Rutas CRUD de clientes."""

from __future__ import annotations

import asyncio
import os

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_supabase
from api.middleware.auth import CurrentUser, get_current_user, require_admin
from api.schemas import (
    AssignPhoneRequest,
    ClientCreateRequest,
    ClientOut,
    ClientUpdateRequest,
    MessageResponse,
)
from api.services.phone_service import (
    assign_phone_to_client,
    setup_livekit_sip,
    verify_twilio_number,
)
from api.services.client_service import (
    build_greeting,
    build_system_prompt,
    create_client_in_db,
    create_gemini_store,
    load_voice_id,
)

router = APIRouter()


@router.get("", response_model=list[ClientOut])
async def list_clients(
    user: CurrentUser = Depends(get_current_user),
) -> list[ClientOut]:
    """Lista clientes. Admin ve todos, client ve solo el suyo."""
    sb = get_supabase()
    query = sb.table("clients").select("*").order("created_at", desc=True)

    if user.role == "client":
        if not user.client_id:
            return []
        query = query.eq("id", user.client_id)

    result = query.execute()
    return [ClientOut(**row) for row in result.data]


@router.get("/{client_id}", response_model=ClientOut)
async def get_client(
    client_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> ClientOut:
    """Obtiene un cliente por ID."""
    if user.role == "client" and user.client_id != client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    sb = get_supabase()
    result = sb.table("clients").select("*").eq("id", client_id).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")
    return ClientOut(**result.data[0])


@router.post("", response_model=ClientOut, status_code=201)
async def create_client(
    req: ClientCreateRequest,
    admin: CurrentUser = Depends(require_admin),
) -> ClientOut:
    """Crea un nuevo cliente (solo admin)."""
    try:
        voice_id = load_voice_id(req.voice_key)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    greeting = req.greeting or build_greeting(req.name, req.agent_name)
    system_prompt = req.system_prompt or build_system_prompt(
        req.business_type, req.agent_name, req.name, req.language,
    )

    store_id = None
    store_name = None
    if not req.skip_store:
        try:
            store_id, store_name = await asyncio.to_thread(
                create_gemini_store, req.slug, os.environ["GOOGLE_API_KEY"]
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Error creando FileSearchStore: {e}",
            )

    sb = get_supabase()
    row = create_client_in_db(
        sb,
        name=req.name,
        slug=req.slug,
        business_type=req.business_type,
        agent_name=req.agent_name,
        language=req.language,
        voice_id=voice_id,
        greeting=greeting,
        system_prompt=system_prompt,
        store_id=store_id,
        store_name=store_name,
        owner_email=req.owner_email,
    )
    return ClientOut(**row)


@router.patch("/{client_id}", response_model=ClientOut)
async def update_client(
    client_id: str,
    req: ClientUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> ClientOut:
    """Actualiza un cliente. Admin puede editar todo, client solo su config de agente."""
    if user.role == "client" and user.client_id != client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    # Campos que un client puede editar
    client_editable = {
        "greeting", "system_prompt", "agent_name", "language",
        "max_call_duration_seconds", "transfer_number", "business_hours",
        "after_hours_message",
        "google_calendar_id", "whatsapp_instance_id", "whatsapp_api_url",
        "whatsapp_api_key", "enabled_tools",
    }

    updates = req.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sin cambios")

    if user.role == "client":
        updates = {k: v for k, v in updates.items() if k in client_editable}
        if not updates:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin permiso para esos campos")

    sb = get_supabase()
    result = sb.table("clients").update(updates).eq("id", client_id).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")
    return ClientOut(**result.data[0])


@router.post("/{client_id}/assign-phone", response_model=ClientOut)
async def assign_phone(
    client_id: str,
    req: AssignPhoneRequest,
    admin: CurrentUser = Depends(require_admin),
) -> ClientOut:
    """Asigna un número de teléfono Twilio a un cliente (solo admin)."""
    # Verificar número en Twilio
    try:
        phone_sid = await asyncio.to_thread(verify_twilio_number, req.phone_number)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error verificando número en Twilio: {e}",
        )

    # Configurar SIP en LiveKit
    trunk_id = None
    if not req.skip_livekit:
        try:
            trunk_id, _ = await setup_livekit_sip(req.phone_number)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Error configurando LiveKit SIP: {e}",
            )

    sb = get_supabase()
    row = assign_phone_to_client(
        sb,
        client_id=client_id,
        phone_number=req.phone_number,
        phone_sid=phone_sid,
        trunk_id=trunk_id,
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")
    return ClientOut(**row)


@router.delete("/{client_id}", response_model=MessageResponse)
async def delete_client(
    client_id: str,
    admin: CurrentUser = Depends(require_admin),
) -> MessageResponse:
    """Elimina un cliente (solo admin)."""
    sb = get_supabase()
    result = sb.table("clients").delete().eq("id", client_id).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")
    return MessageResponse(message="Cliente eliminado")


@router.post("/{client_id}/test-whatsapp", response_model=MessageResponse)
async def test_whatsapp(
    client_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> MessageResponse:
    """Envía un mensaje de prueba por WhatsApp."""
    if user.role == "client" and user.client_id != client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    sb = get_supabase()
    result = (
        sb.table("clients")
        .select("whatsapp_instance_id, whatsapp_api_url, whatsapp_api_key, phone_number")
        .eq("id", client_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")

    client = result.data[0]
    if not client.get("whatsapp_instance_id") or not client.get("whatsapp_api_url") or not client.get("whatsapp_api_key"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WhatsApp no configurado")

    from agent.tools.whatsapp_tool import send_whatsapp_message
    phone = client.get("phone_number", "")
    if not phone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sin número de teléfono para enviar prueba")

    msg = await send_whatsapp_message(
        api_url=client["whatsapp_api_url"],
        api_key=client["whatsapp_api_key"],
        instance_id=client["whatsapp_instance_id"],
        phone_number=phone,
        message="Mensaje de prueba desde Voice AI Platform",
    )
    return MessageResponse(message=msg)


@router.post("/{client_id}/test-calendar", response_model=MessageResponse)
async def test_calendar(
    client_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> MessageResponse:
    """Verifica el acceso al calendario de Google."""
    if user.role == "client" and user.client_id != client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    sb = get_supabase()
    result = (
        sb.table("clients")
        .select("google_calendar_id, google_service_account_key")
        .eq("id", client_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")

    client = result.data[0]
    if not client.get("google_calendar_id") or not client.get("google_service_account_key"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google Calendar no configurado",
        )

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        credentials = service_account.Credentials.from_service_account_info(
            client["google_service_account_key"],
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        )
        service = build("calendar", "v3", credentials=credentials)
        cal = service.calendars().get(calendarId=client["google_calendar_id"]).execute()
        return MessageResponse(message=f"Conexión exitosa. Calendario: {cal.get('summary', 'OK')}")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error conectando con Google Calendar: {e}",
        )
