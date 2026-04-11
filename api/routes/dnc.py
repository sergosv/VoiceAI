"""Endpoints para la lista Do-Not-Call (DNC)."""

from __future__ import annotations

import csv
import io
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.phone_utils import normalize_phone
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
    search: str | None = Query(None, description="Buscar por teléfono"),
):
    """Lista números en DNC del cliente con búsqueda opcional."""
    sb = get_supabase()
    client_id = user.impersonating_client_id or user.client_id

    query = sb.table("dnc_entries").select("*", count="exact").order("created_at", desc=True)
    if client_id:
        query = query.eq("client_id", client_id)
    if search and search.strip():
        # Solo dígitos para match con formato E.164 guardado
        digits_only = "".join(c for c in search if c.isdigit())
        if digits_only:
            query = query.ilike("phone", f"%{digits_only}%")

    offset = (page - 1) * per_page
    result = query.range(offset, offset + per_page - 1).execute()

    return {
        "data": result.data or [],
        "total": result.count or 0,
        "page": page,
        "per_page": per_page,
    }


@router.get("/export")
async def export_dnc(user: CurrentUser = Depends(get_current_user)):
    """Exporta toda la lista DNC como CSV."""
    sb = get_supabase()
    client_id = user.impersonating_client_id or user.client_id

    query = sb.table("dnc_entries").select("*").order("created_at", desc=True)
    if client_id:
        query = query.eq("client_id", client_id)
    result = query.execute()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["phone", "reason", "source", "created_at"])
    for row in result.data or []:
        writer.writerow([
            row.get("phone", ""),
            row.get("reason", "") or "",
            row.get("source", ""),
            row.get("created_at", ""),
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dnc_list.csv"},
    )


class DNCBulkImport(BaseModel):
    phones: list[str]
    reason: str | None = None


@router.post("/bulk")
async def bulk_add_dnc(
    body: DNCBulkImport,
    user: CurrentUser = Depends(get_current_user),
):
    """Agrega múltiples números a la lista DNC."""
    sb = get_supabase()
    client_id = user.impersonating_client_id or user.client_id
    if not client_id:
        raise HTTPException(status_code=400, detail="Se requiere client_id")

    entries = []
    for phone in body.phones:
        phone = phone.strip()
        if not phone:
            continue
        entries.append({
            "client_id": client_id,
            "phone": normalize_phone(phone),
            "reason": body.reason or "Import masivo",
            "source": "import",
            "added_by": user.auth_uid,
        })

    if not entries:
        raise HTTPException(status_code=400, detail="Sin números válidos")

    sb.table("dnc_entries").upsert(entries, on_conflict="client_id,phone").execute()
    return {"ok": True, "added": len(entries)}


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

    normalized = normalize_phone(entry.phone)
    result = sb.table("dnc_entries").upsert({
        "client_id": client_id,
        "phone": normalized,
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

    normalized = normalize_phone(phone)
    result = sb.table("dnc_entries").select("id").eq(
        "client_id", client_id
    ).eq("phone", normalized).limit(1).execute()

    return {"blocked": bool(result.data), "phone": normalized}
