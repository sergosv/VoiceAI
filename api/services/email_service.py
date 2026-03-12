"""Servicio de email via Resend — alertas del sistema."""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger("api.email")

_RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
_FROM_EMAIL = os.environ.get("EMAIL_FROM", "VoiceAI <alertas@innotecnia.app>")
_RESEND_URL = "https://api.resend.com/emails"


async def send_email(
    to: str | list[str],
    subject: str,
    html: str,
) -> dict | None:
    """Envía un email via Resend API. Retorna response o None si falla."""
    if not _RESEND_API_KEY:
        logger.warning("RESEND_API_KEY no configurada, email no enviado: %s", subject)
        return None

    if isinstance(to, str):
        to = [to]

    payload = {
        "from": _FROM_EMAIL,
        "to": to,
        "subject": subject,
        "html": html,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                _RESEND_URL,
                json=payload,
                headers={"Authorization": f"Bearer {_RESEND_API_KEY}"},
            )
            resp.raise_for_status()
            data = resp.json()
            logger.info("Email enviado: %s → %s (id: %s)", subject, to, data.get("id"))
            return data
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

_DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://agentes.innotecnia.app")


async def send_low_balance_alert(
    to: str,
    client_name: str,
    balance: float,
    alert_type: str,
) -> dict | None:
    """Alerta de créditos bajos."""
    is_critical = alert_type == "critical"
    css_class = "critical" if is_critical else "warning"
    emoji = "🚨" if is_critical else "⚠️"
    urgency = "URGENTE" if is_critical else "Aviso"

    subject = f"{emoji} {urgency}: Balance bajo — {balance:.0f} créditos restantes"
    html = f"""
    {_STYLE}
    <div class="card">
        <div class="header {css_class}">{emoji} {urgency}: Balance de créditos bajo</div>
        <p>Hola, el balance de <strong>{client_name}</strong> está bajo:</p>
        <div class="metric {css_class}">{balance:.0f} créditos</div>
        <p class="detail">
            {"Tu agente dejará de funcionar cuando se agoten los créditos." if is_critical else "Te recomendamos recargar pronto para evitar interrupciones."}
        </p>
        <a href="{_DASHBOARD_URL}/billing" class="btn">Recargar créditos</a>
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
    emoji = "🚨" if is_critical else "⚠️"

    subject = f"{emoji} Fallo {'crítico' if is_critical else 'importante'} detectado en {agent_name}"
    types_html = ", ".join(f"<code>{t}</code>" for t in failure_types)
    html = f"""
    {_STYLE}
    <div class="card">
        <div class="header {css_class}">{emoji} Fallo de calidad detectado</div>
        <p>Se detectó un problema en una llamada del agente <strong>{agent_name}</strong> ({client_name}):</p>
        <div class="metric {css_class}">Score: {score}/100</div>
        <p><strong>Fallos:</strong> {critical_count} críticos, {high_count} importantes</p>
        <p><strong>Tipos:</strong> {types_html}</p>
        <p class="detail">{summary}</p>
        <a href="{_DASHBOARD_URL}/quality" class="btn">Ver evaluaciones</a>
        <div class="footer">Call ID: {call_id[:8]}... — VoiceAI Platform</div>
    </div>
    """
    return await send_email(to, subject, html)


async def send_circuit_open_alert(
    to: str | list[str],
    provider: str,
    failure_count: int,
) -> dict | None:
    """Alerta de circuit breaker — provider caído."""
    subject = f"🔴 Provider caído: {provider} ({failure_count} fallos)"
    html = f"""
    {_STYLE}
    <div class="card">
        <div class="header critical">🔴 Provider caído: {provider}</div>
        <p>El circuit breaker se activó para <strong>{provider}</strong> después de <strong>{failure_count}</strong> fallos consecutivos.</p>
        <p>El sistema está usando el <strong>provider de respaldo</strong> automáticamente.</p>
        <p class="detail">El circuit breaker intentará reconectar automáticamente en 60 segundos.</p>
        <a href="{_DASHBOARD_URL}/admin/providers" class="btn">Ver estado de providers</a>
        <div class="footer">VoiceAI Platform — innotecnia.app</div>
    </div>
    """
    return await send_email(to, subject, html)
