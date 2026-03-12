"""Rutas de autenticación."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from supabase import create_client as create_supabase_client

from datetime import datetime, timezone

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


@router.get("/profile")
@limiter.limit("60/minute")
async def get_profile(request: Request, user: CurrentUser = Depends(get_current_user)) -> dict:
    """Retorna perfil completo del usuario con datos del cliente."""
    sb = get_supabase()
    result = (
        sb.table("users")
        .select("id, email, role, client_id, display_name, timezone, language")
        .eq("id", user.id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    row = result.data[0]

    # Obtener nombre del cliente si existe
    client_name = None
    if row.get("client_id"):
        client_result = (
            sb.table("clients")
            .select("name")
            .eq("id", row["client_id"])
            .limit(1)
            .execute()
        )
        if client_result.data:
            client_name = client_result.data[0]["name"]

    return {
        "id": str(row["id"]),
        "email": row["email"],
        "role": row["role"],
        "client_id": str(row["client_id"]) if row.get("client_id") else None,
        "client_name": client_name,
        "display_name": row.get("display_name"),
        "timezone": row.get("timezone", "America/Mexico_City"),
        "language": row.get("language", "es"),
    }


@router.patch("/profile")
@limiter.limit("30/minute")
async def update_profile(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Actualiza perfil del usuario (display_name, timezone, language)."""
    body = await request.json()
    sb = get_supabase()

    allowed_fields = {"display_name", "timezone", "language"}
    updates: dict = {}
    for field in allowed_fields:
        if field in body:
            value = body[field]
            if not isinstance(value, str) or len(value) > 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Campo '{field}' inválido",
                )
            updates[field] = value.strip()

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se proporcionaron campos para actualizar",
        )

    # Validar timezone
    if "timezone" in updates:
        import zoneinfo
        try:
            zoneinfo.ZoneInfo(updates["timezone"])
        except (KeyError, Exception):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Zona horaria inválida",
            )

    # Validar language
    if "language" in updates and updates["language"] not in ("es", "en"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idioma debe ser 'es' o 'en'",
        )

    sb.table("users").update(updates).eq("id", user.id).execute()
    return {"ok": True}


@router.post("/change-password", response_model=MessageResponse)
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
) -> MessageResponse:
    """Cambia la contraseña del usuario e invalida sesiones previas."""
    body = await request.json()
    new_password = body.get("new_password", "")

    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña debe tener al menos 8 caracteres",
        )

    # Actualizar password en Supabase Auth
    sb_admin = create_supabase_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )
    try:
        sb_admin.auth.admin.update_user_by_id(
            user.auth_user_id,
            {"password": new_password},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error actualizando contraseña: {e}",
        )

    # Marcar timestamp para invalidar tokens previos
    sb = get_supabase()
    sb.table("users").update({
        "password_changed_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", user.id).execute()

    return MessageResponse(message="Contraseña actualizada. Inicia sesión de nuevo.")


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
