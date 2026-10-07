"""Tests para monitor de salud Twilio parent (Paso 3).

Cobertura mínima requerida:
  1. parent status=active         → healthy, sin alerta
  2. parent status=suspended      → unhealthy critical (parent_not_active)
  3. Twilio API 401               → unhealthy critical (auth_failed)
  4. Twilio API 500               → unhealthy warning (api_error), con dedup

Plus: recuperación (unhealthy → healthy) dispara alerta "recuperado".
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from twilio.base.exceptions import TwilioRestException

from api.services import twilio_health


@pytest.fixture(autouse=True)
def _patch_env(monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC_PARENT_TEST")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "TOKEN_TEST")
    monkeypatch.setenv("ADMIN_ALERT_EMAIL", "admin@test.com")


def _mock_sb_with_last_event(event: dict | None):
    """Mock que devuelve el último evento para provider_health_events.

    Cachea el MagicMock por nombre de tabla para que las aserciones sobre
    insert/select apliquen al mismo objeto entre llamadas distintas.
    """
    sb = MagicMock()
    tables: dict = {}

    def table_side(name):
        if name not in tables:
            t = MagicMock()
            if name == "provider_health_events":
                (t.select.return_value.eq.return_value.order.return_value
                 .limit.return_value.execute.return_value.data) = (
                    [event] if event else []
                )
                t.insert.return_value.execute.return_value.data = [{"id": "e1"}]
            tables[name] = t
        return tables[name]

    sb.table.side_effect = table_side
    sb._tables = tables  # exponer para aserciones
    return sb


class TestClassifyTwilioError:
    def test_401_is_critical_auth_failed(self):
        exc = TwilioRestException(status=401, uri="/", msg="Unauthorized")
        severity, error_type, _ = twilio_health._classify_twilio_error(exc)
        assert severity == "critical"
        assert error_type == "auth_failed"

    def test_403_is_critical_auth_failed(self):
        exc = TwilioRestException(status=403, uri="/", msg="Forbidden")
        severity, error_type, _ = twilio_health._classify_twilio_error(exc)
        assert severity == "critical"
        assert error_type == "auth_failed"

    def test_500_is_warning_api_error(self):
        exc = TwilioRestException(status=500, uri="/", msg="Internal error")
        severity, error_type, _ = twilio_health._classify_twilio_error(exc)
        assert severity == "warning"
        assert error_type == "api_error"

    def test_429_is_warning_api_error(self):
        exc = TwilioRestException(status=429, uri="/", msg="Rate limited")
        severity, error_type, _ = twilio_health._classify_twilio_error(exc)
        assert severity == "warning"

    def test_timeout_is_warning(self):
        import asyncio
        severity, error_type, _ = twilio_health._classify_twilio_error(
            asyncio.TimeoutError()
        )
        assert severity == "warning"
        assert error_type == "timeout"


class TestCheckSync:
    @patch("twilio.rest.Client")
    def test_active_parent_is_healthy(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.api.v2010.accounts("x").fetch.return_value = MagicMock(status="active")

        result = twilio_health.check_twilio_parent_health_sync()
        assert result["status"] == "healthy"
        assert result["parent_sid"] == "AC_PARENT_TEST"

    @patch("twilio.rest.Client")
    def test_suspended_parent_is_critical(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.api.v2010.accounts("x").fetch.return_value = MagicMock(status="suspended")

        result = twilio_health.check_twilio_parent_health_sync()
        assert result["status"] == "unhealthy"
        assert result["severity"] == "critical"
        assert result["error_type"] == "parent_not_active"
        assert "suspended" in result["message"].lower()

    @patch("twilio.rest.Client")
    def test_401_is_critical_auth_failed(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.api.v2010.accounts("x").fetch.side_effect = TwilioRestException(
            status=401, uri="/", msg="Unauthorized",
        )

        result = twilio_health.check_twilio_parent_health_sync()
        assert result["status"] == "unhealthy"
        assert result["severity"] == "critical"
        assert result["error_type"] == "auth_failed"

    @patch("twilio.rest.Client")
    def test_500_is_warning_api_error(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.api.v2010.accounts("x").fetch.side_effect = TwilioRestException(
            status=500, uri="/", msg="Internal",
        )

        result = twilio_health.check_twilio_parent_health_sync()
        assert result["status"] == "unhealthy"
        assert result["severity"] == "warning"
        assert result["error_type"] == "api_error"


class TestShouldAlert:
    def test_first_check_healthy_silent(self):
        assert twilio_health._should_alert(None, "healthy") is False

    def test_first_check_unhealthy_alerts(self):
        assert twilio_health._should_alert(None, "unhealthy") is True

    def test_healthy_to_unhealthy_alerts(self):
        last = {"status": "healthy"}
        assert twilio_health._should_alert(last, "unhealthy") is True

    def test_unhealthy_to_healthy_alerts_recovery(self):
        last = {"status": "unhealthy"}
        assert twilio_health._should_alert(last, "healthy") is True

    def test_stable_unhealthy_silent_dedup(self):
        """El requerimiento clave: no spammear durante un outage."""
        last = {"status": "unhealthy"}
        assert twilio_health._should_alert(last, "unhealthy") is False

    def test_stable_healthy_silent(self):
        last = {"status": "healthy"}
        assert twilio_health._should_alert(last, "healthy") is False


@pytest.mark.asyncio
class TestRunHealthCheck:
    @patch("api.services.twilio_health._send_alert", new_callable=AsyncMock)
    @patch("api.services.twilio_health.get_supabase")
    @patch("api.services.twilio_health.check_twilio_parent_health_sync")
    async def test_healthy_no_previous_does_not_alert(
        self, mock_check, mock_sb, mock_alert,
    ):
        """Primer check healthy — no alerta, no registra evento."""
        mock_check.return_value = {"status": "healthy", "parent_sid": "AC"}
        mock_sb.return_value = _mock_sb_with_last_event(None)

        await twilio_health.run_health_check()
        mock_alert.assert_not_called()

    @patch("api.services.twilio_health._send_alert", new_callable=AsyncMock)
    @patch("api.services.twilio_health.get_supabase")
    @patch("api.services.twilio_health.check_twilio_parent_health_sync")
    async def test_suspended_first_time_alerts_critical(
        self, mock_check, mock_sb_fn, mock_alert,
    ):
        mock_check.return_value = {
            "status": "unhealthy", "severity": "critical",
            "error_type": "parent_not_active", "parent_sid": "AC",
            "message": "status=suspended",
        }
        sb = _mock_sb_with_last_event(None)
        mock_sb_fn.return_value = sb

        await twilio_health.run_health_check()
        mock_alert.assert_awaited_once()

        # Debe grabar evento con severity=critical
        insert_calls = sb._tables["provider_health_events"].insert.call_args_list
        assert len(insert_calls) == 1
        inserted = insert_calls[0].args[0]
        assert inserted["status"] == "unhealthy"
        assert inserted["severity"] == "critical"
        assert inserted["error_type"] == "parent_not_active"
        assert inserted["alerted"] is True

    @patch("api.services.twilio_health._send_alert", new_callable=AsyncMock)
    @patch("api.services.twilio_health.get_supabase")
    @patch("api.services.twilio_health.check_twilio_parent_health_sync")
    async def test_500_warning_with_dedup_silences_second_call(
        self, mock_check, mock_sb_fn, mock_alert,
    ):
        """Critical requirement: 500 sigue caído → segundo check no duplica alerta."""
        mock_check.return_value = {
            "status": "unhealthy", "severity": "warning",
            "error_type": "api_error", "parent_sid": "AC",
            "message": "HTTP 500",
        }
        # Último evento ya es unhealthy — dedup debe silenciar
        mock_sb_fn.return_value = _mock_sb_with_last_event({"status": "unhealthy"})

        await twilio_health.run_health_check()
        mock_alert.assert_not_called()

    @patch("api.services.twilio_health._send_alert", new_callable=AsyncMock)
    @patch("api.services.twilio_health.get_supabase")
    @patch("api.services.twilio_health.check_twilio_parent_health_sync")
    async def test_recovery_alerts(self, mock_check, mock_sb_fn, mock_alert):
        """Transición unhealthy → healthy dispara alerta 'recuperado'."""
        mock_check.return_value = {"status": "healthy", "parent_sid": "AC"}
        mock_sb_fn.return_value = _mock_sb_with_last_event({"status": "unhealthy"})

        await twilio_health.run_health_check()
        mock_alert.assert_awaited_once()
        # Verificar que se pasó previous como el evento unhealthy
        args = mock_alert.call_args
        assert args.kwargs["previous"]["status"] == "unhealthy"

    @patch("api.services.twilio_health._send_alert", new_callable=AsyncMock)
    @patch("api.services.twilio_health.get_supabase")
    @patch("api.services.twilio_health.check_twilio_parent_health_sync")
    async def test_stable_healthy_does_not_write_to_db(
        self, mock_check, mock_sb_fn, mock_alert,
    ):
        """Durante healthy estable, no escribir en DB (no inflar tabla)."""
        mock_check.return_value = {"status": "healthy", "parent_sid": "AC"}
        sb = _mock_sb_with_last_event({"status": "healthy"})
        mock_sb_fn.return_value = sb

        await twilio_health.run_health_check()
        mock_alert.assert_not_called()
        # Estable healthy: no se graba evento (dedup interno, no inflar tabla)
        if "provider_health_events" in sb._tables:
            sb._tables["provider_health_events"].insert.assert_not_called()


class TestMonitorLifecycle:
    def test_start_is_idempotent(self, monkeypatch):
        """Llamar start 2 veces no crea 2 tasks."""
        import asyncio
        monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC")

        async def _run():
            twilio_health.start_twilio_health_monitor()
            task1 = twilio_health._monitor_task
            twilio_health.start_twilio_health_monitor()
            task2 = twilio_health._monitor_task
            assert task1 is task2
            twilio_health.stop_twilio_health_monitor()

        asyncio.run(_run())

    def test_start_skipped_without_twilio_sid(self, monkeypatch):
        monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
        # Limpiar cualquier task previa
        twilio_health._monitor_task = None

        async def _run():
            twilio_health.start_twilio_health_monitor()
            assert twilio_health._monitor_task is None

        import asyncio
        asyncio.run(_run())
