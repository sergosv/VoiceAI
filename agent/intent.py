"""Extracción de intención del usuario en tiempo real.

Clasifica el intent del usuario en cada turno para analytics,
triggers de flows/tools, y detección de gaps de conocimiento.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Intents por defecto (el negocio puede customizar)
DEFAULT_INTENTS = [
    "agendar_cita",
    "consulta_precio",
    "consulta_horario",
    "consulta_servicio",
    "queja",
    "cancelar",
    "seguimiento",
    "cotizacion",
    "soporte_tecnico",
    "saludo",
    "despedida",
    "otro",
]

_INTENT_PROMPT = """\
Classify the user's intent in this phone call message. \
Reply with ONLY the intent name, nothing else.

Available intents: {intents}

Message: "{text}"
"""


@dataclass
class IntentConfig:
    """Configuración de intent extraction por agente."""

    enabled: bool = False
    custom_intents: list[str] | None = None
    """Lista custom de intents. Si None, usa DEFAULT_INTENTS."""
    track_unresolved: bool = True
    """Si loggear preguntas que el agente no pudo resolver."""

    @classmethod
    def from_dict(cls, data: dict | None) -> IntentConfig:
        if not data:
            return cls()
        return cls(
            enabled=data.get("enabled", False),
            custom_intents=data.get("custom_intents"),
            track_unresolved=data.get("track_unresolved", True),
        )

    @property
    def intents(self) -> list[str]:
        return self.custom_intents or DEFAULT_INTENTS


@dataclass
class IntentState:
    """Estado acumulado de intents durante una llamada."""

    history: list[dict] = field(default_factory=list)
    """Historial: [{turn, intent, text_preview}]"""
    intent_counts: dict[str, int] = field(default_factory=dict)
    """Conteo de cada intent detectado."""
    primary_intent: str | None = None
    """Intent principal de la llamada (el más frecuente excluyendo saludo/despedida)."""

    def update_primary(self) -> None:
        """Recalcula el intent principal."""
        filtered = {
            k: v for k, v in self.intent_counts.items()
            if k not in ("saludo", "despedida", "otro")
        }
        if filtered:
            self.primary_intent = max(filtered, key=filtered.get)  # type: ignore[arg-type]


class RealtimeIntentExtractor:
    """Extrae el intent del usuario turno a turno."""

    def __init__(
        self,
        config: IntentConfig,
    ) -> None:
        self._config = config
        self._state = IntentState()
        self._client: genai.Client | None = None
        self._intents_str = ", ".join(config.intents)

    @property
    def state(self) -> IntentState:
        return self._state

    @property
    def config(self) -> IntentConfig:
        return self._config

    def _get_client(self) -> genai.Client | None:
        if self._client is None:
            api_key = os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                return None
            self._client = genai.Client(api_key=api_key)
        return self._client

    async def extract_intent(self, user_text: str) -> str:
        """Extrae el intent de un turno del usuario.

        Returns:
            Intent detectado (uno de la lista configurada, o "otro").
        """
        if not user_text or len(user_text.strip()) < 3:
            return "otro"

        try:
            intent = await asyncio.to_thread(
                self._classify_sync, user_text.strip()
            )
        except Exception:
            logger.warning("Error extrayendo intent, asumiendo 'otro'")
            intent = "otro"

        # Actualizar estado
        turn = len(self._state.history) + 1
        self._state.history.append({
            "turn": turn,
            "intent": intent,
            "text_preview": user_text[:80],
        })
        self._state.intent_counts[intent] = self._state.intent_counts.get(intent, 0) + 1
        self._state.update_primary()

        logger.debug("Intent turno %d: %s", turn, intent)
        return intent

    def _classify_sync(self, text: str) -> str:
        """Clasificación síncrona con Gemini."""
        client = self._get_client()
        if not client:
            return "otro"

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=_INTENT_PROMPT.format(
                intents=self._intents_str,
                text=text,
            ),
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=10,
            ),
        )

        raw = (response.text or "otro").strip().lower().rstrip(".")
        # Validar que sea un intent conocido
        if raw in self._config.intents:
            return raw
        # Buscar match parcial
        for known in self._config.intents:
            if known in raw:
                return known
        return "otro"

    def get_call_intent_summary(self) -> dict:
        """Resumen de intents para guardar con la llamada."""
        return {
            "history": self._state.history,
            "intent_counts": self._state.intent_counts,
            "primary_intent": self._state.primary_intent,
            "total_turns": len(self._state.history),
        }
