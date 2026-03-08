"""Endpoints de gestión de API keys (autenticados por JWT del dashboard)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.routes.auth import get_current_user
from api.services.api_key_service import (
    create_api_key,
    delete_api_key,
    list_api_keys,
    revoke_api_key,
)

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class CreateApiKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    scopes: list[str] = Field(default_factory=list)
    expires_at: str | None = None


@router.post("/{client_id}", status_code=status.HTTP_201_CREATED)
async def create_key(
    client_id: str,
    req: CreateApiKeyRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    """Crea una nueva API key. La key completa se muestra SOLO en esta respuesta."""
    result = await create_api_key(
        client_id=client_id,
        name=req.name,
        scopes=req.scopes,
        expires_at=req.expires_at,
    )
    return result


@router.get("/{client_id}")
async def list_keys(
    client_id: str,
    user: dict = Depends(get_current_user),
) -> list[dict]:
    """Lista API keys del cliente (sin mostrar la key completa)."""
    return await list_api_keys(client_id)


@router.post("/{client_id}/{key_id}/revoke")
async def revoke_key(
    client_id: str,
    key_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    """Revoca (desactiva) una API key."""
    ok = await revoke_api_key(key_id, client_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key no encontrada")
    return {"revoked": True}


@router.delete("/{client_id}/{key_id}")
async def delete_key(
    client_id: str,
    key_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    """Elimina permanentemente una API key."""
    ok = await delete_api_key(key_id, client_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key no encontrada")
    return {"deleted": True}
