"""Servicio de email via Resend — alertas del sistema."""

from __future__ import annotations

import html as html_lib
import logging
import os

import httpx

logger = logging.getLogger("api.email")

_RESEND_URL = "https://api.resend.com/emails"


def _esc(value: str) -> str:
    """Escapa HTML en valores proporcionados por el usuario."""
    return html_lib.escape(str(value))


async def send_email(
    to: str | list[str],
    subject: str,
    html: str,
) -> dict | None:
    """Envía un email via Resend API. Retorna response o None si falla."""
    api_key = os.environ.get("RESEND_API_KEY", "")
    from_email = os.environ.get("EMAIL_FROM", "VoiceAI <alertas@innotecnia.app>")

    if not api_key:
        logger.warning("RESEND_API_KEY no configurada, email no enviado: %s", subject)
        return None

    if isinstance(to, str):
        to = [to]

    payload = {
        "from": from_email,
        "to": to,
        "subject": subject,
        "html": html,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                _RESEND_URL,
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            logger.info("Email enviado: %s → %s (id: %s)", subject, to, data.get("id"))
            return data
    except httpx.HTTPStatusError as e:
        logger.error("Resend API error %d: %s", e.response.status_code, e.response.text[:200])
        return None
    except Exception:
        logger.exception("Error enviando email: %s → %s", subject, to)
        return None


# ── Templates de alertas ─────────────────────────────────

_STYLE = """
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0f; color: #e0e0e0; padding: 20px; }
  .card { background: #1a1a2e; border-radius: 12px; padding: 24px; max-width: 600px; margin: 0 auto; }
  .header { font-size: 20px; font-weight: 600; margin-bottom: 16px; }
  .critical { color: #ff4d6a; }
  .warning { color: #ffaa00; }
  .info { color: #00f0ff; }
  .metric { font-size: 28px; font-weight: 700; }
  .detail { color: #999; font-size: 14px; margin-top: 8px; }
  .btn { display: inline-block; background: #00f0ff; color: #0a0a0f; padding: 10px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; margin-top: 16px; }
  .footer { color: #666; font-size: 12px; margin-top: 24px; text-align: center; }
</style>
"""


def _dashboard_url() -> str:
    return os.environ.get("DASHBOARD_URL", "https://agentes.innotecnia.app")


async def send_twilio_health_alert(
    to: str | list[str],
    status: str,
    severity: str,
    error_type: str | None,
    message: str | None,
    parent_sid: str,
    *,
    recovered: bool = False,
) -> dict | None:
    """Alerta de salud de la cuenta Twilio parent.

    Incluye timestamp UTC, tipo de error, parent SID y link a Twilio Status Page
    para que el admin descarte outage global antes de investigar credenciales.
    """
    from datetime import datetime, timezone

    is_critical = severity == "critical"
    css_class = "critical" if is_critical else "warning" if severity == "warning" else "info"
    safe_error = _esc(error_type or "unknown")
    safe_msg = _esc(message or "")
    safe_sid = _esc(parent_sid)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    if recovered:
        subject = "Twilio parent RECUPERADO — llamadas vuelven a operar"
        header_text = "Servicio Twilio recuperado"
        header_class = "info"
        body = (
            '<p>La cuenta parent de Twilio está operando normalmente de nuevo.</p>'
            '<p class="detail">Los agentes pueden recibir y hacer llamadas sin intervención adicional.</p>'
        )
    else:
        urgency = "CRÍTICO" if is_critical else "Aviso"
        subject = f"Twilio parent {urgency}: {error_type or 'health check failed'}"
        header_text = f"{urgency}: Twilio parent con problemas"
        header_class = css_class
        impact = (
            "Todos los clientes sin BYOT pueden estar afectados."
            if is_critical
            else "Puede ser transitorio. Si persiste al siguiente check (5 min), escalar."
        )
        body = f"""
        <p><strong>Tipo de error:</strong> <code>{safe_error}</code></p>
        <p><strong>Detalle:</strong> {safe_msg}</p>
        <p class="detail">{impact}</p>
        """

    html = f"""
    {_STYLE}
    <div class="card">
        <div class="header {header_class}">{header_text}</div>
        {body}
        <p class="detail">
            <strong>Parent SID:</strong> <code>{safe_sid}</code><br>
            <strong>Timestamp:</strong> {ts}
        </p>
        <p>
            <a href="https://status.twilio.com" class="btn">Ver Twilio Status</a>
        </p>
        <p class="detail" style="margin-top:12px">
            Si <a href="https://status.twilio.com" style="color:#00f0ff">status.twilio.com</a>
            reporta incidente, es outage global — esperar resolución.
            Si Twilio reporta todo operacional, revisar credenciales y Sentry
            (tag <code>twilio_parent_health</code>).
        </p>
        <div class="footer">VoiceAI Platform — innotecnia.app</div>
    </div>
    """
    return await send_email(to, subject, html)


async def send_low_balance_alert(
    to: str,
    client_name: str,
    balance: float,
    alert_type: str,
) -> dict | None:
    """Alerta de créditos bajos."""
    is_critical = alert_type == "critical"
    css_class = "critical" if is_critical else "warning"
    emoji = "&#128680;" if is_critical else "&#9888;&#65039;"
    urgency = "URGENTE" if is_critical else "Aviso"
    safe_name = _esc(client_name)

    subject = f"{urgency}: Balance bajo — {balance:.0f} créditos restantes"
    html = f"""
    {_STYLE}
    <div class="card">
        <div class="header {css_class}">{emoji} {urgency}: Balance de créditos bajo</div>
        <p>Hola, el balance de <strong>{safe_name}</strong> está bajo:</p>
        <div class="metric {css_class}">{balance:.0f} créditos</div>
        <p class="detail">
            {"Tu agente dejará de funcionar cuando se agoten los créditos." if is_critical else "Te recomendamos recargar pronto para evitar interrupciones."}
        </p>
        <a href="{_dashboard_url()}/billing" class="btn">Recargar créditos</a>
        <div class="footer">VoiceAI Platform — innotecnia.app</div>
    </div>
    """
    return await send_email(to, subject, html)


async def send_quality_alert(
    to: str,
    client_name: str,
    agent_name: str,
    call_id: str,
    severity: str,
    score: int,
    critical_count: int,
    high_count: int,
    failure_types: list[str],
    summary: str,
) -> dict | None:
    """Alerta de quality — fallo crítico o importante detectado."""
    is_critical = severity == "critical"
    css_class = "critical" if is_critical else "warning"
    safe_name = _esc(client_name)
    safe_agent = _esc(agent_name)
    safe_summary = _esc(summary)
    safe_types = ", ".join(f"<code>{_esc(t)}</code>" for t in failure_types)

    subject = f"Fallo {'crítico' if is_critical else 'importante'} detectado en {agent_name}"
    html = f"""
    {_STYLE}
    <div class="card">
        <div class="header {css_class}">Fallo de calidad detectado</div>
        <p>Se detectó un problema en una llamada del agente <strong>{safe_agent}</strong> ({safe_name}):</p>
        <div class="metric {css_class}">Score: {score}/100</div>
        <p><strong>Fallos:</strong> {critical_count} críticos, {high_count} importantes</p>
        <p><strong>Tipos:</strong> {safe_types}</p>
        <p class="detail">{safe_summary}</p>
        <a href="{_dashboard_url()}/quality" class="btn">Ver evaluaciones</a>
        <div class="footer">Call ID: {_esc(call_id[:8])}... — VoiceAI Platform</div>
    </div>
    """
    return await send_email(to, subject, html)


async def send_welcome_email(
    to: str,
    client_name: str,
    temp_password: str,
    login_url: str | None = None,
) -> dict | None:
    """Email de bienvenida al owner de un cliente recién creado.

    Incluye credenciales temporales y link al dashboard. Se espera que el
    usuario cambie su contraseña en el primer login.
    """
    safe_name = _esc(client_name)
    safe_email = _esc(to)
    safe_pwd = _esc(temp_password)
    url = login_url or f"{_dashboard_url()}/login"

    subject = f"Bienvenido a VoiceAI — acceso para {client_name}"
    html = f"""
    {_STYLE}
    <div class="card">
        <div class="header info">Bienvenido a VoiceAI</div>
        <p>Hola, tu cuenta de <strong>{safe_name}</strong> está lista.</p>
        <p>Usa estas credenciales para iniciar sesión:</p>
        <p><strong>Usuario:</strong> <code>{safe_email}</code></p>
        <p><strong>Contraseña temporal:</strong> <code>{safe_pwd}</code></p>
        <p class="detail">Por seguridad, cámbiala después de iniciar sesión desde tu perfil.</p>
        <a href="{url}" class="btn">Ir al dashboard</a>
        <div class="footer">VoiceAI Platform — innotecnia.app</div>
    </div>
    """
    return await send_email(to, subject, html)


async def send_circuit_open_alert(
    to: str | list[str],
    provider: str,
    failure_count: int,
) -> dict | None:
    """Alerta de circuit breaker — provider caído."""
    safe_provider = _esc(provider)
    subject = f"Provider caído: {provider} ({failure_count} fallos)"
    html = f"""
    {_STYLE}
    <div class="card">
        <div class="header critical">Provider caído: {safe_provider}</div>
        <p>El circuit breaker se activó para <strong>{safe_provider}</strong> después de <strong>{failure_count}</strong> fallos consecutivos.</p>
        <p>El sistema está usando el <strong>provider de respaldo</strong> automáticamente.</p>
        <p class="detail">El circuit breaker intentará reconectar automáticamente en 60 segundos.</p>
        <a href="{_dashboard_url()}/admin/providers" class="btn">Ver estado de providers</a>
        <div class="footer">VoiceAI Platform — innotecnia.app</div>
    </div>
    """
    return await send_email(to, subject, html)
