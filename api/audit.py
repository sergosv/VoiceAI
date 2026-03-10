"""Audit logging for sensitive operations."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from api.deps import get_supabase

logger = logging.getLogger("audit")


def log_audit(
    action: str,
    user_id: str | None = None,
    client_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    """Write an audit log entry. Fire-and-forget, never raises."""
    try:
        sb = get_supabase()
        sb.table("audit_logs").insert({
            "action": action,
            "user_id": user_id,
            "client_id": client_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
            "ip_address": ip_address,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception:
        logger.exception("Failed to write audit log: %s", action)
