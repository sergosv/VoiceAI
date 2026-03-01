"""Autenticación JWT con Supabase Auth (ES256 JWKS)."""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from dataclasses import dataclass
from functools import lru_cache

import jwt
from jwt import PyJWK
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.deps import get_supabase

logger = logging.getLogger(__name__)
security = HTTPBearer()


@lru_cache(maxsize=1)
def _fetch_jwks() -> dict:
    """Obtiene las JWKS keys del endpoint de Supabase Auth (cacheado)."""
    supabase_url = os.environ["SUPABASE_URL"]
    anon_key = os.environ["SUPABASE_ANON_KEY"]
    url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
    req = urllib.request.Request(url, headers={"apikey": anon_key})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _get_signing_key(token: str) -> PyJWK:
    """Encuentra la key correcta del JWKS por kid."""
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    jwks = _fetch_jwks()
    for key_data in jwks.get("keys", []):
        if key_data.get("kid") == kid:
            return PyJWK(key_data)
    raise jwt.InvalidTokenError(f"Key con kid={kid} no encontrada en JWKS")


@dataclass(frozen=True)
class CurrentUser:
    """Usuario autenticado extraído del JWT."""

    id: str  # users.id (nuestro)
    auth_user_id: str  # Supabase Auth uid
    email: str
    role: str  # 'admin' | 'client'
    client_id: str | None  # NULL para admin


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> CurrentUser:
    """Decodifica JWT de Supabase y busca el usuario en nuestra tabla users."""
    token = credentials.credentials

    try:
        signing_key = _get_signing_key(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated",
            leeway=30,
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
        )
    except jwt.InvalidTokenError as e:
        logger.warning("JWT inválido: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
        )

    auth_uid = payload.get("sub")
    if not auth_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin sub claim",
        )

    # Buscar en nuestra tabla users
    sb = get_supabase()
    result = (
        sb.table("users")
        .select("id, auth_user_id, email, role, client_id, is_active")
        .eq("auth_user_id", auth_uid)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario no registrado en la plataforma",
        )

    user = result.data[0]
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario desactivado",
        )

    return CurrentUser(
        id=str(user["id"]),
        auth_user_id=str(user["auth_user_id"]),
        email=user["email"],
        role=user["role"],
        client_id=str(user["client_id"]) if user.get("client_id") else None,
    )


async def require_admin(
    user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Dependencia que requiere rol admin."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de administrador",
        )
    return user
