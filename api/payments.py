"""Procesamiento de pagos — Stripe Checkout y MercadoPago.

Flujo:
1. Cliente elige paquete en dashboard
2. Backend crea sesión de pago (Stripe Checkout o MercadoPago Preference)
3. Cliente paga en página del proveedor
4. Webhook confirma pago
5. Se acreditan créditos automáticamente
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("payments")

# Inicialización lazy de Stripe (puede no estar instalado en todos los entornos)
_stripe = None


def _get_stripe():
    global _stripe
    if _stripe is None:
        import stripe
        stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
        _stripe = stripe
    return _stripe


async def create_stripe_checkout(
    client_id: str,
    package_id: str,
    package_name: str,
    price_usd: float,
    credits: int,
    success_url: str,
    cancel_url: str,
) -> dict[str, str]:
    """Crea sesión de Stripe Checkout. Retorna URL de pago."""
    stripe = _get_stripe()
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"Créditos: {package_name}",
                        "description": f"{credits} minutos de agente IA",
                    },
                    "unit_amount": int(price_usd * 100),  # Stripe usa centavos
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            metadata={
                "client_id": client_id,
                "package_id": package_id,
                "credits": str(credits),
            },
        )
        return {"checkout_url": session.url, "session_id": session.id}
    except Exception as e:
        logger.error("Stripe checkout error: %s", e)
        raise


async def create_mercadopago_preference(
    client_id: str,
    package_id: str,
    package_name: str,
    price_mxn: float,
    credits: int,
    success_url: str,
    cancel_url: str,
) -> dict[str, str]:
    """Crea preferencia de Mercado Pago.

    TODO: Descomentar cuando se configure SDK de MercadoPago.
    """
    # import mercadopago
    # mp_sdk = mercadopago.SDK(os.environ.get("MERCADOPAGO_ACCESS_TOKEN"))
    # preference_data = {
    #     "items": [{
    #         "title": f"Créditos: {package_name}",
    #         "description": f"{credits} minutos de agente IA",
    #         "quantity": 1,
    #         "currency_id": "MXN",
    #         "unit_price": float(price_mxn),
    #     }],
    #     "back_urls": {
    #         "success": success_url,
    #         "failure": cancel_url,
    #         "pending": cancel_url,
    #     },
    #     "auto_return": "approved",
    #     "external_reference": f"{client_id}|{package_id}|{credits}",
    #     "notification_url": os.environ.get("MERCADOPAGO_WEBHOOK_URL"),
    # }
    # result = mp_sdk.preference().create(preference_data)
    # preference = result["response"]
    # return {
    #     "checkout_url": preference["init_point"],
    #     "preference_id": preference["id"],
    # }
    logger.warning("MercadoPago not yet configured, returning placeholder")
    return {"checkout_url": "", "preference_id": ""}
