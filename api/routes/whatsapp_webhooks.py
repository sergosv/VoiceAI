"""Webhooks públicos para mensajería (GHL multi-canal + Evolution WhatsApp)."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request, Response

from api.services.whatsapp.evolution import EvolutionProvider
from api.services.whatsapp.gohighlevel import GoHighLevelProvider
from api.services.whatsapp.service import process_inbound_message

logger = logging.getLogger(__name__)

# Router para Evolution (WhatsApp) — montado en /api/webhooks/whatsapp
router = APIRouter()

# Router para GHL (multi-canal) — montado en /api/webhooks/gohighlevel
ghl_router = APIRouter()

_evo = EvolutionProvider()
_ghl = GoHighLevelProvider()


async def _handle_ghl_webhook(request: Request) -> Response:
    """Procesa webhook de GoHighLevel (todos los canales)."""
    body = await request.body()
    headers = dict(request.headers)

    if not _ghl.validate_webhook(headers, body):
        logger.warning("GHL webhook: firma inválida")
        return Response(status_code=401)

    try:
        payload = await request.json()
    except Exception:
        return Response(status_code=400)

    msg = _ghl.parse_webhook(payload)
    if msg:
        logger.info("GHL webhook: mensaje de %s (canal=%s)", msg.remote_phone, msg.channel)
        asyncio.create_task(_safe_process(msg))

    return Response(status_code=200)


# Ruta principal: /api/webhooks/gohighlevel
@ghl_router.post("")
async def webhook_gohighlevel(request: Request) -> Response:
    """Webhook público para GoHighLevel (multi-canal)."""
    return await _handle_ghl_webhook(request)


# Backwards compatibility: /api/webhooks/whatsapp/gohighlevel
@router.post("/gohighlevel")
async def webhook_gohighlevel_legacy(request: Request) -> Response:
    """Webhook legacy — redirige al handler principal."""
    return await _handle_ghl_webhook(request)


@router.post("/evolution")
async def webhook_evolution(request: Request) -> Response:
    """Webhook público para Evolution API (WhatsApp).

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
        logger.exception("Error procesando mensaje de %s", msg.remote_phone)
