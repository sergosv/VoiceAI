"""Control de créditos en llamadas.

1. check_can_take_call() — Verificar ANTES de conectar
2. start_tracking() — Iniciar cuando conecta
3. _incremental_billing() — Llamadas >5min: cobra cada minuto
4. finish_call() — Cobra restante al colgar
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

from supabase import Client, create_client

logger = logging.getLogger("billing")


def _get_supabase() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


class CallBilling:
    """Una instancia por llamada."""

    def __init__(self, client_id: str) -> None:
        self.supabase = _get_supabase()
        self.client_id = client_id
        self.call_id: str | None = None
        self.agent_id: str | None = None
        self.start_time: datetime | None = None
        self._billing_task: asyncio.Task | None = None
        self._is_active = False

    async def check_can_take_call(self) -> dict[str, object]:
        """Verificar créditos ANTES de conectar."""
        try:
            result = self.supabase.rpc(
                "check_credits", {"p_client_id": self.client_id}
            ).execute()
            if result.data:
                row = result.data[0] if isinstance(result.data, list) else result.data
                has = row.get("has_credits", False)
                bal = float(row.get("balance", 0))
                logger.info("Credit check %s: balance=%.2f, allowed=%s", self.client_id, bal, has)
                return {"allowed": has, "balance": bal}
        except Exception:
            logger.exception("Error checking credits for %s", self.client_id)
        return {"allowed": False, "balance": 0}

    def start_tracking(self, call_id: str, agent_id: str | None = None) -> None:
        """Iniciar tracking cuando la llamada se conecta."""
        self.call_id = call_id
        self.agent_id = agent_id
        self.start_time = datetime.now(timezone.utc)
        self._is_active = True
        self._billing_task = asyncio.create_task(self._incremental_billing())
        logger.info("Billing started for call %s", call_id)

    async def _incremental_billing(self) -> None:
        """Llamadas largas (>5 min): cobra 1 crédito cada minuto.

        Esto evita que una llamada de 30 min consuma todo de golpe al final.
        """
        try:
            await asyncio.sleep(300)  # Esperar 5 min antes de empezar
            while self._is_active:
                result = self.supabase.rpc("consume_credits", {
                    "p_client_id": self.client_id,
                    "p_credits": 1.0,
                    "p_call_id": self.call_id,
                    "p_agent_id": self.agent_id,
                    "p_duration_seconds": 60,
                }).execute()
                if result.data:
                    row = result.data[0] if isinstance(result.data, list) else result.data
                    if row.get("was_insufficient"):
                        logger.warning("Client %s out of credits mid-call", self.client_id)
                        break
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            pass  # Normal al colgar

    async def finish_call(self, duration_seconds: int) -> None:
        """Finalizar billing. Cobra créditos restantes."""
        self._is_active = False
        if self._billing_task:
            self._billing_task.cancel()
            try:
                await self._billing_task
            except asyncio.CancelledError:
                pass

        total_minutes = duration_seconds / 60.0

        try:
            if duration_seconds < 300:
                # Llamadas cortas (<5 min): no hubo billing incremental, cobrar todo
                credits_to_consume = round(total_minutes, 2)
                if credits_to_consume > 0:
                    self.supabase.rpc("consume_credits", {
                        "p_client_id": self.client_id,
                        "p_credits": credits_to_consume,
                        "p_call_id": self.call_id,
                        "p_agent_id": self.agent_id,
                        "p_duration_seconds": duration_seconds,
                    }).execute()
            else:
                # Llamadas largas: cobrar minutos restantes no facturados
                # El billing incremental cobró 1 crédito cada 60s después del min 5
                incremental_billed = max((duration_seconds - 300) // 60, 0)
                remaining = total_minutes - incremental_billed
                if remaining > 0:
                    self.supabase.rpc("consume_credits", {
                        "p_client_id": self.client_id,
                        "p_credits": round(remaining, 2),
                        "p_call_id": self.call_id,
                        "p_agent_id": self.agent_id,
                        "p_duration_seconds": duration_seconds,
                    }).execute()
        except Exception:
            logger.exception("Error consuming credits for call %s", self.call_id)

        logger.info(
            "Call %s billed: %.1f min (%ds)", self.call_id, total_minutes, duration_seconds
        )
