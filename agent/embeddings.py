"""Generación de embeddings con Gemini gemini-embedding-001.

NOTA: text-embedding-004 fue deprecado en enero 2026 por Google.
Migramos a gemini-embedding-001 con output_dimensionality=768.

gemini-embedding-001 usa Matryoshka Representation Learning (MRL).
Cuando output_dimensionality < 3072, Google recomienda L2-normalizar
el vector resultante para que la similitud coseno mantenga calidad
(sin eso, los componentes truncados sesgan la magnitud).

Los embeddings que existían antes de esta migración (generados con
text-embedding-004) viven en un espacio vectorial distinto y no son
comparables con los nuevos. Ver migración 057 y scripts/reembed_memories.py.
"""

from __future__ import annotations

import logging
import math
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


def _l2_normalize(vec: list[float]) -> list[float]:
    """Normaliza el vector a norma unitaria. Requerido para MRL truncado."""
    norm = math.sqrt(sum(v * v for v in vec))
    if norm <= 0.0:
        return vec
    return [v / norm for v in vec]


async def generate_embedding(text: str) -> list[float]:
    """Genera un embedding de 768 dimensiones (L2-normalizado) para el texto dado."""
    client = _get_client()
    response = await client.aio.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMS),
    )
    return _l2_normalize(list(response.embeddings[0].values))


async def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Genera embeddings (L2-normalizados) para múltiples textos en un solo request."""
    if not texts:
        return []

    client = _get_client()
    response = await client.aio.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMS),
    )
    return [_l2_normalize(list(e.values)) for e in response.embeddings]
