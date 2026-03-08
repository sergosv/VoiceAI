"""Servicio de clonación de voces — Cartesia + ElevenLabs."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# API base URLs
CARTESIA_API_URL = "https://api.cartesia.ai"
CARTESIA_API_VERSION = "2025-04-16"
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"


def _get_cartesia_key() -> str:
    """Obtiene la API key de Cartesia desde env."""
    key = os.getenv("CARTESIA_API_KEY", "")
    if not key:
        raise ValueError("CARTESIA_API_KEY no configurada")
    return key


async def clone_voice_cartesia(
    audio_data: bytes,
    name: str,
    language: str = "es",
    description: str = "",
    api_key: str | None = None,
) -> dict[str, Any]:
    """Clona una voz usando Cartesia Instant Clone.

    Returns:
        Dict con 'id', 'name', 'language', 'description' de la voz creada.
    """
    key = api_key or _get_cartesia_key()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{CARTESIA_API_URL}/voices/clone",
            headers={
                "X-API-Key": key,
                "Cartesia-Version": CARTESIA_API_VERSION,
            },
            data={
                "name": name,
                "language": language,
                "description": description,
            },
            files={"clip": ("voice_sample.wav", audio_data, "audio/wav")},
        )

        if resp.status_code != 200:
            error_text = resp.text[:300]
            logger.error("Cartesia clone error %d: %s", resp.status_code, error_text)
            raise RuntimeError(f"Error clonando voz en Cartesia: {error_text}")

        result = resp.json()
        logger.info(
            "Voz clonada en Cartesia: id=%s name=%s",
            result.get("id"),
            result.get("name"),
        )
        return result


async def clone_voice_elevenlabs(
    audio_data: bytes,
    name: str,
    description: str = "",
    api_key: str | None = None,
) -> dict[str, Any]:
    """Clona una voz usando ElevenLabs Instant Clone.

    Returns:
        Dict con 'voice_id', 'name' de la voz creada.
    """
    key = api_key or os.getenv("ELEVENLABS_API_KEY", "")
    if not key:
        raise ValueError("API key de ElevenLabs requerida")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{ELEVENLABS_API_URL}/voices/add",
            headers={"xi-api-key": key},
            data={
                "name": name,
                "description": description,
            },
            files={"files": ("voice_sample.wav", audio_data, "audio/wav")},
        )

        if resp.status_code != 200:
            error_text = resp.text[:300]
            logger.error("ElevenLabs clone error %d: %s", resp.status_code, error_text)
            raise RuntimeError(f"Error clonando voz en ElevenLabs: {error_text}")

        result = resp.json()
        logger.info(
            "Voz clonada en ElevenLabs: id=%s",
            result.get("voice_id"),
        )
        return result


async def delete_voice_cartesia(
    voice_id: str,
    api_key: str | None = None,
) -> bool:
    """Elimina una voz clonada de Cartesia."""
    key = api_key or _get_cartesia_key()

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.delete(
            f"{CARTESIA_API_URL}/voices/{voice_id}",
            headers={
                "X-API-Key": key,
                "Cartesia-Version": CARTESIA_API_VERSION,
            },
        )

        if resp.status_code in (200, 204):
            logger.info("Voz eliminada de Cartesia: %s", voice_id)
            return True

        logger.error(
            "Error eliminando voz de Cartesia %s: %d %s",
            voice_id, resp.status_code, resp.text[:200],
        )
        return False


async def delete_voice_elevenlabs(
    voice_id: str,
    api_key: str | None = None,
) -> bool:
    """Elimina una voz clonada de ElevenLabs."""
    key = api_key or os.getenv("ELEVENLABS_API_KEY", "")
    if not key:
        raise ValueError("API key de ElevenLabs requerida")

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.delete(
            f"{ELEVENLABS_API_URL}/voices/{voice_id}",
            headers={"xi-api-key": key},
        )

        if resp.status_code in (200, 204):
            logger.info("Voz eliminada de ElevenLabs: %s", voice_id)
            return True

        logger.error(
            "Error eliminando voz de ElevenLabs %s: %d %s",
            voice_id, resp.status_code, resp.text[:200],
        )
        return False


async def preview_voice_cartesia(
    voice_id: str,
    text: str = "Hola, esta es mi voz clonada. ¿Cómo suena?",
    language: str = "es",
    api_key: str | None = None,
) -> bytes:
    """Genera audio de preview con una voz clonada en Cartesia.

    Returns:
        Bytes del audio WAV generado.
    """
    key = api_key or _get_cartesia_key()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{CARTESIA_API_URL}/tts/bytes",
            headers={
                "X-API-Key": key,
                "Cartesia-Version": CARTESIA_API_VERSION,
                "Content-Type": "application/json",
            },
            json={
                "model_id": "sonic-3",
                "transcript": text,
                "voice": {"mode": "id", "id": voice_id},
                "language": language,
                "output_format": {
                    "container": "wav",
                    "encoding": "pcm_s16le",
                    "sample_rate": 24000,
                },
            },
        )

        if resp.status_code != 200:
            error_text = resp.text[:300]
            logger.error("Cartesia TTS preview error %d: %s", resp.status_code, error_text)
            raise RuntimeError(f"Error generando preview: {error_text}")

        return resp.content
