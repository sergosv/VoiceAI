"""Generador de insights cross-call para agentes.

Analiza transcripts de llamadas recientes para detectar:
- Preguntas frecuentes (FAQs)
- Temas recurrentes
- Puntos de frustración
- Sugerencias de mejora al system prompt
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Mínimo de llamadas para generar insights
MIN_CALLS_FOR_ANALYSIS = 5
# Ventana de análisis en días
ANALYSIS_WINDOW_DAYS = 7


async def generate_insights_for_agent(
    agent_id: str,
    client_id: str,
    force: bool = False,
) -> list[dict]:
    """Genera insights analizando las llamadas recientes de un agente.

    Args:
        agent_id: UUID del agente.
        client_id: UUID del cliente.
        force: Si True, genera aunque ya haya insights recientes.

    Returns:
        Lista de insights generados.
    """
    from api.deps import get_supabase

    sb = get_supabase()
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=ANALYSIS_WINDOW_DAYS)

    # Verificar si ya hay insights recientes (evitar re-análisis)
    if not force:
        recent = (
            sb.table("agent_insights")
            .select("id")
            .eq("agent_id", agent_id)
            .gte("created_at", (now - timedelta(hours=24)).isoformat())
            .limit(1)
            .execute()
        )
        if recent.data:
            logger.info("Insights recientes encontrados para %s, saltando", agent_id)
            return []

    # Cargar transcripts recientes
    calls = (
        sb.table("calls")
        .select("id, transcript, duration_seconds, status, quality_score, sentiment_realtime, created_at")
        .eq("agent_id", agent_id)
        .eq("status", "completed")
        .gte("created_at", window_start.isoformat())
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )

    if not calls.data or len(calls.data) < MIN_CALLS_FOR_ANALYSIS:
        logger.info(
            "Insuficientes llamadas para insights (%d/%d) — agente %s",
            len(calls.data or []), MIN_CALLS_FOR_ANALYSIS, agent_id,
        )
        return []

    # Preparar datos para el LLM
    transcripts_summary = _prepare_transcripts(calls.data)

    # Llamar a Gemini para análisis
    insights_raw = await _analyze_with_llm(transcripts_summary, len(calls.data))
    if not insights_raw:
        return []

    # Guardar insights en DB
    saved = []
    for insight in insights_raw:
        try:
            row = {
                "client_id": client_id,
                "agent_id": agent_id,
                "insight_type": insight.get("type", "faq"),
                "title": insight.get("title", ""),
                "description": insight.get("description", ""),
                "evidence": insight.get("evidence", {}),
                "suggested_response": insight.get("suggested_response"),
                "suggested_prompt_addition": insight.get("suggested_prompt_addition"),
                "frequency": insight.get("frequency", 1),
                "confidence": insight.get("confidence", 0.5),
                "analyzed_from": window_start.isoformat(),
                "analyzed_to": now.isoformat(),
                "calls_analyzed": len(calls.data),
            }
            result = sb.table("agent_insights").insert(row).execute()
            if result.data:
                saved.append(result.data[0])
        except Exception:
            logger.exception("Error guardando insight: %s", insight.get("title"))

    logger.info("Generados %d insights para agente %s", len(saved), agent_id)
    return saved


def _prepare_transcripts(calls: list[dict]) -> str:
    """Prepara un resumen de transcripts para el LLM."""
    summaries = []
    for call in calls[:30]:  # Limitar para no exceder contexto
        transcript = call.get("transcript") or []
        if not transcript:
            continue

        # Extraer solo mensajes del usuario (las preguntas)
        user_messages = [t["text"] for t in transcript if t.get("role") == "user"]
        agent_messages = [t["text"] for t in transcript if t.get("role") == "assistant"]

        duration = call.get("duration_seconds", 0)
        quality = call.get("quality_score")
        sentiment = call.get("sentiment_realtime", {})

        summary = f"--- Llamada ({duration}s"
        if quality:
            summary += f", calidad: {quality}/100"
        if sentiment and sentiment.get("overall"):
            summary += f", sentimiento: {sentiment['overall']}"
        summary += ") ---\n"
        summary += f"Usuario preguntó: {' | '.join(user_messages[:5])}\n"
        if agent_messages:
            summary += f"Agente respondió (resumen): {agent_messages[0][:100]}...\n"

        summaries.append(summary)

    return "\n".join(summaries)


async def _analyze_with_llm(transcripts_summary: str, call_count: int) -> list[dict]:
    """Usa Gemini para analizar los transcripts y generar insights."""
    try:
        from google import genai

        client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

        prompt = f"""Analiza estos {call_count} transcripts de llamadas de un agente de voz/chat y genera insights accionables.

{transcripts_summary}

Genera un JSON array con insights. Cada insight debe tener:
- "type": uno de "faq", "topic_trend", "drop_point", "prompt_suggestion", "sentiment_pattern"
- "title": título corto del insight
- "description": descripción detallada
- "frequency": cuántas llamadas muestran este patrón (estimado)
- "confidence": 0.0-1.0
- "suggested_response": (solo para faq) respuesta sugerida
- "suggested_prompt_addition": (solo para prompt_suggestion) texto a agregar al prompt
- "evidence": {{"example_queries": ["..."]}} con ejemplos concretos

Reglas:
- Solo genera insights que aparezcan en 3+ llamadas
- Prioriza FAQs y prompt_suggestions (son los más accionables)
- Máximo 10 insights
- Responde SOLO con el JSON array, sin texto adicional

JSON:"""

        response = await asyncio.to_thread(
            lambda: client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
        )

        text = (response.text or "").strip()
        # Limpiar markdown si viene envuelto
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text
            text = text.rsplit("```", 1)[0] if "```" in text else text

        return json.loads(text)

    except json.JSONDecodeError:
        logger.error("Error parseando insights JSON del LLM")
        return []
    except Exception:
        logger.exception("Error generando insights con LLM")
        return []


async def get_active_insights(agent_id: str) -> list[dict]:
    """Retorna insights activos de un agente."""
    from api.deps import get_supabase

    sb = get_supabase()
    result = (
        sb.table("agent_insights")
        .select("*")
        .eq("agent_id", agent_id)
        .eq("status", "active")
        .order("confidence", desc=True)
        .order("frequency", desc=True)
        .limit(20)
        .execute()
    )
    return result.data or []


async def get_faq_context_for_agent(agent_id: str) -> str:
    """Genera contexto de FAQs para inyectar al system prompt del agente.

    Retorna un texto con las preguntas frecuentes y sus respuestas sugeridas,
    que se puede agregar al prompt para que el agente las responda mejor.
    """
    from api.deps import get_supabase

    sb = get_supabase()
    faqs = (
        sb.table("agent_insights")
        .select("title, suggested_response, frequency")
        .eq("agent_id", agent_id)
        .eq("insight_type", "faq")
        .eq("status", "active")
        .gte("confidence", 0.6)
        .order("frequency", desc=True)
        .limit(5)
        .execute()
    )

    if not faqs.data:
        return ""

    lines = ["\n\n## Preguntas frecuentes (basadas en llamadas anteriores)"]
    for faq in faqs.data:
        if faq.get("suggested_response"):
            lines.append(f"- Si preguntan sobre '{faq['title']}': {faq['suggested_response']}")

    return "\n".join(lines) if len(lines) > 1 else ""
