"""Worker para alertas de balance bajo.

Corre como background task cada 60 minutos.

Lógica:
- Si balance < 20% del total comprado -> "warning"
- Si balance < 5% del total comprado -> "critical"
- No repite la misma alerta si ya se envió
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger("credit_alerts")

_worker_task: asyncio.Task | None = None


def start_credit_alert_worker(interval_minutes: int = 60) -> None:
    """Inicia el worker de alertas de créditos como task async."""
    global _worker_task
    if _worker_task and not _worker_task.done():
        logger.warning("Credit alert worker ya está corriendo")
        return
    _worker_task = asyncio.create_task(_credit_alert_loop(interval_minutes))
    logger.info("Credit alert worker started (interval=%dm)", interval_minutes)


async def _credit_alert_loop(interval_minutes: int = 60) -> None:
    """Background loop que revisa balances bajos periódicamente."""
    await asyncio.sleep(120)  # Esperar a que la app arranque
    while True:
        try:
            await check_low_balances()
        except asyncio.CancelledError:
            logger.info("Credit alert worker cancelado")
            return
        except Exception:
            logger.exception("Credit alert worker error")
        await asyncio.sleep(interval_minutes * 60)


async def check_low_balances() -> None:
    """Revisa balances bajos y envía alertas por email."""
    from api.deps import get_supabase

    sb = get_supabase()

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
                sb=sb,
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
    sb, client_id: str, balance: float, alert_type: str,
) -> None:
    """Envía email de alerta de créditos bajos via Resend."""
    from api.services.email_service import send_low_balance_alert

    # Obtener email y nombre del cliente
    client = (
        sb.table("clients")
        .select("name, email")
        .eq("id", client_id)
        .limit(1)
        .execute()
    )
    if not client.data or not client.data[0].get("email"):
        logger.warning("No email for client %s, skipping alert", client_id)
        return

    client_name = client.data[0].get("name", "Cliente")
    email = client.data[0]["email"]

    result = await send_low_balance_alert(
        to=email,
        client_name=client_name,
        balance=balance,
        alert_type=alert_type,
    )
    if result:
        logger.info("Credit alert '%s' sent to %s (%s)", alert_type, email, client_id)
    else:
        logger.error("Failed to send credit alert to %s (%s)", email, client_id)
