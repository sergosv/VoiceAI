"""Autenticación por API Key (X-API-Key header) para la Public API v1."""

from __future__ import annotations

from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from api.services.api_key_service import resolve_api_key

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key_client(
    request: Request,
    api_key: str | None = Security(api_key_header),
) -> dict:
    """Dependency que resuelve la API key y retorna el registro.

    Returns:
        dict con client_id, scopes, etc.

    Raises:
        HTTPException 401 si la key es inválida o falta.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key requerida. Usa el header X-API-Key.",
        )
    record = await resolve_api_key(api_key)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida o expirada.",
        )
    return record


def require_scope(scope: str):
    """Factory que retorna un dependency que verifica que la API key tenga el scope requerido."""

    async def _check(api_key_record: dict = Security(get_api_key_client)) -> dict:
        scopes = api_key_record.get("scopes") or []
        if scopes and scope not in scopes and "*" not in scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Scope '{scope}' requerido. Tu key tiene: {scopes}",
            )
        return api_key_record

    return _check
