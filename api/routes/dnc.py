"""Endpoints para la lista Do-Not-Call (DNC)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.deps import get_supabase
from api.middleware.auth import CurrentUser, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


class DNCEntry(BaseModel):
    phone: str
    reason: str | None = None


class DNCOut(BaseModel):
    id: str
    phone: str
    reason: str | None
    source: str
    created_at: str


@router.get("")
async def list_dnc(
    user: CurrentUser = Depends(get_current_user),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    """Lista números en DNC del cliente."""
    sb = get_supabase()
    client_id = user.impersonating_client_id or user.client_id

    query = sb.table("dnc_entries").select("*", count="exact").order("created_at", desc=True)
    if client_id:
        query = query.eq("client_id", client_id)

    offset = (page - 1) * per_page
    result = query.range(offset, offset + per_page - 1).execute()

    return {
        "data": result.data or [],
        "total": result.count or 0,
        "page": page,
        "per_page": per_page,
    }


@router.post("")
async def add_dnc(
    entry: DNCEntry,
    user: CurrentUser = Depends(get_current_user),
):
    """Agrega un número a la lista DNC."""
    sb = get_supabase()
    client_id = user.impersonating_client_id or user.client_id
    if not client_id:
        raise HTTPException(status_code=400, detail="Se requiere client_id")

    result = sb.table("dnc_entries").upsert({
        "client_id": client_id,
        "phone": entry.phone,
        "reason": entry.reason or "Agregado manualmente",
        "source": "manual",
        "added_by": user.auth_uid,
    }, on_conflict="client_id,phone").execute()

    return {"ok": True, "data": result.data[0] if result.data else None}


@router.delete("/{dnc_id}")
async def remove_dnc(
    dnc_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Elimina un número de la lista DNC."""
    sb = get_supabase()
    client_id = user.impersonating_client_id or user.client_id

    query = sb.table("dnc_entries").delete().eq("id", dnc_id)
    if client_id:
        query = query.eq("client_id", client_id)

    query.execute()
    return {"ok": True}


@router.get("/check/{phone}")
async def check_dnc(
    phone: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Verifica si un número está en DNC."""
    sb = get_supabase()
    client_id = user.impersonating_client_id or user.client_id
    if not client_id:
        return {"blocked": False}

    result = sb.table("dnc_entries").select("id").eq(
        "client_id", client_id
    ).eq("phone", phone).limit(1).execute()

    return {"blocked": bool(result.data), "phone": phone}
