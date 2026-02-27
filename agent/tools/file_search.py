"""Herramienta de búsqueda en base de conocimientos usando Gemini File Search."""

from __future__ import annotations

import logging
import os

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Cliente Gemini singleton
_gemini_client: genai.Client | None = None


def _get_gemini() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    return _gemini_client


async def search_knowledge_base(query: str, store_id: str) -> str:
    """Busca información en la base de conocimientos del cliente.

    Usa Gemini File Search para consultar el vector store del cliente
    y retorna la información relevante encontrada.
    """
    if not store_id:
        return "No hay base de conocimientos configurada para este cliente."

    try:
        client = _get_gemini()
        response = client.models.generate_content(
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
        )
        return response.text or "No se encontró información relevante."

    except Exception as e:
        logger.error("Error en File Search: %s", e)
        return "No pude consultar la base de conocimientos en este momento."
