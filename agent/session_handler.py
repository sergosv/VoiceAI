"""Maneja el lifecycle de cada llamada: tracking, costos, logging."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal

from supabase import create_client, Client

from agent.call_analyzer import analyze_call_transcript, analyze_call_universal
from agent.config_loader import ResolvedConfig
from agent.phone_utils import normalize_phone

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
        config: ResolvedConfig,
        direction: str,
        caller_number: str | None,
        callee_number: str | None,
        room_name: str | None = None,
        campaign_id: str | None = None,
        campaign_script: str | None = None,
    ) -> None:
        self._config = config
        self._client_id = config.client.id
        self._agent_id = config.agent.id
        self._direction = direction
        self._caller_number = caller_number
        self._callee_number = callee_number
        self._room_name = room_name
        self._campaign_id = campaign_id
        self._campaign_script = campaign_script
        self._started_at = datetime.now(timezone.utc)
        self._transcript: list[dict] = []
        self._agent_turns: list[dict] = []

    def set_agent_turns(self, turns: list[dict]) -> None:
        """Establece el historial de ruteo de agentes (modo orquestado)."""
        self._agent_turns = turns

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
            "Llamada finalizada para '%s/%s': %ds, $%.4f USD",
            self._config.client.slug,
            self._config.agent.slug,
            duration_seconds,
            total_cost,
        )

        sb = _get_supabase()

        # Guardar call log
        call_data = {
            "client_id": self._client_id,
            "agent_id": self._agent_id,
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
            "metadata": {
                "voice_mode": self._config.agent.agent_mode,
                "stt_provider": self._config.agent.stt_provider,
                "llm_provider": self._config.agent.llm_provider,
                "tts_provider": self._config.agent.tts_provider,
                "agent_name": self._config.agent.name,
            },
        }
        if self._agent_turns:
            call_data["agent_turns"] = self._agent_turns
        call_result = sb.table("calls").insert(call_data).execute()
        call_id = call_result.data[0]["id"] if call_result.data else None

        # Actualizar campaign_calls si es una llamada de campaña
        if self._campaign_id and self._direction == "outbound":
            try:
                phone = self._callee_number or self._caller_number
                if phone:
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

                        summary_text = None
                        if self._transcript:
                            summary_text = " | ".join(
                                f"{t['role']}: {t['text'][:80]}"
                                for t in self._transcript[:6]
                            )
                            if len(summary_text) > 500:
                                summary_text = summary_text[:500]

                        update_data: dict = {
                            "status": call_status,
                            "call_id": call_id,
                            "result_summary": summary_text,
                        }

                        if had_conversation:
                            analysis = await analyze_call_transcript(
                                self._transcript, self._campaign_script
                            )
                            if analysis:
                                update_data["analysis_data"] = analysis
                                _enrich_contact(
                                    sb,
                                    self._client_id,
                                    phone,
                                    cc.data[0].get("contact_id"),
                                    analysis,
                                )

                        sb.table("campaign_calls").update(
                            update_data
                        ).eq("id", cc_id).execute()

                        _update_campaign_counters(sb, self._campaign_id)
                        logger.info(
                            "Campaign call actualizada: %s -> %s (transcript: %d entries)",
                            phone, call_status, len(self._transcript),
                        )
            except Exception:
                logger.exception("Error actualizando campaign_call")

        # Auto-capturar contacto con deduplicación inteligente
        phone_for_contact = self._caller_number
        if self._direction == "outbound" and self._callee_number:
            phone_for_contact = self._callee_number
        if phone_for_contact:
            try:
                _smart_upsert_contact(
                    sb, self._client_id, phone_for_contact,
                    self._direction + "_call", call_id,
                )
            except Exception:
                logger.exception("Error auto-capturando contacto")

        # Lanzar análisis universal IA como task async para TODAS las llamadas
        if call_id and len(self._transcript) >= 2:
            asyncio.create_task(
                _async_universal_analysis(
                    call_id=call_id,
                    transcript=list(self._transcript),
                    direction=self._direction,
                    client_id=self._client_id,
                    business_type=self._config.client.business_type,
                    phone_for_contact=phone_for_contact,
                )
            )

        # Actualizar usage_daily (upsert)
        today = self._started_at.date().isoformat()
        is_inbound = 1 if self._direction == "inbound" else 0
        is_outbound = 1 if self._direction == "outbound" else 0

        existing = (
            sb.table("usage_daily")
            .select("*")
            .eq("client_id", self._client_id)
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
                "client_id": self._client_id,
                "date": today,
                "total_calls": 1,
                "total_minutes": float(duration_minutes),
                "total_cost": float(total_cost),
                "inbound_calls": is_inbound,
                "outbound_calls": is_outbound,
            }).execute()


def _smart_upsert_contact(
    sb: Client,
    client_id: str,
    phone: str,
    source: str,
    call_id: str | None,
) -> None:
    """Upsert inteligente de contacto con normalización y deduplicación."""
    normalized = normalize_phone(phone)

    result = (
        sb.table("contacts").select("*")
        .eq("client_id", client_id)
        .eq("phone", normalized)
        .limit(1)
        .execute()
    )

    now_iso = datetime.now(timezone.utc).isoformat()

    if result.data:
        contact = result.data[0]
        updates: dict = {
            "call_count": (contact.get("call_count") or 0) + 1,
            "last_call_at": now_iso,
        }
        metadata = contact.get("metadata") or {}
        if call_id:
            metadata["last_call_id"] = call_id
        updates["metadata"] = metadata

        sb.table("contacts").update(updates).eq("id", contact["id"]).execute()
        logger.info("Contacto actualizado (call_count +1): %s", normalized)
    else:
        contact_data = {
            "client_id": client_id,
            "phone": normalized,
            "source": source,
            "call_count": 1,
            "last_call_at": now_iso,
            "metadata": {"last_call_id": call_id} if call_id else {},
        }
        sb.table("contacts").insert(contact_data).execute()
        logger.info("Contacto nuevo creado: %s", normalized)


def _enrich_contact(
    sb: Client,
    client_id: str,
    phone: str,
    contact_id: str | None,
    analysis: dict,
) -> None:
    """Enriquece el contacto con datos extraídos del análisis de la llamada."""
    try:
        normalized = normalize_phone(phone)
        if contact_id:
            result = sb.table("contacts").select("*").eq("id", contact_id).limit(1).execute()
        else:
            result = (
                sb.table("contacts").select("*")
                .eq("client_id", client_id)
                .eq("phone", normalized)
                .limit(1)
                .execute()
            )

        if not result.data:
            return

        contact = result.data[0]
        updates: dict = {}

        # Nombre: buscar en ambos formatos (outbound y universal)
        datos = analysis.get("datos_capturados") or {}
        extracted_name = analysis.get("contact_name") or datos.get("nombre")
        if extracted_name and not contact.get("name"):
            updates["name"] = extracted_name

        # Email: buscar en ambos formatos
        extracted_email = analysis.get("contact_email") or datos.get("email")
        if extracted_email and not contact.get("email"):
            updates["email"] = extracted_email

        new_lead = analysis.get("calificacion_lead")
        if new_lead and new_lead > (contact.get("lead_score") or 0):
            updates["lead_score"] = new_lead

        existing_tags = contact.get("tags") or []
        new_tags = analysis.get("tags") or []
        if new_tags:
            merged = list(set(existing_tags) | set(new_tags))
            if merged != existing_tags:
                updates["tags"] = merged

        metadata = contact.get("metadata") or {}
        metadata["last_analysis"] = {
            "result": analysis.get("result"),
            "summary": analysis.get("summary") or analysis.get("resumen"),
            "sentiment": analysis.get("sentiment") or analysis.get("sentimiento"),
        }
        updates["metadata"] = metadata

        if updates:
            sb.table("contacts").update(updates).eq("id", contact["id"]).execute()
            logger.info("Contacto enriquecido: %s", phone)
    except Exception:
        logger.exception("Error enriqueciendo contacto %s", phone)


async def _async_universal_analysis(
    call_id: str,
    transcript: list[dict],
    direction: str,
    client_id: str,
    business_type: str | None,
    phone_for_contact: str | None,
) -> None:
    """Ejecuta análisis universal IA de forma async y actualiza la DB."""
    try:
        analysis = await analyze_call_universal(transcript, direction, business_type)
        if not analysis:
            return

        sb = _get_supabase()

        call_updates = {
            "sentimiento": analysis.get("sentimiento"),
            "intencion": analysis.get("intencion_detectada"),
            "lead_score": analysis.get("calificacion_lead"),
            "siguiente_accion": analysis.get("siguiente_accion"),
            "resumen_ia": analysis.get("resumen"),
            "preguntas_sin_respuesta": analysis.get("preguntas_sin_respuesta"),
        }
        sb.table("calls").update(call_updates).eq("id", call_id).execute()
        logger.info("Análisis universal guardado para call %s", call_id)

        if phone_for_contact:
            _enrich_contact(sb, client_id, phone_for_contact, None, analysis)

    except Exception:
        logger.exception("Error en análisis universal async para call %s", call_id)


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
