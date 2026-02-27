"""Lógica de negocio para gestión de documentos."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from google import genai
from supabase import Client

logger = logging.getLogger(__name__)


def upload_document_to_gemini(
    file_path: str,
    store_id: str,
    google_api_key: str,
) -> None:
    """Sube un archivo al FileSearchStore y espera indexación."""
    client = genai.Client(api_key=google_api_key)
    operation = client.file_search_stores.upload_to_file_search_store(
        file=file_path,
        file_search_store_name=store_id,
        config={"display_name": Path(file_path).name},
    )
    # Esperar indexación
    while not operation.done:
        time.sleep(3)
        operation = client.operations.get(operation)
    logger.info("Documento indexado: %s", file_path)


def save_document_record(
    sb: Client,
    *,
    client_id: str,
    filename: str,
    file_type: str,
    file_size_bytes: int,
    description: str,
    indexing_status: str = "indexed",
) -> dict:
    """Guarda referencia de documento en DB."""
    data = {
        "client_id": client_id,
        "filename": filename,
        "file_type": file_type,
        "file_size_bytes": file_size_bytes,
        "indexing_status": indexing_status,
        "description": description,
    }
    result = sb.table("documents").insert(data).execute()
    return result.data[0]


def delete_document_record(sb: Client, document_id: str) -> None:
    """Elimina registro de documento de DB."""
    sb.table("documents").delete().eq("id", document_id).execute()
