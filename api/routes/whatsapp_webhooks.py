"""Webhooks públicos para WhatsApp (GHL + Evolution API)."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request, Response

from api.services.whatsapp.evolution import EvolutionProvider
from api.services.whatsapp.gohighlevel import GoHighLevelProvider
from api.services.whatsapp.service import process_inbound_message

logger = logging.getLogger(__name__)

router = APIRouter()

_evo = EvolutionProvider()
_ghl = GoHighLevelProvider()


@router.post("/gohighlevel")
async def webhook_gohighlevel(request: Request) -> Response:
    """Webhook público para GoHighLevel.

    Retorna 200 inmediato y procesa en background.
    """
    body = await request.body()
    headers = dict(request.headers)

    # Validar firma
    if not _ghl.validate_webhook(headers, body):
        logger.warning("GHL webhook: firma inválida")
        return Response(status_code=401)

    try:
        payload = await request.json()
    except Exception:
        return Response(status_code=400)

    msg = _ghl.parse_webhook(payload)
    if msg:
        logger.info("GHL webhook: mensaje de %s", msg.remote_phone)
        asyncio.create_task(_safe_process(msg))

    return Response(status_code=200)


@router.post("/evolution")
async def webhook_evolution(request: Request) -> Response:
    """Webhook público para Evolution API.

    Retorna 200 inmediato y procesa en background.
    """
    try:
        payload = await request.json()
    except Exception:
        return Response(status_code=400)

    msg = _evo.parse_webhook(payload)
    if msg:
        logger.info("Evolution webhook: mensaje de %s (instance=%s)", msg.remote_phone, msg.evo_instance_id)
        asyncio.create_task(_safe_process(msg))

    return Response(status_code=200)


async def _safe_process(msg) -> None:
    """Wrapper para procesar mensaje sin que errores rompan el task."""
    try:
        await process_inbound_message(msg)
    except Exception:
        logger.exception("Error procesando mensaje WhatsApp de %s", msg.remote_phone)
