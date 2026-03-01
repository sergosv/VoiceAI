"""Constantes y helpers para calidad de voz humana."""

from __future__ import annotations

import random

# ── Filler phrases (mientras el LLM piensa) ──────────────

FILLER_PHRASES = {
    "es": [
        "Déjeme ver...",
        "Un momento...",
        "Ajá, claro...",
        "Ok, déjeme checar...",
        "Mire...",
        "A ver...",
        "Sí, un segundo...",
    ],
    "en": [
        "Let me check...",
        "One moment...",
        "Sure, let me see...",
        "Right...",
        "Ok, let me look into that...",
    ],
}

# ── Backchannels (escucha activa mientras el usuario habla) ──

BACKCHANNELS = {
    "es": ["Mjm", "Ajá", "Sí", "Claro", "Ok", "Entiendo"],
    "en": ["Mhm", "Uh-huh", "Right", "I see", "Ok", "Sure"],
}

# ── Timing constants ─────────────────────────────────────

FILLER_DELAY_SECONDS = 1.2
"""Segundos a esperar antes de reproducir un filler. Si el LLM responde antes, no se reproduce."""

BACKCHANNEL_FIRST_DELAY = 4.0
"""Segundos de habla continua del usuario antes del primer backchannel."""

BACKCHANNEL_INTERVAL = 5.5
"""Segundos entre backchannels subsiguientes."""


def random_filler(language: str) -> str:
    """Retorna un filler phrase aleatorio para el idioma dado."""
    lang = "es" if language.startswith("es") else "en"
    return random.choice(FILLER_PHRASES[lang])


def random_backchannel(language: str) -> str:
    """Retorna un backchannel aleatorio para el idioma dado."""
    lang = "es" if language.startswith("es") else "en"
    return random.choice(BACKCHANNELS[lang])
