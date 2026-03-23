"""Herramienta de búsqueda en base de conocimientos usando Gemini File Search."""

from __future__ import annotations

import asyncio
import logging
import os
import threading

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Timeout para llamadas a Gemini (segundos)
GEMINI_TIMEOUT_S = 15.0

# Cliente Gemini singleton (thread-safe)
_gemini_client: genai.Client | None = None
_gemini_lock = threading.Lock()


def _get_gemini() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        with _gemini_lock:
            if _gemini_client is None:
                api_key = os.environ.get("GOOGLE_API_KEY")
                if not api_key:
                    raise RuntimeError("GOOGLE_API_KEY no configurada.")
                _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


async def search_knowledge_base(query: str, store_id: str) -> str:
    """Busca información en la base de conocimientos del cliente.

    Usa Gemini File Search para consultar el vector store del cliente
    y retorna la información relevante encontrada.
    """
    if not store_id:
        return "No hay base de conocimientos configurada para este cliente."

    async def _do_search() -> str:
        client = _get_gemini()
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.5-flash",
                contents=f"Busca y responde basándote SOLO en los documentos disponibles: {query}",
                config=types.GenerateContentConfig(
                    tools=[
                        types.Tool(
                            file_search=types.FileSearch(
                                file_search_store_names=[store_id]
                            )
                        )
                    ],
                    system_instruction=(
                        "Eres un asistente de búsqueda. Responde ÚNICAMENTE con "
                        "información encontrada en los documentos. Si no encuentras "
                        "información relevante, di exactamente: 'No encontré información "
                        "sobre eso en los documentos disponibles.' Sé conciso."
                    ),
                ),
            ),
            timeout=GEMINI_TIMEOUT_S,
        )
        return response.text or "No se encontró información relevante."

    try:
        from agent.tools.retry import retry_async
        return await retry_async(_do_search, max_retries=2, base_delay=1.0)
    except asyncio.TimeoutError:
        logger.warning("Timeout en File Search (%.0fs, tras retries) para query: %s", GEMINI_TIMEOUT_S, query[:80])
        return (
            "La búsqueda tardó demasiado después de varios intentos. "
            "Responde con lo que sepas o dile al usuario que intente preguntar de otra forma."
        )
    except Exception as e:
        logger.error("Error en File Search (tras retries): %s", e)
        return (
            "No pude consultar la base de conocimientos en este momento. "
            "Responde con lo que sepas del contexto del negocio o pide disculpas al usuario."
        )
