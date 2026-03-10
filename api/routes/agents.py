"""Rutas CRUD de agentes (sub-recurso de clients)."""

from __future__ import annotations

import asyncio
import re

from fastapi import APIRouter, Depends, HTTPException, status

from api.crypto import encrypt_value
from api.deps import get_supabase
from api.middleware.auth import CurrentUser, get_current_user, require_admin
from api.schemas import (
    AgentCreateRequest,
    AgentOut,
    AgentUpdateRequest,
    AssignPhoneRequest,
    FlowValidationResult,
    MessageResponse,
    PurchaseNumberRequest,
    agent_out_from_row,
)
from api.services.client_service import build_greeting, build_system_prompt, load_voice_id
from api.services.phone_service import (
    assign_phone_to_agent,
    purchase_phone_number,
    setup_livekit_sip,
    verify_twilio_number,
)

router = APIRouter()

# Prefijos válidos por provider para validación de API keys
_PROVIDER_KEY_HINTS: dict[str, tuple[str, str]] = {
    "cartesia": ("sk_car_", "Cartesia inician con 'sk_car_'"),
    "openai": ("sk-", "OpenAI inician con 'sk-'"),
    "elevenlabs": ("", "ElevenLabs"),
}


def _validate_provider_key(provider: str, api_key: str | None) -> None:
    """Valida formato de API key vs provider. Lanza HTTPException si no coincide."""
    if not api_key or provider not in _PROVIDER_KEY_HINTS:
        return
    prefix, hint = _PROVIDER_KEY_HINTS[provider]
    if not api_key.startswith(prefix):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"La API key no corresponde al provider {provider}. "
                f"Keys de {hint}."
            ),
        )
    # Extra: descartar keys de Cartesia pasadas como ElevenLabs
    if provider == "elevenlabs" and api_key.startswith("sk_car_"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La API key parece ser de Cartesia, no de ElevenLabs.",
        )


def _check_client_access(user: CurrentUser, client_id: str) -> None:
    """Verifica que el usuario tenga acceso al cliente."""
    if user.role == "client" and user.client_id != client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")


def _slugify(name: str) -> str:
    """Genera un slug desde un nombre."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "-", slug)
    return slug[:50] or "agent"


@router.get("/{client_id}/agents", response_model=list[AgentOut])
async def list_agents(
    client_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> list[AgentOut]:
    """Lista agentes de un cliente."""
    _check_client_access(user, client_id)

    sb = get_supabase()
    result = (
        sb.table("agents")
        .select("*")
        .eq("client_id", client_id)
        .order("created_at")
        .execute()
    )
    return [agent_out_from_row(row) for row in result.data]


@router.post("/{client_id}/agents", response_model=AgentOut, status_code=201)
async def create_agent(
    client_id: str,
    req: AgentCreateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> AgentOut:
    """Crea un nuevo agente para un cliente."""
    _check_client_access(user, client_id)

    sb = get_supabase()

    # Verificar que el cliente existe
    client = sb.table("clients").select("name, business_type, language").eq("id", client_id).limit(1).execute()
    if not client.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")

    c = client.data[0]

    # Resolver voice_id
    try:
        voice_id = load_voice_id(req.voice_key)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Auto-slug
    slug = req.slug or _slugify(req.name)

    # Generar prompt/greeting si no vienen
    greeting = req.greeting or build_greeting(c["name"], req.name)
    system_prompt = req.system_prompt or build_system_prompt(
        c.get("business_type", "generic"), req.name, c["name"], c.get("language", "es"),
    )

    # Validar formato de API keys vs provider
    _validate_provider_key(req.tts_provider, req.tts_api_key)
    _validate_provider_key(req.llm_provider, req.llm_api_key)
    _validate_provider_key(req.stt_provider, req.stt_api_key)

    # Construir JSONB configs
    voice_config = {
        "provider": req.tts_provider,
        "voice_id": voice_id,
        "realtime_voice": req.realtime_voice,
        "realtime_model": req.realtime_model,
    }
    if req.tts_api_key:
        voice_config["api_key"] = encrypt_value(req.tts_api_key)
    if req.realtime_api_key:
        voice_config["realtime_api_key"] = encrypt_value(req.realtime_api_key)

    llm_config: dict = {"provider": req.llm_provider}
    if req.llm_api_key:
        llm_config["api_key"] = encrypt_value(req.llm_api_key)

    stt_config: dict = {"provider": req.stt_provider}
    if req.stt_api_key:
        stt_config["api_key"] = encrypt_value(req.stt_api_key)

    data = {
        "client_id": client_id,
        "name": req.name,
        "slug": slug,
        "system_prompt": system_prompt,
        "greeting": greeting,
        "examples": req.examples,
        "voice_config": voice_config,
        "llm_config": llm_config,
        "stt_config": stt_config,
        "agent_mode": req.agent_mode,
        "agent_type": req.agent_type,
        "transfer_number": req.transfer_number,
        "after_hours_message": req.after_hours_message,
        "max_call_duration_seconds": req.max_call_duration_seconds,
        "role_description": req.role_description,
        "orchestrator_enabled": req.orchestrator_enabled,
        "orchestrator_priority": req.orchestrator_priority,
        "conversation_mode": req.conversation_mode,
        "conversation_flow": req.conversation_flow,
        "mode_config": req.mode_config or {},
    }

    result = sb.table("agents").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creando agente")
    return agent_out_from_row(result.data[0])


@router.get("/{client_id}/agents/{agent_id}", response_model=AgentOut)
async def get_agent(
    client_id: str,
    agent_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> AgentOut:
    """Obtiene un agente por ID."""
    _check_client_access(user, client_id)

    sb = get_supabase()
    result = (
        sb.table("agents")
        .select("*")
        .eq("id", agent_id)
        .eq("client_id", client_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente no encontrado")
    return agent_out_from_row(result.data[0])


@router.patch("/{client_id}/agents/{agent_id}", response_model=AgentOut)
async def update_agent(
    client_id: str,
    agent_id: str,
    req: AgentUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> AgentOut:
    """Actualiza un agente."""
    _check_client_access(user, client_id)

    sb = get_supabase()

    # Leer agente actual
    existing = (
        sb.table("agents")
        .select("*")
        .eq("id", agent_id)
        .eq("client_id", client_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente no encontrado")

    agent_row = existing.data[0]
    updates: dict = {}
    req_data = req.model_dump(exclude_none=True)

    # Campos directos del agente
    direct_fields = {
        "name", "system_prompt", "greeting", "examples", "agent_mode", "agent_type",
        "transfer_number", "after_hours_message", "max_call_duration_seconds", "is_active",
        "role_description", "orchestrator_enabled", "orchestrator_priority",
        "conversation_mode", "conversation_flow", "mode_config",
    }
    for f in direct_fields:
        if f in req_data:
            updates[f] = req_data[f]

    # Actualizar voice_config
    voice_config = dict(agent_row.get("voice_config") or {})
    voice_changed = False
    if req.voice_id is not None:
        voice_config["voice_id"] = req.voice_id
        voice_changed = True
    if req.tts_provider is not None:
        # Si cambia el provider, limpiar la api_key vieja (no aplica al nuevo provider)
        old_provider = voice_config.get("provider")
        voice_config["provider"] = req.tts_provider
        if old_provider and old_provider != req.tts_provider:
            voice_config.pop("api_key", None)
        voice_changed = True
    if req.tts_api_key is not None:
        voice_config["api_key"] = req.tts_api_key
        voice_changed = True
    if req.realtime_api_key is not None:
        voice_config["realtime_api_key"] = req.realtime_api_key
        voice_changed = True
    if req.realtime_voice is not None:
        voice_config["realtime_voice"] = req.realtime_voice
        voice_changed = True
    if req.realtime_model is not None:
        voice_config["realtime_model"] = req.realtime_model
        voice_changed = True
    if voice_changed:
        updates["voice_config"] = voice_config

    # Actualizar llm_config
    llm_config = dict(agent_row.get("llm_config") or {})
    llm_changed = False
    if req.llm_provider is not None:
        old_provider = llm_config.get("provider")
        llm_config["provider"] = req.llm_provider
        if old_provider and old_provider != req.llm_provider:
            llm_config.pop("api_key", None)
        llm_changed = True
    if req.llm_api_key is not None:
        llm_config["api_key"] = req.llm_api_key
        llm_changed = True
    if llm_changed:
        updates["llm_config"] = llm_config

    # Actualizar stt_config
    stt_config = dict(agent_row.get("stt_config") or {})
    stt_changed = False
    if req.stt_provider is not None:
        old_provider = stt_config.get("provider")
        stt_config["provider"] = req.stt_provider
        if old_provider and old_provider != req.stt_provider:
            stt_config.pop("api_key", None)
        stt_changed = True
    if req.stt_api_key is not None:
        stt_config["api_key"] = req.stt_api_key
        stt_changed = True
    if stt_changed:
        updates["stt_config"] = stt_config

    # Validar formato de API keys vs provider en configs actualizados
    # Solo validar keys nuevas (no encriptadas) — las existentes ya fueron validadas al crearlas
    if voice_changed and voice_config.get("api_key") and not voice_config["api_key"].startswith("enc:"):
        _validate_provider_key(voice_config.get("provider", ""), voice_config["api_key"])
    if llm_changed and llm_config.get("api_key") and not llm_config["api_key"].startswith("enc:"):
        _validate_provider_key(llm_config.get("provider", ""), llm_config["api_key"])
    if stt_changed and stt_config.get("api_key") and not stt_config["api_key"].startswith("enc:"):
        _validate_provider_key(stt_config.get("provider", ""), stt_config["api_key"])

    # Encrypt API keys before persisting (skip already-encrypted values)
    if "voice_config" in updates:
        vc = updates["voice_config"]
        if vc.get("api_key") and not vc["api_key"].startswith("enc:"):
            vc["api_key"] = encrypt_value(vc["api_key"])
        if vc.get("realtime_api_key") and not vc["realtime_api_key"].startswith("enc:"):
            vc["realtime_api_key"] = encrypt_value(vc["realtime_api_key"])
    if "llm_config" in updates:
        lc = updates["llm_config"]
        if lc.get("api_key") and not lc["api_key"].startswith("enc:"):
            lc["api_key"] = encrypt_value(lc["api_key"])
    if "stt_config" in updates:
        sc = updates["stt_config"]
        if sc.get("api_key") and not sc["api_key"].startswith("enc:"):
            sc["api_key"] = encrypt_value(sc["api_key"])

    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sin cambios")

    result = sb.table("agents").update(updates).eq("id", agent_id).eq("client_id", client_id).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente no encontrado")
    return agent_out_from_row(result.data[0])


@router.delete("/{client_id}/agents/{agent_id}", response_model=MessageResponse)
async def delete_agent(
    client_id: str,
    agent_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> MessageResponse:
    """Elimina un agente (no permite eliminar el último)."""
    _check_client_access(user, client_id)

    sb = get_supabase()

    # Verificar que no sea el último agente
    count = (
        sb.table("agents")
        .select("id", count="exact")
        .eq("client_id", client_id)
        .execute()
    )
    if (count.count or 0) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar el último agente del cliente",
        )

    result = sb.table("agents").delete().eq("id", agent_id).eq("client_id", client_id).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente no encontrado")
    return MessageResponse(message="Agente eliminado")


@router.post("/{client_id}/agents/{agent_id}/assign-phone", response_model=AgentOut)
async def assign_agent_phone(
    client_id: str,
    agent_id: str,
    req: AssignPhoneRequest,
    admin: CurrentUser = Depends(require_admin),
) -> AgentOut:
    """Asigna un número de teléfono Twilio a un agente (solo admin)."""
    try:
        phone_sid = await asyncio.to_thread(verify_twilio_number, req.phone_number)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error verificando número en Twilio: {e}",
        )

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
    row = assign_phone_to_agent(
        sb,
        agent_id=agent_id,
        phone_number=req.phone_number,
        phone_sid=phone_sid,
        trunk_id=trunk_id,
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente no encontrado")
    return agent_out_from_row(row)


@router.post("/{client_id}/agents/{agent_id}/validate-flow", response_model=FlowValidationResult)
async def validate_flow(
    client_id: str,
    agent_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> FlowValidationResult:
    """Valida el flujo de conversación de un agente."""
    _check_client_access(user, client_id)

    sb = get_supabase()
    result = (
        sb.table("agents")
        .select("conversation_flow")
        .eq("id", agent_id)
        .eq("client_id", client_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente no encontrado")

    flow_json = result.data[0].get("conversation_flow")
    if not flow_json:
        return FlowValidationResult(
            valid=False,
            errors=["No hay flujo configurado"],
            node_count=0,
            edge_count=0,
        )

    from agent.flow_engine import FlowEngine
    valid, errors, warnings = FlowEngine.validate_flow(flow_json)
    nodes = flow_json.get("nodes", [])
    edges = flow_json.get("edges", [])
    return FlowValidationResult(
        valid=valid,
        errors=errors,
        warnings=warnings,
        node_count=len(nodes),
        edge_count=len(edges),
    )


@router.post("/{client_id}/agents/{agent_id}/purchase-phone", response_model=AgentOut)
async def purchase_agent_phone(
    client_id: str,
    agent_id: str,
    req: PurchaseNumberRequest,
    admin: CurrentUser = Depends(require_admin),
) -> AgentOut:
    """Compra un número en Twilio y lo asigna a un agente (solo admin)."""
    try:
        phone_sid, normalized_number = await asyncio.to_thread(
            purchase_phone_number, req.phone_number
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error comprando número en Twilio: {e}",
        )

    try:
        trunk_id, _ = await setup_livekit_sip(normalized_number)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Número comprado ({normalized_number}) pero error configurando SIP: {e}",
        )

    sb = get_supabase()
    row = assign_phone_to_agent(
        sb,
        agent_id=agent_id,
        phone_number=normalized_number,
        phone_sid=phone_sid,
        trunk_id=trunk_id,
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente no encontrado")
    return agent_out_from_row(row)
