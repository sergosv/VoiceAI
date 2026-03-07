"""Webhooks de pago — reciben confirmaciones de Stripe/MercadoPago y acreditan créditos.

IMPORTANTE: Estos endpoints son públicos (sin auth) para que Stripe/MP los llamen.
La seguridad depende de la verificación de firma del proveedor.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os

from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.deps import get_supabase

router = APIRouter()
logger = logging.getLogger("webhooks")
limiter = Limiter(key_func=get_remote_address)

STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
MERCADOPAGO_WEBHOOK_SECRET = os.environ.get("MERCADOPAGO_WEBHOOK_SECRET")


@router.post("/stripe")
@limiter.limit("30/minute")
async def stripe_webhook(request: Request) -> dict[str, str]:
    """Webhook de Stripe. Valida firma, acredita créditos."""
    if not STRIPE_WEBHOOK_SECRET:
        logger.error("STRIPE_WEBHOOK_SECRET no configurado — rechazando webhook")
        raise HTTPException(500, "Webhook not configured")

    import stripe

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(400, "Missing stripe-signature header")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        logger.warning("Stripe webhook: payload inválido")
        raise HTTPException(400, "Invalid payload")
    except stripe.error.SignatureVerificationError:
        logger.warning("Stripe webhook: firma inválida")
        raise HTTPException(400, "Invalid signature")

    logger.info("Stripe event: %s", event["type"])

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        metadata = session.get("metadata", {})
        client_id = metadata.get("client_id")
        credits = int(metadata.get("credits", 0))
        amount_paid = session.get("amount_total", 0) / 100

        if client_id and credits > 0:
            sb = get_supabase()
            sb.rpc("add_credits", {
                "p_client_id": client_id,
                "p_credits": credits,
                "p_type": "purchase",
                "p_payment_provider": "stripe",
                "p_payment_id": session["id"],
                "p_amount_paid": amount_paid,
                "p_currency": "USD",
                "p_package_id": metadata.get("package_id"),
            }).execute()
            logger.info("Stripe: %d credits added to %s", credits, client_id)
        else:
            logger.warning(
                "Stripe checkout sin client_id/credits válidos: metadata=%s", metadata
            )

    return {"status": "ok"}


def _verify_mercadopago_signature(
    request: Request, body: bytes
) -> bool:
    """Verifica la firma HMAC-SHA256 de Mercado Pago.

    MP envía `x-signature` con formato: `ts=...,v1=...`
    y `x-request-id` como datos adicionales.
    Docs: https://www.mercadopago.com.mx/developers/es/docs/your-integrations/notifications/webhooks
    """
    if not MERCADOPAGO_WEBHOOK_SECRET:
        return False

    x_signature = request.headers.get("x-signature", "")
    x_request_id = request.headers.get("x-request-id", "")

    # Parsear ts y v1 del header x-signature
    parts = {}
    for part in x_signature.split(","):
        kv = part.strip().split("=", 1)
        if len(kv) == 2:
            parts[kv[0].strip()] = kv[1].strip()

    ts = parts.get("ts")
    v1 = parts.get("v1")
    if not ts or not v1:
        return False

    # Reconstruir el string firmado según docs de MP
    # manifest = "id:{data.id};request-id:{x-request-id};ts:{ts};"
    # Para notificaciones tipo payment, el data.id viene en el body JSON
    import json
    try:
        data = json.loads(body)
        data_id = str(data.get("data", {}).get("id", ""))
    except (json.JSONDecodeError, AttributeError):
        return False

    manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
    expected = hmac.new(
        MERCADOPAGO_WEBHOOK_SECRET.encode(),
        manifest.encode(),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, v1)


@router.post("/mercadopago")
@limiter.limit("30/minute")
async def mercadopago_webhook(request: Request) -> dict[str, str]:
    """Webhook de Mercado Pago. Valida firma HMAC, acredita créditos."""
    body = await request.body()

    # Verificar firma si el secret está configurado
    if MERCADOPAGO_WEBHOOK_SECRET:
        if not _verify_mercadopago_signature(request, body):
            logger.warning("MercadoPago webhook: firma inválida")
            raise HTTPException(400, "Invalid signature")

    # TODO: Implementar acreditación cuando se configure el SDK de MercadoPago
    # import json
    # data = json.loads(body)
    # if data.get("type") == "payment":
    #     payment_id = data["data"]["id"]
    #     ...

    logger.info("MercadoPago webhook recibido (pendiente implementación)")
    return {"status": "ok"}
