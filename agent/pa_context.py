"""Construye el contexto del Asistente Personal para inyectar en el system prompt.

Carga tareas pendientes, notas recientes, recordatorios próximos,
y lo formatea como bloque de contexto para el LLM.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from supabase import Client

logger = logging.getLogger(__name__)

PA_PROMPT_TEMPLATE = """Eres un asistente personal de voz. Tu trabajo es ayudar a tu dueño con todo lo que necesite: recordar información, gestionar tareas, enviar emails, y programar recordatorios.

{owner_instructions}

## Tus capacidades:
- **Memoria**: Puedes recordar y buscar cualquier información que te digan. Usa la herramienta "remember" cuando te digan "recuerda que...", "anota que...", o compartan datos importantes.
- **Tareas**: Puedes crear, listar y completar tareas/pendientes. Usa "create_task" para nuevas, "list_tasks" para ver pendientes, "complete_task" cuando te digan que ya terminaron algo.
- **Notas**: Puedes crear notas con "create_note" para guardar información más extensa.
- **Email**: Puedes enviar emails con "send_email" en nombre de tu dueño.
- **Memoria**: Puedes buscar en todo lo que recuerdas con "search_my_memory".
- **Olvidar**: Si te piden borrar algo, usa "forget".
- **Recordatorios**: Puedes programar recordatorios que te avisarán por llamada o mensaje.

## Reglas:
- Habla en español de forma natural y cercana, como un asistente de confianza.
- Cuando te digan algo para recordar, confírmalo brevemente: "Listo, lo tengo guardado."
- Cuando busques en tu memoria, resume lo encontrado de forma clara.
- Si no encuentras algo, dilo honestamente: "No tengo eso registrado."
- Para emails, siempre confirma destinatario y contenido antes de enviar.

{pa_context}"""


async def build_pa_system_context(sb: Client, agent_id: str) -> str:
    """Carga y formatea el contexto actual del PA: tareas, notas, recordatorios."""
    sections: list[str] = []

    try:
        # Cargar tareas pendientes, notas recientes y recordatorios en paralelo
        tasks_task = asyncio.to_thread(
            lambda: sb.table("pa_memory_items")
            .select("content, metadata, created_at")
            .eq("agent_id", agent_id)
            .eq("item_type", "task")
            .eq("is_completed", False)
            .eq("is_deleted", False)
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        )
        notes_task = asyncio.to_thread(
            lambda: sb.table("pa_memory_items")
            .select("content, metadata, created_at")
            .eq("agent_id", agent_id)
            .eq("item_type", "note")
            .eq("is_deleted", False)
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        facts_task = asyncio.to_thread(
            lambda: sb.table("pa_memory_items")
            .select("content, metadata, created_at")
            .eq("agent_id", agent_id)
            .in_("item_type", ["fact", "preference"])
            .eq("is_deleted", False)
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        )
        reminders_task = asyncio.to_thread(
            lambda: sb.table("pa_memory_items")
            .select("content, metadata, created_at")
            .eq("agent_id", agent_id)
            .eq("item_type", "reminder")
            .eq("is_completed", False)
            .eq("is_deleted", False)
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )

        tasks_result, notes_result, facts_result, reminders_result = await asyncio.gather(
            tasks_task, notes_task, facts_task, reminders_task,
            return_exceptions=True,
        )

        # Formatear tareas pendientes
        if not isinstance(tasks_result, Exception) and tasks_result.data:
            lines = []
            for t in tasks_result.data:
                meta = t.get("metadata") or {}
                if isinstance(meta, str):
                    import json
                    meta = json.loads(meta)
                due = meta.get("due_date", "")
                due_str = f" (fecha límite: {due})" if due else ""
                lines.append(f"- {t['content']}{due_str}")
            sections.append("## Tareas pendientes:\n" + "\n".join(lines))

        # Formatear hechos/preferencias conocidas
        if not isinstance(facts_result, Exception) and facts_result.data:
            lines = [f"- {f['content']}" for f in facts_result.data]
            sections.append("## Lo que sé de mi dueño:\n" + "\n".join(lines))

        # Formatear notas recientes
        if not isinstance(notes_result, Exception) and notes_result.data:
            lines = []
            for n in notes_result.data:
                meta = n.get("metadata") or {}
                if isinstance(meta, str):
                    import json
                    meta = json.loads(meta)
                title = meta.get("title", "")
                prefix = f"[{title}] " if title else ""
                lines.append(f"- {prefix}{n['content'][:100]}")
            sections.append("## Notas recientes:\n" + "\n".join(lines))

        # Formatear recordatorios activos
        if not isinstance(reminders_result, Exception) and reminders_result.data:
            lines = [f"- {r['content']}" for r in reminders_result.data]
            sections.append("## Recordatorios activos:\n" + "\n".join(lines))

    except Exception as e:
        logger.error("Error building PA context: %s", e)

    if not sections:
        return "\n## Estado actual:\nNo hay tareas, notas ni recordatorios guardados aún."

    return "\n" + "\n\n".join(sections)


def build_pa_prompt(
    owner_instructions: str,
    pa_context: str,
    memory_context: str = "",
) -> str:
    """Construye el system prompt completo para un agente PA."""
    ctx = pa_context
    if memory_context:
        ctx += f"\n\n## Historial de conversaciones:\n{memory_context}"

    return PA_PROMPT_TEMPLATE.format(
        owner_instructions=owner_instructions,
        pa_context=ctx,
    )
