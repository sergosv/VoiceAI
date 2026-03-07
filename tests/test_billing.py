"""Tests para billing: agent/billing.py (CallBilling) y api/routes/billing.py."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.middleware.auth import CurrentUser, get_current_user

client = TestClient(app)

ADMIN_USER = CurrentUser(
    id="admin-uuid", auth_user_id="auth-admin", email="admin@test.com",
    role="admin", client_id=None,
)

CLIENT_USER = CurrentUser(
    id="client-uuid", auth_user_id="auth-client", email="cli@test.com",
    role="client", client_id="client-id-123",
)


# =====================================================================
# CallBilling (agent/billing.py)
# =====================================================================


class TestCallBillingCheckCanTakeCall:
    """Tests para check_can_take_call."""

    @pytest.mark.asyncio
    @patch("agent.billing._get_supabase")
    async def test_check_can_take_call_allowed(self, mock_get_sb):
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = [
            {"has_credits": True, "balance": 50.0}
        ]
        mock_get_sb.return_value = mock_sb

        from agent.billing import CallBilling
        billing = CallBilling(client_id="client-id-123")

        result = await billing.check_can_take_call()
        assert result["allowed"] is True
        assert result["balance"] == 50.0
        mock_sb.rpc.assert_called_once_with(
            "check_credits", {"p_client_id": "client-id-123"}
        )

    @pytest.mark.asyncio
    @patch("agent.billing._get_supabase")
    async def test_check_can_take_call_no_credits(self, mock_get_sb):
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = [
            {"has_credits": False, "balance": 0}
        ]
        mock_get_sb.return_value = mock_sb

        from agent.billing import CallBilling
        billing = CallBilling(client_id="client-id-123")

        result = await billing.check_can_take_call()
        assert result["allowed"] is False
        assert result["balance"] == 0

    @pytest.mark.asyncio
    @patch("agent.billing._get_supabase")
    async def test_check_can_take_call_rpc_error(self, mock_get_sb):
        mock_sb = MagicMock()
        mock_sb.rpc.side_effect = Exception("DB connection failed")
        mock_get_sb.return_value = mock_sb

        from agent.billing import CallBilling
        billing = CallBilling(client_id="client-id-123")

        result = await billing.check_can_take_call()
        assert result["allowed"] is False
        assert result["balance"] == 0


class TestCallBillingStartTracking:
    """Tests para start_tracking."""

    @patch("agent.billing._get_supabase")
    def test_start_tracking_sets_fields(self, mock_get_sb):
        mock_get_sb.return_value = MagicMock()

        from agent.billing import CallBilling
        billing = CallBilling(client_id="client-id-123")

        # Patch asyncio.create_task para no lanzar la coroutine real
        with patch("asyncio.create_task") as mock_task:
            mock_task.return_value = MagicMock(spec=asyncio.Task)
            billing.start_tracking(call_id="call-001", agent_id="agent-001")

        assert billing.call_id == "call-001"
        assert billing.agent_id == "agent-001"
        assert billing.start_time is not None
        assert isinstance(billing.start_time, datetime)
        assert billing._is_active is True
        assert billing._billing_task is not None


class TestCallBillingFinishCall:
    """Tests para finish_call."""

    @pytest.mark.asyncio
    @patch("agent.billing._get_supabase")
    async def test_finish_call_short_call(self, mock_get_sb):
        """Llamada corta (<5 min): cobra todo de golpe. 120s = 2.0 créditos."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = None
        mock_get_sb.return_value = mock_sb

        from agent.billing import CallBilling
        billing = CallBilling(client_id="client-id-123")
        billing.call_id = "call-001"
        billing.agent_id = "agent-001"
        billing._is_active = True
        billing._billing_task = None

        await billing.finish_call(duration_seconds=120)

        assert billing._is_active is False
        mock_sb.rpc.assert_called_once_with("consume_credits", {
            "p_client_id": "client-id-123",
            "p_credits": 2.0,
            "p_call_id": "call-001",
            "p_agent_id": "agent-001",
            "p_duration_seconds": 120,
        })

    @pytest.mark.asyncio
    @patch("agent.billing._get_supabase")
    async def test_finish_call_long_call(self, mock_get_sb):
        """Llamada larga (>5 min): cobra solo lo restante.

        420s = 7 min total.
        Incremental billed = (420-300)//60 = 2 créditos (min 6 y 7).
        Remaining = 7.0 - 2 = 5.0 créditos.
        """
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = None
        mock_get_sb.return_value = mock_sb

        from agent.billing import CallBilling
        billing = CallBilling(client_id="client-id-123")
        billing.call_id = "call-002"
        billing.agent_id = "agent-001"
        billing._is_active = True
        billing._billing_task = None

        await billing.finish_call(duration_seconds=420)

        assert billing._is_active is False
        mock_sb.rpc.assert_called_once_with("consume_credits", {
            "p_client_id": "client-id-123",
            "p_credits": 5.0,
            "p_call_id": "call-002",
            "p_agent_id": "agent-001",
            "p_duration_seconds": 420,
        })

    @pytest.mark.asyncio
    @patch("agent.billing._get_supabase")
    async def test_finish_call_cancels_billing_task(self, mock_get_sb):
        """finish_call cancela la tarea de billing incremental."""
        mock_get_sb.return_value = MagicMock()

        from agent.billing import CallBilling
        billing = CallBilling(client_id="client-id-123")
        billing.call_id = "call-003"
        billing.agent_id = "agent-001"
        billing._is_active = True

        # Crear un task real que se pueda cancelar y awaitear
        async def _fake_billing():
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                raise

        task = asyncio.create_task(_fake_billing())
        billing._billing_task = task

        await billing.finish_call(duration_seconds=60)

        assert task.cancelled()
        assert billing._is_active is False

    @pytest.mark.asyncio
    @patch("agent.billing._get_supabase")
    async def test_finish_call_handles_rpc_error(self, mock_get_sb):
        """Si consume_credits falla, no propaga la excepción."""
        mock_sb = MagicMock()
        mock_sb.rpc.side_effect = Exception("RPC failed")
        mock_get_sb.return_value = mock_sb

        from agent.billing import CallBilling
        billing = CallBilling(client_id="client-id-123")
        billing.call_id = "call-004"
        billing.agent_id = "agent-001"
        billing._is_active = True
        billing._billing_task = None

        # No debe lanzar excepción
        await billing.finish_call(duration_seconds=90)
        assert billing._is_active is False


# =====================================================================
# API Routes (api/routes/billing.py)
# =====================================================================


class TestGetBalance:
    @patch("api.routes.billing.get_supabase")
    def test_get_balance_client(self, mock_get_sb):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_sb = MagicMock()
        (mock_sb.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [
            {
                "balance": 42.5,
                "total_purchased": 100,
                "total_consumed": 57.5,
                "total_gifted": 0,
            }
        ]
        mock_get_sb.return_value = mock_sb

        resp = client.get("/api/billing/balance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["balance"] == 42.5
        assert data["total_purchased"] == 100
        app.dependency_overrides.clear()

    @patch("api.routes.billing.get_supabase")
    def test_get_balance_no_data(self, mock_get_sb):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_sb = MagicMock()
        (mock_sb.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = []
        mock_get_sb.return_value = mock_sb

        resp = client.get("/api/billing/balance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["balance"] == 0
        assert data["total_purchased"] == 0
        assert data["total_consumed"] == 0
        assert data["total_gifted"] == 0
        app.dependency_overrides.clear()


class TestListPackages:
    @patch("api.routes.billing.get_supabase")
    def test_list_packages(self, mock_get_sb):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_sb = MagicMock()
        packages = [
            {"id": "pkg-1", "name": "Starter", "credits": 100, "price_usd": 10, "is_active": True},
            {"id": "pkg-2", "name": "Pro", "credits": 500, "price_usd": 45, "is_active": True},
        ]
        (mock_sb.table.return_value.select.return_value
         .eq.return_value.order.return_value.execute.return_value.data) = packages
        mock_get_sb.return_value = mock_sb

        resp = client.get("/api/billing/packages")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "Starter"
        assert data[1]["credits"] == 500
        app.dependency_overrides.clear()


class TestListTransactions:
    @patch("api.routes.billing.get_supabase")
    def test_list_transactions(self, mock_get_sb):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_sb = MagicMock()
        txns = [
            {"id": "tx-1", "client_id": "client-id-123", "type": "purchase", "credits": 100},
            {"id": "tx-2", "client_id": "client-id-123", "type": "consumption", "credits": -2.5},
        ]
        (mock_sb.table.return_value.select.return_value
         .eq.return_value.order.return_value.limit.return_value
         .execute.return_value.data) = txns
        mock_get_sb.return_value = mock_sb

        resp = client.get("/api/billing/transactions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["type"] == "purchase"
        assert data[1]["credits"] == -2.5
        app.dependency_overrides.clear()


class TestPurchaseCredits:
    @patch("api.routes.billing.create_stripe_checkout")
    @patch("api.routes.billing.get_supabase")
    def test_purchase_stripe(self, mock_get_sb, mock_stripe):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_sb = MagicMock()
        (mock_sb.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = [
            {"id": "pkg-1", "name": "Starter", "credits": 100, "price_usd": 10.0, "price_mxn": 180.0}
        ]
        mock_get_sb.return_value = mock_sb

        mock_stripe.return_value = {"checkout_url": "https://checkout.stripe.com/session-123"}

        resp = client.post("/api/billing/purchase", json={
            "client_id": "client-id-123",
            "package_id": "pkg-1",
            "payment_method": "stripe",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "checkout_url" in data
        mock_stripe.assert_called_once()
        app.dependency_overrides.clear()

    @patch("api.routes.billing.get_supabase")
    def test_purchase_invalid_package(self, mock_get_sb):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER
        mock_sb = MagicMock()
        (mock_sb.table.return_value.select.return_value
         .eq.return_value.limit.return_value.execute.return_value.data) = []
        mock_get_sb.return_value = mock_sb

        resp = client.post("/api/billing/purchase", json={
            "client_id": "client-id-123",
            "package_id": "pkg-nonexistent",
            "payment_method": "stripe",
        })
        assert resp.status_code == 404
        app.dependency_overrides.clear()


class TestGiftCredits:
    @patch("api.routes.billing.get_supabase")
    def test_gift_credits_admin(self, mock_get_sb):
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = 150.0
        mock_get_sb.return_value = mock_sb

        resp = client.post("/api/billing/admin/gift-credits", json={
            "client_id": "client-id-123",
            "credits": 50,
            "reason": "Promotional gift for onboarding",
            "admin_email": "admin@test.com",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["new_balance"] == 150.0
        assert data["gifted"] == 50
        mock_sb.rpc.assert_called_once_with("add_credits", {
            "p_client_id": "client-id-123",
            "p_credits": 50,
            "p_type": "gift",
            "p_reason": "Promotional gift for onboarding",
            "p_admin_email": "admin@test.com",
        })
        app.dependency_overrides.clear()

    def test_gift_credits_client_forbidden(self):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER

        resp = client.post("/api/billing/admin/gift-credits", json={
            "client_id": "client-id-123",
            "credits": 50,
            "reason": "Trying to gift myself",
            "admin_email": "cli@test.com",
        })
        assert resp.status_code == 403
        app.dependency_overrides.clear()


class TestPricingConfig:
    @patch("api.routes.billing.get_supabase")
    def test_get_pricing_admin(self, mock_get_sb):
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER
        mock_sb = MagicMock()
        config = {
            "id": "pricing-1",
            "cost_twilio_per_min": 0.01,
            "cost_stt_per_min": 0.005,
            "cost_llm_per_min": 0.008,
            "cost_tts_per_min": 0.006,
            "cost_livekit_per_min": 0.004,
            "cost_mcp_per_min": 0.001,
            "profit_margin": 0.3,
        }
        (mock_sb.table.return_value.select.return_value
         .limit.return_value.execute.return_value.data) = [config]
        mock_get_sb.return_value = mock_sb

        resp = client.get("/api/billing/admin/pricing")
        assert resp.status_code == 200
        data = resp.json()
        assert "_calculated" in data
        # cost_per_min = 0.01 + 0.005 + 0.008 + 0.006 + 0.004 + 0.001 = 0.034
        assert data["_calculated"]["cost_per_min_usd"] == 0.034
        # price = 0.034 / (1 - 0.3) = 0.034 / 0.7 ≈ 0.0486
        assert data["_calculated"]["price_per_credit_usd"] == round(0.034 / 0.7, 4)
        app.dependency_overrides.clear()

    def test_get_pricing_client_forbidden(self):
        app.dependency_overrides[get_current_user] = lambda: CLIENT_USER

        resp = client.get("/api/billing/admin/pricing")
        assert resp.status_code == 403
        app.dependency_overrides.clear()

    @patch("api.routes.billing.get_supabase")
    def test_update_pricing_admin(self, mock_get_sb):
        app.dependency_overrides[get_current_user] = lambda: ADMIN_USER
        mock_sb = MagicMock()
        # select id
        (mock_sb.table.return_value.select.return_value
         .limit.return_value.execute.return_value.data) = [{"id": "pricing-1"}]
        # update + rpc + packages select
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = None
        mock_sb.rpc.return_value.execute.return_value = None
        updated_packages = [
            {"id": "pkg-1", "name": "Starter", "credits": 100, "price_usd": 12.0},
        ]
        # Necesitamos que la segunda llamada a table("credit_packages") retorne los paquetes.
        # Como MagicMock encadena, simplificamos: el último select retorna los paquetes.
        (mock_sb.table.return_value.select.return_value
         .eq.return_value.order.return_value.execute.return_value.data) = updated_packages
        mock_get_sb.return_value = mock_sb

        resp = client.patch("/api/billing/admin/pricing", json={
            "profit_margin": 0.35,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Precios actualizados y paquetes recalculados"
        assert "packages" in data
        mock_sb.rpc.assert_called_once_with("recalculate_package_prices")
        app.dependency_overrides.clear()
