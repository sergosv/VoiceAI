"""Maneja el lifecycle de cada llamada: tracking, costos, logging."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from decimal import Decimal

from supabase import create_client, Client

from agent.config_loader import ClientConfig

logger = logging.getLogger(__name__)

# Rates por minuto (USD)
RATES = {
    "livekit": Decimal("0.01"),
    "stt": Decimal("0.005"),
    "llm": Decimal("0.01"),
    "tts": Decimal("0.01"),
    "telephony": Decimal("0.01"),
}


def _get_supabase() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


class SessionHandler:
    """Trackea una sesión de llamada individual."""

    def __init__(
        self,
        config: ClientConfig,
        direction: str,
        caller_number: str | None,
        callee_number: str | None,
        room_name: str | None = None,
        campaign_id: str | None = None,
    ) -> None:
        self._config = config
        self._direction = direction
        self._caller_number = caller_number
        self._callee_number = callee_number
        self._room_name = room_name
        self._campaign_id = campaign_id
        self._started_at = datetime.now(timezone.utc)
        self._transcript: list[dict] = []

    def add_transcript_entry(self, role: str, text: str) -> None:
        """Agrega una entrada a la transcripción."""
        self._transcript.append({
            "role": role,
            "text": text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def finalize(
        self,
        status: str = "completed",
        summary: str | None = None,
    ) -> None:
        """Finaliza la sesión: calcula costos y guarda en DB."""
        ended_at = datetime.now(timezone.utc)
        duration_seconds = int((ended_at - self._started_at).total_seconds())
        duration_minutes = Decimal(duration_seconds) / Decimal(60)

        # Calcular costos
        costs = {
            "livekit": duration_minutes * RATES["livekit"],
            "stt": duration_minutes * RATES["stt"],
            "llm": duration_minutes * RATES["llm"],
            "tts": duration_minutes * RATES["tts"],
            "telephony": duration_minutes * RATES["telephony"],
        }
        total_cost = sum(costs.values())

        logger.info(
            "Llamada finalizada para '%s': %ds, $%.4f USD",
            self._config.slug,
            duration_seconds,
            total_cost,
        )

        sb = _get_supabase()

        # Guardar call log
        call_data = {
            "client_id": self._config.id,
            "direction": self._direction,
            "caller_number": self._caller_number,
            "callee_number": self._callee_number,
            "livekit_room_name": self._room_name,
            "duration_seconds": duration_seconds,
            "cost_livekit": float(costs["livekit"]),
            "cost_stt": float(costs["stt"]),
            "cost_llm": float(costs["llm"]),
            "cost_tts": float(costs["tts"]),
            "cost_telephony": float(costs["telephony"]),
            "cost_total": float(total_cost),
            "status": status,
            "summary": summary,
            "transcript": self._transcript,
            "started_at": self._started_at.isoformat(),
            "ended_at": ended_at.isoformat(),
        }
        call_result = sb.table("calls").insert(call_data).execute()
        call_id = call_result.data[0]["id"] if call_result.data else None

        # Actualizar campaign_calls si es una llamada de campaña
        if self._campaign_id and self._direction == "outbound":
            try:
                phone = self._callee_number or self._caller_number
                if phone:
                    # Buscar el campaign_call por campaign_id + phone + status calling
                    cc = (
                        sb.table("campaign_calls")
                        .select("id, campaign_id")
                        .eq("campaign_id", self._campaign_id)
                        .eq("phone", phone)
                        .eq("status", "calling")
                        .limit(1)
                        .execute()
                    )
                    if cc.data:
                        cc_id = cc.data[0]["id"]
                        had_conversation = len(self._transcript) > 1
                        call_status = "completed" if had_conversation else "no_answer"

                        # Generar resumen de la conversación
                        summary_text = None
                        if self._transcript:
                            summary_text = " | ".join(
                                f"{t['role']}: {t['text'][:80]}"
                                for t in self._transcript[:6]
                            )
                            if len(summary_text) > 500:
                                summary_text = summary_text[:500]

                        sb.table("campaign_calls").update({
                            "status": call_status,
                            "call_id": call_id,
                            "result_summary": summary_text,
                        }).eq("id", cc_id).execute()

                        # Actualizar contadores de la campaña
                        _update_campaign_counters(sb, self._campaign_id)
                        logger.info(
                            "Campaign call actualizada: %s -> %s (transcript: %d entries)",
                            phone, call_status, len(self._transcript),
                        )
            except Exception:
                logger.exception("Error actualizando campaign_call")

        # Auto-capturar contacto del llamante
        phone_for_contact = self._caller_number
        if self._direction == "outbound" and self._callee_number:
            phone_for_contact = self._callee_number
        if phone_for_contact:
            try:
                contact_data = {
                    "client_id": self._config.id,
                    "phone": phone_for_contact,
                    "source": self._direction + "_call",
                    "metadata": {"last_call_id": call_id} if call_id else {},
                }
                sb.table("contacts").upsert(
                    contact_data, on_conflict="client_id,phone"
                ).execute()
                logger.info("Contacto auto-capturado: %s", phone_for_contact)
            except Exception:
                logger.exception("Error auto-capturando contacto")

        # Actualizar usage_daily (upsert)
        today = self._started_at.date().isoformat()
        is_inbound = 1 if self._direction == "inbound" else 0
        is_outbound = 1 if self._direction == "outbound" else 0

        # Buscar registro existente
        existing = (
            sb.table("usage_daily")
            .select("*")
            .eq("client_id", self._config.id)
            .eq("date", today)
            .limit(1)
            .execute()
        )

        if existing.data:
            row = existing.data[0]
            sb.table("usage_daily").update({
                "total_calls": row["total_calls"] + 1,
                "total_minutes": float(Decimal(str(row["total_minutes"])) + duration_minutes),
                "total_cost": float(Decimal(str(row["total_cost"])) + total_cost),
                "inbound_calls": row["inbound_calls"] + is_inbound,
                "outbound_calls": row["outbound_calls"] + is_outbound,
            }).eq("id", row["id"]).execute()
        else:
            sb.table("usage_daily").insert({
                "client_id": self._config.id,
                "date": today,
                "total_calls": 1,
                "total_minutes": float(duration_minutes),
                "total_cost": float(total_cost),
                "inbound_calls": is_inbound,
                "outbound_calls": is_outbound,
            }).execute()


def _update_campaign_counters(sb: Client, campaign_id: str) -> None:
    """Recalcula los contadores de una campaña basándose en los status reales."""
    completed = (
        sb.table("campaign_calls")
        .select("id", count="exact")
        .eq("campaign_id", campaign_id)
        .in_("status", ["completed", "failed", "no_answer", "busy"])
        .execute()
    )
    successful = (
        sb.table("campaign_calls")
        .select("id", count="exact")
        .eq("campaign_id", campaign_id)
        .eq("status", "completed")
        .execute()
    )
    sb.table("campaigns").update({
        "completed_contacts": completed.count or 0,
        "successful_contacts": successful.count or 0,
    }).eq("id", campaign_id).execute()
