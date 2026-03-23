"""Prompt Auto-Tuner — genera sugerencias de mejora al system prompt.

Analiza quality scores, sentiment patterns, y transcripts para recomendar
cambios específicos al system prompt del agente.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


async def generate_prompt_suggestions(
    agent_id: str,
    client_id: str,
) -> list[dict]:
    """Analiza las métricas del agente y genera sugerencias de mejora al prompt.

    Returns:
        Lista de sugerencias, cada una con:
        - category: 'empathy', 'clarity', 'accuracy', 'efficiency', 'safety'
        - title: título corto
        - current_issue: qué problema se detectó
        - suggestion: texto sugerido para agregar/modificar
        - impact: 'high', 'medium', 'low'
        - evidence: datos que soportan la sugerencia
    """
    from api.deps import get_supabase

    sb = get_supabase()
    now = datetime.now(timezone.utc)
    window = now - timedelta(days=14)

    # Cargar datos del agente
    agent = sb.table("agents").select("system_prompt, name").eq("id", agent_id).limit(1).execute()
    if not agent.data:
        return []
    current_prompt = agent.data[0].get("system_prompt", "")
    agent_name = agent.data[0].get("name", "")

    # Cargar métricas recientes
    calls = (
        sb.table("calls")
        .select("quality_score, sentiment_realtime, duration_seconds, transcript, status")
        .eq("agent_id", agent_id)
        .eq("status", "completed")
        .gte("created_at", window.isoformat())
        .order("created_at", desc=True)
        .limit(30)
        .execute()
    )

    if not calls.data or len(calls.data) < 3:
        return []

    # Calcular métricas agregadas
    scores = [c["quality_score"] for c in calls.data if c.get("quality_score")]
    avg_score = sum(scores) / len(scores) if scores else 0
    short_calls = [c for c in calls.data if (c.get("duration_seconds") or 0) < 30]
    short_rate = len(short_calls) / len(calls.data) if calls.data else 0

    sentiments = []
    for c in calls.data:
        s = c.get("sentiment_realtime") or {}
        if s.get("overall"):
            sentiments.append(s["overall"])
    negative_rate = sentiments.count("negative") / len(sentiments) if sentiments else 0

    # Extraer muestras de transcripts problemáticos
    problem_transcripts = []
    for c in calls.data:
        if (c.get("quality_score") or 100) < 60:
            transcript = c.get("transcript") or []
            if transcript:
                sample = " | ".join(t.get("text", "")[:80] for t in transcript[:4])
                problem_transcripts.append(sample)

    # Generar sugerencias con LLM
    suggestions = await _generate_with_llm(
        current_prompt=current_prompt,
        agent_name=agent_name,
        avg_score=avg_score,
        short_rate=short_rate,
        negative_rate=negative_rate,
        total_calls=len(calls.data),
        problem_transcripts=problem_transcripts[:5],
    )

    return suggestions


async def _generate_with_llm(
    current_prompt: str,
    agent_name: str,
    avg_score: float,
    short_rate: float,
    negative_rate: float,
    total_calls: int,
    problem_transcripts: list[str],
) -> list[dict]:
    """Usa Gemini para analizar el prompt y generar sugerencias."""
    try:
        from google import genai

        client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

        problems_text = ""
        if problem_transcripts:
            problems_text = "\n\nTranscripts de llamadas con baja calidad:\n"
            for i, t in enumerate(problem_transcripts, 1):
                problems_text += f"{i}. {t}\n"

        prompt = f"""Eres un experto en diseño de prompts para agentes de voz/chat.
Analiza este system prompt y las métricas del agente "{agent_name}" para generar sugerencias de mejora.

## System Prompt Actual
{current_prompt[:2000]}

## Métricas (últimas 2 semanas, {total_calls} llamadas)
- Calidad promedio: {avg_score:.0f}/100
- Tasa de llamadas cortas (<30s): {short_rate:.0%}
- Tasa de sentimiento negativo: {negative_rate:.0%}
{problems_text}

## Genera sugerencias

Responde con un JSON array. Cada sugerencia debe tener:
- "category": "empathy" | "clarity" | "accuracy" | "efficiency" | "safety"
- "title": título corto (máx 50 chars)
- "current_issue": qué problema detectaste
- "suggestion": el texto EXACTO a agregar o modificar en el prompt
- "impact": "high" | "medium" | "low"

Reglas:
- Solo sugerencias ACCIONABLES y ESPECÍFICAS
- El texto de "suggestion" debe ser copy-paste directo al prompt
- Máximo 5 sugerencias, priorizadas por impacto
- Si el prompt ya es bueno (calidad >80, sin problemas), retorna array vacío
- Responde SOLO con el JSON array

JSON:"""

        response = await asyncio.to_thread(
            lambda: client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
        )

        text = (response.text or "").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text
            text = text.rsplit("```", 1)[0] if "```" in text else text

        return json.loads(text)

    except json.JSONDecodeError:
        logger.error("Error parseando prompt suggestions JSON")
        return []
    except Exception:
        logger.exception("Error generando prompt suggestions")
        return []
