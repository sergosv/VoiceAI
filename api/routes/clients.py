"""Rutas CRUD de clientes."""

from __future__ import annotations

import asyncio
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, status

from api.audit import log_audit
from api.crypto import encrypt_value
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
    SaveTwilioCredentialsRequest,
    client_out_from_row,
)
from api.services.phone_service import (
    assign_phone_to_client,
    associate_number_to_trunk,
    enable_geo_permission,
    ensure_client_subaccount,
    get_client_twilio_creds,
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
    create_owner_user,
    delete_gemini_store,
    delete_owner_user,
    generate_temp_password,
    load_voice_id,
)
from api.services.email_service import send_welcome_email
from api.services.webhook_service import dispatch_event

router = APIRouter()
logger = logging.getLogger("api.clients")

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

    if user.client_id:
        query = query.eq("id", user.client_id)

    result = query.execute()
    return [client_out_from_row(row) for row in result.data]


@router.get("/available-numbers", response_model=list[AvailableNumberOut])
async def list_available_numbers(
    country: str = "MX",
    area_code: str | None = None,
    limit: int = 10,
    client_id: str | None = None,
    admin: CurrentUser = Depends(require_admin),
) -> list[AvailableNumberOut]:
    """Busca números disponibles en Twilio (solo admin). Si el cliente tiene BYOT, usa su cuenta."""
    byot_sid, byot_token = None, None
    if client_id:
        sb = get_supabase()
        byot_sid, byot_token = get_client_twilio_creds(sb, client_id)
    try:
        numbers = await asyncio.to_thread(
            search_available_numbers, country, area_code, limit,
            account_sid=byot_sid, auth_token=byot_token,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error buscando números en Twilio: {e}",
        )
    return [AvailableNumberOut(**n) for n in numbers]


def _country_from_phone(phone: str) -> str:
    """Infiere el país ISO desde un número en formato E.164."""
    if phone.startswith("+57"):
        return "CO"
    if phone.startswith("+56"):
        return "CL"
    if phone.startswith("+54"):
        return "AR"
    if phone.startswith("+1"):
        return "US"
    return "MX"


@router.post("/{client_id}/purchase-phone", response_model=ClientOut)
async def purchase_and_assign_phone(
    client_id: str,
    req: PurchaseNumberRequest,
    admin: CurrentUser = Depends(require_admin),
) -> ClientOut:
    """Compra un número en Twilio y lo asigna al cliente con SIP config (solo admin).

    Flujo de resolución de credenciales:
      1. BYOT: cliente tiene sus propias creds Twilio → usarlas directamente.
      2. Subaccount: si no hay BYOT, asegurar que el cliente tenga subaccount + trunk
         (crear al primer uso). Comprar número DENTRO de la subaccount y asociarlo
         al trunk de la subaccount que apunta a LiveKit.
      3. Main (grandfathered): ningún cliente nuevo cae aquí; solo aplica si el
         admin expresamente omitió la subaccount. La ruta no lo permite.
    """
    sb = get_supabase()
    byot_sid, byot_token = get_client_twilio_creds(sb, client_id)
    country = _country_from_phone(req.phone_number)

    twilio_trunk_sid: str | None = None
    if byot_sid:
        creds_sid, creds_token = byot_sid, byot_token
    else:
        try:
            creds_sid, creds_token, twilio_trunk_sid = await asyncio.to_thread(
                ensure_client_subaccount, sb, client_id,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Error creando Twilio subaccount: {e}",
            )

    # Habilitar geo permissions en la cuenta (BYOT o subaccount).
    # Fallo no bloquea la compra — Twilio lo rechazaría con un error claro más adelante.
    try:
        await asyncio.to_thread(
            enable_geo_permission, country,
            account_sid=creds_sid, auth_token=creds_token,
        )
    except Exception as e:
        logger.warning("No se pudieron habilitar geo permissions para %s: %s", country, e)

    # Comprar número en la cuenta resuelta
    try:
        phone_sid, normalized_number = await asyncio.to_thread(
            purchase_phone_number, req.phone_number,
            account_sid=creds_sid, auth_token=creds_token,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error comprando número en Twilio: {e}",
        )

    # Si es subaccount, asociar el número al Elastic SIP Trunk de la subaccount
    if twilio_trunk_sid:
        try:
            await asyncio.to_thread(
                associate_number_to_trunk,
                phone_sid, twilio_trunk_sid,
                account_sid=creds_sid, auth_token=creds_token,
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Número comprado ({normalized_number}) pero falló asociación con trunk Twilio: {e}",
            )

    # Configurar SIP en LiveKit (inbound trunk + dispatch rule)
    try:
        trunk_id, _ = await setup_livekit_sip(normalized_number)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Número comprado ({normalized_number}) pero error configurando SIP en LiveKit: {e}",
        )

    # Guardar en DB
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
    """Crea un nuevo cliente completo (solo admin).

    Flujo:
      1. Valida slug único y owner_email libre
      2. Crea FileSearchStore en Gemini (aislado por cliente)
      3. Inserta fila en clients + agent default + créditos de bienvenida
      4. Crea usuario Supabase Auth + fila en users (si owner_email)
      5. Envía email de bienvenida con credenciales (opt-in)
      6. Dispara webhook client.created + audit log

    Si falla cualquier paso posterior al Gemini store, rollback
    (borra store Gemini + auth user para no dejar recursos huérfanos).
    """
    try:
        voice_id = load_voice_id(req.voice_key)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    sb = get_supabase()

    # 1. Pre-validar slug único (evita 500 de Supabase por UNIQUE constraint)
    existing_slug = (
        sb.table("clients").select("id").eq("slug", req.slug).limit(1).execute()
    )
    if existing_slug.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El slug '{req.slug}' ya está en uso",
        )

    # Pre-validar owner_email no usado en tabla users
    if req.owner_email:
        existing_user = (
            sb.table("users").select("id").eq("email", req.owner_email).limit(1).execute()
        )
        if existing_user.data:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El email '{req.owner_email}' ya está registrado",
            )

    greeting = req.greeting or build_greeting(req.name, req.agent_name)
    system_prompt = req.system_prompt or build_system_prompt(
        req.business_type, req.agent_name, req.name, req.language,
    )

    # 2. Crear FileSearchStore en Gemini
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

    # A partir de aquí, cualquier fallo requiere rollback del store
    client_id: str | None = None
    created_auth_email: str | None = None

    try:
        # 3. Insertar cliente + otorgar créditos de bienvenida
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
        client_id = row["id"]

        # Crear agent default
        voice_config = {
            "provider": "cartesia",
            "voice_id": voice_id,
            "realtime_voice": "alloy",
            "realtime_model": "gpt-4o-realtime-preview",
        }
        sb.table("agents").insert({
            "client_id": client_id,
            "name": req.agent_name,
            "slug": "default",
            "system_prompt": system_prompt,
            "greeting": greeting,
            "voice_config": voice_config,
            "llm_config": {"provider": "google"},
            "stt_config": {"provider": "deepgram"},
        }).execute()

        # 4. Crear usuario Supabase Auth + fila en users
        temp_password: str | None = None
        if req.owner_email:
            temp_password = req.owner_password or generate_temp_password()
            try:
                await asyncio.to_thread(
                    create_owner_user,
                    sb,
                    email=req.owner_email,
                    password=temp_password,
                    client_id=client_id,
                )
                created_auth_email = req.owner_email
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e),
                )

        # 5. Enviar email de bienvenida (opt-in) — no bloquea si falla Resend
        if req.owner_email and req.send_welcome_email and temp_password:
            try:
                await send_welcome_email(
                    to=req.owner_email,
                    client_name=req.name,
                    temp_password=temp_password,
                )
            except Exception:
                logger.exception("Fallo enviando welcome email a %s", req.owner_email)

        # 6. Webhook + audit log — fire-and-forget, no debe impedir la respuesta
        try:
            await dispatch_event(
                client_id=client_id,
                event="client.created",
                payload={
                    "id": client_id,
                    "slug": req.slug,
                    "name": req.name,
                    "owner_email": req.owner_email,
                    "created_at": row.get("created_at"),
                },
            )
        except Exception:
            logger.exception("Fallo despachando webhook client.created")

        log_audit(
            action="client.created",
            user_id=admin.id,
            client_id=client_id,
            resource_type="client",
            resource_id=client_id,
            details={
                "slug": req.slug,
                "name": req.name,
                "owner_email": req.owner_email,
                "user_created": bool(created_auth_email),
                "welcome_email_sent": bool(
                    req.owner_email and req.send_welcome_email
                ),
            },
        )

        return client_out_from_row(row)

    except HTTPException:
        await _rollback_client_creation(sb, client_id, store_id, created_auth_email)
        raise
    except Exception as e:
        await _rollback_client_creation(sb, client_id, store_id, created_auth_email)
        logger.exception("Error inesperado en create_client")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creando cliente: {e}",
        )


async def _rollback_client_creation(
    sb,
    client_id: str | None,
    store_id: str | None,
    owner_email: str | None,
) -> None:
    """Revierte recursos creados durante create_client ante un fallo parcial."""
    # Borrar user de Auth (si se creó)
    if owner_email:
        await asyncio.to_thread(delete_owner_user, owner_email)

    # Borrar agent + client de DB (si se insertaron)
    if client_id:
        try:
            sb.table("agents").delete().eq("client_id", client_id).execute()
            sb.table("clients").delete().eq("id", client_id).execute()
            logger.info("Client %s borrado en rollback", client_id)
        except Exception:
            logger.exception("Error borrando client %s en rollback", client_id)

    # Borrar FileSearchStore en Gemini
    if store_id:
        await asyncio.to_thread(
            delete_gemini_store, store_id, os.environ.get("GOOGLE_API_KEY", "")
        )


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
        "google_calendar_id", "enabled_tools",
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
                vc["api_key"] = encrypt_value(agent_updates["tts_api_key"])
                vc_changed = True
            if "realtime_api_key" in agent_updates:
                vc["realtime_api_key"] = encrypt_value(agent_updates["realtime_api_key"])
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
                lc["api_key"] = encrypt_value(agent_updates["llm_api_key"])
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
                sc["api_key"] = encrypt_value(agent_updates["stt_api_key"])
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
    sb = get_supabase()
    byot_sid, byot_token = get_client_twilio_creds(sb, client_id)

    # Verificar número en Twilio (usa cuenta BYOT si existe)
    try:
        phone_sid = await asyncio.to_thread(
            verify_twilio_number, req.phone_number,
            account_sid=byot_sid, auth_token=byot_token,
        )
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


# ── BYOT (Bring Your Own Twilio) ──────────────────────


@router.put("/{client_id}/twilio-credentials", response_model=ClientOut)
async def save_twilio_credentials(
    client_id: str,
    req: SaveTwilioCredentialsRequest,
    user: CurrentUser = Depends(get_current_user),
) -> ClientOut:
    """Guarda credenciales BYOT de Twilio para un cliente."""
    if user.role == "client" and user.client_id != client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    # Validar credenciales con Twilio
    from api.services.phone_service import validate_twilio_credentials
    valid = await asyncio.to_thread(
        validate_twilio_credentials, req.account_sid, req.auth_token
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credenciales de Twilio inválidas o cuenta inactiva.",
        )

    # Encriptar auth_token y guardar
    sb = get_supabase()
    encrypted_token = encrypt_value(req.auth_token)
    result = (
        sb.table("clients")
        .update({
            "twilio_account_sid": req.account_sid,
            "twilio_auth_token": encrypted_token,
        })
        .eq("id", client_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")

    await log_audit(
        sb, user_id=user.id, action="byot_credentials_saved",
        resource_type="client", resource_id=client_id,
        details={"account_sid": req.account_sid},
    )
    logger.info("BYOT credentials saved for client %s", client_id)
    return client_out_from_row(result.data[0])


@router.delete("/{client_id}/twilio-credentials", response_model=ClientOut)
async def delete_twilio_credentials(
    client_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> ClientOut:
    """Elimina credenciales BYOT de Twilio de un cliente."""
    if user.role == "client" and user.client_id != client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    sb = get_supabase()
    result = (
        sb.table("clients")
        .update({"twilio_account_sid": None, "twilio_auth_token": None})
        .eq("id", client_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")

    await log_audit(
        sb, user_id=user.id, action="byot_credentials_deleted",
        resource_type="client", resource_id=client_id,
    )
    logger.info("BYOT credentials deleted for client %s", client_id)
    return client_out_from_row(result.data[0])


@router.post("/{client_id}/twilio-sip-trunk", response_model=MessageResponse)
async def create_twilio_sip_trunk(
    client_id: str,
    admin: CurrentUser = Depends(require_admin),
) -> MessageResponse:
    """Crea un Elastic SIP Trunk en la cuenta Twilio del cliente apuntando a LiveKit."""
    sb = get_supabase()
    byot_sid, byot_token = get_client_twilio_creds(sb, client_id)
    if not byot_sid or not byot_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El cliente no tiene credenciales BYOT configuradas.",
        )

    from api.services.phone_service import setup_twilio_elastic_sip_trunk
    try:
        trunk_sid = await asyncio.to_thread(
            setup_twilio_elastic_sip_trunk,
            account_sid=byot_sid, auth_token=byot_token,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error creando SIP trunk en cuenta del cliente: {e}",
        )

    await log_audit(
        sb, user_id=admin.id, action="byot_sip_trunk_created",
        resource_type="client", resource_id=client_id,
        details={"twilio_trunk_sid": trunk_sid},
    )
    return MessageResponse(message=f"SIP trunk creado: {trunk_sid}")


@router.post("/{client_id}/create-store", response_model=ClientOut)
async def create_store(
    client_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> ClientOut:
    """Crea (o reintenta) el FileSearchStore de Gemini para un cliente sin store."""
    if user.role == "client" and user.client_id != client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    sb = get_supabase()
    client = sb.table("clients").select("id, slug, file_search_store_id").eq("id", client_id).limit(1).execute()
    if not client.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")

    if client.data[0].get("file_search_store_id"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El cliente ya tiene un FileSearchStore configurado",
        )

    slug = client.data[0]["slug"]
    try:
        store_id, store_name = await asyncio.to_thread(
            create_gemini_store, slug, os.environ["GOOGLE_API_KEY"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error creando FileSearchStore: {e}",
        )

    result = sb.table("clients").update({
        "file_search_store_id": store_id,
        "file_search_store_name": store_name,
    }).eq("id", client_id).execute()

    if not result.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error actualizando cliente")

    logger.info("FileSearchStore creado para cliente %s: %s", client_id, store_id)
    return client_out_from_row(result.data[0])


@router.delete("/{client_id}", response_model=MessageResponse)
async def delete_client(
    client_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> MessageResponse:
    """Elimina un cliente y TODOS sus datos asociados (GDPR Right to Erasure)."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo admin puede eliminar clientes")

    sb = get_supabase()

    # Verify client exists
    client = sb.table("clients").select("id, name").eq("id", client_id).single().execute()
    if not client.data:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    logger.info(
        "GDPR DELETE: Starting cascade delete for client %s (%s)",
        client_id,
        client.data.get("name"),
    )

    # Order matters — delete children before parents
    # Each delete is wrapped in try/except to continue even if table doesn't exist or is empty
    tables_to_clean: list[tuple[str, str | None]] = [
        # Level 4: Deepest children
        ("evaluation_failures", "client_id"),
        ("call_tool_traces", "call_id"),  # Special: needs call_ids first
        ("quality_alerts", "client_id"),
        ("call_evaluations", "client_id"),

        # Level 3: Conversation data
        ("whatsapp_messages", "client_id"),
        ("whatsapp_conversations", "client_id"),
        ("ghl_messages", "client_id"),
        ("ghl_conversations", "client_id"),
        ("conversation_results", "client_id"),

        # Level 2: Agent-related
        ("campaign_calls", None),  # via campaigns
        ("campaigns", "client_id"),
        ("scheduled_actions", "client_id"),
        ("mcp_server_configs", "client_id"),
        ("api_integrations", "client_id"),
        ("webhook_deliveries", None),  # via webhook_endpoints
        ("webhook_endpoints", "client_id"),
        ("api_keys", "client_id"),
        ("whatsapp_configs", "client_id"),
        ("ghl_configs", "client_id"),
        ("cloned_voices", "client_id"),

        # Level 1: Core data
        ("active_calls", "client_id"),
        ("calls", "client_id"),
        ("contact_identifiers", None),  # via contacts CASCADE
        ("contact_memories", None),  # via contacts CASCADE
        ("appointments", "client_id"),
        ("contacts", "client_id"),
        ("documents", "client_id"),
        ("agents", "client_id"),
        ("usage_daily", "client_id"),
        ("billing_transactions", "client_id"),

        # Level 0: Audit (keep for compliance, or delete)
        ("audit_logs", "client_id"),
    ]

    deleted_counts: dict[str, int] = {}
    for table, fk_column in tables_to_clean:
        if not fk_column:
            continue  # Skip tables that cascade automatically
        try:
            result = sb.table(table).delete().eq(fk_column, client_id).execute()
            count = len(result.data) if result.data else 0
            if count > 0:
                deleted_counts[table] = count
                logger.info("GDPR DELETE: %s — %d rows deleted", table, count)
        except Exception as e:
            logger.warning("GDPR DELETE: %s — skipped (%s)", table, str(e)[:100])

    # Finally delete the client itself
    sb.table("clients").delete().eq("id", client_id).execute()

    logger.info(
        "GDPR DELETE: Client %s fully deleted. Tables cleaned: %s",
        client_id,
        deleted_counts,
    )

    total = sum(deleted_counts.values())
    log_audit(
        "client.gdpr_delete",
        user_id=user.id,
        client_id=client_id,
        resource_type="client",
        resource_id=client_id,
        details={"deleted_counts": deleted_counts, "total_rows": total},
    )
    return MessageResponse(
        message=f"Cliente y todos sus datos eliminados ({total} registros)"
    )


@router.post("/{client_id}/request-deletion", response_model=MessageResponse)
async def request_account_deletion(
    client_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> MessageResponse:
    """GDPR: Solicitar eliminación de cuenta.

    Los clientes pueden solicitar la eliminación de su propia cuenta.
    Esto marca la cuenta como pendiente de eliminación y notifica al admin.
    El admin tiene 30 días para procesar la solicitud.
    """
    if user.role == "client" and user.client_id != client_id:
        raise HTTPException(status_code=403, detail="Solo puedes solicitar eliminar tu propia cuenta")

    sb = get_supabase()

    # Marcar cuenta como pending deletion
    sb.table("clients").update({
        "is_active": False,
    }).eq("id", client_id).execute()

    log_audit(
        "client.deletion_requested",
        user_id=user.id,
        client_id=client_id,
        resource_type="client",
        resource_id=client_id,
        details={"requested_by": user.email},
    )

    logger.info("GDPR: Deletion requested for client %s by user %s", client_id, user.id)

    return MessageResponse(
        message="Solicitud de eliminación recibida. Tu cuenta será eliminada en un plazo de 30 días."
    )


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
