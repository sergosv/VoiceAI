"""Cron job para alertas de balance bajo.

Ejecutar cada hora con cron, Supabase Edge Function, o similar.

Lógica:
- Si balance < 20% del total comprado -> "warning"
- Si balance < 5% del total comprado -> "critical"
- No repite la misma alerta si ya se envió
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from supabase import Client, create_client

logger = logging.getLogger("credit_alerts")


def _get_supabase() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


async def check_low_balances() -> None:
    """Revisa balances bajos y envía alertas por email."""
    sb = _get_supabase()

    # Leer umbrales de la config
    config = (
        sb.table("pricing_config")
        .select("alert_threshold_warning, alert_threshold_critical")
        .limit(1)
        .execute()
    )
    if not config.data:
        return

    cfg = config.data[0]
    warning_threshold = float(cfg["alert_threshold_warning"])
    critical_threshold = float(cfg["alert_threshold_critical"])

    # Obtener clientes con balance > 0
    balances = (
        sb.table("credit_balances")
        .select("*")
        .gt("balance", 0)
        .execute()
    )

    for bal in balances.data or []:
        # No alertar cuentas que solo tienen créditos gratis
        if bal["total_purchased"] == 0:
            continue

        remaining_pct = bal["balance"] / bal["total_purchased"]

        alert_type = None
        if remaining_pct <= critical_threshold:
            alert_type = "critical"
        elif remaining_pct <= warning_threshold:
            alert_type = "warning"

        if alert_type and bal.get("last_alert_type") != alert_type:
            await send_credit_alert_email(
                client_id=bal["client_id"],
                balance=bal["balance"],
                alert_type=alert_type,
            )

            sb.table("credit_balances").update({
                "last_alert_sent_at": datetime.now(timezone.utc).isoformat(),
                "last_alert_type": alert_type,
            }).eq("id", bal["id"]).execute()

            logger.info(
                "Alert '%s' for client %s (balance: %s)",
                alert_type, bal["client_id"], bal["balance"],
            )


async def send_credit_alert_email(
    client_id: str, balance: float, alert_type: str,
) -> None:
    """Envía email de alerta.

    TODO: Implementar con SendGrid, SES, Resend, etc.
    """
    if alert_type == "critical":
        subject = "URGENTE: Tu agente IA se quedará sin créditos pronto"
    else:
        subject = "Aviso: Tu balance de créditos está bajo"

    logger.info(
        "Would send '%s' email to client %s (balance: %.0f): %s",
        alert_type, client_id, balance, subject,
    )
