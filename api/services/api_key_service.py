"""Servicio de API keys para la Public API."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timezone

from api.deps import get_supabase

logger = logging.getLogger(__name__)

PREFIX = "vai_"  # Voice AI prefix


def generate_api_key() -> tuple[str, str, str]:
    """Genera una API key.

    Returns:
        (full_key, key_prefix, key_hash)
    """
    raw = secrets.token_urlsafe(32)
    full_key = f"{PREFIX}{raw}"
    key_prefix = full_key[:12]
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, key_prefix, key_hash


def hash_api_key(key: str) -> str:
    """Calcula el hash SHA-256 de una API key."""
    return hashlib.sha256(key.encode()).hexdigest()


async def create_api_key(
    client_id: str,
    name: str,
    scopes: list[str] | None = None,
    expires_at: str | None = None,
) -> dict:
    """Crea una nueva API key y retorna los datos (incluyendo key en texto plano, solo esta vez)."""
    full_key, key_prefix, key_hash = generate_api_key()
    sb = get_supabase()
    data = {
        "client_id": client_id,
        "name": name,
        "key_prefix": key_prefix,
        "key_hash": key_hash,
        "scopes": scopes or [],
    }
    if expires_at:
        data["expires_at"] = expires_at
    result = sb.table("api_keys").insert(data).execute()
    row = result.data[0] if result.data else {}
    row["key"] = full_key  # Solo se muestra una vez
    logger.info("API key creada: %s (%s) para client %s", name, key_prefix, client_id)
    return row


async def resolve_api_key(key: str) -> dict | None:
    """Resuelve una API key a su registro en DB. Retorna None si inválida/expirada."""
    key_hash = hash_api_key(key)
    sb = get_supabase()
    result = (
        sb.table("api_keys")
        .select("*")
        .eq("key_hash", key_hash)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    row = result.data[0]

    # Verificar expiración
    if row.get("expires_at"):
        expires = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
        if expires < datetime.now(timezone.utc):
            return None

    # Actualizar last_used_at
    sb.table("api_keys").update({
        "last_used_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", row["id"]).execute()

    return row


async def list_api_keys(client_id: str) -> list[dict]:
    """Lista API keys de un cliente (sin hashes)."""
    sb = get_supabase()
    result = (
        sb.table("api_keys")
        .select("id, client_id, name, key_prefix, scopes, is_active, last_used_at, expires_at, created_at")
        .eq("client_id", client_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


async def revoke_api_key(key_id: str, client_id: str) -> bool:
    """Revoca (desactiva) una API key."""
    sb = get_supabase()
    result = (
        sb.table("api_keys")
        .update({"is_active": False})
        .eq("id", key_id)
        .eq("client_id", client_id)
        .execute()
    )
    if result.data:
        logger.info("API key revocada: %s", key_id)
        return True
    return False


async def delete_api_key(key_id: str, client_id: str) -> bool:
    """Elimina permanentemente una API key."""
    sb = get_supabase()
    result = (
        sb.table("api_keys")
        .delete()
        .eq("id", key_id)
        .eq("client_id", client_id)
        .execute()
    )
    if result.data:
        logger.info("API key eliminada: %s", key_id)
        return True
    return False
