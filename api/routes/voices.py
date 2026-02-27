"""Rutas para catálogo de voces."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from api.schemas import VoiceOut

router = APIRouter()

VOICES_FILE = Path(__file__).parent.parent.parent / "config" / "voices.json"


@router.get("", response_model=list[VoiceOut])
async def list_voices() -> list[VoiceOut]:
    """Retorna el catálogo de voces disponibles."""
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
