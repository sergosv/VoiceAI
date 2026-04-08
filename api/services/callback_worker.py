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


async def _worker_loop() -> None:
    """Loop principal del worker."""
    while True:
        try:
            from api.services.callback_service import process_pending_callbacks
            stats = await process_pending_callbacks()
            if stats["processed"] > 0:
                logger.info(
                    "Callback worker: procesados=%d, ok=%d, fallidos=%d",
                    stats["processed"], stats["succeeded"], stats["failed"],
                )
        except asyncio.CancelledError:
            logger.info("Callback worker cancelado")
            return
        except Exception:
            logger.exception("Error en callback worker loop")
        await asyncio.sleep(POLL_INTERVAL_S)
