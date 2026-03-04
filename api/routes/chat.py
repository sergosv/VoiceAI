"""Rutas del chat tester para probar agentes via texto."""

from __future__ import annotations

import logging
from dataclasses import replace

from fastapi import APIRouter, Depends, HTTPException, status

from agent.config_loader import load_api_integrations, load_config_by_agent_id
from api.middleware.auth import CurrentUser, get_current_user
from api.schemas import ChatMessageRequest, ChatMessageResponse, ChatResetResponse
from api.services.chat_service import build_chat_system_prompt, chat_turn, init_flow_state
from api.services.chat_store import (
    MAX_TURNS,
    create_conversation,
    delete_conversation,
    get_conversation,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/agents/{agent_id}/chat", response_model=ChatMessageResponse)
async def chat_with_agent(
    agent_id: str,
    req: ChatMessageRequest,
    user: CurrentUser = Depends(get_current_user),
) -> ChatMessageResponse:
    """Envía un mensaje al chat tester de un agente."""

    if req.conversation_id:
        # ── Continuar conversación existente ──
        conv = get_conversation(req.conversation_id)
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversación no encontrada o expirada",
            )
        # Verificar acceso
        if user.role == "client" and conv.client_id != user.client_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")
        if conv.turn_count >= MAX_TURNS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Límite de {MAX_TURNS} turnos alcanzado. Reinicia la conversación.",
            )

        # Cargar API integrations para este agente
        api_integrations = await load_api_integrations(
            conv.config.client.id, conv.config.agent.id
        )

        text, tool_calls = await chat_turn(conv, req.message, api_integrations=api_integrations)
        return ChatMessageResponse(
            conversation_id=conv.id,
            text=text,
            tool_calls=tool_calls,
        )

    # ── Nueva conversación ──
    config = await load_config_by_agent_id(agent_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agente no encontrado",
        )
    # Verificar acceso
    if user.role == "client" and config.client.id != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    # Cargar API integrations
    api_integrations = await load_api_integrations(config.client.id, config.agent.id)

    # Si viene flow_override, inyectar el flujo del editor en la config (frozen dataclass)
    if req.flow_override and req.flow_override.get("nodes"):
        new_agent = replace(config.agent, conversation_flow=req.flow_override, conversation_mode="flow")
        config = replace(config, agent=new_agent)

    system_prompt = build_chat_system_prompt(
        config, req.contact_name, req.campaign_script,
        api_integrations=api_integrations,
    )
    conv = create_conversation(config, system_prompt, req.contact_name)

    # Inicializar flow state si es flow mode
    init_flow_state(conv)

    # Si no hay mensaje o es greeting, devolver el saludo del agente
    if not req.message or req.message == "__greeting__":
        # En flow mode, usar greeting del nodo Start
        if (
            config.agent.conversation_mode == "flow"
            and hasattr(conv, "_flow_engine")
            and hasattr(conv, "_flow_state")
        ):
            greeting = conv._flow_engine.get_greeting(conv._flow_state)
        else:
            greeting = config.agent.greeting
        if not greeting:
            greeting = f"Hola, soy {config.agent.name}. ¿En qué puedo ayudarte?"
        return ChatMessageResponse(
            conversation_id=conv.id,
            text=greeting,
            tool_calls=[],
        )

    # Mensaje inicial con contenido
    text, tool_calls = await chat_turn(conv, req.message, api_integrations=api_integrations)
    return ChatMessageResponse(
        conversation_id=conv.id,
        text=text,
        tool_calls=tool_calls,
    )


@router.delete("/agents/{agent_id}/chat/{conversation_id}", response_model=ChatResetResponse)
async def reset_chat(
    agent_id: str,
    conversation_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> ChatResetResponse:
    """Elimina una conversación de chat tester."""
    conv = get_conversation(conversation_id)
    if conv:
        if user.role == "client" and conv.client_id != user.client_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")
    delete_conversation(conversation_id)
    return ChatResetResponse(message="Conversación reiniciada")
