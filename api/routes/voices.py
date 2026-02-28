"""Rutas para catálogo de voces."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_supabase
from api.middleware.auth import CurrentUser, get_current_user
from api.schemas import VoiceOut

logger = logging.getLogger(__name__)
router = APIRouter()

VOICES_FILE = Path(__file__).parent.parent.parent / "config" / "voices.json"

# Voces fijas de OpenAI TTS
OPENAI_TTS_VOICES = [
    {"id": "alloy", "name": "Alloy", "gender": "neutral", "description": "Neutral, balanceada"},
    {"id": "echo", "name": "Echo", "gender": "male", "description": "Resonante, profunda"},
    {"id": "fable", "name": "Fable", "gender": "neutral", "description": "Expresiva, narrativa"},
    {"id": "onyx", "name": "Onyx", "gender": "male", "description": "Profunda, autoritativa"},
    {"id": "nova", "name": "Nova", "gender": "female", "description": "Energetica, amigable"},
    {"id": "shimmer", "name": "Shimmer", "gender": "female", "description": "Brillante, optimista"},
]


@router.get("", response_model=list[VoiceOut])
async def list_voices() -> list[VoiceOut]:
    """Retorna el catálogo de voces Cartesia disponibles."""
    with open(VOICES_FILE) as f:
        data = json.load(f)

    return [
        VoiceOut(
            key=key,
            id=v["id"],
            name=v["name"],
            language=v["language"],
            gender=v["gender"],
            description=v["description"],
        )
        for key, v in data["voices"].items()
    ]


@router.get("/provider/{client_id}", response_model=list[VoiceOut])
async def list_provider_voices(
    client_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> list[VoiceOut]:
    """Retorna voces según el TTS provider del cliente."""
    if user.role == "client" and user.client_id != client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    sb = get_supabase()
    result = (
        sb.table("clients")
        .select("tts_provider, tts_api_key")
        .eq("id", client_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")

    client = result.data[0]
    provider = client.get("tts_provider", "cartesia")
    api_key = client.get("tts_api_key")

    if provider == "elevenlabs":
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="API key de ElevenLabs requerida para listar voces",
            )
        return await _fetch_elevenlabs_voices(api_key)

    if provider == "openai":
        return [
            VoiceOut(key=v["id"], id=v["id"], name=v["name"], language="multi",
                     gender=v["gender"], description=v["description"])
            for v in OPENAI_TTS_VOICES
        ]

    # Cartesia / Google: devolver voces del catálogo
    return await list_voices()


async def _fetch_elevenlabs_voices(api_key: str) -> list[VoiceOut]:
    """Consulta la API de ElevenLabs para obtener las voces del usuario."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.elevenlabs.io/v1/voices",
                headers={"xi-api-key": api_key},
            )
            resp.raise_for_status()
            data = resp.json()

        voices = []
        for v in data.get("voices", []):
            labels = v.get("labels", {})
            gender = labels.get("gender", "unknown")
            accent = labels.get("accent", "")
            lang = "es" if "spanish" in accent.lower() or "mexican" in accent.lower() else "multi"
            desc = labels.get("description", "") or labels.get("use_case", "") or v.get("category", "")

            voices.append(VoiceOut(
                key=v["voice_id"],
                id=v["voice_id"],
                name=v["name"],
                language=lang,
                gender=gender,
                description=desc[:80] if desc else f"{gender} voice",
            ))

        return voices
    except httpx.HTTPStatusError as e:
        logger.error("ElevenLabs API error: %s", e.response.text[:200])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Error consultando voces de ElevenLabs. Verifica tu API key.",
        )
    except Exception as e:
        logger.error("Error fetching ElevenLabs voices: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error consultando ElevenLabs: {e}",
        )
