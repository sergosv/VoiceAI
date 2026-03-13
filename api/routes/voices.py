"""Rutas para catálogo de voces y clonación."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response

from api.crypto import decrypt_value
from api.deps import get_supabase
from api.middleware.auth import CurrentUser, get_current_user
from api.schemas import ClonedVoiceOut, VoiceOut
from api.services.voice_cloning import (
    clone_voice_cartesia,
    clone_voice_elevenlabs,
    delete_voice_cartesia,
    delete_voice_elevenlabs,
    preview_voice_cartesia,
)

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
    agent_id: str | None = None,
    provider: str | None = Query(None, description="Override del provider TTS"),
    user: CurrentUser = Depends(get_current_user),
) -> list[VoiceOut]:
    """Retorna voces según el TTS provider del agente o cliente."""
    if user.role == "client" and user.client_id != client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    sb = get_supabase()

    # Si el frontend manda provider explícito, usarlo directamente
    api_key = None
    if not provider:
        provider = "cartesia"
        if agent_id:
            agent_result = (
                sb.table("agents").select("voice_config").eq("id", agent_id).limit(1).execute()
            )
            if agent_result.data:
                vc = agent_result.data[0].get("voice_config") or {}
                provider = vc.get("provider", "cartesia")
                api_key = decrypt_value(vc.get("api_key"))

        if not agent_id or not provider:
            result = (
                sb.table("clients")
                .select("tts_provider, tts_api_key")
                .eq("id", client_id)
                .limit(1)
                .execute()
            )
            if not result.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado"
                )
            client = result.data[0]
            provider = client.get("tts_provider", "cartesia")
            api_key = decrypt_value(client.get("tts_api_key"))
    else:
        # Con provider override, aún necesitamos la API key del agente
        if agent_id:
            agent_result = (
                sb.table("agents").select("voice_config").eq("id", agent_id).limit(1).execute()
            )
            if agent_result.data:
                vc = agent_result.data[0].get("voice_config") or {}
                api_key = decrypt_value(vc.get("api_key"))

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


# ── Clonación de voces ────────────────────────────────────

# Límites de audio
MAX_AUDIO_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_CONTENT_TYPES = {
    "audio/wav", "audio/x-wav", "audio/wave",
    "audio/mpeg", "audio/mp3", "audio/mp4",
    "audio/ogg", "audio/webm", "audio/flac",
}

# Magic bytes para validar formato real del archivo
_AUDIO_MAGIC = {
    b"RIFF": "WAV",        # WAV (RIFF header)
    b"\xff\xfb": "MP3",    # MP3 (frame sync)
    b"\xff\xf3": "MP3",    # MP3 MPEG2 Layer3
    b"\xff\xf2": "MP3",    # MP3 MPEG2.5 Layer3
    b"ID3": "MP3",         # MP3 con ID3 tag
    b"OggS": "OGG",        # OGG container
    b"fLaC": "FLAC",       # FLAC
    b"\x1aE\xdf\xa3": "WEBM",  # WebM/Matroska
}


def _validate_audio_magic(data: bytes) -> str | None:
    """Valida los magic bytes del archivo y retorna el formato detectado o None."""
    for magic, fmt in _AUDIO_MAGIC.items():
        if data[:len(magic)] == magic:
            return fmt
    # MP4/M4A: buscar "ftyp" en bytes 4-8
    if len(data) >= 8 and data[4:8] == b"ftyp":
        return "MP4"
    return None


@router.post("/clone", response_model=ClonedVoiceOut, status_code=status.HTTP_201_CREATED)
async def clone_voice(
    audio: UploadFile = File(..., description="Audio para clonar (WAV/MP3, 5-30s)"),
    name: str = Form(..., min_length=1, max_length=100),
    client_id: str = Form(...),
    agent_id: str | None = Form(None),
    language: str = Form("es"),
    description: str = Form(""),
    provider: str = Form("cartesia"),
    user: CurrentUser = Depends(get_current_user),
) -> ClonedVoiceOut:
    """Clona una voz a partir de un audio subido por el cliente."""
    # Verificar permisos
    if user.role == "client" and user.client_id != client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    # Validar content type (primera capa)
    content_type = audio.content_type or ""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato de audio no soportado: {content_type}. Usa WAV, MP3, OGG o FLAC.",
        )

    # Leer audio con límite de tamaño (sin cargar todo el archivo en memoria)
    audio_data = await audio.read(MAX_AUDIO_SIZE + 1)
    if len(audio_data) > MAX_AUDIO_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Audio file too large. Max {MAX_AUDIO_SIZE // (1024 * 1024)}MB",
        )

    if len(audio_data) < 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio demasiado corto. Se necesitan al menos 3 segundos.",
        )

    # Validar magic bytes (segunda capa — anti-spoofing de Content-Type)
    detected_format = _validate_audio_magic(audio_data)
    if not detected_format:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo no es un audio válido. Los headers del archivo no corresponden a WAV, MP3, OGG, FLAC o WebM.",
        )

    # La clonación siempre usa las keys de la plataforma (env vars).
    # Las keys BYOK del agente son para TTS en llamadas, no para clonar.
    api_key = None
    sb = get_supabase()

    # Clonar según provider
    try:
        if provider == "elevenlabs":
            result = await clone_voice_elevenlabs(
                audio_data=audio_data,
                name=name,
                description=description,
                api_key=api_key,
            )
            external_id = result.get("voice_id", "")
        else:
            result = await clone_voice_cartesia(
                audio_data=audio_data,
                name=name,
                language=language,
                description=description,
                api_key=api_key,
            )
            external_id = result.get("id", "")

        if not external_id:
            raise RuntimeError("No se recibió ID de voz del provider")

    except Exception as e:
        logger.error("Error en clonación de voz: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error clonando voz: {e}",
        )

    # Guardar en DB
    insert_data = {
        "client_id": client_id,
        "agent_id": agent_id,
        "provider": provider,
        "external_voice_id": external_id,
        "name": name,
        "language": language,
        "description": description,
        "status": "ready",
        "metadata": result,
    }

    res = sb.table("cloned_voices").insert(insert_data).execute()
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error guardando voz clonada en DB",
        )

    row = res.data[0]
    return ClonedVoiceOut(
        id=row["id"],
        client_id=row["client_id"],
        agent_id=row.get("agent_id"),
        provider=row["provider"],
        external_voice_id=row["external_voice_id"],
        name=row["name"],
        language=row["language"],
        description=row.get("description", ""),
        duration_seconds=row.get("duration_seconds"),
        status=row["status"],
        created_at=row.get("created_at"),
    )


@router.get("/cloned/{client_id}", response_model=list[ClonedVoiceOut])
async def list_cloned_voices(
    client_id: str,
    provider: str | None = Query(None),
    user: CurrentUser = Depends(get_current_user),
) -> list[ClonedVoiceOut]:
    """Lista las voces clonadas de un cliente."""
    if user.role == "client" and user.client_id != client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    sb = get_supabase()
    query = sb.table("cloned_voices").select("*").eq("client_id", client_id)
    if provider:
        query = query.eq("provider", provider)
    query = query.order("created_at", desc=True).limit(500)

    result = query.execute()
    return [
        ClonedVoiceOut(
            id=r["id"],
            client_id=r["client_id"],
            agent_id=r.get("agent_id"),
            provider=r["provider"],
            external_voice_id=r["external_voice_id"],
            name=r["name"],
            language=r["language"],
            description=r.get("description", ""),
            duration_seconds=r.get("duration_seconds"),
            status=r["status"],
            created_at=r.get("created_at"),
        )
        for r in result.data
    ]


@router.delete("/cloned/{voice_id}")
async def delete_cloned_voice(
    voice_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    """Elimina una voz clonada del provider y de la DB."""
    sb = get_supabase()

    # Buscar la voz
    res = sb.table("cloned_voices").select("*").eq("id", voice_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voz clonada no encontrada")

    voice = res.data[0]

    # Verificar permisos
    if user.role == "client" and user.client_id != voice["client_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    # Eliminar del provider (usa keys de plataforma, no BYOK)
    external_id = voice["external_voice_id"]
    provider = voice["provider"]
    try:
        if provider == "elevenlabs":
            await delete_voice_elevenlabs(external_id)
        else:
            await delete_voice_cartesia(external_id)
    except Exception as e:
        logger.warning("No se pudo eliminar voz %s del provider: %s", external_id, e)

    # Eliminar de DB
    sb.table("cloned_voices").delete().eq("id", voice_id).execute()

    return {"status": "deleted", "voice_id": voice_id}


@router.post("/cloned/{voice_id}/preview")
async def preview_cloned_voice(
    voice_id: str,
    text: str = Query("Hola, esta es mi voz clonada. ¿Cómo suena?", max_length=200),
    user: CurrentUser = Depends(get_current_user),
) -> Response:
    """Genera un audio de preview con la voz clonada."""
    sb = get_supabase()

    res = sb.table("cloned_voices").select("*").eq("id", voice_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voz no encontrada")

    voice = res.data[0]

    if user.role == "client" and user.client_id != voice["client_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    if voice["provider"] != "cartesia":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Preview solo disponible para voces Cartesia",
        )

    try:
        audio_bytes = await preview_voice_cartesia(
            voice_id=voice["external_voice_id"],
            text=text,
            language=voice.get("language", "es"),
        )
    except Exception as e:
        logger.error("Error generando preview: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error generando preview: {e}",
        )

    return Response(content=audio_bytes, media_type="audio/wav")


@router.post("/cloned/{voice_id}/assign")
async def assign_cloned_voice_to_agent(
    voice_id: str,
    agent_id: str = Query(...),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    """Asigna una voz clonada a un agente (actualiza voice_config del agente)."""
    sb = get_supabase()

    # Buscar voz clonada
    res = sb.table("cloned_voices").select("*").eq("id", voice_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voz no encontrada")

    voice = res.data[0]

    if user.role == "client" and user.client_id != voice["client_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    # Leer voice_config actual del agente
    agent_res = (
        sb.table("agents").select("voice_config, client_id").eq("id", agent_id).limit(1).execute()
    )
    if not agent_res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente no encontrado")

    agent = agent_res.data[0]

    # Verificar que el agente pertenece al mismo cliente
    if agent["client_id"] != voice["client_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La voz y el agente deben pertenecer al mismo cliente",
        )

    # Actualizar voice_config del agente con el voice_id clonado
    vc = agent.get("voice_config") or {}
    vc["voice_id"] = voice["external_voice_id"]
    vc["provider"] = voice["provider"]
    vc["cloned_voice_id"] = voice["id"]  # Referencia interna

    sb.table("agents").update({"voice_config": vc}).eq("id", agent_id).execute()

    # Vincular la voz clonada al agente
    sb.table("cloned_voices").update({"agent_id": agent_id}).eq("id", voice_id).execute()

    return {
        "status": "assigned",
        "agent_id": agent_id,
        "voice_id": voice_id,
        "external_voice_id": voice["external_voice_id"],
    }
