"""Análisis de sentimiento en tiempo real durante la llamada.

Detecta el estado emocional del usuario turno a turno y permite
al agente reaccionar: cambiar tono, empatizar, o escalar a humano.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Sentimientos posibles (ordenados de peor a mejor)
SENTIMENT_LEVELS = {
    "frustrated": -2,
    "angry": -2,
    "negative": -1,
    "neutral": 0,
    "positive": 1,
    "happy": 2,
}

# Prompt ultra-ligero para clasificación rápida (~50 tokens de entrada extra)
_SENTIMENT_PROMPT = """\
Classify the emotional state of this user message in a phone call. \
Reply with ONLY one word: frustrated, angry, negative, neutral, positive, or happy.

Message: "{text}"
"""

# Directivas emocionales que se inyectan al system prompt según el estado
EMPATHY_DIRECTIVES = {
    "es": {
        "mild": (
            "\n\n## ALERTA: El cliente suena algo molesto\n"
            "- Usa tono más cálido y empático\n"
            "- Reconoce su frustración: 'Entiendo su molestia'\n"
            "- Ofrece soluciones concretas, no excusas\n"
            "- No le pidas que se calme\n"
        ),
        "severe": (
            "\n\n## ALERTA URGENTE: El cliente está muy frustrado\n"
            "- Prioridad absoluta: resolver su problema AHORA\n"
            "- Tono empático máximo: 'Tiene toda la razón, lamento mucho esto'\n"
            "- Ofrece transferir a un supervisor si no puedes resolver\n"
            "- No repitas información que ya diste\n"
            "- Sé breve y directo, no rellenes\n"
        ),
    },
    "en": {
        "mild": (
            "\n\n## ALERT: The customer sounds somewhat upset\n"
            "- Use a warmer, more empathetic tone\n"
            "- Acknowledge their frustration: 'I understand your concern'\n"
            "- Offer concrete solutions, not excuses\n"
            "- Don't ask them to calm down\n"
        ),
        "severe": (
            "\n\n## URGENT ALERT: The customer is very frustrated\n"
            "- Top priority: resolve their issue NOW\n"
            "- Maximum empathy: 'You're absolutely right, I'm very sorry'\n"
            "- Offer to transfer to a supervisor if you can't resolve\n"
            "- Don't repeat information already given\n"
            "- Be brief and direct\n"
        ),
    },
}


@dataclass
class SentimentConfig:
    """Configuración de sentimiento por agente."""

    enabled: bool = False
    escalation_threshold: int = 3
    """Turnos negativos consecutivos para activar escalación."""
    auto_transfer: bool = False
    """Transferir automáticamente al alcanzar el umbral."""
    notify_on_negative: bool = True
    """Loggear alertas cuando el sentimiento es negativo."""

    @classmethod
    def from_dict(cls, data: dict | None) -> SentimentConfig:
        if not data:
            return cls()
        return cls(
            enabled=data.get("enabled", False),
            escalation_threshold=data.get("escalation_threshold", 3),
            auto_transfer=data.get("auto_transfer", False),
            notify_on_negative=data.get("notify_on_negative", True),
        )


@dataclass
class SentimentState:
    """Estado acumulado de sentimiento durante una llamada."""

    history: list[str] = field(default_factory=list)
    """Historial de sentimientos por turno del usuario."""
    consecutive_negative: int = 0
    """Turnos negativos consecutivos."""
    escalation_triggered: bool = False
    """Si ya se activó la escalación."""
    current_directive: str | None = None
    """Directiva emocional activa (mild/severe/None)."""
    analysis_times: list[float] = field(default_factory=list)
    """Tiempos de análisis en ms para monitoreo."""

    @property
    def last_sentiment(self) -> str | None:
        return self.history[-1] if self.history else None

    @property
    def average_score(self) -> float:
        """Score promedio de la llamada (-2 a +2)."""
        if not self.history:
            return 0.0
        scores = [SENTIMENT_LEVELS.get(s, 0) for s in self.history]
        return sum(scores) / len(scores)

    @property
    def timeline(self) -> list[dict]:
        """Timeline de sentimiento para analytics."""
        return [
            {"turn": i + 1, "sentiment": s, "score": SENTIMENT_LEVELS.get(s, 0)}
            for i, s in enumerate(self.history)
        ]


class RealtimeSentimentAnalyzer:
    """Analiza sentimiento del usuario en tiempo real, turno a turno."""

    def __init__(
        self,
        config: SentimentConfig,
        language: str = "es",
    ) -> None:
        self._config = config
        self._language = "es" if language.startswith("es") else "en"
        self._state = SentimentState()
        self._client: genai.Client | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> SentimentState:
        return self._state

    @property
    def config(self) -> SentimentConfig:
        return self._config

    def _get_client(self) -> genai.Client | None:
        """Lazy init del cliente Gemini."""
        if self._client is None:
            api_key = os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                return None
            self._client = genai.Client(api_key=api_key)
        return self._client

    async def analyze_turn(self, user_text: str) -> str:
        """Analiza el sentimiento de un turno del usuario.

        Args:
            user_text: Texto transcrito del usuario.

        Returns:
            Sentimiento detectado (frustrated/angry/negative/neutral/positive/happy).
        """
        if not user_text or len(user_text.strip()) < 3:
            return "neutral"

        start = time.monotonic()

        try:
            sentiment = await asyncio.to_thread(
                self._classify_sync, user_text.strip()
            )
        except Exception:
            logger.warning("Error en análisis de sentimiento, asumiendo neutral")
            sentiment = "neutral"

        elapsed_ms = (time.monotonic() - start) * 1000
        self._state.analysis_times.append(elapsed_ms)

        # Actualizar estado
        async with self._lock:
            self._state.history.append(sentiment)
            score = SENTIMENT_LEVELS.get(sentiment, 0)

            if score < 0:
                self._state.consecutive_negative += 1
            else:
                self._state.consecutive_negative = 0

            # Determinar directiva emocional
            old_directive = self._state.current_directive
            if self._state.consecutive_negative >= self._config.escalation_threshold:
                self._state.current_directive = "severe"
                if not self._state.escalation_triggered:
                    self._state.escalation_triggered = True
                    logger.warning(
                        "Escalación de sentimiento activada: %d turnos negativos consecutivos",
                        self._state.consecutive_negative,
                    )
            elif self._state.consecutive_negative >= 2:
                self._state.current_directive = "mild"
            elif score >= 0:
                self._state.current_directive = None

            if old_directive != self._state.current_directive:
                logger.info(
                    "Directiva emocional cambió: %s -> %s (sentiment=%s, consecutive=%d)",
                    old_directive,
                    self._state.current_directive,
                    sentiment,
                    self._state.consecutive_negative,
                )

        if self._config.notify_on_negative and score < 0:
            logger.info(
                "Sentimiento negativo detectado: '%s' (turno %d, consecutivos: %d)",
                sentiment,
                len(self._state.history),
                self._state.consecutive_negative,
            )

        logger.debug(
            "Sentimiento: %s (%.0fms, turno %d)",
            sentiment,
            elapsed_ms,
            len(self._state.history),
        )

        return sentiment

    def _classify_sync(self, text: str) -> str:
        """Clasificación síncrona con Gemini (se ejecuta en thread)."""
        client = self._get_client()
        if not client:
            return "neutral"

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=_SENTIMENT_PROMPT.format(text=text),
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=5,
            ),
        )

        raw = (response.text or "neutral").strip().lower().rstrip(".")
        # Validar que sea un sentimiento conocido
        if raw not in SENTIMENT_LEVELS:
            # Buscar match parcial
            for known in SENTIMENT_LEVELS:
                if known in raw:
                    return known
            return "neutral"
        return raw

    def get_empathy_directive(self) -> str:
        """Retorna la directiva emocional actual para inyectar al prompt."""
        directive = self._state.current_directive
        if not directive:
            return ""
        directives = EMPATHY_DIRECTIVES.get(self._language, EMPATHY_DIRECTIVES["es"])
        return directives.get(directive, "")

    def should_auto_transfer(self) -> bool:
        """Indica si se debe transferir automáticamente por frustración."""
        return (
            self._config.auto_transfer
            and self._state.escalation_triggered
            and not getattr(self._state, "_transfer_done", False)
        )

    def mark_transfer_done(self) -> None:
        """Marca que ya se realizó la transferencia automática."""
        self._state._transfer_done = True  # type: ignore[attr-defined]

    def get_call_sentiment_summary(self) -> dict:
        """Resumen de sentimiento para guardar con la llamada."""
        return {
            "timeline": self._state.timeline,
            "average_score": round(self._state.average_score, 2),
            "escalation_triggered": self._state.escalation_triggered,
            "consecutive_negative_max": self._count_max_consecutive_negative(),
            "total_turns": len(self._state.history),
            "avg_analysis_ms": (
                round(
                    sum(self._state.analysis_times) / len(self._state.analysis_times),
                    1,
                )
                if self._state.analysis_times
                else 0
            ),
        }

    def _count_max_consecutive_negative(self) -> int:
        """Cuenta el máximo de turnos negativos consecutivos en la historia."""
        max_count = 0
        current = 0
        for s in self._state.history:
            if SENTIMENT_LEVELS.get(s, 0) < 0:
                current += 1
                max_count = max(max_count, current)
            else:
                current = 0
        return max_count
