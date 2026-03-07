"""Servicio de ejecución de tests LoopTalk: simula conversaciones persona-agente."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import traceback
from typing import Any

from google import genai
from google.genai import types

from agent.config_loader import load_config_by_agent_id
from api.deps import get_supabase
from api.services.chat_service import build_chat_system_prompt, chat_turn
from api.services.chat_store import Conversation

logger = logging.getLogger("looptalk")

# Sentinel que la persona envía cuando la conversación termina naturalmente
END_TOKEN = "[END]"

# Cliente Gemini singleton
_gemini: genai.Client | None = None


def _get_gemini() -> genai.Client:
    """Retorna un cliente Gemini singleton."""
    global _gemini
    if _gemini is None:
        _gemini = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    return _gemini


def _build_persona_prompt(persona: dict) -> str:
    """Construye el system prompt para que Gemini actúe como la persona de prueba."""
    name = persona.get("name", "Persona de prueba")
    personality = persona.get("personality", "")
    objective = persona.get("objective", "")
    curveballs = persona.get("curveballs") or []
    language = persona.get("language", "es")

    lang_instruction = ""
    if language == "es":
        lang_instruction = "Habla en español."
    elif language == "en":
        lang_instruction = "Speak in English."
    else:
        lang_instruction = f"Habla en {language}."

    prompt = (
        f"Eres {name}. {personality}\n\n"
        f"Tu objetivo en esta conversación: {objective}\n\n"
        f"Comportamiento:\n"
        f"- Actúa de forma natural y realista\n"
        f"- NO reveles que eres una IA o un test\n"
        f"- Responde de forma consistente con tu personalidad\n"
        f"- Si la conversación llega a un punto natural de cierre, "
        f'responde exactamente "{END_TOKEN}"\n'
        f"- Máximo 2-3 oraciones por respuesta\n"
        f"- {lang_instruction}\n"
    )

    if curveballs:
        prompt += "\nComportamientos especiales que debes incluir durante la conversación:\n"
        for i, cb in enumerate(curveballs, 1):
            prompt += f"  {i}. {cb}\n"

    return prompt


def _build_evaluation_prompt(persona: dict, conversation_log: list[dict]) -> str:
    """Construye el prompt para que Gemini evalúe la conversación."""
    name = persona.get("name", "Persona")
    objective = persona.get("objective", "")
    success_criteria = persona.get("success_criteria") or []

    transcript = ""
    for msg in conversation_log:
        role = msg.get("role", "unknown")
        text = msg.get("text", "")
        label = "PERSONA" if role == "persona" else "AGENTE"
        transcript += f"[{label}]: {text}\n"

    criteria_section = ""
    if success_criteria:
        criteria_section = "\nCriterios de éxito a evaluar:\n"
        for i, c in enumerate(success_criteria, 1):
            criteria_section += f"  {i}. {c}\n"

    prompt = (
        f"Evalúa la siguiente conversación entre un agente de IA y un cliente llamado {name}.\n\n"
        f"Objetivo del cliente: {objective}\n"
        f"{criteria_section}\n"
        f"Transcripción:\n{transcript}\n\n"
        f"Responde EXCLUSIVAMENTE con un JSON válido (sin markdown, sin ```), con esta estructura:\n"
        f'{{\n'
        f'  "score": <número 0-100>,\n'
        f'  "criteria_results": [\n'
        f'    {{"criterion": "<criterio>", "passed": <true/false>, "explanation": "<explicación>"}}\n'
        f'  ],\n'
        f'  "summary": "<resumen de 2-3 oraciones>",\n'
        f'  "suggestions": ["<sugerencia1>", "<sugerencia2>"]\n'
        f'}}\n\n'
        f"Si no hay criterios de éxito específicos, evalúa: profesionalismo, claridad, "
        f"utilidad de las respuestas, y si se resolvió la consulta del cliente."
    )
    return prompt


async def _persona_reply(
    persona_prompt: str,
    history: list[dict],
    agent_response: str,
) -> str:
    """Genera la respuesta de la persona de prueba usando Gemini."""
    client = _get_gemini()

    # Construir mensajes para Gemini
    contents: list[types.Content] = []
    for msg in history:
        role = "user" if msg["role"] == "agent" else "model"
        contents.append(
            types.Content(role=role, parts=[types.Part.from_text(text=msg["text"])])
        )
    # Agregar la última respuesta del agente
    contents.append(
        types.Content(role="user", parts=[types.Part.from_text(text=agent_response)])
    )

    response = await asyncio.to_thread(
        client.models.generate_content,
        model="gemini-2.5-flash",
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=persona_prompt,
            temperature=0.8,
        ),
    )
    return (response.text or "").strip()


async def _evaluate_conversation(
    persona: dict,
    conversation_log: list[dict],
) -> dict[str, Any]:
    """Evalúa la conversación completa usando Gemini. Retorna score y detalles."""
    client = _get_gemini()
    eval_prompt = _build_evaluation_prompt(persona, conversation_log)

    response = await asyncio.to_thread(
        client.models.generate_content,
        model="gemini-2.5-flash",
        contents=[
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=eval_prompt)],
            )
        ],
        config=types.GenerateContentConfig(
            temperature=0.2,
        ),
    )

    raw = (response.text or "").strip()

    # Limpiar posible markdown
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw = "\n".join(lines)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("No se pudo parsear evaluación JSON: %s", raw[:200])
        result = {
            "score": 50,
            "criteria_results": [],
            "summary": raw[:500],
            "suggestions": [],
        }
    return result


async def run_test(
    run_id: str,
    agent_id: str,
    persona_id: str,
    client_id: str,
    max_turns: int = 20,
) -> None:
    """Ejecuta un test completo: conversación persona-agente + evaluación.

    Actualiza el registro en DB con el resultado.
    """
    sb = get_supabase()

    try:
        # Marcar como running
        sb.table("looptalk_runs").update({
            "status": "running",
        }).eq("id", run_id).execute()

        # Cargar persona
        persona_result = (
            sb.table("looptalk_personas")
            .select("*")
            .eq("id", persona_id)
            .limit(1)
            .execute()
        )
        if not persona_result.data:
            raise ValueError(f"Persona {persona_id} no encontrada")
        persona = persona_result.data[0]

        # Cargar config del agente
        config = await load_config_by_agent_id(agent_id)
        if not config:
            raise ValueError(f"Agente {agent_id} no encontrado")

        # Construir conversación del chat tester
        system_prompt = build_chat_system_prompt(config)
        conversation = Conversation(
            id=f"looptalk-{run_id}",
            config=config,
            system_prompt=system_prompt,
            history=[],
            created_at=__import__("time").time(),
            client_id=client_id,
        )

        # Construir prompt de la persona
        persona_prompt = _build_persona_prompt(persona)
        conversation_log: list[dict] = []

        # El primer mensaje viene de la persona (inicia la conversación)
        # Generar mensaje inicial de la persona
        first_message = await _persona_reply(persona_prompt, [], config.agent.greeting)
        conversation_log.append({"role": "persona", "text": first_message})

        if END_TOKEN in first_message:
            # La persona terminó inmediatamente (raro pero posible)
            first_message = first_message.replace(END_TOKEN, "").strip()
            if first_message:
                conversation_log[-1]["text"] = first_message

        else:
            # Loop de conversación
            for turn in range(max_turns):
                # Agente responde al mensaje de la persona
                persona_text = conversation_log[-1]["text"]
                agent_text, tool_calls = await chat_turn(conversation, persona_text)
                conversation_log.append({
                    "role": "agent",
                    "text": agent_text,
                    "tool_calls": tool_calls if tool_calls else None,
                })

                # Verificar si quedan turnos
                if turn >= max_turns - 1:
                    break

                # Persona responde al agente
                persona_response = await _persona_reply(
                    persona_prompt, conversation_log, agent_text
                )

                if END_TOKEN in persona_response:
                    # Conversación terminó naturalmente
                    clean = persona_response.replace(END_TOKEN, "").strip()
                    if clean:
                        conversation_log.append({"role": "persona", "text": clean})
                        # Dar al agente la oportunidad de despedirse
                        agent_final, tc = await chat_turn(conversation, clean)
                        conversation_log.append({
                            "role": "agent",
                            "text": agent_final,
                            "tool_calls": tc if tc else None,
                        })
                    break

                conversation_log.append({"role": "persona", "text": persona_response})

        # Evaluar la conversación
        evaluation = await _evaluate_conversation(persona, conversation_log)
        score = evaluation.get("score", 0)

        # Guardar resultado
        sb.table("looptalk_runs").update({
            "status": "completed",
            "conversation_log": conversation_log,
            "evaluation": evaluation,
            "score": score,
            "turns_used": len([m for m in conversation_log if m["role"] == "persona"]),
        }).eq("id", run_id).execute()

        logger.info(
            "Test run %s completado: score=%s, turnos=%s",
            run_id, score, len(conversation_log),
        )

    except Exception as e:
        logger.error("Test run %s falló: %s", run_id, e, exc_info=True)
        sb.table("looptalk_runs").update({
            "status": "failed",
            "evaluation": {
                "error": str(e),
                "traceback": traceback.format_exc(),
            },
            "score": 0,
        }).eq("id", run_id).execute()


async def generate_personas(
    description: str,
    count: int = 5,
    language: str = "es",
) -> list[dict[str, Any]]:
    """Genera personas de prueba usando Gemini basándose en una descripción del negocio."""
    client = _get_gemini()

    prompt = (
        f"Genera exactamente {count} personas de prueba para evaluar un agente de IA "
        f"de atención al cliente.\n\n"
        f"Contexto del negocio: {description}\n\n"
        f"Cada persona debe tener personalidad y objetivo diferentes. Incluye variedad:\n"
        f"- Al menos una persona fácil (pregunta directa)\n"
        f"- Al menos una difícil (enojada, confundida, o con preguntas complejas)\n"
        f"- Variedad de edades y estilos de comunicación\n\n"
        f"Responde EXCLUSIVAMENTE con un JSON array válido (sin markdown, sin ```), "
        f"donde cada elemento tiene:\n"
        f'{{\n'
        f'  "name": "<nombre completo realista>",\n'
        f'  "personality": "<descripción de 2-3 oraciones de la personalidad>",\n'
        f'  "objective": "<qué quiere lograr en la conversación>",\n'
        f'  "success_criteria": ["<criterio1>", "<criterio2>"],\n'
        f'  "curveballs": ["<comportamiento especial opcional>"],\n'
        f'  "difficulty": "<easy|medium|hard>",\n'
        f'  "tags": ["<tag1>", "<tag2>"]\n'
        f'}}\n\n'
        f'Idioma de las personas: {"español" if language == "es" else language}'
    )

    response = await asyncio.to_thread(
        client.models.generate_content,
        model="gemini-2.5-flash",
        contents=[
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)],
            )
        ],
        config=types.GenerateContentConfig(
            temperature=0.9,
        ),
    )

    raw = (response.text or "").strip()

    # Limpiar markdown
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw = "\n".join(lines)

    try:
        personas = json.loads(raw)
        if not isinstance(personas, list):
            personas = [personas]
    except json.JSONDecodeError:
        logger.warning("No se pudo parsear personas generadas: %s", raw[:200])
        personas = []

    return personas
