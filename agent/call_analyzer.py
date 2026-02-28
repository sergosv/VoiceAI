"""Analiza transcripciones de llamadas con Gemini (outbound + universal)."""

from __future__ import annotations

import asyncio
import json
import logging
import os

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Schema para la respuesta estructurada
ANALYSIS_SCHEMA = types.Schema(
    type="OBJECT",
    properties={
        "result": types.Schema(
            type="STRING",
            enum=[
                "demo_agendada",
                "interesado",
                "no_interesado",
                "no_contactar",
                "voicemail",
                "no_answer",
            ],
            description="Clasificación del resultado de la llamada",
        ),
        "confidence": types.Schema(
            type="NUMBER",
            description="Confianza en la clasificación (0.0 a 1.0)",
        ),
        "contact_name": types.Schema(
            type="STRING",
            description="Nombre del contacto si se mencionó",
            nullable=True,
        ),
        "contact_email": types.Schema(
            type="STRING",
            description="Email del contacto si se mencionó",
            nullable=True,
        ),
        "objections": types.Schema(
            type="ARRAY",
            items=types.Schema(type="STRING"),
            description="Objeciones o razones de rechazo mencionadas",
        ),
        "next_step": types.Schema(
            type="STRING",
            description="Siguiente paso recomendado",
            nullable=True,
        ),
        "summary": types.Schema(
            type="STRING",
            description="Resumen conciso de la conversación (2-3 oraciones)",
        ),
        "sentiment": types.Schema(
            type="STRING",
            enum=["positive", "neutral", "negative"],
            description="Sentimiento general del prospecto",
        ),
    },
    required=["result", "confidence", "summary", "sentiment", "objections"],
)

ANALYSIS_PROMPT = """\
Analiza la siguiente transcripción de una llamada de venta outbound y extrae información estructurada.

{script_section}

## Transcripción
{transcript_text}

## Instrucciones
- Clasifica el resultado de la llamada según las opciones disponibles
- Si la conversación tiene menos de 2 turnos reales, clasifica como "no_answer"
- Extrae nombre y email del contacto SOLO si se mencionaron explícitamente
- Lista las objeciones específicas que mencionó el prospecto (array vacío si no hubo)
- El resumen debe ser en español, conciso (2-3 oraciones)
- La confianza debe reflejar qué tan claro fue el resultado
"""


def _build_transcript_text(transcript: list[dict]) -> str:
    """Formatea la transcripción como texto legible."""
    lines: list[str] = []
    for entry in transcript:
        role = entry.get("role", "unknown")
        text = entry.get("text", "")
        if text.strip():
            lines.append(f"{role}: {text}")
    return "\n".join(lines)


def _sync_analyze(transcript_text: str, campaign_script: str | None) -> dict | None:
    """Ejecuta el análisis con Gemini (síncrono)."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("GOOGLE_API_KEY no configurada, saltando análisis")
        return None

    client = genai.Client(api_key=api_key)

    script_section = ""
    if campaign_script:
        script_section = f"## Script de la campaña\n{campaign_script}\n"

    prompt = ANALYSIS_PROMPT.format(
        script_section=script_section,
        transcript_text=transcript_text,
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ANALYSIS_SCHEMA,
            temperature=0.1,
        ),
    )

    return json.loads(response.text)


async def analyze_call_transcript(
    transcript: list[dict],
    campaign_script: str | None = None,
) -> dict | None:
    """Analiza la transcripción de una llamada outbound con Gemini.

    Returns:
        Dict con análisis estructurado o None si falla.
    """
    if not transcript or len(transcript) < 2:
        logger.info("Transcripción muy corta, saltando análisis")
        return None

    transcript_text = _build_transcript_text(transcript)
    if not transcript_text.strip():
        return None

    try:
        result = await asyncio.to_thread(
            _sync_analyze, transcript_text, campaign_script
        )
        logger.info("Análisis de llamada completado: result=%s", result.get("result") if result else None)
        return result
    except Exception:
        logger.exception("Error analizando transcripción de llamada")
        return None


# ── Análisis universal (inbound + outbound) ─────────────────────

UNIVERSAL_SCHEMA = types.Schema(
    type="OBJECT",
    properties={
        "sentimiento": types.Schema(
            type="STRING",
            enum=["positivo", "neutral", "negativo"],
            description="Sentimiento general del interlocutor",
        ),
        "intencion_detectada": types.Schema(
            type="STRING",
            enum=[
                "agendar_cita", "consulta_info", "queja", "cancelar",
                "cotizacion", "seguimiento", "otro",
            ],
            description="Intención principal de la llamada",
        ),
        "datos_capturados": types.Schema(
            type="OBJECT",
            properties={
                "nombre": types.Schema(type="STRING", nullable=True),
                "email": types.Schema(type="STRING", nullable=True),
                "servicio_interes": types.Schema(type="STRING", nullable=True),
            },
            description="Datos del contacto capturados durante la llamada",
        ),
        "preguntas_sin_respuesta": types.Schema(
            type="ARRAY",
            items=types.Schema(type="STRING"),
            description="Preguntas que el agente no pudo responder",
        ),
        "calificacion_lead": types.Schema(
            type="INTEGER",
            description="Calificación del lead de 0 a 100",
        ),
        "siguiente_accion": types.Schema(
            type="STRING",
            enum=["seguimiento", "enviar_info", "agendar_cita", "ninguna"],
            description="Acción recomendada después de la llamada",
        ),
        "resumen": types.Schema(
            type="STRING",
            description="Resumen conciso en español (2-3 oraciones)",
        ),
        "cita_agendada": types.Schema(
            type="BOOLEAN",
            description="Si se agendó una cita durante la llamada",
        ),
    },
    required=[
        "sentimiento", "intencion_detectada", "calificacion_lead",
        "siguiente_accion", "resumen", "cita_agendada", "preguntas_sin_respuesta",
    ],
)

UNIVERSAL_PROMPT = """\
Analiza la siguiente transcripción de una llamada telefónica {direction} \
y extrae información estructurada.

{business_section}

## Transcripción
{transcript_text}

## Instrucciones
- Determina el sentimiento general del interlocutor (positivo/neutral/negativo)
- Identifica la intención principal de la llamada
- Extrae datos del contacto SOLO si se mencionaron explícitamente
- Lista preguntas que el agente no pudo responder (array vacío si respondió todo)
- Califica el lead de 0 a 100 (0=no interesado, 100=listo para comprar/agendar)
- Recomienda la siguiente acción
- El resumen debe ser en español, conciso (2-3 oraciones)
- Indica si se agendó una cita durante la llamada
"""


def _sync_analyze_universal(
    transcript_text: str,
    direction: str,
    business_type: str | None,
) -> dict | None:
    """Ejecuta análisis universal con Gemini (síncrono)."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("GOOGLE_API_KEY no configurada, saltando análisis universal")
        return None

    client = genai.Client(api_key=api_key)

    business_section = ""
    if business_type:
        business_section = f"## Tipo de negocio\n{business_type}\n"

    direction_label = "entrante (inbound)" if direction == "inbound" else "saliente (outbound)"
    prompt = UNIVERSAL_PROMPT.format(
        direction=direction_label,
        business_section=business_section,
        transcript_text=transcript_text,
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=UNIVERSAL_SCHEMA,
            temperature=0.1,
        ),
    )

    return json.loads(response.text)


async def analyze_call_universal(
    transcript: list[dict],
    direction: str,
    business_type: str | None = None,
) -> dict | None:
    """Analiza cualquier llamada (inbound/outbound) con Gemini.

    Returns:
        Dict con análisis estructurado o None si falla.
    """
    if not transcript or len(transcript) < 2:
        logger.info("Transcripción muy corta, saltando análisis universal")
        return None

    transcript_text = _build_transcript_text(transcript)
    if not transcript_text.strip():
        return None

    try:
        result = await asyncio.to_thread(
            _sync_analyze_universal, transcript_text, direction, business_type
        )
        logger.info(
            "Análisis universal completado: sentimiento=%s, lead=%s",
            result.get("sentimiento") if result else None,
            result.get("calificacion_lead") if result else None,
        )
        return result
    except Exception:
        logger.exception("Error en análisis universal de llamada")
        return None
