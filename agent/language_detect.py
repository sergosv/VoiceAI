"""Detección dinámica de idioma del caller.

Analiza los primeros turnos del usuario para detectar su idioma
y adaptar STT/TTS/prompt automáticamente.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Mapeo de idiomas a configs de STT/TTS
LANGUAGE_CONFIGS = {
    "es": {"stt_lang": "es", "tts_lang": "es", "label": "Español"},
    "en": {"stt_lang": "en", "tts_lang": "en", "label": "English"},
    "pt": {"stt_lang": "pt-BR", "tts_lang": "pt-BR", "label": "Português"},
    "fr": {"stt_lang": "fr", "tts_lang": "fr", "label": "Français"},
}

_DETECT_PROMPT = """\
Detect the language of this phone call message. \
Reply with ONLY the ISO 639-1 code (es, en, pt, fr, etc.).

Message: "{text}"
"""


@dataclass
class LanguageDetectionConfig:
    """Configuración de detección de idioma por agente."""

    enabled: bool = False
    supported_languages: list[str] = field(default_factory=lambda: ["es", "en"])
    """Idiomas soportados (ISO 639-1)."""
    detection_turns: int = 2
    """Turnos a analizar antes de decidir el idioma."""
    prompts_by_language: dict[str, str] | None = None
    """System prompt override por idioma."""

    @classmethod
    def from_dict(cls, data: dict | None) -> LanguageDetectionConfig:
        if not data:
            return cls()
        return cls(
            enabled=data.get("enabled", False),
            supported_languages=data.get("supported_languages", ["es", "en"]),
            detection_turns=data.get("detection_turns", 2),
            prompts_by_language=data.get("prompts_by_language"),
        )


@dataclass
class LanguageState:
    """Estado de detección de idioma durante la llamada."""

    detections: list[str] = field(default_factory=list)
    """Idioma detectado por turno."""
    decided: bool = False
    """Si ya se tomó la decisión de idioma."""
    detected_language: str | None = None
    """Idioma final detectado."""
    switched: bool = False
    """Si se realizó un switch de idioma."""


class LanguageDetector:
    """Detecta el idioma del caller y señala cuándo hacer switch."""

    def __init__(
        self,
        config: LanguageDetectionConfig,
        default_language: str = "es",
    ) -> None:
        self._config = config
        self._default_language = default_language
        self._state = LanguageState()
        self._client: genai.Client | None = None

    @property
    def state(self) -> LanguageState:
        return self._state

    def _get_client(self) -> genai.Client | None:
        if self._client is None:
            api_key = os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                return None
            self._client = genai.Client(api_key=api_key)
        return self._client

    async def detect_turn(self, user_text: str) -> str | None:
        """Detecta el idioma de un turno del usuario.

        Returns:
            Idioma detectado si ya se decidió (trigger switch), None si aún analizando.
        """
        if self._state.decided:
            return None  # Ya decidido, no más detecciones

        if not user_text or len(user_text.strip()) < 5:
            return None

        try:
            lang = await asyncio.to_thread(self._detect_sync, user_text.strip())
        except Exception:
            logger.warning("Error detectando idioma, asumiendo default")
            lang = self._default_language

        self._state.detections.append(lang)

        # Esperar N turnos antes de decidir
        if len(self._state.detections) >= self._config.detection_turns:
            return self._decide()

        return None

    def _decide(self) -> str | None:
        """Decide el idioma final basado en las detecciones."""
        self._state.decided = True

        # Votar por mayoría
        counts: dict[str, int] = {}
        for lang in self._state.detections:
            counts[lang] = counts.get(lang, 0) + 1

        winner = max(counts, key=counts.get)  # type: ignore[arg-type]

        # Solo switchear si es un idioma soportado Y diferente al default
        if winner in self._config.supported_languages:
            self._state.detected_language = winner
            if winner != self._default_language:
                self._state.switched = True
                logger.info(
                    "Idioma detectado: %s (switch desde %s)",
                    winner,
                    self._default_language,
                )
                return winner
            else:
                logger.info("Idioma detectado: %s (mismo que default)", winner)
                return None
        else:
            self._state.detected_language = self._default_language
            logger.info(
                "Idioma detectado '%s' no soportado, manteniendo %s",
                winner,
                self._default_language,
            )
            return None

    def _detect_sync(self, text: str) -> str:
        """Detección síncrona con Gemini."""
        client = self._get_client()
        if not client:
            return self._default_language

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=_DETECT_PROMPT.format(text=text),
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=5,
            ),
        )

        raw = (response.text or self._default_language).strip().lower().rstrip(".")
        # Validar: debe ser código ISO 639-1 (2 chars)
        clean = re.sub(r"[^a-z]", "", raw)[:2]
        if len(clean) == 2:
            return clean
        return self._default_language

    def get_language_prompt_override(self) -> str | None:
        """Retorna el prompt override para el idioma detectado, si existe."""
        if not self._state.detected_language or not self._config.prompts_by_language:
            return None
        return self._config.prompts_by_language.get(self._state.detected_language)

    def get_summary(self) -> dict:
        """Resumen de detección de idioma para la llamada."""
        return {
            "detections": self._state.detections,
            "detected_language": self._state.detected_language,
            "switched": self._state.switched,
            "default_language": self._default_language,
        }
