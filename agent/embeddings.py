"""Generación de embeddings con Gemini text-embedding-004."""

from __future__ import annotations

import logging
import os

from google import genai

logger = logging.getLogger(__name__)

# Reutilizar el singleton de genai.Client
_client: genai.Client | None = None

EMBEDDING_MODEL = "text-embedding-004"
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
    )
    return [list(e.values) for e in response.embeddings]
