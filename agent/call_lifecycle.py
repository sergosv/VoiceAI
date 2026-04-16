"""Tracker de ciclo de vida de llamadas.

Registra eventos granulares (ring, answer, speech, hangup) para
trazabilidad completa de cada llamada — inbound y outbound.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class CallEvent:
    """Un evento individual en el ciclo de vida de una llamada."""

    event: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event": self.event,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


class CallLifecycleTracker:
    """Rastrea todos los eventos del ciclo de vida de una llamada.

    Eventos rastreados:
    - call_initiated: Agente se conectó al room
    - sip_ringing: SIP participant creado (outbound) o detectado (inbound)
    - sip_answered: SIP participant conectado al room (persona contestó)
    - agent_ready: Pipeline de voz listo (session.start completó)
    - first_speech_agent: Primera vez que el agente habla
    - first_speech_user: Primera vez que el usuario habla
    - user_hangup: El usuario colgó (SIP participant desconectó)
    - agent_hangup: El agente terminó la llamada
    - transfer_started: Inicio de transferencia
    - transfer_completed: Transferencia exitosa
    - timeout_inactivity: Timeout por silencio
    - call_ended: Llamada finalizada (cualquier razón)
    - error: Error durante la llamada
    """

    def __init__(self, room_name: str, direction: str) -> None:
        self.room_name = room_name
        self.direction = direction
        self.events: list[CallEvent] = []

        # Timestamps clave para cálculos
        self._initiated_at: datetime | None = None
        self._answered_at: datetime | None = None
        self._first_speech_agent_at: datetime | None = None
        self._first_speech_user_at: datetime | None = None
        # Última vez que el usuario habló (turno más reciente). Se usa para
        # medir latencia real del agente: tiempo desde el último turno del
        # usuario hasta que el agente responde. first_speech_user_at marca
        # el inicio del turno y dejaría fuera la duración del habla.
        self._last_speech_user_at: datetime | None = None
        # Snapshot de `_last_speech_user_at` en el instante en que el agente
        # habla por primera vez. Permite medir latencia real sin incluir la
        # duración del turno del usuario.
        self._user_last_speech_before_agent_first: datetime | None = None
        self._ended_at: datetime | None = None

        # Estado de desconexión
        self._disconnect_reason: str | None = None
        self._disconnect_by: str | None = None
        self._sip_participant_left: bool = False
        self._agent_ended: bool = False

        # Contadores
        self._user_turns: int = 0
        self._agent_turns: int = 0

    def add_event(self, event: str, details: dict | None = None) -> None:
        """Registra un evento en el lifecycle."""
        ev = CallEvent(event=event, details=details or {})
        self.events.append(ev)
        logger.info("Lifecycle [%s]: %s %s", self.room_name, event, details or "")

        # Actualizar timestamps clave
        if event == "call_initiated" and not self._initiated_at:
            self._initiated_at = ev.timestamp
        elif event == "sip_answered" and not self._answered_at:
            self._answered_at = ev.timestamp
        elif event == "first_speech_agent" and not self._first_speech_agent_at:
            self._first_speech_agent_at = ev.timestamp
        elif event == "first_speech_user" and not self._first_speech_user_at:
            self._first_speech_user_at = ev.timestamp
        elif event == "call_ended":
            self._ended_at = ev.timestamp

    def record_user_speech(self) -> None:
        """Registra un turno de habla del usuario."""
        self._user_turns += 1
        self._last_speech_user_at = datetime.now(timezone.utc)
        if self._user_turns == 1:
            self.add_event("first_speech_user")

    def record_agent_speech(self) -> None:
        """Registra un turno de habla del agente."""
        self._agent_turns += 1
        if self._agent_turns == 1:
            self.add_event("first_speech_agent")
            # Capturar la última vez que habló el usuario antes de esta respuesta
            # para calcular latencia real del agente.
            self._user_last_speech_before_agent_first = self._last_speech_user_at

    def record_sip_connected(self, caller: str | None, called: str | None) -> None:
        """SIP participant se conectó (persona contestó o llamada entrante)."""
        self.add_event("sip_answered", {
            "caller_number": caller,
            "called_number": called,
        })

    def record_sip_disconnected(self, identity: str, reason: str = "") -> None:
        """SIP participant se desconectó (persona colgó)."""
        self._sip_participant_left = True
        self.add_event("user_hangup", {
            "participant_identity": identity,
            "reason": reason,
        })
        if not self._disconnect_reason:
            self._disconnect_reason = "caller_hangup"
            self._disconnect_by = "caller"

    def record_agent_ended(self, reason: str = "normal") -> None:
        """El agente terminó la llamada (transfer, hook, etc.)."""
        self._agent_ended = True
        self.add_event("agent_hangup", {"reason": reason})
        if not self._disconnect_reason:
            self._disconnect_reason = "agent_hangup"
            self._disconnect_by = "agent"

    def record_transfer(self, target: str, success: bool = True) -> None:
        """Se completó o falló una transferencia."""
        event = "transfer_completed" if success else "transfer_failed"
        self.add_event(event, {"target": target, "success": success})
        if success and not self._disconnect_reason:
            self._disconnect_reason = "transfer"
            self._disconnect_by = "transfer"

    def record_timeout(self, timeout_type: str = "inactivity") -> None:
        """Timeout por inactividad o duración máxima."""
        self.add_event("timeout_inactivity", {"type": timeout_type})
        if not self._disconnect_reason:
            self._disconnect_reason = f"timeout_{timeout_type}"
            self._disconnect_by = "system"

    def record_error(self, error: str, category: str = "unknown") -> None:
        """Error durante la llamada."""
        self.add_event("error", {"error": error[:500], "category": category})
        if not self._disconnect_reason:
            self._disconnect_reason = f"error_{category}"
            self._disconnect_by = "system"

    def record_no_answer(self) -> None:
        """Outbound: nadie contestó."""
        self.add_event("no_answer")
        self._disconnect_reason = "no_answer"
        self._disconnect_by = "system"

    def finalize(self) -> None:
        """Marca el fin de la llamada y calcula el disconnect_reason final."""
        if not self._ended_at:
            self.add_event("call_ended")

        # Si nadie marcó explícitamente quién colgó, deducirlo
        if not self._disconnect_reason:
            if self._sip_participant_left and not self._agent_ended:
                self._disconnect_reason = "caller_hangup"
                self._disconnect_by = "caller"
            elif self._agent_ended and not self._sip_participant_left:
                self._disconnect_reason = "agent_hangup"
                self._disconnect_by = "agent"
            else:
                # Ambos o ninguno — asumir que el caller colgó (caso más común)
                self._disconnect_reason = "caller_hangup"
                self._disconnect_by = "caller"

    # ── Cálculos ────────────────────────────────────────

    @property
    def ring_duration_seconds(self) -> int | None:
        """Tiempo que sonó antes de contestar (outbound) o antes del agente (inbound)."""
        if not self._initiated_at:
            return None
        answer_time = self._answered_at or self._ended_at
        if not answer_time:
            return None
        return max(0, int((answer_time - self._initiated_at).total_seconds()))

    @property
    def talk_duration_seconds(self) -> int | None:
        """Tiempo real de conversación (desde que contestó hasta que colgó)."""
        if not self._answered_at:
            return None
        end_time = self._ended_at or datetime.now(timezone.utc)
        return max(0, int((end_time - self._answered_at).total_seconds()))

    @property
    def first_speech_at(self) -> datetime | None:
        """Momento de la primera palabra (user o agent, lo que haya sido primero)."""
        times = [t for t in (self._first_speech_agent_at, self._first_speech_user_at) if t]
        return min(times) if times else None

    @property
    def disconnect_reason(self) -> str | None:
        return self._disconnect_reason

    @property
    def disconnect_by(self) -> str | None:
        return self._disconnect_by

    @property
    def disposition(self) -> str:
        """Clasificación del resultado de la llamada.

        - completed: Conversación real (>1 turno de cada lado)
        - short_call: Contestó pero conversación muy breve (<15s o ≤1 turno user)
        - abandoned: Colgó antes de que el agente hablara o inmediatamente después
        - no_answer: No contestó (outbound)
        - transferred: Se transfirió
        - voicemail: Detectado como buzón de voz
        - error: Error técnico
        """
        if self._disconnect_reason and self._disconnect_reason.startswith("error"):
            return "error"
        if self._disconnect_reason == "no_answer":
            return "no_answer"
        if self._disconnect_reason == "transfer":
            return "transferred"

        # Si el usuario nunca habló
        if self._user_turns == 0:
            if not self._answered_at:
                return "no_answer"
            # Contestó pero nunca habló — abandoned
            return "abandoned"

        # Si el agente nunca habló
        if self._agent_turns == 0:
            return "abandoned"

        # Conversación muy breve
        talk_time = self.talk_duration_seconds
        if talk_time is not None and talk_time < 15:
            return "short_call"
        if self._user_turns <= 1 and self._agent_turns <= 1:
            return "short_call"

        return "completed"

    @property
    def agent_response_latency_ms(self) -> int | None:
        """Latencia real desde que el usuario dejó de hablar hasta que el agente respondió.

        - Si el agente habla primero (outbound greeting): `answered_at → first_speech_agent`.
        - Si el usuario habla primero (inbound): usa el último `record_user_speech`
          antes del primer turno del agente (fin del turno del usuario), no el
          inicio. Sin esto, la métrica incluiría la duración del habla del
          usuario y sobreestimaría la latencia.
        """
        if not self._first_speech_user_at or not self._first_speech_agent_at:
            return None
        # Agente habla primero (outbound greeting)
        if self._first_speech_agent_at < self._first_speech_user_at:
            if self._answered_at:
                return max(0, int((self._first_speech_agent_at - self._answered_at).total_seconds() * 1000))
            return None
        # Usuario habla primero: medir desde el último turno del usuario
        # antes de la respuesta del agente.
        reference = self._user_last_speech_before_agent_first or self._first_speech_user_at
        return max(0, int((self._first_speech_agent_at - reference).total_seconds() * 1000))

    @property
    def greeting_latency_ms(self) -> int | None:
        """Tiempo desde session ready (agent_ready) hasta primer audio del agente."""
        agent_ready_at = None
        for ev in self.events:
            if ev.event == "agent_ready":
                agent_ready_at = ev.timestamp
                break
        if not agent_ready_at or not self._first_speech_agent_at:
            return None
        return max(0, int((self._first_speech_agent_at - agent_ready_at).total_seconds() * 1000))

    def get_summary(self) -> dict:
        """Retorna resumen completo para guardar en DB."""
        self.finalize()
        return {
            "ring_duration_seconds": self.ring_duration_seconds,
            "talk_duration_seconds": self.talk_duration_seconds,
            "disconnect_reason": self.disconnect_reason,
            "disconnect_by": self.disconnect_by,
            "disposition": self.disposition,
            "first_speech_at": self.first_speech_at.isoformat() if self.first_speech_at else None,
            "answered_at": self._answered_at.isoformat() if self._answered_at else None,
            "user_turns": self._user_turns,
            "agent_turns": self._agent_turns,
            "agent_response_latency_ms": self.agent_response_latency_ms,
            "greeting_latency_ms": self.greeting_latency_ms,
            "events": [e.to_dict() for e in self.events],
        }
