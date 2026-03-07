"""Tests para api/payments.py — procesamiento de pagos Stripe/MercadoPago."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from api.payments import create_mercadopago_preference, create_stripe_checkout


class TestCreateStripeCheckout:
    @pytest.mark.asyncio
    @patch("api.payments._get_stripe")
    async def test_creates_session(self, mock_get_stripe):
        mock_stripe = MagicMock()
        mock_get_stripe.return_value = mock_stripe

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/pay/cs_test"
        mock_session.id = "cs_test_123"
        mock_stripe.checkout.Session.create.return_value = mock_session

        result = await create_stripe_checkout(
            client_id="c1",
            package_id="pkg-1",
            package_name="Plan Basico",
            price_usd=50.0,
            credits=100,
            success_url="https://app.test/success",
            cancel_url="https://app.test/cancel",
        )

        assert result["checkout_url"] == "https://checkout.stripe.com/pay/cs_test"
        assert result["session_id"] == "cs_test_123"
        mock_stripe.checkout.Session.create.assert_called_once()

        # Verify the call arguments
        call_args = mock_stripe.checkout.Session.create.call_args
        assert call_args[1]["metadata"]["client_id"] == "c1"
        assert call_args[1]["metadata"]["credits"] == "100"

    @pytest.mark.asyncio
    @patch("api.payments._get_stripe")
    async def test_raises_on_stripe_error(self, mock_get_stripe):
        mock_stripe = MagicMock()
        mock_get_stripe.return_value = mock_stripe
        mock_stripe.checkout.Session.create.side_effect = Exception("Stripe API error")

        with pytest.raises(Exception, match="Stripe API error"):
            await create_stripe_checkout(
                client_id="c1", package_id="p1", package_name="Test",
                price_usd=10.0, credits=10,
                success_url="https://test/ok", cancel_url="https://test/no",
            )


class TestCreateMercadoPagoPreference:
    @pytest.mark.asyncio
    async def test_returns_placeholder(self):
        """MercadoPago aun no implementado, retorna placeholder."""
        result = await create_mercadopago_preference(
            client_id="c1",
            package_id="pkg-1",
            package_name="Plan Basico",
            price_mxn=1000.0,
            credits=100,
            success_url="https://app.test/success",
            cancel_url="https://app.test/cancel",
        )
        assert result["checkout_url"] == ""
        assert result["preference_id"] == ""
