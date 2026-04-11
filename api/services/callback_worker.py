"""Worker background para ejecutar scheduled callbacks.

Cada 60 segundos consulta `scheduled_callbacks` con `status='pending'` y
`scheduled_at <= now()`, y ejecuta la llamada outbound correspondiente.
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

POLL_INTERVAL_S = 60

_worker_task: asyncio.Task | None = None


def start_callback_worker() -> None:
    """Inicia el worker de callbacks como task async."""
    global _worker_task
    if _worker_task and not _worker_task.done():
        logger.warning("Callback worker ya esta corriendo")
        return
    _worker_task = asyncio.create_task(_worker_loop())
    logger.info("Callback worker iniciado (poll=%ds)", POLL_INTERVAL_S)


def stop_callback_worker() -> None:
    """Detiene el worker de callbacks."""
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        _worker_task = None
        logger.info("Callback worker detenido")


async def _reap_stuck_callbacks() -> int:
    """Recupera callbacks que quedaron atorados en in_progress > 10 min.

    Esto pasa si el worker cae a mitad de ejecución (Railway kill,
    network, crash). Los devuelve a pending para retry.
    """
    from datetime import datetime, timedelta, timezone
    from api.deps import get_supabase
    sb = get_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    result = sb.table("scheduled_callbacks").update({
        "status": "pending",
        "failure_reason": "Recuperado de in_progress atorado",
    }).eq("status", "in_progress").lt("last_attempt_at", cutoff).execute()
    return len(result.data or [])


async def _worker_loop() -> None:
    """Loop principal del worker."""
    reap_counter = 0
    while True:
        try:
            from api.services.callback_service import process_pending_callbacks
            stats = await process_pending_callbacks()
            if stats["processed"] > 0:
                logger.info(
                    "Callback worker: procesados=%d, ok=%d, fallidos=%d",
                    stats["processed"], stats["succeeded"], stats["failed"],
                )
            # Cada 5 ciclos (5 min) recuperar callbacks atorados
            reap_counter += 1
            if reap_counter >= 5:
                reap_counter = 0
                try:
                    reaped = await _reap_stuck_callbacks()
                    if reaped > 0:
                        logger.warning(
                            "Callback reaper: %d callbacks recuperados de in_progress atorado",
                            reaped,
                        )
                except Exception:
                    logger.exception("Error en callback reaper")
        except asyncio.CancelledError:
            logger.info("Callback worker cancelado")
            return
        except Exception:
            logger.exception("Error en callback worker loop")
        await asyncio.sleep(POLL_INTERVAL_S)
