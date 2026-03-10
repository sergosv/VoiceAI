"""Maneja el lifecycle de cada llamada: tracking, costos, logging."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal

from supabase import Client

from agent.call_analyzer import analyze_call_transcript, analyze_call_universal
from agent.config_loader import ResolvedConfig
from agent.db import get_supabase
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
    return get_supabase()


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
        memory_contact_id: str | None = None,
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
        self._memory_contact_id = memory_contact_id
        self._started_at = datetime.now(timezone.utc)
        self._transcript: list[dict] = []
        self._agent_turns: list[dict] = []
        self._tool_traces: list[dict] = []
        self._sentiment_summary: dict | None = None
        self._intent_summary: dict | None = None
        self._mode_results: dict | None = None
        # Almacenar referencias a tareas fire-and-forget para evitar GC
        self._background_tasks: set[asyncio.Task] = set()

    def set_agent_turns(self, turns: list[dict]) -> None:
        """Establece el historial de ruteo de agentes (modo orquestado)."""
        self._agent_turns = turns

    def set_sentiment_summary(self, summary: dict) -> None:
        """Establece el resumen de sentimiento en tiempo real."""
        self._sentiment_summary = summary

    def set_intent_summary(self, summary: dict) -> None:
        """Establece el resumen de intents detectados."""
        self._intent_summary = summary

    def set_mode_results(self, results: dict) -> None:
        """Establece los resultados del modo de conversación (survey/quiz/negotiation/interview)."""
        self._mode_results = results

    def add_tool_trace(
        self,
        tool_name: str,
        params: dict | None = None,
        result: dict | None = None,
        duration_ms: int | None = None,
        success: bool = True,
        error_message: str | None = None,
    ) -> None:
        """Registra la ejecución de un tool call para trazabilidad."""
        self._tool_traces.append({
            "tool_name": tool_name,
            "params": params or {},
            "result": result or {},
            "duration_ms": duration_ms,
            "success": success,
            "error_message": error_message,
            "turn_index": len(self._transcript),
        })

    def add_transcript_entry(self, role: str, text: str) -> None:
        """Agrega una entrada a la transcripción."""
        self._transcript.append({
            "role": role,
            "text": text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def _create_background_task(self, coro) -> asyncio.Task:
        """Crea un task async y almacena la referencia para evitar GC prematuro."""
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

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
        if self._sentiment_summary:
            call_data["sentiment_realtime"] = self._sentiment_summary
        if self._intent_summary:
            call_data["intent_realtime"] = self._intent_summary
        call_result = sb.table("calls").insert(call_data).execute()
        call_id = call_result.data[0]["id"] if call_result.data else None

        # Dispatch webhook: call.completed (fire-and-forget)
        try:
            from agent.webhook_dispatch import dispatch_event as _dispatch

            self._create_background_task(_dispatch(
                self._client_id,
                "call.completed",
                {
                    "client_id": self._client_id,
                    "call_id": call_id,
                    "agent_id": self._agent_id,
                    "room_name": self._room_name,
                    "direction": self._direction,
                    "caller_number": self._caller_number,
                    "callee_number": self._callee_number,
                    "duration_seconds": duration_seconds,
                    "cost_total": float(total_cost),
                    "status": status,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            ))
        except Exception:
            logger.exception("Error dispatching call.completed webhook")

        # Guardar resultados de modo estructurado si aplica
        if self._mode_results and call_id:
            try:
                mode = self._mode_results.get("mode", "")
                result_data = {
                    "call_id": call_id,
                    "agent_id": self._agent_id,
                    "client_id": self._client_id,
                    "mode": mode,
                    "answers": self._mode_results.get("answers", []),
                    "completed": self._mode_results.get("completed", False),
                    "metadata": {},
                }
                if mode in ("quiz", "interview"):
                    result_data["score"] = self._mode_results.get("score")
                    result_data["max_score"] = self._mode_results.get("max_score")
                    result_data["passed"] = self._mode_results.get("passed")
                if mode == "negotiation":
                    result_data["metadata"] = {
                        "negotiation_history": self._mode_results.get("negotiation_history", []),
                        "final_offer": self._mode_results.get("final_offer"),
                        "deal_closed": self._mode_results.get("deal_closed", False),
                    }
                if mode == "interview":
                    result_data["metadata"]["category_scores"] = self._mode_results.get(
                        "category_scores", {}
                    )
                # Contacto si lo tenemos
                if self._memory_contact_id:
                    result_data["contact_id"] = self._memory_contact_id

                sb.table("conversation_results").insert(result_data).execute()
                logger.info("Mode results guardados: %s (completed=%s)", mode, result_data["completed"])
            except Exception:
                logger.exception("Error guardando conversation_results")

        # Actualizar campaign_calls si es una llamada de campaña
        if self._campaign_id and self._direction == "outbound":
            try:
                phone = self._callee_number or self._caller_number
                if phone:
                    cc = (
                        sb.table("campaign_calls")
                        .select("id, campaign_id, contact_id")
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
        # Si memory ya identificó el contacto, usamos ese directamente
        phone_for_contact = self._caller_number
        if self._direction == "outbound" and self._callee_number:
            phone_for_contact = self._callee_number
        if self._memory_contact_id and phone_for_contact:
            # Memory ya manejó la creación/resolución — solo actualizar stats
            try:
                _update_contact_stats(sb, self._memory_contact_id, call_id)
            except Exception:
                logger.exception("Error actualizando stats de contacto (memory)")
        elif phone_for_contact:
            try:
                _smart_upsert_contact(
                    sb, self._client_id, phone_for_contact,
                    self._direction + "_call", call_id,
                )
            except Exception:
                logger.exception("Error auto-capturando contacto")

        # Evaluar reglas proactivas post-llamada
        if self._config.agent.proactive_config:
            try:
                _evaluate_proactive_rules(
                    config=self._config,
                    call_id=call_id,
                    status=status,
                    transcript=self._transcript,
                    caller_number=self._caller_number,
                    callee_number=self._callee_number,
                    direction=self._direction,
                )
            except Exception:
                logger.exception("Error evaluando reglas proactivas post-llamada")

        # Lanzar análisis universal IA como task async para TODAS las llamadas
        if call_id and len(self._transcript) >= 2:
            self._create_background_task(
                _async_universal_analysis(
                    call_id=call_id,
                    transcript=list(self._transcript),
                    direction=self._direction,
                    client_id=self._client_id,
                    business_type=self._config.client.business_type,
                    phone_for_contact=phone_for_contact,
                )
            )

        # Lanzar detección de fallos silenciosos (fire-and-forget)
        if call_id and len(self._transcript) >= 2:
            self._create_background_task(
                _async_failure_detection(
                    call_id=call_id,
                    client_id=self._client_id,
                    agent_id=self._agent_id,
                    transcript=list(self._transcript),
                    system_prompt=self._config.agent.system_prompt,
                    tool_traces=list(self._tool_traces),
                    agent_name=self._config.agent.name,
                    agent_type=self._config.agent.agent_type,
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
                "total_calls": (row.get("total_calls") or 0) + 1,
                "total_minutes": float(Decimal(str(row.get("total_minutes") or 0)) + duration_minutes),
                "total_cost": float(Decimal(str(row.get("total_cost") or 0)) + total_cost),
                "inbound_calls": (row.get("inbound_calls") or 0) + is_inbound,
                "outbound_calls": (row.get("outbound_calls") or 0) + is_outbound,
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


def _update_contact_stats(
    sb: Client,
    contact_id: str,
    call_id: str | None,
) -> None:
    """Actualiza call_count y last_call_at de un contacto ya identificado por memory."""
    now_iso = datetime.now(timezone.utc).isoformat()
    result = (
        sb.table("contacts").select("id, call_count, metadata")
        .eq("id", contact_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return

    contact = result.data[0]
    updates: dict = {
        "call_count": (contact.get("call_count") or 0) + 1,
        "last_call_at": now_iso,
    }
    metadata = contact.get("metadata") or {}
    if call_id:
        metadata["last_call_id"] = call_id
    updates["metadata"] = metadata

    sb.table("contacts").update(updates).eq("id", contact_id).execute()
    logger.info("Contact stats actualizados (memory): %s", contact_id)


def _smart_upsert_contact(
    sb: Client,
    client_id: str,
    phone: str,
    source: str,
    call_id: str | None,
) -> None:
    """Upsert inteligente de contacto con normalización y deduplicación."""
    normalized = normalize_phone(phone)

    # Validar que parece un teléfono real (al menos 7 dígitos)
    digits = "".join(c for c in normalized if c.isdigit())
    if len(digits) < 7:
        logger.warning("Teléfono inválido, ignorando upsert: %s", phone)
        return

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

        # Asegurar canal "phone" registrado
        channels = contact.get("channels") or []
        if "phone" not in channels:
            updates["channels"] = list(set(channels + ["phone"]))

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
            "channels": ["phone"],
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


def _evaluate_proactive_rules(
    config: ResolvedConfig,
    call_id: str | None,
    status: str,
    transcript: list[dict],
    caller_number: str | None,
    callee_number: str | None,
    direction: str,
) -> None:
    """Evalúa reglas proactivas del agente y crea acciones programadas post-llamada.

    Reglas soportadas:
    - callback_missed_call: si la llamada fue corta o no contestada
    - followup_no_conversion: si la llamada terminó sin cita/venta
    - reminder_appointment: si se agendó una cita (requiere datos de la cita)
    - post_sale: si hubo conversión exitosa
    """
    proactive_cfg = config.agent.proactive_config
    if not proactive_cfg or not proactive_cfg.get("enabled"):
        return

    rules = proactive_cfg.get("rules", [])
    if not rules:
        return

    # Determinar número destino
    target_number = caller_number if direction == "inbound" else callee_number
    if not target_number:
        return

    sb = get_supabase()
    now = datetime.now(timezone.utc)

    for rule in rules:
        rule_type = rule.get("type", "")
        delay_minutes = rule.get("delay_minutes", 60)
        channel = rule.get("channel", "call")
        message = rule.get("message", "")
        max_attempts = rule.get("max_attempts", 2)
        schedule_config = rule.get("schedule")

        # Verificar horario si existe (convertir a zona horaria del negocio)
        if schedule_config:
            from datetime import timedelta
            try:
                from zoneinfo import ZoneInfo
            except ImportError:
                from backports.zoneinfo import ZoneInfo

            scheduled_time = now + timedelta(minutes=delay_minutes)
            # Usar timezone del cliente si disponible, default a México
            client_timezone = getattr(config.client, "timezone", None)
            biz_tz = ZoneInfo(client_timezone or "America/Mexico_City")
            local_time = scheduled_time.astimezone(biz_tz)

            allowed_hours = schedule_config.get("hours", "09:00-19:00")
            allowed_days = schedule_config.get("days", ["mon", "tue", "wed", "thu", "fri"])
            day_map = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}
            if day_map.get(local_time.weekday()) not in allowed_days:
                continue
            try:
                start_h, end_h = allowed_hours.split("-")
                sh, sm = map(int, start_h.split(":"))
                eh, em = map(int, end_h.split(":"))
                hour_decimal = local_time.hour + local_time.minute / 60
                start_decimal = sh + sm / 60
                end_decimal = eh + em / 60
                if not (start_decimal <= hour_decimal <= end_decimal):
                    continue
            except (ValueError, AttributeError):
                pass

        should_create = False
        from datetime import timedelta

        if rule_type == "callback_missed_call":
            # Llamada perdida o muy corta (< 2 turnos de transcript)
            if status in ("missed", "no_answer") or len(transcript) < 2:
                should_create = True

        elif rule_type == "followup_no_conversion":
            # Llamada completada pero sin cita (heurística: no se usó schedule_appointment)
            condition = rule.get("condition", {})
            if status == "completed" and len(transcript) >= 2:
                has_appointment = any(
                    "cita" in t.get("text", "").lower() or "agendada" in t.get("text", "").lower()
                    for t in transcript if t.get("role") == "assistant"
                )
                if condition.get("no_appointment") and not has_appointment:
                    should_create = True
                elif not condition:
                    should_create = True

        elif rule_type == "post_sale":
            # Conversión exitosa (heurística: transcript menciona confirmación)
            if status == "completed" and len(transcript) >= 2:
                has_conversion = any(
                    any(w in t.get("text", "").lower() for w in ("confirmado", "agendada", "reservado", "listo"))
                    for t in transcript if t.get("role") == "assistant"
                )
                if has_conversion:
                    should_create = True

        if should_create:
            scheduled_at = (now + timedelta(minutes=delay_minutes)).isoformat()

            # Reemplazar variables en el mensaje
            final_message = message
            if "{{name}}" in final_message:
                final_message = final_message.replace("{{name}}", target_number)

            try:
                sb.table("scheduled_actions").insert({
                    "agent_id": config.agent.id,
                    "client_id": config.client.id,
                    "rule_type": rule_type,
                    "channel": channel,
                    "target_number": target_number,
                    "message": final_message,
                    "scheduled_at": scheduled_at,
                    "max_attempts": max_attempts,
                    "source": "rule",
                    "source_call_id": call_id,
                    "metadata": {"rule": rule},
                    "status": "pending",
                }).execute()
                logger.info(
                    "Acción proactiva creada: %s -> %s @ %s vía %s",
                    rule_type, target_number, scheduled_at, channel,
                )
            except Exception:
                logger.exception("Error creando acción proactiva '%s'", rule_type)


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


async def _async_failure_detection(
    call_id: str,
    client_id: str,
    agent_id: str,
    transcript: list[dict],
    system_prompt: str,
    tool_traces: list[dict],
    agent_name: str,
    agent_type: str,
) -> None:
    """Ejecuta detección de fallos silenciosos post-llamada y guarda resultados."""
    try:
        from agent.failure_detector import detect_failures

        # Construir transcript como texto
        transcript_text = "\n".join(
            f"{t['role']}: {t['text']}" for t in transcript if t.get("text")
        )
        if len(transcript_text) < 50:
            return

        # Convertir tool traces al formato que espera el detector
        tool_calls = [
            {"name": t["tool_name"], "params": t.get("params", {}), "result": t.get("result", {})}
            for t in tool_traces
        ] if tool_traces else None

        analysis = await detect_failures(
            transcript=transcript_text,
            system_prompt=system_prompt,
            tool_calls=tool_calls,
            agent_name=agent_name,
            agent_type=agent_type,
        )

        if analysis.overall_score < 0:
            logger.warning("Failure detection returned error for call %s: %s", call_id, analysis.summary)
            return

        sb = _get_supabase()

        # Guardar tool traces en DB
        if tool_traces:
            trace_rows = [
                {
                    "call_id": call_id,
                    "tool_name": t["tool_name"],
                    "tool_params": t.get("params", {}),
                    "tool_result": t.get("result", {}),
                    "duration_ms": t.get("duration_ms"),
                    "success": t.get("success", True),
                    "error_message": t.get("error_message"),
                    "turn_index": t.get("turn_index"),
                }
                for t in tool_traces
            ]
            try:
                sb.table("call_tool_traces").insert(trace_rows).execute()
            except Exception:
                logger.exception("Error guardando tool traces para call %s", call_id)

        # Guardar evaluación
        eval_data = {
            "call_id": call_id,
            "client_id": client_id,
            "agent_id": agent_id,
            "overall_score": analysis.overall_score,
            "failures_found": len(analysis.failures),
            "critical_failures": analysis.critical_count,
            "evaluation_data": analysis.to_dict(),
            "status": "completed",
        }
        result = sb.table("call_evaluations").insert(eval_data).execute()
        evaluation_id = result.data[0]["id"] if result.data else None

        # Guardar fallos individuales
        if evaluation_id and analysis.failures:
            failure_rows = [
                {
                    "evaluation_id": evaluation_id,
                    "call_id": call_id,
                    "client_id": client_id,
                    "failure_type": f.failure_type.value,
                    "severity": f.severity.value,
                    "description": f.description,
                    "evidence": f.evidence,
                    "turn_index": f.turn_index,
                    "recommendation": f.recommendation,
                }
                for f in analysis.failures
            ]
            sb.table("evaluation_failures").insert(failure_rows).execute()

        # Generar alerta si hay fallos críticos o altos
        if evaluation_id and (analysis.critical_count > 0 or analysis.high_count > 0):
            severity = "critical" if analysis.critical_count > 0 else "high"
            alert = {
                "client_id": client_id,
                "agent_id": agent_id,
                "call_id": call_id,
                "evaluation_id": evaluation_id,
                "alert_type": "critical_failure" if severity == "critical" else "high_failure",
                "severity": severity,
                "title": f"Fallo {'crítico' if severity == 'critical' else 'importante'} detectado en {agent_name}",
                "description": analysis.summary,
                "metadata": {
                    "score": analysis.overall_score,
                    "critical": analysis.critical_count,
                    "high": analysis.high_count,
                    "failure_types": list(set(f.failure_type.value for f in analysis.failures)),
                },
            }
            sb.table("quality_alerts").insert(alert).execute()
            logger.warning(
                "QUALITY ALERT [%s]: call=%s score=%d critical=%d — %s",
                severity.upper(), call_id, analysis.overall_score,
                analysis.critical_count, analysis.summary,
            )

        logger.info(
            "Failure detection completada: call=%s score=%d failures=%d",
            call_id, analysis.overall_score, len(analysis.failures),
        )
    except Exception:
        logger.exception("Error en failure detection para call %s", call_id)
