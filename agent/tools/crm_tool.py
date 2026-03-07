"""Herramienta CRM para capturar y actualizar contactos desde el agente de voz."""

from __future__ import annotations

import logging
import os

from supabase import Client

from agent.db import get_supabase

logger = logging.getLogger(__name__)


def _get_supabase() -> Client:
    return get_supabase()


async def save_contact(
    client_id: str,
    phone: str,
    name: str | None = None,
    email: str | None = None,
    notes: str | None = None,
    source: str = "inbound_call",
) -> str:
    """Guarda o actualiza un contacto en la base de datos.

    Hace upsert por (client_id, phone) para evitar duplicados.
    """
    data: dict = {
        "client_id": client_id,
        "phone": phone,
        "source": source,
    }
    if name:
        data["name"] = name
    if email:
        data["email"] = email
    if notes:
        data["notes"] = notes

    try:
        sb = _get_supabase()
        result = (
            sb.table("contacts")
            .upsert(data, on_conflict="client_id,phone")
            .execute()
        )
        if result.data:
            contact_name = result.data[0].get("name") or phone
            logger.info("Contacto guardado: %s para client %s", contact_name, client_id)
            return f"Contacto '{contact_name}' guardado exitosamente."
        return "No se pudo guardar el contacto."
    except Exception as e:
        logger.error("Error guardando contacto: %s", e)
        return "Hubo un error al guardar la información del contacto."


async def update_contact_notes(
    client_id: str,
    phone: str,
    notes: str,
) -> str:
    """Actualiza las notas de un contacto existente."""
    try:
        sb = _get_supabase()
        result = (
            sb.table("contacts")
            .update({"notes": notes})
            .eq("client_id", client_id)
            .eq("phone", phone)
            .execute()
        )
        if result.data:
            return "Notas del contacto actualizadas."
        return "No se encontró el contacto para actualizar."
    except Exception as e:
        logger.error("Error actualizando notas de contacto: %s", e)
        return "Hubo un error al actualizar las notas."
