"""Webhooks de pago — reciben confirmaciones de Stripe/MercadoPago y acreditan créditos.

IMPORTANTE: Estos endpoints son públicos (sin auth) para que Stripe/MP los llamen.
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException, Request

from api.deps import get_supabase

router = APIRouter()
logger = logging.getLogger("webhooks")

STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")


@router.post("/stripe")
async def stripe_webhook(request: Request) -> dict[str, str]:
    """Webhook de Stripe. Valida firma, acredita créditos."""
    import stripe

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(400, "Invalid webhook signature")

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

    return {"status": "ok"}


@router.post("/mercadopago")
async def mercadopago_webhook(request: Request) -> dict[str, str]:
    """Webhook de Mercado Pago.

    TODO: Descomentar cuando se configure SDK.
    """
    # data = await request.json()
    # if data.get("type") == "payment":
    #     payment_id = data["data"]["id"]
    #     mp_sdk = mercadopago.SDK(os.environ.get("MERCADOPAGO_ACCESS_TOKEN"))
    #     payment = mp_sdk.payment().get(payment_id)["response"]
    #     if payment["status"] == "approved":
    #         ref = payment["external_reference"]
    #         client_id, package_id, credits = ref.split("|")
    #         sb = get_supabase()
    #         sb.rpc("add_credits", {
    #             "p_client_id": client_id,
    #             "p_credits": int(credits),
    #             "p_type": "purchase",
    #             "p_payment_provider": "mercadopago",
    #             "p_payment_id": str(payment_id),
    #             "p_amount_paid": payment["transaction_amount"],
    #             "p_currency": "MXN",
    #             "p_package_id": package_id,
    #         }).execute()
    return {"status": "ok"}
