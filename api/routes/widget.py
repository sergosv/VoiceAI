"""API pública para el web widget embeddable.

Estos endpoints NO requieren auth — son públicos para que el widget
funcione en sitios web de terceros.
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.deps import get_supabase

router = APIRouter()
logger = logging.getLogger("widget")
limiter = Limiter(key_func=get_remote_address)


@router.get("/config/{agent_slug}")
@limiter.limit("60/minute")
async def widget_config(request: Request, agent_slug: str) -> dict:
    """Retorna config pública del agente para el widget (sin datos sensibles)."""
    sb = get_supabase()

    # Buscar agente por slug (activo)
    result = (
        sb.table("agents")
        .select("id, name, slug, greeting, client_id, widget_channels")
        .eq("slug", agent_slug)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")

    agent = result.data[0]

    # Verificar que el cliente está activo
    client_result = (
        sb.table("clients")
        .select("id, name, slug, language")
        .eq("id", agent["client_id"])
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not client_result.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client not found")

    client = client_result.data[0]

    channels = agent.get("widget_channels") or ["voice"]

    return {
        "agent_id": agent["id"],
        "agent_name": agent["name"],
        "agent_slug": agent["slug"],
        "greeting": agent["greeting"],
        "client_name": client["name"],
        "language": client["language"],
        "livekit_url": os.environ.get("LIVEKIT_URL", ""),
        "widget_channels": channels,
    }


@router.post("/token/{agent_slug}")
@limiter.limit("20/minute")
async def widget_token(request: Request, agent_slug: str) -> dict:
    """Genera un token LiveKit temporal para conectar al widget."""
    from livekit.api import AccessToken, VideoGrants

    sb = get_supabase()

    # Verificar agente y cliente
    result = (
        sb.table("agents")
        .select("id, client_id")
        .eq("slug", agent_slug)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")

    agent = result.data[0]

    # Verificar cliente activo
    client_result = (
        sb.table("clients")
        .select("id")
        .eq("id", agent["client_id"])
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not client_result.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client not found")

    # Generar room name y token
    import uuid

    from livekit.api import LiveKitAPI
    from livekit.api.room_service import CreateRoomRequest

    room_name = f"widget-{uuid.uuid4().hex[:8]}"

    api_key = os.environ.get("LIVEKIT_API_KEY")
    api_secret = os.environ.get("LIVEKIT_API_SECRET")
    livekit_url = os.environ.get("LIVEKIT_URL", "")
    if not api_key or not api_secret:
        raise HTTPException(500, "LiveKit not configured")

    # Crear room + despachar agente explícitamente
    room_metadata = f'{{"agent_id": "{agent["id"]}", "type": "widget"}}'
    try:
        from livekit.api import CreateAgentDispatchRequest

        async with LiveKitAPI(
            url=livekit_url, api_key=api_key, api_secret=api_secret,
        ) as lk_api:
            await lk_api.room.create_room(
                CreateRoomRequest(name=room_name, metadata=room_metadata)
            )
            # Dispatch explícito — la dispatch rule por prefix no basta
            await lk_api.agent_dispatch.create_dispatch(
                CreateAgentDispatchRequest(
                    room=room_name,
                    agent_name="voice-ai-platform",
                    metadata=room_metadata,
                )
            )
            logger.info("Widget room + dispatch created: %s (agent_id=%s)", room_name, agent["id"])
    except Exception as e:
        logger.error("Could not create room/dispatch: %s", e)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Could not create room")

    from datetime import timedelta

    token = (
        AccessToken(api_key, api_secret)
        .with_identity(f"widget-user-{uuid.uuid4().hex[:6]}")
        .with_name("Web Visitor")
        .with_ttl(timedelta(minutes=10))
        .with_grants(
            VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            )
        )
        .with_metadata(room_metadata)
        .to_jwt()
    )

    return {
        "token": token,
        "room": room_name,
        "url": livekit_url,
    }


# ── Chat widget (texto) ──────────────────────────────────────


class WidgetChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str = ""


class WidgetChatResponse(BaseModel):
    conversation_id: str
    text: str
    agent_name: str = ""


@router.post("/chat/{agent_slug}", response_model=WidgetChatResponse)
@limiter.limit("30/minute")
async def widget_chat(
    request: Request,
    agent_slug: str,
    req: WidgetChatRequest,
) -> WidgetChatResponse:
    """Endpoint público de chat para el widget embeddable. Sin auth."""
    from agent.config_loader import load_api_integrations, load_config_by_slug, load_mcp_servers
    from agent.hook_engine import HookEngine, load_hooks_for_agent
    from api.services.chat_service import build_chat_system_prompt, chat_turn, init_flow_state
    from api.services.chat_store import MAX_TURNS, create_conversation, get_conversation

    if req.conversation_id:
        # ── Continuar conversación ──
        conv = get_conversation(req.conversation_id)
        if not conv:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversación expirada")
        if conv.turn_count >= MAX_TURNS:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Límite de mensajes alcanzado")

        api_integrations = await load_api_integrations(
            conv.config.client.id, conv.config.agent.id
        )
        mcp_servers = await load_mcp_servers(
            conv.config.client.id, conv.config.agent.id
        )
        hook_defs = await load_hooks_for_agent(conv.config.agent.id)
        _hook_engine = HookEngine(hook_defs) if hook_defs else None

        text, _ = await chat_turn(
            conv, req.message,
            api_integrations=api_integrations,
            mcp_servers=mcp_servers or None,
            hook_engine=_hook_engine,
            hook_channel="widget",
        )
        return WidgetChatResponse(
            conversation_id=conv.id,
            text=text,
            agent_name=conv.config.agent.name,
        )

    # ── Nueva conversación ──
    config = await load_config_by_slug(agent_slug)
    if not config:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agente no encontrado")

    # Verificar que chat está habilitado
    channels = config.agent.widget_channels or ["voice"]
    if "chat" not in channels:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Chat no habilitado para este agente")

    api_integrations = await load_api_integrations(config.client.id, config.agent.id)
    mcp_servers = await load_mcp_servers(config.client.id, config.agent.id)

    system_prompt = build_chat_system_prompt(
        config, None, None,
        api_integrations=api_integrations,
        mcp_servers=mcp_servers or None,
    )
    conv = create_conversation(config, system_prompt)
    init_flow_state(conv)

    # Si no hay mensaje, devolver greeting
    if not req.message:
        greeting = config.agent.greeting or f"Hola, soy {config.agent.name}. ¿En qué puedo ayudarte?"
        return WidgetChatResponse(
            conversation_id=conv.id,
            text=greeting,
            agent_name=config.agent.name,
        )

    hook_defs = await load_hooks_for_agent(config.agent.id)
    _hook_engine = HookEngine(hook_defs) if hook_defs else None

    text, _ = await chat_turn(
        conv, req.message,
        api_integrations=api_integrations,
        mcp_servers=mcp_servers or None,
        hook_engine=_hook_engine,
        hook_channel="widget",
    )
    return WidgetChatResponse(
        conversation_id=conv.id,
        text=text,
        agent_name=config.agent.name,
    )
