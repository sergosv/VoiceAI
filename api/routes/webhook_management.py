"""Endpoints de gestión de webhooks (autenticados por JWT del dashboard)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.routes.auth import get_current_user
from api.services.webhook_service import (
    create_webhook_endpoint,
    delete_webhook_endpoint,
    list_deliveries,
    list_webhook_endpoints,
    update_webhook_endpoint,
)

router = APIRouter(prefix="/webhook-endpoints", tags=["webhook-management"])


class CreateWebhookRequest(BaseModel):
    url: str = Field(..., min_length=1)
    events: list[str] = Field(..., min_length=1)
    description: str | None = None


class UpdateWebhookRequest(BaseModel):
    url: str | None = None
    events: list[str] | None = None
    is_active: bool | None = None
    description: str | None = None


@router.get("/{client_id}")
async def list_endpoints(
    client_id: str,
    user: dict = Depends(get_current_user),
) -> list[dict]:
    """Lista webhook endpoints del cliente."""
    return await list_webhook_endpoints(client_id)


@router.post("/{client_id}", status_code=status.HTTP_201_CREATED)
async def create_endpoint(
    client_id: str,
    req: CreateWebhookRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    """Crea un webhook endpoint. Retorna el secret (SOLO en esta respuesta)."""
    return await create_webhook_endpoint(
        client_id=client_id,
        url=req.url,
        events=req.events,
        description=req.description,
    )


@router.patch("/{client_id}/{endpoint_id}")
async def update_endpoint(
    client_id: str,
    endpoint_id: str,
    req: UpdateWebhookRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    """Actualiza un webhook endpoint."""
    updates = req.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")
    result = await update_webhook_endpoint(endpoint_id, client_id, updates)
    if not result:
        raise HTTPException(status_code=404, detail="Webhook no encontrado")
    return result


@router.delete("/{client_id}/{endpoint_id}")
async def delete_endpoint(
    client_id: str,
    endpoint_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    """Elimina un webhook endpoint."""
    ok = await delete_webhook_endpoint(endpoint_id, client_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Webhook no encontrado")
    return {"deleted": True}


@router.get("/{client_id}/{endpoint_id}/deliveries")
async def get_deliveries(
    client_id: str,
    endpoint_id: str,
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
) -> list[dict]:
    """Lista entregas de un webhook endpoint."""
    return await list_deliveries(endpoint_id, limit)
