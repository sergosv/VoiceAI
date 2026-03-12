"""Circuit breaker for external provider resilience."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock

logger = logging.getLogger("agent.circuit_breaker")


class CircuitState(str, Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Provider down, using fallback
    HALF_OPEN = "half_open" # Testing if provider recovered


@dataclass
class ProviderCircuit:
    provider: str
    failure_threshold: int = 3
    recovery_timeout: float = 60.0  # seconds before trying again
    _state: CircuitState = CircuitState.CLOSED
    _failure_count: int = 0
    _last_failure_time: float = 0.0
    _lock: Lock = field(default_factory=Lock)

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.time() - self._last_failure_time >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    logger.info("Circuit %s: OPEN → HALF_OPEN (testing recovery)", self.provider)
            return self._state

    def is_available(self) -> bool:
        return self.state != CircuitState.OPEN

    def record_success(self) -> None:
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                logger.info("Circuit %s: HALF_OPEN → CLOSED (recovered)", self.provider)
            self._state = CircuitState.CLOSED
            self._failure_count = 0

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self.failure_threshold:
                was_open = self._state == CircuitState.OPEN
                if not was_open:
                    logger.warning(
                        "Circuit %s: → OPEN after %d failures",
                        self.provider, self._failure_count,
                    )
                    # Enviar alerta por email (fire-and-forget)
                    _notify_circuit_open(self.provider, self._failure_count)
                self._state = CircuitState.OPEN


# Global registry of circuits
_circuits: dict[str, ProviderCircuit] = {}
_registry_lock = Lock()


def get_circuit(provider: str) -> ProviderCircuit:
    with _registry_lock:
        if provider not in _circuits:
            _circuits[provider] = ProviderCircuit(provider=provider)
        return _circuits[provider]


def get_all_circuits() -> dict[str, dict]:
    """Return status of all tracked circuits."""
    with _registry_lock:
        return {
            name: {
                "state": c.state.value,
                "failure_count": c._failure_count,
                "provider": c.provider,
            }
            for name, c in _circuits.items()
        }


# Fallback provider chains
FALLBACK_CHAINS: dict[str, dict[str, str]] = {
    "stt": {
        "deepgram": "google",
        "google": "deepgram",
        "openai": "deepgram",
    },
    "tts": {
        "cartesia": "elevenlabs",
        "elevenlabs": "cartesia",
        "openai": "cartesia",
    },
    "llm": {
        "google": "openai",
        "openai": "google",
        "anthropic": "google",
    },
}


def get_fallback_provider(component: str, primary: str) -> str | None:
    """Get fallback provider for a component if primary is down."""
    chain = FALLBACK_CHAINS.get(component, {})
    fallback = chain.get(primary)
    if fallback and get_circuit(fallback).is_available():
        return fallback
    return None


def resolve_provider(component: str, primary: str) -> str:
    """Resolve which provider to use, considering circuit breaker state."""
    circuit = get_circuit(primary)
    if circuit.is_available():
        return primary

    fallback = get_fallback_provider(component, primary)
    if fallback:
        logger.warning(
            "Provider %s is DOWN — falling back to %s for %s",
            primary, fallback, component,
        )
        return fallback

    # No fallback available — try primary anyway (half-open or forced)
    logger.warning("No fallback for %s/%s — attempting primary anyway", component, primary)
    return primary


def _notify_circuit_open(provider: str, failure_count: int) -> None:
    """Envía alerta por email cuando un circuit breaker se abre (fire-and-forget)."""
    import asyncio
    import os

    admin_email = os.environ.get("ADMIN_ALERT_EMAIL", "")
    if not admin_email:
        logger.warning("ADMIN_ALERT_EMAIL not set — circuit open alert not sent for %s", provider)
        return

    async def _send() -> None:
        try:
            from api.services.email_service import send_circuit_open_alert
            await send_circuit_open_alert(
                to=admin_email,
                provider=provider,
                failure_count=failure_count,
            )
        except Exception:
            logger.exception("Error sending circuit open alert for %s", provider)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_send())
    except RuntimeError:
        pass  # No hay event loop, ignorar
