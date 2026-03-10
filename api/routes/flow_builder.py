"""Rutas de versionamiento de flujos de conversación."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from api.deps import get_supabase
from api.middleware.auth import CurrentUser, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


def _check_access(user: CurrentUser, client_id: str) -> None:
    """Verifica que el usuario tenga acceso al cliente."""
    if user.role == "client" and user.client_id != client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")


def _auto_save_version(
    agent_id: str, client_id: str, flow_data: dict, user_id: str | None = None
) -> int:
    """Crea una nueva versión del flujo automáticamente. Retorna el número de versión."""
    sb = get_supabase()

    # Obtener siguiente número de versión
    latest = (
        sb.table("flow_versions")
        .select("version")
        .eq("agent_id", agent_id)
        .order("version", desc=True)
        .limit(1)
        .execute()
    )
    next_version = (latest.data[0]["version"] + 1) if latest.data else 1

    sb.table("flow_versions").insert({
        "agent_id": agent_id,
        "client_id": client_id,
        "version": next_version,
        "label": f"Versión {next_version}",
        "flow_data": flow_data,
        "is_published": False,
        "created_by": user_id,
    }).execute()

    logger.info("Auto-saved flow version %d for agent %s", next_version, agent_id)
    return next_version


@router.get("/{client_id}/agents/{agent_id}/flow-versions")
async def list_flow_versions(
    client_id: str,
    agent_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Lista todas las versiones de flujo de un agente, ordenadas por versión desc."""
    _check_access(user, client_id)
    sb = get_supabase()
    result = (
        sb.table("flow_versions")
        .select("id, version, label, is_published, created_at")
        .eq("agent_id", agent_id)
        .eq("client_id", client_id)
        .order("version", desc=True)
        .limit(50)
        .execute()
    )
    return {"data": result.data or []}


@router.post("/{client_id}/agents/{agent_id}/flow-versions")
async def save_flow_version(
    client_id: str,
    agent_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Guarda el flujo actual como una nueva versión."""
    _check_access(user, client_id)
    body = await request.json()

    if "flow_data" not in body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere flow_data",
        )

    next_version = _auto_save_version(
        agent_id=agent_id,
        client_id=client_id,
        flow_data=body["flow_data"],
        user_id=user.id,
    )

    # Si se proporcionó un label personalizado, actualizar
    if body.get("label"):
        sb = get_supabase()
        sb.table("flow_versions").update({"label": body["label"]}).eq(
            "agent_id", agent_id
        ).eq("version", next_version).execute()

    return {"version": next_version}


@router.post("/{client_id}/agents/{agent_id}/flow-versions/{version_id}/publish")
async def publish_flow_version(
    client_id: str,
    agent_id: str,
    version_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Publica una versión de flujo (la convierte en el flujo activo del agente)."""
    _check_access(user, client_id)
    sb = get_supabase()

    # Obtener datos del flujo de la versión
    version = (
        sb.table("flow_versions")
        .select("flow_data, version")
        .eq("id", version_id)
        .eq("agent_id", agent_id)
        .limit(1)
        .execute()
    )
    if not version.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Versión no encontrada"
        )

    # Despublicar todas las demás versiones
    sb.table("flow_versions").update({"is_published": False}).eq(
        "agent_id", agent_id
    ).execute()

    # Publicar esta versión
    sb.table("flow_versions").update({"is_published": True}).eq(
        "id", version_id
    ).execute()

    # Actualizar conversation_flow del agente
    sb.table("agents").update(
        {"conversation_flow": version.data[0]["flow_data"]}
    ).eq("id", agent_id).execute()

    return {"ok": True, "version": version.data[0]["version"]}


@router.get("/{client_id}/agents/{agent_id}/flow-versions/{version_id}")
async def get_flow_version(
    client_id: str,
    agent_id: str,
    version_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Obtiene los datos de una versión específica para preview/rollback."""
    _check_access(user, client_id)
    sb = get_supabase()
    result = (
        sb.table("flow_versions")
        .select("*")
        .eq("id", version_id)
        .eq("agent_id", agent_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Versión no encontrada"
        )
    return result.data[0]


@router.delete("/{client_id}/agents/{agent_id}/flow-versions/{version_id}")
async def delete_flow_version(
    client_id: str,
    agent_id: str,
    version_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Elimina una versión de flujo (no permite eliminar la versión publicada)."""
    _check_access(user, client_id)
    sb = get_supabase()

    version = (
        sb.table("flow_versions")
        .select("is_published")
        .eq("id", version_id)
        .eq("agent_id", agent_id)
        .limit(1)
        .execute()
    )
    if not version.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Versión no encontrada"
        )
    if version.data[0].get("is_published"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar la versión publicada",
        )

    sb.table("flow_versions").delete().eq("id", version_id).execute()
    return {"ok": True}
