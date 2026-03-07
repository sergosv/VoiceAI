"""Rutas para gestión de documentos."""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status

from api.deps import get_supabase
from api.middleware.auth import CurrentUser, get_current_user
from api.schemas import DocumentOut, MessageResponse
from api.services.document_service import (
    delete_document_record,
    save_document_record,
    upload_document_to_gemini,
)

router = APIRouter()


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = None,
) -> list[DocumentOut]:
    """Lista documentos. Client ve solo los suyos."""
    sb = get_supabase()
    query = sb.table("documents").select("*").order("uploaded_at", desc=True)

    if user.role == "client":
        if not user.client_id:
            return []
        query = query.eq("client_id", user.client_id)
    elif client_id:
        query = query.eq("client_id", client_id)

    result = query.execute()
    return [DocumentOut(**row) for row in result.data]


@router.post("", response_model=DocumentOut, status_code=201)
async def upload_document(
    file: UploadFile,
    description: str = Form(""),
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = Form(None),
) -> DocumentOut:
    """Sube un documento al FileSearchStore del cliente."""
    # Determinar client_id
    effective_client_id = user.client_id if user.role == "client" else client_id
    if not effective_client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere client_id",
        )

    # Verificar acceso
    if user.role == "client" and user.client_id != effective_client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    # Obtener store_id del cliente
    sb = get_supabase()
    client_result = (
        sb.table("clients")
        .select("file_search_store_id")
        .eq("id", effective_client_id)
        .limit(1)
        .execute()
    )
    if not client_result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")

    store_id = client_result.data[0].get("file_search_store_id")
    if not store_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cliente no tiene FileSearchStore configurado",
        )

    # Leer y validar tamaño (máx 50 MB)
    MAX_FILE_SIZE = 50 * 1024 * 1024
    suffix = Path(file.filename or "doc").suffix
    file_content = await file.read()
    file_size = len(file_content)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Archivo demasiado grande ({file_size // (1024*1024)} MB). Máximo: 50 MB.",
        )

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo está vacío.",
        )

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name

    try:
        await asyncio.to_thread(
            upload_document_to_gemini, tmp_path, store_id, os.environ["GOOGLE_API_KEY"]
        )
    except Exception as e:
        os.unlink(tmp_path)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error subiendo a Gemini: {e}",
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    # Guardar en DB
    row = save_document_record(
        sb,
        client_id=effective_client_id,
        filename=file.filename or "documento",
        file_type=suffix.lstrip("."),
        file_size_bytes=file_size,
        description=description or f"Documento {file.filename}",
    )
    return DocumentOut(**row)


@router.delete("/{document_id}", response_model=MessageResponse)
async def delete_document(
    document_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> MessageResponse:
    """Elimina un documento."""
    sb = get_supabase()

    # Verificar que el documento existe y el usuario tiene acceso
    doc_result = sb.table("documents").select("*").eq("id", document_id).limit(1).execute()
    if not doc_result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado")

    doc = doc_result.data[0]
    if user.role == "client" and doc.get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    delete_document_record(sb, document_id)
    return MessageResponse(message="Documento eliminado")
