"""Lifecycle helpers: cerrar conversaciones + generar resúmenes."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

from supabase import Client

logger = logging.getLogger(__name__)


async def close_conversation(
    sb: Client,
    conversation_id: str,
    table: str,
    summary: str | None = None,
    result: str | None = None,
    closed_by: str = "manual",
    generate_summary: bool = False,
    history: list | None = None,
) -> None:
    """Cierra una conversación con resumen y clasificación opcionales."""
    if generate_summary and not summary and history:
        try:
            summary = await _generate_summary(history)
        except Exception:
            logger.exception("Error generando resumen para %s", conversation_id)

    status = "expired" if closed_by == "timeout" else "closed"
    update: dict = {"status": status, "closed_by": closed_by}
    if summary:
        update["summary"] = summary
    if result:
        update["result"] = result

    try:
        sb.table(table).update(update).eq("id", conversation_id).execute()
        logger.info(
            "Conversación %s cerrada (%s, by=%s, result=%s)",
            conversation_id[:8], table, closed_by, result or "n/a",
        )

        # Dispatch webhook: conversation.closed (fire-and-forget)
        try:
            from api.services.webhook_service import dispatch_event as _wh_dispatch

            # Obtener client_id de la conversación via config
            config_table = "whatsapp_configs" if "whatsapp" in table else "ghl_configs"
            conv_row = (
                sb.table(table).select("config_id")
                .eq("id", conversation_id).limit(1).execute()
            )
            if conv_row.data:
                cfg_row = (
                    sb.table(config_table).select("client_id")
                    .eq("id", conv_row.data[0]["config_id"]).limit(1).execute()
                )
                if cfg_row.data:
                    client_id = cfg_row.data[0]["client_id"]
                    asyncio.create_task(_wh_dispatch(
                        client_id,
                        "conversation.closed",
                        {
                            "client_id": client_id,
                            "conversation_id": conversation_id,
                            "table": table,
                            "closed_by": closed_by,
                            "result": result,
                            "summary": summary,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    ))
        except Exception:
            logger.exception("Error dispatching conversation.closed webhook")
    except Exception:
        logger.exception("Error cerrando conversación %s", conversation_id)


async def _generate_summary(history: list) -> str:
    """Genera resumen breve de la conversación vía Gemini."""
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        return ""

    messages = []
    for entry in history[-20:]:
        role = entry.get("role", "")
        parts = entry.get("parts", [])
        text = " ".join(p.get("text", "") for p in parts if p.get("text"))
        if text:
            label = "Agente" if role == "model" else "Usuario"
            messages.append(f"{label}: {text}")

    if not messages:
        return ""

    transcript = "\n".join(messages)

    client = genai.Client(api_key=api_key)
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=(
            "Resume esta conversación de atención al cliente en 1-2 oraciones en español. "
            "Incluye el tema principal y el resultado (si se agendó cita, se resolvió duda, etc.):\n\n"
            f"{transcript}"
        ),
        config=types.GenerateContentConfig(temperature=0.3, max_output_tokens=150),
    )
    return response.text or ""
