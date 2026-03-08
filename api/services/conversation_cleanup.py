"""Worker periódico: expira conversaciones inactivas + genera resúmenes."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from supabase import create_client, Client

from api.services.conversation_lifecycle import close_conversation

logger = logging.getLogger(__name__)

POLL_INTERVAL_S = 300  # 5 minutos


def _get_supabase() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def start_conversation_cleanup() -> None:
    """Inicia el loop de limpieza de conversaciones."""
    asyncio.get_event_loop().create_task(_cleanup_loop())
    logger.info("Conversation cleanup worker started (poll=%ds)", POLL_INTERVAL_S)


async def _cleanup_loop() -> None:
    await asyncio.sleep(30)  # Esperar a que la app arranque
    while True:
        try:
            count = await _sweep_stale_conversations()
            if count:
                logger.info("Cleanup: %d conversaciones expiradas", count)
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("Error en conversation cleanup loop")
        await asyncio.sleep(POLL_INTERVAL_S)


async def _sweep_stale_conversations() -> int:
    """Barre conversaciones activas que superaron su timeout."""
    sb = _get_supabase()
    now = datetime.now(timezone.utc)
    closed_count = 0

    # ── WhatsApp (Evolution) — timeout único por config ──
    closed_count += await _sweep_whatsapp(sb, now)

    # ── GHL — timeout por canal ──
    closed_count += await _sweep_ghl(sb, now)

    return closed_count


async def _sweep_whatsapp(sb: Client, now: datetime) -> int:
    """Expira conversaciones WhatsApp inactivas."""
    configs = (
        sb.table("whatsapp_configs")
        .select("id, session_timeout_minutes")
        .eq("is_active", True)
        .execute()
    )
    closed = 0
    for cfg in configs.data or []:
        timeout = cfg.get("session_timeout_minutes", 30)
        cutoff = (now - timedelta(minutes=timeout)).isoformat()
        stale = (
            sb.table("whatsapp_conversations")
            .select("id, history")
            .eq("config_id", cfg["id"])
            .eq("status", "active")
            .lt("last_message_at", cutoff)
            .limit(50)
            .execute()
        )
        for conv in stale.data or []:
            await close_conversation(
                sb, conv["id"], "whatsapp_conversations",
                closed_by="timeout",
                generate_summary=True,
                history=conv.get("history"),
            )
            closed += 1
    return closed


async def _sweep_ghl(sb: Client, now: datetime) -> int:
    """Expira conversaciones GHL inactivas con timeout por canal."""
    configs = (
        sb.table("ghl_configs")
        .select("id, session_timeout_minutes, channel_timeouts")
        .eq("is_active", True)
        .execute()
    )
    default_timeouts = {
        "webchat": 10, "whatsapp": 60, "sms": 60,
        "facebook": 30, "instagram": 30, "email": 1440,
    }
    closed = 0
    for cfg in configs.data or []:
        channel_timeouts = cfg.get("channel_timeouts") or {}
        fallback = cfg.get("session_timeout_minutes", 30)

        stale = (
            sb.table("ghl_conversations")
            .select("id, channel, last_message_at, history")
            .eq("config_id", cfg["id"])
            .eq("status", "active")
            .limit(100)
            .execute()
        )
        for conv in stale.data or []:
            channel = conv.get("channel", "whatsapp")
            timeout = channel_timeouts.get(
                channel, default_timeouts.get(channel, fallback)
            )
            cutoff = now - timedelta(minutes=timeout)
            last_msg_str = conv.get("last_message_at", "")
            if not last_msg_str:
                continue
            last_msg = datetime.fromisoformat(last_msg_str.replace("Z", "+00:00"))
            if last_msg < cutoff:
                await close_conversation(
                    sb, conv["id"], "ghl_conversations",
                    closed_by="timeout",
                    generate_summary=True,
                    history=conv.get("history"),
                )
                closed += 1
    return closed
