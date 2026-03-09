"""Webhook dispatch para el runtime del agente (LiveKit Cloud).

Versión standalone que no depende de api.services.webhook_service,
ya que el agente corre en un proceso separado (LiveKit Cloud).
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone

import httpx

from agent.db import get_supabase

logger = logging.getLogger(__name__)

RETRY_DELAYS = [5, 30, 120]


async def dispatch_event(client_id: str, event: str, payload: dict) -> None:
    """Despacha un evento a todos los webhook endpoints suscritos del cliente."""
    try:
        sb = get_supabase()
        result = (
            sb.table("webhook_endpoints")
            .select("id, url, secret, events")
            .eq("client_id", client_id)
            .eq("is_active", True)
            .execute()
        )

        endpoints = result.data or []

        for ep in endpoints:
            subscribed = ep.get("events") or []
            if not _event_matches(event, subscribed):
                continue
            asyncio.create_task(
                _deliver(ep["id"], ep["url"], ep["secret"], client_id, event, payload)
            )
    except Exception:
        logger.exception("Error dispatching webhook event %s", event)


def _event_matches(event: str, subscribed: list[str]) -> bool:
    """Verifica si un evento coincide con la lista de suscripciones."""
    for sub in subscribed:
        if sub == "*" or sub == event:
            return True
        if sub.endswith(".*") and event.startswith(sub[:-1]):
            return True
    return False


async def _deliver(
    endpoint_id: str,
    url: str,
    secret: str,
    client_id: str,
    event: str,
    payload: dict,
) -> None:
    """Entrega un webhook con reintentos."""
    body = json.dumps(
        {
            "event": event,
            "timestamp": int(time.time()),
            "data": payload,
        },
        default=str,
    )

    signature = hmac.new(
        secret.encode(), body.encode(), hashlib.sha256
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": signature,
        "X-Webhook-Event": event,
    }

    sb = get_supabase()

    for attempt in range(len(RETRY_DELAYS) + 1):
        status_code = 0
        error_msg = None
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, content=body, headers=headers)
                status_code = resp.status_code
                if 200 <= status_code < 300:
                    # Log success
                    try:
                        sb.table("webhook_deliveries").insert(
                            {
                                "endpoint_id": endpoint_id,
                                "event": event,
                                "payload": json.loads(body),
                                "status_code": status_code,
                                "success": True,
                                "attempt": attempt + 1,
                            }
                        ).execute()
                    except Exception:
                        logger.exception("Error logging webhook delivery success")
                    return
                error_msg = resp.text[:500]
        except Exception as e:
            error_msg = str(e)[:500]

        # Log failed attempt
        try:
            sb.table("webhook_deliveries").insert(
                {
                    "endpoint_id": endpoint_id,
                    "event": event,
                    "payload": json.loads(body),
                    "status_code": status_code,
                    "success": False,
                    "attempt": attempt + 1,
                    "error": error_msg,
                }
            ).execute()
        except Exception:
            pass

        if attempt < len(RETRY_DELAYS):
            await asyncio.sleep(RETRY_DELAYS[attempt])
