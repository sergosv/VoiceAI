"""Rutas CRUD de clientes."""

from __future__ import annotations

import asyncio
import os

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_supabase
from api.middleware.auth import CurrentUser, get_current_user, require_admin
from api.schemas import (
    AssignPhoneRequest,
    AvailableNumberOut,
    ClientCreateRequest,
    ClientOut,
    ClientUpdateRequest,
    MessageResponse,
    PromptTemplateOut,
    PurchaseNumberRequest,
    client_out_from_row,
)
from api.services.phone_service import (
    assign_phone_to_client,
    purchase_phone_number,
    search_available_numbers,
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

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "config", "prompts", "templates")


def _parse_template_name(content: str) -> str:
    """Extrae el nombre del template del header."""
    for line in content.splitlines():
        if line.startswith("# TEMPLATE:"):
            return line.split(":", 1)[1].strip()
    return "Sin nombre"


@router.get("/templates", response_model=list[PromptTemplateOut])
async def list_templates(
    user: CurrentUser = Depends(get_current_user),
) -> list[PromptTemplateOut]:
    """Lista templates de prompts disponibles por industria."""
    templates = []
    tpl_dir = os.path.normpath(TEMPLATES_DIR)
    if not os.path.isdir(tpl_dir):
        return []
    for filename in sorted(os.listdir(tpl_dir)):
        if not filename.endswith(".txt"):
            continue
        key = filename.replace(".txt", "")
        filepath = os.path.join(tpl_dir, filename)
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        name = _parse_template_name(content)
        templates.append(PromptTemplateOut(key=key, name=name, content=content))
    return templates


@router.get("/templates/{key}", response_model=PromptTemplateOut)
async def get_template(
    key: str,
    agent_name: str = "María",
    business_name: str = "Mi Negocio",
    user: CurrentUser = Depends(get_current_user),
) -> PromptTemplateOut:
    """Devuelve un template con variables sustituidas."""
    tpl_dir = os.path.normpath(TEMPLATES_DIR)
    filepath = os.path.join(tpl_dir, f"{key}.txt")
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template no encontrado")
    with open(filepath, encoding="utf-8") as f:
        content = f.read()
    name = _parse_template_name(content)
    # Sustituir variables
    content = content.replace("{agent_name}", agent_name)
    content = content.replace("{business_name}", business_name)
    content = content.replace("{language}", "es")
    return PromptTemplateOut(key=key, name=name, content=content)


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
    return [client_out_from_row(row) for row in result.data]


@router.get("/available-numbers", response_model=list[AvailableNumberOut])
async def list_available_numbers(
    country: str = "MX",
    area_code: str | None = None,
    limit: int = 10,
    admin: CurrentUser = Depends(require_admin),
) -> list[AvailableNumberOut]:
    """Busca números disponibles en Twilio (solo admin)."""
    try:
        numbers = await asyncio.to_thread(
            search_available_numbers, country, area_code, limit
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error buscando números en Twilio: {e}",
        )
    return [AvailableNumberOut(**n) for n in numbers]


@router.post("/{client_id}/purchase-phone", response_model=ClientOut)
async def purchase_and_assign_phone(
    client_id: str,
    req: PurchaseNumberRequest,
    admin: CurrentUser = Depends(require_admin),
) -> ClientOut:
    """Compra un número en Twilio y lo asigna al cliente con SIP config (solo admin)."""
    # Comprar número
    try:
        phone_sid, normalized_number = await asyncio.to_thread(
            purchase_phone_number, req.phone_number
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error comprando número en Twilio: {e}",
        )

    # Configurar SIP en LiveKit
    try:
        trunk_id, _ = await setup_livekit_sip(normalized_number)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Número comprado ({normalized_number}) pero error configurando SIP: {e}",
        )

    # Guardar en DB
    sb = get_supabase()
    row = assign_phone_to_client(
        sb,
        client_id=client_id,
        phone_number=normalized_number,
        phone_sid=phone_sid,
        trunk_id=trunk_id,
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado"
        )

    # También actualizar el agent default
    from api.services.phone_service import assign_phone_to_agent
    default_agent = sb.table("agents").select("id").eq("client_id", client_id).order("created_at").limit(1).execute()
    if default_agent.data:
        assign_phone_to_agent(
            sb,
            agent_id=default_agent.data[0]["id"],
            phone_number=normalized_number,
            phone_sid=phone_sid,
            trunk_id=trunk_id,
        )

    return client_out_from_row(row)


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
    return client_out_from_row(result.data[0])


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

    # Crear agent default para el nuevo cliente
    client_id = row["id"]
    voice_config = {"provider": "cartesia", "voice_id": voice_id, "realtime_voice": "alloy", "realtime_model": "gpt-4o-realtime-preview"}
    llm_config = {"provider": "google"}
    stt_config = {"provider": "deepgram"}
    sb.table("agents").insert({
        "client_id": client_id,
        "name": req.agent_name,
        "slug": "default",
        "system_prompt": system_prompt,
        "greeting": greeting,
        "voice_config": voice_config,
        "llm_config": llm_config,
        "stt_config": stt_config,
    }).execute()

    return client_out_from_row(row)


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
        "greeting", "system_prompt", "conversation_examples",
        "agent_name", "language", "voice_id",
        "max_call_duration_seconds", "transfer_number", "business_hours",
        "after_hours_message",
        "google_calendar_id", "whatsapp_instance_id", "whatsapp_api_url",
        "whatsapp_api_key", "enabled_tools",
        "voice_mode", "stt_provider", "llm_provider", "tts_provider",
        "stt_api_key", "llm_api_key", "tts_api_key",
        "realtime_api_key", "realtime_voice", "realtime_model",
        "orchestration_mode", "orchestrator_model", "orchestrator_prompt",
    }

    updates = req.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sin cambios")

    if user.role == "client":
        updates = {k: v for k, v in updates.items() if k in client_editable}
        if not updates:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin permiso para esos campos")

    # Separar campos de agente de campos de cliente
    agent_fields = {
        "greeting", "system_prompt", "conversation_examples",
        "agent_name", "voice_id",
        "max_call_duration_seconds", "transfer_number", "after_hours_message",
        "voice_mode", "stt_provider", "llm_provider", "tts_provider",
        "stt_api_key", "llm_api_key", "tts_api_key",
        "realtime_api_key", "realtime_voice", "realtime_model",
    }
    agent_updates: dict = {}
    client_updates: dict = {}
    for k, v in updates.items():
        if k in agent_fields:
            agent_updates[k] = v
        client_updates[k] = v  # Siempre escribir en clients para backward compat

    sb = get_supabase()

    # Delegar campos de agente al agent default
    if agent_updates:
        default_agent = (
            sb.table("agents")
            .select("id, voice_config, llm_config, stt_config")
            .eq("client_id", client_id)
            .order("created_at")
            .limit(1)
            .execute()
        )
        if default_agent.data:
            a = default_agent.data[0]
            a_updates: dict = {}
            # Campos directos
            for f in ("greeting", "system_prompt", "max_call_duration_seconds",
                       "transfer_number", "after_hours_message"):
                if f in agent_updates:
                    a_updates[f] = agent_updates[f]
            if "agent_name" in agent_updates:
                a_updates["name"] = agent_updates["agent_name"]
            if "conversation_examples" in agent_updates:
                a_updates["examples"] = agent_updates["conversation_examples"]
            if "voice_mode" in agent_updates:
                a_updates["agent_mode"] = agent_updates["voice_mode"]
            # JSONB voice_config
            vc = dict(a.get("voice_config") or {})
            vc_changed = False
            if "voice_id" in agent_updates:
                vc["voice_id"] = agent_updates["voice_id"]
                vc_changed = True
            if "tts_provider" in agent_updates:
                vc["provider"] = agent_updates["tts_provider"]
                vc_changed = True
            if "tts_api_key" in agent_updates:
                vc["api_key"] = agent_updates["tts_api_key"]
                vc_changed = True
            if "realtime_api_key" in agent_updates:
                vc["realtime_api_key"] = agent_updates["realtime_api_key"]
                vc_changed = True
            if "realtime_voice" in agent_updates:
                vc["realtime_voice"] = agent_updates["realtime_voice"]
                vc_changed = True
            if "realtime_model" in agent_updates:
                vc["realtime_model"] = agent_updates["realtime_model"]
                vc_changed = True
            if vc_changed:
                a_updates["voice_config"] = vc
            # JSONB llm_config
            lc = dict(a.get("llm_config") or {})
            lc_changed = False
            if "llm_provider" in agent_updates:
                lc["provider"] = agent_updates["llm_provider"]
                lc_changed = True
            if "llm_api_key" in agent_updates:
                lc["api_key"] = agent_updates["llm_api_key"]
                lc_changed = True
            if lc_changed:
                a_updates["llm_config"] = lc
            # JSONB stt_config
            sc = dict(a.get("stt_config") or {})
            sc_changed = False
            if "stt_provider" in agent_updates:
                sc["provider"] = agent_updates["stt_provider"]
                sc_changed = True
            if "stt_api_key" in agent_updates:
                sc["api_key"] = agent_updates["stt_api_key"]
                sc_changed = True
            if sc_changed:
                a_updates["stt_config"] = sc

            if a_updates:
                sb.table("agents").update(a_updates).eq("id", a["id"]).execute()

    result = sb.table("clients").update(client_updates).eq("id", client_id).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")
    return client_out_from_row(result.data[0])


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

    # También actualizar el agent default
    from api.services.phone_service import assign_phone_to_agent
    default_agent = sb.table("agents").select("id").eq("client_id", client_id).order("created_at").limit(1).execute()
    if default_agent.data:
        assign_phone_to_agent(
            sb,
            agent_id=default_agent.data[0]["id"],
            phone_number=req.phone_number,
            phone_sid=phone_sid,
            trunk_id=trunk_id,
        )

    return client_out_from_row(row)


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
