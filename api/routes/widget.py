"""API pública para el web widget embeddable.

Estos endpoints NO requieren auth — son públicos para que el widget
funcione en sitios web de terceros.
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException, Request, status
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
        .select("id, name, slug, greeting, client_id")
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

    return {
        "agent_id": agent["id"],
        "agent_name": agent["name"],
        "agent_slug": agent["slug"],
        "greeting": agent["greeting"],
        "client_name": client["name"],
        "language": client["language"],
        "livekit_url": os.environ.get("LIVEKIT_URL", ""),
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

    room_name = f"widget-{uuid.uuid4().hex[:8]}"

    api_key = os.environ.get("LIVEKIT_API_KEY")
    api_secret = os.environ.get("LIVEKIT_API_SECRET")
    if not api_key or not api_secret:
        raise HTTPException(500, "LiveKit not configured")

    token = (
        AccessToken(api_key, api_secret)
        .with_identity(f"widget-user-{uuid.uuid4().hex[:6]}")
        .with_name("Web Visitor")
        .with_grants(
            VideoGrants(
                room_join=True,
                room=room_name,
            )
        )
        .with_metadata(f'{{"agent_id": "{agent["id"]}", "type": "widget"}}')
        .to_jwt()
    )

    return {
        "token": token,
        "room": room_name,
        "url": os.environ.get("LIVEKIT_URL", ""),
    }
