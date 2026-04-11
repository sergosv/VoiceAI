"""Generación de embeddings con Gemini gemini-embedding-001.

NOTA: text-embedding-004 fue deprecado en enero 2026 por Google.
Migramos a gemini-embedding-001 con output_dimensionality=768 para
mantener compatibilidad con los embeddings ya guardados en la DB
(que son de 768 dims por el modelo anterior).

gemini-embedding-001 usa Matryoshka Representation Learning (MRL)
así que truncar a 768 dims preserva la calidad del vector.
"""

from __future__ import annotations

import logging
import os

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Reutilizar el singleton de genai.Client
_client: genai.Client | None = None

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMS = 768


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    return _client


async def generate_embedding(text: str) -> list[float]:
    """Genera un embedding de 768 dimensiones para el texto dado."""
    client = _get_client()
    response = await client.aio.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMS),
    )
    return list(response.embeddings[0].values)


async def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Genera embeddings para múltiples textos en un solo request."""
    if not texts:
        return []

    client = _get_client()
    response = await client.aio.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMS),
    )
    return [list(e.values) for e in response.embeddings]
