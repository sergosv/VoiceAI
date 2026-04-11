"""Worker de retención de grabaciones.

Elimina grabaciones más viejas que RETENTION_DAYS tanto del R2 como
de la DB (campo recording_key se limpia).

Corre una vez al día.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

RETENTION_DAYS = int(os.environ.get("RECORDING_RETENTION_DAYS", "90"))
POLL_INTERVAL_S = 24 * 60 * 60  # 24 horas

_worker_task: asyncio.Task | None = None


def start_retention_worker() -> None:
    """Inicia el worker de retención de grabaciones."""
    global _worker_task
    if _worker_task and not _worker_task.done():
        logger.warning("Retention worker ya esta corriendo")
        return
    _worker_task = asyncio.create_task(_worker_loop())
    logger.info("Retention worker iniciado (retention=%d dias)", RETENTION_DAYS)


def stop_retention_worker() -> None:
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        _worker_task = None


async def _worker_loop() -> None:
    # Esperar 5 minutos antes del primer run para no saturar startup
    await asyncio.sleep(300)
    while True:
        try:
            await _cleanup_old_recordings()
        except asyncio.CancelledError:
            logger.info("Retention worker cancelado")
            return
        except Exception:
            logger.exception("Error en retention worker loop")
        await asyncio.sleep(POLL_INTERVAL_S)


async def _cleanup_old_recordings() -> None:
    """Elimina grabaciones más viejas que RETENTION_DAYS."""
    from api.deps import get_supabase
    from api.services.recording_service import delete_recording

    sb = get_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).isoformat()

    # Buscar calls con recording_key y started_at más viejo que cutoff
    result = sb.table("calls").select("id, recording_key, started_at").not_.is_(
        "recording_key", "null"
    ).lt("started_at", cutoff).limit(100).execute()

    if not result.data:
        logger.info("Retention: no hay grabaciones para eliminar")
        return

    deleted = 0
    failed = 0
    for row in result.data:
        key = row.get("recording_key")
        if not key:
            continue
        try:
            ok = await asyncio.to_thread(delete_recording, key)
            if ok:
                # Limpiar el campo en DB para que no se intente de nuevo
                sb.table("calls").update({
                    "recording_key": None,
                    "recording_status": "deleted_retention",
                }).eq("id", row["id"]).execute()
                deleted += 1
            else:
                failed += 1
        except Exception:
            logger.exception("Error eliminando grabación %s", key)
            failed += 1

    logger.info(
        "Retention sweep: eliminadas=%d, fallidas=%d, cutoff=%s",
        deleted, failed, cutoff,
    )
