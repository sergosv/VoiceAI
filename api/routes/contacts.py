"""Rutas CRUD de contactos."""

from __future__ import annotations

import asyncio
import csv
import io
from datetime import datetime, timezone

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse

from api.deps import get_supabase
from api.middleware.auth import CurrentUser, get_current_user
from api.schemas import (
    ContactCreateRequest,
    ContactOut,
    ContactUpdateRequest,
    IdentifierCreateRequest,
    IdentifierOut,
    MemoryOut,
    MessageResponse,
)
from agent.phone_utils import normalize_phone
from api.services.webhook_service import dispatch_event

router = APIRouter()


@router.get("", response_model=list[ContactOut])
async def list_contacts(
    user: CurrentUser = Depends(get_current_user),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = None,
    source: str | None = None,
    client_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[ContactOut]:
    """Lista contactos con búsqueda y paginación."""
    sb = get_supabase()
    query = sb.table("contacts").select("*").order("created_at", desc=True)

    # Multi-tenancy
    if user.role == "client":
        if not user.client_id:
            return []
        query = query.eq("client_id", user.client_id)
    elif client_id:
        query = query.eq("client_id", client_id)

    if source:
        query = query.eq("source", source)

    if date_from:
        query = query.gte("created_at", f"{date_from}T00:00:00")
    if date_to:
        query = query.lte("created_at", f"{date_to}T23:59:59")

    if search:
        import re
        safe_search = re.sub(r'[,.()*%:!]', '', search)
        query = query.or_(f"name.ilike.%{safe_search}%,phone.ilike.%{safe_search}%,email.ilike.%{safe_search}%")

    offset = (page - 1) * per_page
    query = query.range(offset, offset + per_page - 1)

    result = query.execute()
    return [ContactOut(**row) for row in result.data]


@router.get("/export/csv")
async def export_contacts_csv(
    user: CurrentUser = Depends(get_current_user),
    client_id: str | None = None,
) -> Response:
    """Exporta contactos a CSV."""
    sb = get_supabase()
    query = sb.table("contacts").select("*").order("created_at", desc=True)

    if user.role == "client":
        if not user.client_id:
            return StreamingResponse(io.StringIO(""), media_type="text/csv")
        query = query.eq("client_id", user.client_id)
    elif client_id:
        query = query.eq("client_id", client_id)

    query = query.limit(10000)
    result = query.execute()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Nombre", "Teléfono", "Email", "Fuente",
        "Llamadas", "Tags", "Notas", "Creado",
    ])
    for row in result.data:
        tags = ", ".join(row.get("tags") or [])
        writer.writerow([
            row.get("name", ""),
            row.get("phone", ""),
            row.get("email", ""),
            row.get("source", ""),
            row.get("call_count", 0),
            tags,
            row.get("notes", ""),
            row.get("created_at", ""),
        ])

    output.seek(0)
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=contactos_{today_str}.csv"},
    )


@router.post("/import/csv")
async def import_contacts_csv(
    file: UploadFile,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Importa contactos desde un archivo CSV."""
    logger = logging.getLogger("api.contacts.import")

    effective_client_id = user.client_id
    if not effective_client_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="client_id requerido")

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo debe ser CSV")

    # Leer y decodificar el archivo
    try:
        raw = await file.read()
        content = raw.decode("utf-8-sig")  # utf-8-sig maneja BOM de Excel
    except UnicodeDecodeError:
        try:
            content = raw.decode("latin-1")
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se pudo leer el archivo CSV")

    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV vacío o sin encabezados")

    # Normalizar nombres de columnas (minúsculas, sin espacios)
    field_map: dict[str, str] = {}
    for f in reader.fieldnames:
        normalized = f.strip().lower()
        if normalized in ("nombre", "name"):
            field_map[f] = "name"
        elif normalized in ("telefono", "teléfono", "phone"):
            field_map[f] = "phone"
        elif normalized in ("email", "correo"):
            field_map[f] = "email"
        elif normalized in ("notas", "notes"):
            field_map[f] = "notes"
        elif normalized in ("tags", "etiquetas"):
            field_map[f] = "tags"

    sb = get_supabase()
    imported = 0
    skipped = 0
    errors: list[str] = []
    max_rows = 1000

    for i, raw_row in enumerate(reader):
        if i >= max_rows:
            errors.append(f"Se alcanzó el límite de {max_rows} filas. Filas restantes ignoradas.")
            break

        # Mapear columnas
        row: dict[str, str] = {}
        for original_key, mapped_key in field_map.items():
            val = raw_row.get(original_key, "").strip()
            if val:
                row[mapped_key] = val

        phone = row.get("phone", "")
        if not phone:
            skipped += 1
            continue

        try:
            normalized = normalize_phone(phone)
        except Exception:
            normalized = phone

        # Parsear tags
        tags: list[str] = []
        if row.get("tags"):
            tags = [t.strip() for t in row["tags"].split(",") if t.strip()]

        data = {
            "client_id": effective_client_id,
            "phone": normalized,
            "name": row.get("name", ""),
            "email": row.get("email", ""),
            "notes": row.get("notes", ""),
            "tags": tags,
            "source": "csv_import",
            "call_count": 0,
        }

        try:
            sb.table("contacts").insert(data).execute()
            imported += 1
        except Exception as exc:
            exc_str = str(exc)
            if "duplicate" in exc_str.lower() or "unique" in exc_str.lower() or "23505" in exc_str:
                skipped += 1
            else:
                row_num = i + 2  # +2: header + 0-index
                errors.append(f"Fila {row_num} ({phone}): {exc_str[:100]}")
                logger.warning("Error importando fila %d: %s", row_num, exc_str)

    logger.info(
        "CSV import: client=%s imported=%d skipped=%d errors=%d",
        effective_client_id, imported, skipped, len(errors),
    )
    return {"imported": imported, "skipped": skipped, "errors": errors}


@router.get("/{contact_id}", response_model=ContactOut)
async def get_contact(
    contact_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> ContactOut:
    """Obtiene un contacto por ID."""
    sb = get_supabase()
    result = sb.table("contacts").select("*").eq("id", contact_id).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contacto no encontrado")

    contact = result.data[0]
    if user.role == "client" and contact.get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    return ContactOut(**contact)


@router.post("", response_model=ContactOut, status_code=201)
async def create_contact(
    req: ContactCreateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> ContactOut:
    """Crea un contacto manualmente."""
    effective_client_id = user.client_id
    if user.role == "admin":
        effective_client_id = user.client_id  # Admin usa su propio client o recibe en query
    if not effective_client_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="client_id requerido")

    sb = get_supabase()
    normalized = normalize_phone(req.phone)

    # Check de duplicado
    existing = (
        sb.table("contacts").select("id")
        .eq("client_id", effective_client_id)
        .eq("phone", normalized)
        .limit(1)
        .execute()
    )
    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un contacto con ese teléfono",
        )

    data = {
        "client_id": effective_client_id,
        "phone": normalized,
        "name": req.name,
        "email": req.email,
        "notes": req.notes,
        "tags": req.tags,
        "source": "manual",
        "call_count": 0,
    }
    result = sb.table("contacts").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creando contacto")
    contact_out = ContactOut(**result.data[0])
    # Webhook: contact.created
    asyncio.create_task(dispatch_event(effective_client_id, "contact.created", result.data[0]))
    return contact_out


@router.patch("/{contact_id}", response_model=ContactOut)
async def update_contact(
    contact_id: str,
    req: ContactUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> ContactOut:
    """Actualiza un contacto."""
    sb = get_supabase()

    # Verificar acceso
    existing = sb.table("contacts").select("client_id").eq("id", contact_id).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contacto no encontrado")
    if user.role == "client" and existing.data[0].get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    updates = req.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sin cambios")

    result = sb.table("contacts").update(updates).eq("id", contact_id).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contacto no encontrado")
    contact_out = ContactOut(**result.data[0])
    # Webhook: contact.updated
    client_id_for_webhook = result.data[0].get("client_id") or existing.data[0].get("client_id")
    if client_id_for_webhook:
        asyncio.create_task(dispatch_event(client_id_for_webhook, "contact.updated", result.data[0]))
    return contact_out


@router.delete("/{contact_id}", response_model=MessageResponse)
async def delete_contact(
    contact_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> MessageResponse:
    """Elimina un contacto y todo su historial (llamadas, memorias, identificadores, citas)."""
    sb = get_supabase()

    existing = sb.table("contacts").select("client_id, phone").eq("id", contact_id).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contacto no encontrado")

    row = existing.data[0]
    if user.role == "client" and row.get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    client_id = row["client_id"]
    phone = row.get("phone")

    # Borrar llamadas asociadas (por teléfono)
    if phone:
        sb.table("calls").delete().eq("client_id", client_id).or_(
            f"caller_number.eq.{phone},callee_number.eq.{phone}"
        ).execute()

    # Borrar citas del contacto
    sb.table("appointments").delete().eq("contact_id", contact_id).execute()

    # Borrar campaign_calls por teléfono (scoped por client_id via campaign)
    if phone:
        campaigns = sb.table("campaigns").select("id").eq("client_id", client_id).execute()
        if campaigns.data:
            campaign_ids = [c["id"] for c in campaigns.data]
            for cid in campaign_ids:
                sb.table("campaign_calls").delete().eq("campaign_id", cid).eq("phone", phone).execute()

    # contact_identifiers y memories se borran por CASCADE
    sb.table("contacts").delete().eq("id", contact_id).execute()
    # Webhook: contact.deleted
    asyncio.create_task(dispatch_event(client_id, "contact.deleted", {"id": contact_id, "phone": phone}))
    return MessageResponse(message="Contacto y su historial eliminados")


@router.get("/{contact_id}/calls")
async def get_contact_calls(
    contact_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    """Historial de llamadas de un contacto (por número de teléfono)."""
    sb = get_supabase()

    contact = sb.table("contacts").select("phone, client_id").eq("id", contact_id).limit(1).execute()
    if not contact.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contacto no encontrado")

    row = contact.data[0]
    if user.role == "client" and row.get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    calls = (
        sb.table("calls")
        .select(
            "id, direction, caller_number, callee_number, duration_seconds, "
            "cost_total, status, summary, started_at, sentimiento, resumen_ia, lead_score"
        )
        .eq("client_id", row["client_id"])
        .or_(f"caller_number.eq.{row['phone']},callee_number.eq.{row['phone']}")
        .order("started_at", desc=True)
        .limit(50)
        .execute()
    )
    return calls.data


@router.get("/{contact_id}/timeline")
async def get_contact_timeline(
    contact_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Timeline unificado del contacto: llamadas, citas, campañas."""
    sb = get_supabase()

    contact = sb.table("contacts").select("phone, client_id").eq("id", contact_id).limit(1).execute()
    if not contact.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contacto no encontrado")

    row = contact.data[0]
    if user.role == "client" and row.get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    phone = row["phone"]
    cid = row["client_id"]

    # Llamadas con análisis
    calls = (
        sb.table("calls")
        .select(
            "id, direction, caller_number, callee_number, duration_seconds, "
            "cost_total, status, summary, started_at, sentimiento, resumen_ia, lead_score, intencion"
        )
        .eq("client_id", cid)
        .or_(f"caller_number.eq.{phone},callee_number.eq.{phone}")
        .order("started_at", desc=True)
        .limit(50)
        .execute()
    )

    # Citas del contacto
    appointments = (
        sb.table("appointments")
        .select("id, title, description, start_time, end_time, status, created_at")
        .eq("contact_id", contact_id)
        .order("start_time", desc=True)
        .limit(50)
        .execute()
    )

    # Campaign calls por teléfono (scoped por client_id via campaigns)
    client_campaigns = sb.table("campaigns").select("id").eq("client_id", cid).execute()
    campaign_ids_for_calls = [c["id"] for c in (client_campaigns.data or [])]

    if campaign_ids_for_calls:
        campaign_calls_raw = (
            sb.table("campaign_calls")
            .select("id, campaign_id, phone, status, result_summary, analysis_data, created_at")
            .eq("phone", phone)
            .in_("campaign_id", campaign_ids_for_calls)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
    else:
        # Sin campañas del cliente, no hay campaign_calls
        class _Empty:
            data = []
        campaign_calls_raw = _Empty()

    # Enriquecer campaign_calls con nombre de campaña
    campaign_calls = campaign_calls_raw.data or []
    campaign_ids = list({cc["campaign_id"] for cc in campaign_calls if cc.get("campaign_id")})
    campaign_names: dict[str, str] = {}
    if campaign_ids:
        campaigns = (
            sb.table("campaigns")
            .select("id, name")
            .in_("id", campaign_ids)
            .execute()
        )
        campaign_names = {c["id"]: c["name"] for c in (campaigns.data or [])}
    for cc in campaign_calls:
        cc["campaign_name"] = campaign_names.get(cc.get("campaign_id", ""), "")

    # Summary
    total_calls = len(calls.data or [])
    total_appointments = len(appointments.data or [])
    last_contact_date = None
    if calls.data:
        last_contact_date = calls.data[0].get("started_at")

    next_appointment = None
    for apt in reversed(appointments.data or []):
        if apt.get("status") in ("confirmed", "pending"):
            next_appointment = apt.get("start_time")
            break

    return {
        "calls": calls.data or [],
        "appointments": appointments.data or [],
        "campaign_calls": campaign_calls,
        "summary": {
            "total_calls": total_calls,
            "total_appointments": total_appointments,
            "last_contact_date": last_contact_date,
            "next_appointment": next_appointment,
        },
    }


@router.get("/{contact_id}/conversations")
async def get_contact_conversations(
    contact_id: str,
    user: CurrentUser = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    """Conversaciones (WhatsApp + GHL) de un contacto."""
    sb = get_supabase()

    contact = sb.table("contacts").select("client_id").eq("id", contact_id).limit(1).execute()
    if not contact.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contacto no encontrado")
    if user.role == "client" and contact.data[0].get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    conversations: list[dict] = []

    # WhatsApp conversations
    wa = (
        sb.table("whatsapp_conversations")
        .select("id, config_id, remote_phone, status, message_count, last_message_at, created_at, summary, result, closed_by")
        .eq("contact_id", contact_id)
        .order("last_message_at", desc=True)
        .limit(limit)
        .execute()
    )
    for row in wa.data or []:
        row["channel"] = "whatsapp"
        conversations.append(row)

    # GHL conversations
    ghl = (
        sb.table("ghl_conversations")
        .select("id, config_id, channel, status, message_count, last_message_at, created_at, summary, result, closed_by")
        .eq("contact_id", contact_id)
        .order("last_message_at", desc=True)
        .limit(limit)
        .execute()
    )
    for row in ghl.data or []:
        row["channel"] = row.get("channel") or "ghl"
        conversations.append(row)

    # Ordenar por fecha más reciente
    conversations.sort(key=lambda c: c.get("last_message_at") or c.get("created_at") or "", reverse=True)

    return conversations[:limit]


@router.get("/{contact_id}/memories", response_model=list[MemoryOut])
async def get_contact_memories(
    contact_id: str,
    user: CurrentUser = Depends(get_current_user),
    channel: str | None = None,
    limit: int = Query(20, ge=1, le=100),
) -> list[MemoryOut]:
    """Obtiene las memorias de un contacto, opcionalmente filtradas por canal."""
    sb = get_supabase()

    # Verificar acceso
    contact = sb.table("contacts").select("client_id").eq("id", contact_id).limit(1).execute()
    if not contact.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contacto no encontrado")
    if user.role == "client" and contact.data[0].get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    query = (
        sb.table("memories")
        .select("id, summary, channel, agent_name, duration_seconds, sentiment, topics, action_items, extracted_data, created_at")
        .eq("contact_id", contact_id)
        .order("created_at", desc=True)
        .limit(limit)
    )
    if channel:
        query = query.eq("channel", channel)

    result = query.execute()
    return [MemoryOut(**row) for row in (result.data or [])]


@router.get("/{contact_id}/identifiers", response_model=list[IdentifierOut])
async def get_contact_identifiers(
    contact_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> list[IdentifierOut]:
    """Lista todos los identificadores de un contacto."""
    sb = get_supabase()

    contact = sb.table("contacts").select("client_id").eq("id", contact_id).limit(1).execute()
    if not contact.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contacto no encontrado")
    if user.role == "client" and contact.data[0].get("client_id") != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    result = (
        sb.table("contact_identifiers")
        .select("id, identifier_type, identifier_value, is_primary, is_verified, created_at")
        .eq("contact_id", contact_id)
        .order("created_at")
        .execute()
    )
    return [IdentifierOut(**row) for row in (result.data or [])]


@router.post("/{contact_id}/identifiers", response_model=IdentifierOut, status_code=201)
async def add_contact_identifier(
    contact_id: str,
    req: IdentifierCreateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> IdentifierOut:
    """Vincula un nuevo identificador a un contacto."""
    sb = get_supabase()

    contact = sb.table("contacts").select("client_id").eq("id", contact_id).limit(1).execute()
    if not contact.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contacto no encontrado")

    client_id = contact.data[0]["client_id"]
    if user.role == "client" and client_id != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    # Verificar que no exista ya
    existing = (
        sb.table("contact_identifiers")
        .select("id")
        .eq("client_id", client_id)
        .eq("identifier_type", req.identifier_type)
        .eq("identifier_value", req.identifier_value)
        .limit(1)
        .execute()
    )
    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un identificador con ese tipo y valor",
        )

    data = {
        "client_id": client_id,
        "contact_id": contact_id,
        "identifier_type": req.identifier_type,
        "identifier_value": req.identifier_value,
    }
    result = sb.table("contact_identifiers").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creando identificador")
    return IdentifierOut(**result.data[0])
