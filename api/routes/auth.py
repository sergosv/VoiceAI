"""Rutas de autenticación."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from supabase import create_client as create_supabase_client

from api.deps import get_supabase
from api.middleware.auth import CurrentUser, get_current_user, require_admin
from api.schemas import MessageResponse, RegisterUserRequest, UserOut

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.get("/me", response_model=UserOut)
@limiter.limit("60/minute")
async def get_me(request: Request, user: CurrentUser = Depends(get_current_user)) -> UserOut:
    """Retorna datos del usuario autenticado."""
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role,
        client_id=user.client_id,
        display_name=None,
    )


@router.post("/register-user", response_model=UserOut, status_code=201)
@limiter.limit("10/minute")
async def register_user(
    request: Request,
    req: RegisterUserRequest,
    admin: CurrentUser = Depends(require_admin),
) -> UserOut:
    """Registra un nuevo usuario (solo admin).

    Crea el usuario en Supabase Auth y en nuestra tabla users.
    """
    # Crear en Supabase Auth
    sb_admin = create_supabase_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )
    try:
        auth_response = sb_admin.auth.admin.create_user({
            "email": req.email,
            "password": req.password,
            "email_confirm": True,
        })
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creando usuario en Auth: {e}",
        )

    auth_uid = auth_response.user.id

    # Insertar en nuestra tabla users
    sb = get_supabase()
    data = {
        "auth_user_id": str(auth_uid),
        "email": req.email,
        "role": req.role,
        "client_id": req.client_id,
        "display_name": req.display_name,
    }
    result = sb.table("users").insert(data).execute()
    row = result.data[0]

    return UserOut(
        id=str(row["id"]),
        email=row["email"],
        role=row["role"],
        client_id=str(row["client_id"]) if row.get("client_id") else None,
        display_name=row.get("display_name"),
    )
