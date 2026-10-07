"""Monitor de salud de la cuenta Twilio parent.

Modelo:
- Check cada 5 min: `accounts(TWILIO_ACCOUNT_SID).fetch()` usando env vars.
- Clasifica el resultado en 3 escenarios con severity distinta:
    (a) parent.status != 'active'      → CRITICAL (todos los clientes caen)
    (b) Twilio API 401/403             → CRITICAL (creds revocadas/comprometidas)
    (c) Twilio API 5xx / timeout       → WARNING  (posiblemente temporal)
- Dedup vía `provider_health_events`: solo alerta en transiciones
  healthy↔unhealthy. Durante un estado estable no se duplican emails.
- Integración: Sentry (tag `twilio_parent_health`) + Resend email.

El fallback provider (Telnyx/Bandwidth) NO está en MVP — aquí solo alertamos.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Literal

from twilio.base.exceptions import TwilioRestException

from api.deps import get_supabase

logger = logging.getLogger(__name__)

PROVIDER_NAME = "twilio_parent"
CHECK_INTERVAL_S = 300  # 5 minutos
TWILIO_STATUS_URL = "https://status.twilio.com"

Severity = Literal["critical", "warning"]
ErrorType = Literal["parent_not_active", "auth_failed", "api_error", "timeout"]


_monitor_task: asyncio.Task | None = None


def _classify_twilio_error(exc: Exception) -> tuple[Severity, ErrorType, str]:
    """Clasifica una excepción de Twilio en severity + error_type + mensaje.

    Retorna (severity, error_type, human_message).
    """
    if isinstance(exc, TwilioRestException):
        code = exc.status
        if code in (401, 403):
            return "critical", "auth_failed", f"HTTP {code}: credenciales rechazadas"
        if code is not None and code >= 500:
            return "warning", "api_error", f"HTTP {code}: error del servidor Twilio"
        # 4xx distintos a 401/403 (ej 404, 429) — también warning
        return "warning", "api_error", f"HTTP {code or '?'}: {exc.msg or 'error Twilio'}"

    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return "warning", "timeout", "Timeout al consultar Twilio API"

    # Fallback genérico — probablemente red/DNS
    return "warning", "timeout", f"Error de conexión: {type(exc).__name__}: {exc}"


def check_twilio_parent_health_sync() -> dict[str, Any]:
    """Ejecuta un check síncrono contra Twilio y retorna un dict con el resultado.

    No escribe en DB ni envía alertas — eso lo hace `run_health_check()`.
    Útil para tests y para invocar desde endpoints de diagnóstico.

    Formato del retorno:
      {"status": "healthy"}
      {"status": "unhealthy", "severity": "...", "error_type": "...", "message": "..."}
    """
    from twilio.rest import Client as TwilioClient

    sid = os.environ["TWILIO_ACCOUNT_SID"]
    token = os.environ["TWILIO_AUTH_TOKEN"]

    try:
        client = TwilioClient(sid, token)
        account = client.api.v2010.accounts(sid).fetch()
    except TwilioRestException as e:
        severity, error_type, message = _classify_twilio_error(e)
        return {
            "status": "unhealthy",
            "severity": severity,
            "error_type": error_type,
            "message": message,
            "parent_sid": sid,
        }
    except Exception as e:
        severity, error_type, message = _classify_twilio_error(e)
        return {
            "status": "unhealthy",
            "severity": severity,
            "error_type": error_type,
            "message": message,
            "parent_sid": sid,
        }

    if account.status != "active":
        return {
            "status": "unhealthy",
            "severity": "critical",
            "error_type": "parent_not_active",
            "message": f"parent account status='{account.status}' (esperado: active)",
            "parent_sid": sid,
            "twilio_status": account.status,
        }

    return {"status": "healthy", "parent_sid": sid}


def _last_health_event() -> dict | None:
    """Obtiene el último evento registrado para twilio_parent."""
    sb = get_supabase()
    result = (
        sb.table("provider_health_events")
        .select("status, severity, error_type, created_at")
        .eq("provider", PROVIDER_NAME)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def _record_event(
    status: str,
    *,
    severity: str | None = None,
    error_type: str | None = None,
    details: dict | None = None,
    alerted: bool = False,
) -> None:
    sb = get_supabase()
    sb.table("provider_health_events").insert({
        "provider": PROVIDER_NAME,
        "status": status,
        "severity": severity,
        "error_type": error_type,
        "details": details or {},
        "alerted": alerted,
    }).execute()


def _should_alert(last: dict | None, current_status: str) -> bool:
    """Decide si debe enviarse alerta basado en transición.

    Alerta solo en:
      - Primera vez (last=None) si current=unhealthy
      - last=healthy → current=unhealthy (caída)
      - last=unhealthy → current=healthy (recuperación)

    Silencia:
      - last=healthy → current=healthy (nada cambia)
      - last=unhealthy → current=unhealthy (ya alertamos, no spammear)
    """
    if last is None:
        return current_status == "unhealthy"
    return last["status"] != current_status


async def run_health_check() -> dict[str, Any]:
    """Ejecuta un ciclo completo: check + dedup + grabar evento + alertar.

    Retorna el resultado del check (útil para logs y tests).
    """
    check = await asyncio.to_thread(check_twilio_parent_health_sync)
    current_status = check["status"]
    last = _last_health_event()
    should_alert = _should_alert(last, current_status)

    if not should_alert:
        logger.debug(
            "Twilio health check: %s (sin cambio, dedup activo)", current_status,
        )
        # No grabamos cada tick para evitar crecer la tabla — solo en transiciones
        return check

    # Transición detectada: registrar evento + alertar
    await _send_alert(check, previous=last)
    _record_event(
        current_status,
        severity=check.get("severity"),
        error_type=check.get("error_type"),
        details={
            "message": check.get("message"),
            "parent_sid": check.get("parent_sid"),
            "twilio_status": check.get("twilio_status"),
            "previous_status": (last or {}).get("status"),
        },
        alerted=True,
    )
    logger.warning(
        "Twilio parent health transicionó: %s → %s (severity=%s)",
        (last or {}).get("status", "first_check"),
        current_status,
        check.get("severity"),
    )
    return check


async def _send_alert(check: dict, *, previous: dict | None) -> None:
    """Envía alerta a Sentry + email a admin. Fire-and-forget."""
    try:
        import sentry_sdk
    except ImportError:
        sentry_sdk = None

    status_now = check["status"]
    severity = check.get("severity")

    # Sentry: tag + level por severity
    if sentry_sdk is not None:
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("twilio_parent_health", status_now)
            if severity:
                scope.set_tag("twilio_severity", severity)
            sentry_level = "error" if severity == "critical" else (
                "warning" if severity == "warning" else "info"
            )
            scope.level = sentry_level  # type: ignore[assignment]
            msg = check.get("message") or f"Twilio parent health: {status_now}"
            if status_now == "healthy":
                msg = "Twilio parent health RECUPERADO"
            sentry_sdk.capture_message(msg)

    # Email
    try:
        from api.services.email_service import send_twilio_health_alert
        admin_email = os.environ.get("ADMIN_ALERT_EMAIL", "")
        if admin_email:
            await send_twilio_health_alert(
                to=admin_email,
                status=status_now,
                severity=severity or "info",
                error_type=check.get("error_type"),
                message=check.get("message"),
                parent_sid=check.get("parent_sid", "unknown"),
                recovered=(status_now == "healthy" and previous is not None),
            )
    except Exception:
        logger.exception("Fallo enviando email de alerta Twilio")


async def _monitor_loop() -> None:
    """Loop principal — corre cada CHECK_INTERVAL_S."""
    logger.info("Twilio parent health monitor iniciado (intervalo=%ds)", CHECK_INTERVAL_S)
    while True:
        try:
            await run_health_check()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Error en ciclo de health check Twilio (continuando)")
        try:
            await asyncio.sleep(CHECK_INTERVAL_S)
        except asyncio.CancelledError:
            raise


def start_twilio_health_monitor() -> None:
    """Arranca el monitor. Idempotente — si ya corre, no hace nada."""
    global _monitor_task
    if _monitor_task and not _monitor_task.done():
        logger.warning("Twilio health monitor ya esta corriendo")
        return
    if not os.environ.get("TWILIO_ACCOUNT_SID"):
        logger.warning("TWILIO_ACCOUNT_SID no configurado — monitor no arrancado")
        return
    _monitor_task = asyncio.create_task(_monitor_loop())


def stop_twilio_health_monitor() -> None:
    """Detiene el monitor (para shutdown limpio)."""
    global _monitor_task
    if _monitor_task and not _monitor_task.done():
        _monitor_task.cancel()
        _monitor_task = None
        logger.info("Twilio health monitor detenido")
