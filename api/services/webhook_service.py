"""Servicio de webhooks — entrega de eventos a endpoints suscritos."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
import uuid

import httpx

from api.deps import get_supabase

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAYS = [5, 30, 120]  # segundos entre reintentos

# Almacenar referencias a tasks para evitar garbage collection prematuro
_tasks: set[asyncio.Task] = set()


def _sign_payload(payload: str, secret: str) -> str:
    """Genera firma HMAC-SHA256 del payload."""
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


async def dispatch_event(
    client_id: str,
    event: str,
    payload: dict,
) -> None:
    """Despacha un evento a todos los endpoints suscritos del cliente.

    Se ejecuta async — no bloquea la operación principal.
    """
    sb = get_supabase()
    result = (
        sb.table("webhook_endpoints")
        .select("*")
        .eq("client_id", client_id)
        .eq("is_active", True)
        .execute()
    )
    endpoints = result.data or []
    if not endpoints:
        return

    for ep in endpoints:
        subscribed = ep.get("events") or []
        # Wildcard "*" or exact match or category match (e.g. "call.*" matches "call.completed")
        event_matches = (
            "*" in subscribed
            or event in subscribed
            or any(
                s.endswith(".*") and event.startswith(s[:-2])
                for s in subscribed
            )
        )
        if not event_matches:
            continue

        task = asyncio.create_task(
            _deliver_webhook(ep, event, payload)
        )
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)


async def _deliver_webhook(
    endpoint: dict,
    event: str,
    payload: dict,
    attempt: int = 1,
) -> None:
    """Entrega un webhook con reintentos."""
    sb = get_supabase()
    url = endpoint["url"]
    secret = endpoint.get("secret") or ""

    if not secret:
        logger.warning(
            "Webhook endpoint %s has no secret configured, skipping delivery to %s",
            endpoint.get("id"),
            url,
        )
        return

    body = json.dumps({
        "event": event,
        "timestamp": int(time.time()),
        "delivery_id": str(uuid.uuid4()),
        "data": payload,
    })
    signature = _sign_payload(body, secret)

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": signature,
        "X-Webhook-Event": event,
    }

    status_code = None
    response_body = None
    success = False
    error = None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, content=body, headers=headers)
            status_code = resp.status_code
            response_body = resp.text[:1000]
            success = 200 <= resp.status_code < 300
    except Exception as exc:
        error = str(exc)[:500]
        logger.warning("Webhook delivery failed: %s -> %s (%s)", event, url, error)

    # Determinar status de la entrega
    if success:
        delivery_status = "delivered"
    elif attempt >= MAX_RETRIES:
        delivery_status = "dead_letter"
    else:
        delivery_status = "failed"

    # Log la entrega
    sb.table("webhook_deliveries").insert({
        "endpoint_id": endpoint["id"],
        "event": event,
        "payload": json.loads(body),
        "status_code": status_code,
        "response_body": response_body,
        "attempt": attempt,
        "success": success,
        "error": error,
        "status": delivery_status,
    }).execute()

    if delivery_status == "dead_letter":
        logger.warning(
            "Webhook DLQ: %s -> %s after %d attempts (event=%s)",
            endpoint.get("id"), url, attempt, event,
        )

    # Reintentar si falló
    if not success and attempt < MAX_RETRIES:
        delay = RETRY_DELAYS[attempt - 1] if attempt <= len(RETRY_DELAYS) else 120
        logger.info("Webhook retry %d/%d for %s in %ds", attempt + 1, MAX_RETRIES, url, delay)
        await asyncio.sleep(delay)
        await _deliver_webhook(endpoint, event, payload, attempt + 1)


async def create_webhook_endpoint(
    client_id: str,
    url: str,
    events: list[str],
    description: str | None = None,
) -> dict:
    """Crea un webhook endpoint."""
    import secrets
    secret = secrets.token_hex(32)
    sb = get_supabase()
    result = sb.table("webhook_endpoints").insert({
        "client_id": client_id,
        "url": url,
        "secret": secret,
        "events": events,
        "description": description,
    }).execute()
    row = result.data[0] if result.data else {}
    logger.info("Webhook endpoint creado: %s (%s)", url, events)
    return row


async def list_webhook_endpoints(client_id: str) -> list[dict]:
    """Lista webhook endpoints de un cliente."""
    sb = get_supabase()
    result = (
        sb.table("webhook_endpoints")
        .select("id, client_id, url, events, is_active, description, created_at, updated_at")
        .eq("client_id", client_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


async def update_webhook_endpoint(
    endpoint_id: str,
    client_id: str,
    updates: dict,
) -> dict | None:
    """Actualiza un webhook endpoint."""
    sb = get_supabase()
    result = (
        sb.table("webhook_endpoints")
        .update(updates)
        .eq("id", endpoint_id)
        .eq("client_id", client_id)
        .execute()
    )
    return result.data[0] if result.data else None


async def delete_webhook_endpoint(endpoint_id: str, client_id: str) -> bool:
    """Elimina un webhook endpoint."""
    sb = get_supabase()
    result = (
        sb.table("webhook_endpoints")
        .delete()
        .eq("id", endpoint_id)
        .eq("client_id", client_id)
        .execute()
    )
    return bool(result.data)


async def list_deliveries(
    endpoint_id: str,
    limit: int = 50,
    status_filter: str | None = None,
) -> list[dict]:
    """Lista entregas de un webhook endpoint, opcionalmente filtradas por status."""
    sb = get_supabase()
    query = (
        sb.table("webhook_deliveries")
        .select("*")
        .eq("endpoint_id", endpoint_id)
        .order("delivered_at", desc=True)
        .limit(limit)
    )
    if status_filter:
        query = query.eq("status", status_filter)
    result = query.execute()
    return result.data or []
