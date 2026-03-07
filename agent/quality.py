"""Quality scoring para llamadas reales.

Evalúa la calidad de cada llamada post-hoc usando Gemini,
generando un score 0-100 y detectando gaps de conocimiento.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

QUALITY_SCHEMA = types.Schema(
    type="OBJECT",
    properties={
        "quality_score": types.Schema(
            type="INTEGER",
            description="Score de calidad de 0 a 100",
        ),
        "resolution_achieved": types.Schema(
            type="BOOLEAN",
            description="Si el problema/consulta del usuario fue resuelto",
        ),
        "unanswered_questions": types.Schema(
            type="ARRAY",
            items=types.Schema(type="STRING"),
            description="Preguntas del usuario que el agente no pudo responder",
        ),
        "knowledge_gaps": types.Schema(
            type="ARRAY",
            items=types.Schema(type="STRING"),
            description="Temas sobre los que el agente no tiene información suficiente",
        ),
        "adherence_issues": types.Schema(
            type="ARRAY",
            items=types.Schema(type="STRING"),
            description="Problemas de adherencia al script/instrucciones",
        ),
        "strengths": types.Schema(
            type="ARRAY",
            items=types.Schema(type="STRING"),
            description="Aspectos positivos de la conversación",
        ),
        "improvement_suggestions": types.Schema(
            type="ARRAY",
            items=types.Schema(type="STRING"),
            description="Sugerencias de mejora",
        ),
    },
    required=["quality_score", "resolution_achieved", "unanswered_questions", "knowledge_gaps"],
)

_QUALITY_PROMPT = """\
Evalúa la calidad de esta llamada telefónica de un agente de IA.

{business_section}
## Transcripción
{transcript_text}

## Criterios de evaluación
- Resolución: ¿Se resolvió la consulta/problema del usuario? (0-30 pts)
- Conocimiento: ¿El agente tenía la información necesaria? (0-25 pts)
- Naturalidad: ¿La conversación fue natural y empática? (0-20 pts)
- Eficiencia: ¿Se manejó en un tiempo razonable? (0-15 pts)
- Adherencia: ¿Siguió las instrucciones/script? (0-10 pts)

Evalúa de forma estricta pero justa. Una llamada perfecta es 90+, buena 70-89, regular 50-69, mala <50.
"""


@dataclass
class QualityConfig:
    """Configuración de quality scoring por agente."""

    enabled: bool = False
    min_score_alert: int = 50
    """Score mínimo antes de generar alerta."""
    score_criteria: dict | None = None
    """Criterios custom de evaluación."""

    @classmethod
    def from_dict(cls, data: dict | None) -> QualityConfig:
        if not data:
            return cls()
        return cls(
            enabled=data.get("enabled", False),
            min_score_alert=data.get("min_score_alert", 50),
            score_criteria=data.get("score_criteria"),
        )


def _build_transcript_text(transcript: list[dict]) -> str:
    """Formatea la transcripción como texto legible."""
    lines: list[str] = []
    for entry in transcript:
        role = entry.get("role", "unknown")
        text = entry.get("text", "")
        if text.strip():
            lines.append(f"{role}: {text}")
    return "\n".join(lines)


def _sync_score(
    transcript_text: str,
    business_type: str | None,
) -> dict | None:
    """Ejecuta el quality scoring con Gemini (síncrono)."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None

    client = genai.Client(api_key=api_key)

    business_section = ""
    if business_type:
        business_section = f"## Tipo de negocio\n{business_type}\n"

    prompt = _QUALITY_PROMPT.format(
        business_section=business_section,
        transcript_text=transcript_text,
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=QUALITY_SCHEMA,
            temperature=0.1,
        ),
    )

    return json.loads(response.text)


async def score_call_quality(
    transcript: list[dict],
    business_type: str | None = None,
) -> dict | None:
    """Evalúa la calidad de una llamada real.

    Returns:
        Dict con quality_score, knowledge_gaps, unanswered_questions, etc.
    """
    if not transcript or len(transcript) < 2:
        return None

    transcript_text = _build_transcript_text(transcript)
    if not transcript_text.strip():
        return None

    try:
        result = await asyncio.to_thread(
            _sync_score, transcript_text, business_type
        )
        if result:
            logger.info(
                "Quality score: %d (resolution=%s, gaps=%d)",
                result.get("quality_score", 0),
                result.get("resolution_achieved"),
                len(result.get("knowledge_gaps", [])),
            )
        return result
    except Exception:
        logger.exception("Error en quality scoring")
        return None
