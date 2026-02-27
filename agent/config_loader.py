"""Carga configuración de clientes desde Supabase."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from supabase import create_client, Client

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClientConfig:
    """Configuración completa de un cliente para el agente de voz."""

    id: str
    name: str
    slug: str
    business_type: str
    agent_name: str
    language: str
    voice_id: str
    greeting: str
    system_prompt: str
    file_search_store_id: str | None
    tools_enabled: list[str]
    max_call_duration_seconds: int
    transfer_number: str | None
    business_hours: dict | None
    after_hours_message: str | None


def _get_supabase() -> Client:
    """Crea cliente Supabase con service key."""
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


async def load_client_config_by_phone(phone_number: str) -> ClientConfig | None:
    """Carga config de cliente buscando por número de teléfono.

    Busca coincidencia exacta o sin prefijo de país.
    Retorna None si no se encuentra cliente activo.
    """
    sb = _get_supabase()

    # Buscar por número exacto
    result = (
        sb.table("clients")
        .select("*")
        .eq("phone_number", phone_number)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )

    if not result.data:
        # Intentar variantes del número (con/sin +52, etc.)
        clean = phone_number.lstrip("+")
        result = (
            sb.table("clients")
            .select("*")
            .eq("is_active", True)
            .execute()
        )
        # Buscar coincidencia flexible
        for row in result.data:
            db_phone = (row.get("phone_number") or "").lstrip("+")
            if db_phone and (db_phone == clean or clean.endswith(db_phone) or db_phone.endswith(clean)):
                return _row_to_config(row)
        return None

    return _row_to_config(result.data[0])


async def load_client_config_by_slug(slug: str) -> ClientConfig | None:
    """Carga config de cliente por slug."""
    sb = _get_supabase()
    result = (
        sb.table("clients")
        .select("*")
        .eq("slug", slug)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return _row_to_config(result.data[0])


async def load_client_config_by_id(client_id: str) -> ClientConfig | None:
    """Carga config de cliente por UUID."""
    sb = _get_supabase()
    result = (
        sb.table("clients")
        .select("*")
        .eq("id", client_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return _row_to_config(result.data[0])


def _row_to_config(row: dict) -> ClientConfig:
    """Convierte un row de Supabase a ClientConfig."""
    return ClientConfig(
        id=str(row["id"]),
        name=row["name"],
        slug=row["slug"],
        business_type=row.get("business_type", "generic"),
        agent_name=row["agent_name"],
        language=row.get("language", "es"),
        voice_id=row["voice_id"],
        greeting=row["greeting"],
        system_prompt=row["system_prompt"],
        file_search_store_id=row.get("file_search_store_id"),
        tools_enabled=row.get("tools_enabled") or ["search_knowledge"],
        max_call_duration_seconds=row.get("max_call_duration_seconds", 300),
        transfer_number=row.get("transfer_number"),
        business_hours=row.get("business_hours"),
        after_hours_message=row.get("after_hours_message"),
    )
