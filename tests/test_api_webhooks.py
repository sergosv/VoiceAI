"""Tests para api/routes/webhooks.py — webhooks de Stripe y MercadoPago."""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture()
def client():
    yield TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def mock_sb():
    with patch("api.routes.webhooks.get_supabase") as m:
        sb = MagicMock()
        m.return_value = sb
        yield sb


class TestStripeWebhook:
    def test_no_secret_configured(self, client):
        import api.routes.webhooks as wh_mod
        orig = wh_mod.STRIPE_WEBHOOK_SECRET
        wh_mod.STRIPE_WEBHOOK_SECRET = None
        try:
            resp = client.post("/api/webhooks/stripe", content=b"{}")
            assert resp.status_code == 500
        finally:
            wh_mod.STRIPE_WEBHOOK_SECRET = orig

    def test_missing_signature_header(self, client):
        import api.routes.webhooks as wh_mod
        orig = wh_mod.STRIPE_WEBHOOK_SECRET
        wh_mod.STRIPE_WEBHOOK_SECRET = "whsec_test123"
        try:
            resp = client.post("/api/webhooks/stripe", content=b"{}")
            assert resp.status_code == 400
        finally:
            wh_mod.STRIPE_WEBHOOK_SECRET = orig

    @patch("stripe.Webhook.construct_event", side_effect=ValueError("bad payload"))
    def test_invalid_payload(self, mock_construct, client):
        import api.routes.webhooks as wh_mod
        orig = wh_mod.STRIPE_WEBHOOK_SECRET
        wh_mod.STRIPE_WEBHOOK_SECRET = "whsec_test123"
        try:
            resp = client.post(
                "/api/webhooks/stripe",
                content=b"invalid",
                headers={"stripe-signature": "t=123,v1=abc"},
            )
            assert resp.status_code == 400
        finally:
            wh_mod.STRIPE_WEBHOOK_SECRET = orig

    def test_invalid_signature(self, client):
        import stripe
        import api.routes.webhooks as wh_mod
        orig = wh_mod.STRIPE_WEBHOOK_SECRET
        wh_mod.STRIPE_WEBHOOK_SECRET = "whsec_test123"
        try:
            with patch("stripe.Webhook.construct_event",
                       side_effect=stripe.error.SignatureVerificationError("bad sig", "sig")):
                resp = client.post(
                    "/api/webhooks/stripe",
                    content=b'{"type":"test"}',
                    headers={"stripe-signature": "t=123,v1=badsig"},
                )
                assert resp.status_code == 400
        finally:
            wh_mod.STRIPE_WEBHOOK_SECRET = orig

    @patch("stripe.Webhook.construct_event")
    def test_checkout_completed_adds_credits(self, mock_construct, client, mock_sb):
        import api.routes.webhooks as wh_mod
        orig = wh_mod.STRIPE_WEBHOOK_SECRET
        wh_mod.STRIPE_WEBHOOK_SECRET = "whsec_test123"
        try:
            mock_construct.return_value = {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_test_123",
                        "metadata": {
                            "client_id": "client-uuid-1",
                            "credits": "100",
                            "package_id": "pkg-1",
                        },
                        "amount_total": 5000,  # $50.00
                    }
                }
            }

            mock_sb.rpc.return_value.execute.return_value = MagicMock()

            resp = client.post(
                "/api/webhooks/stripe",
                content=b'{"type":"checkout.session.completed"}',
                headers={"stripe-signature": "t=123,v1=valid"},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"
            mock_sb.rpc.assert_called_once_with("add_credits", {
                "p_client_id": "client-uuid-1",
                "p_credits": 100,
                "p_type": "purchase",
                "p_payment_provider": "stripe",
                "p_payment_id": "cs_test_123",
                "p_amount_paid": 50.0,
                "p_currency": "USD",
                "p_package_id": "pkg-1",
            })
        finally:
            wh_mod.STRIPE_WEBHOOK_SECRET = orig

    @patch("stripe.Webhook.construct_event")
    def test_checkout_missing_metadata(self, mock_construct, client, mock_sb):
        """No acredita créditos si falta client_id o credits."""
        import api.routes.webhooks as wh_mod
        orig = wh_mod.STRIPE_WEBHOOK_SECRET
        wh_mod.STRIPE_WEBHOOK_SECRET = "whsec_test123"
        try:
            mock_construct.return_value = {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_test_456",
                        "metadata": {},
                        "amount_total": 0,
                    }
                }
            }

            resp = client.post(
                "/api/webhooks/stripe",
                content=b'{"type":"checkout.session.completed"}',
                headers={"stripe-signature": "t=123,v1=valid"},
            )
            assert resp.status_code == 200
            mock_sb.rpc.assert_not_called()
        finally:
            wh_mod.STRIPE_WEBHOOK_SECRET = orig

    @patch("stripe.Webhook.construct_event")
    def test_other_event_type(self, mock_construct, client, mock_sb):
        """Otros tipos de eventos devuelven ok sin hacer nada."""
        import api.routes.webhooks as wh_mod
        orig = wh_mod.STRIPE_WEBHOOK_SECRET
        wh_mod.STRIPE_WEBHOOK_SECRET = "whsec_test123"
        try:
            mock_construct.return_value = {
                "type": "payment_intent.succeeded",
                "data": {"object": {}},
            }

            resp = client.post(
                "/api/webhooks/stripe",
                content=b'{"type":"payment_intent.succeeded"}',
                headers={"stripe-signature": "t=123,v1=valid"},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"
            mock_sb.rpc.assert_not_called()
        finally:
            wh_mod.STRIPE_WEBHOOK_SECRET = orig


class TestMercadoPagoSignatureVerification:
    """Tests para _verify_mercadopago_signature."""

    def test_verify_valid_signature(self):
        from api.routes.webhooks import _verify_mercadopago_signature

        secret = "test-mp-secret"
        data_id = "12345"
        request_id = "req-abc"
        ts = "1709827200"

        manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
        expected_v1 = hmac.new(
            secret.encode(), manifest.encode(), hashlib.sha256
        ).hexdigest()

        body = json.dumps({"data": {"id": data_id}}).encode()

        mock_request = MagicMock()
        mock_request.headers = {
            "x-signature": f"ts={ts},v1={expected_v1}",
            "x-request-id": request_id,
        }

        with patch("api.routes.webhooks.MERCADOPAGO_WEBHOOK_SECRET", secret):
            result = _verify_mercadopago_signature(mock_request, body)
        assert result is True

    def test_verify_invalid_signature(self):
        from api.routes.webhooks import _verify_mercadopago_signature

        body = json.dumps({"data": {"id": "12345"}}).encode()
        mock_request = MagicMock()
        mock_request.headers = {
            "x-signature": "ts=1234,v1=invalidsig",
            "x-request-id": "req-1",
        }

        with patch("api.routes.webhooks.MERCADOPAGO_WEBHOOK_SECRET", "secret"):
            result = _verify_mercadopago_signature(mock_request, body)
        assert result is False

    def test_verify_no_secret(self):
        from api.routes.webhooks import _verify_mercadopago_signature

        mock_request = MagicMock()
        with patch("api.routes.webhooks.MERCADOPAGO_WEBHOOK_SECRET", None):
            result = _verify_mercadopago_signature(mock_request, b"{}")
        assert result is False

    def test_verify_missing_ts_or_v1(self):
        from api.routes.webhooks import _verify_mercadopago_signature

        mock_request = MagicMock()
        mock_request.headers = {
            "x-signature": "onlythis=value",
            "x-request-id": "req-1",
        }
        with patch("api.routes.webhooks.MERCADOPAGO_WEBHOOK_SECRET", "secret"):
            result = _verify_mercadopago_signature(mock_request, b'{"data":{"id":"1"}}')
        assert result is False

    def test_verify_bad_json_body(self):
        from api.routes.webhooks import _verify_mercadopago_signature

        mock_request = MagicMock()
        mock_request.headers = {
            "x-signature": "ts=1234,v1=abc",
            "x-request-id": "req-1",
        }
        with patch("api.routes.webhooks.MERCADOPAGO_WEBHOOK_SECRET", "secret"):
            result = _verify_mercadopago_signature(mock_request, b"not json")
        assert result is False


class TestMercadoPagoWebhook:
    def test_no_secret_accepts_all(self, client):
        """Sin secret configurado, acepta sin verificar firma."""
        import api.routes.webhooks as wh_mod
        orig = wh_mod.MERCADOPAGO_WEBHOOK_SECRET
        wh_mod.MERCADOPAGO_WEBHOOK_SECRET = None
        try:
            resp = client.post("/api/webhooks/mercadopago", content=b'{"type":"payment"}')
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"
        finally:
            wh_mod.MERCADOPAGO_WEBHOOK_SECRET = orig

    @patch("api.routes.webhooks._verify_mercadopago_signature", return_value=False)
    def test_invalid_signature_rejected(self, mock_verify, client):
        import api.routes.webhooks as wh_mod
        orig = wh_mod.MERCADOPAGO_WEBHOOK_SECRET
        wh_mod.MERCADOPAGO_WEBHOOK_SECRET = "mp-secret"
        try:
            resp = client.post(
                "/api/webhooks/mercadopago",
                content=b'{"type":"payment"}',
                headers={"x-signature": "ts=1,v1=bad", "x-request-id": "r1"},
            )
            assert resp.status_code == 400
        finally:
            wh_mod.MERCADOPAGO_WEBHOOK_SECRET = orig

    @patch("api.routes.webhooks._verify_mercadopago_signature", return_value=True)
    def test_valid_signature_accepted(self, mock_verify, client):
        import api.routes.webhooks as wh_mod
        orig = wh_mod.MERCADOPAGO_WEBHOOK_SECRET
        wh_mod.MERCADOPAGO_WEBHOOK_SECRET = "mp-secret"
        try:
            resp = client.post(
                "/api/webhooks/mercadopago",
                content=b'{"type":"payment","data":{"id":"123"}}',
                headers={"x-signature": "ts=1,v1=good", "x-request-id": "r1"},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"
        finally:
            wh_mod.MERCADOPAGO_WEBHOOK_SECRET = orig
