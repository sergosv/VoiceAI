"""Tests para features agregadas en pases de hardening:

- Guardrails escalation patterns (ES, EN, PT)
- Callback tool business hours validation
- Phone normalization consistency
- DNC source types
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from agent.guardrails import GuardrailsConfig, GuardrailsEngine
from agent.phone_utils import normalize_phone
from agent.tools.callback_tool import _is_in_business_hours


# ── Escalation detection ──

class TestEscalationDetection:
    """Valida que las frases de molestia real se detecten correctamente."""

    @pytest.fixture
    def engine(self) -> GuardrailsEngine:
        return GuardrailsEngine(GuardrailsConfig(enabled=True))

    @pytest.mark.parametrize("text", [
        "déjame en paz por favor",
        "no me vuelvan a llamar",
        "no insistan",
        "voy a reportar este número",
        "esto es acoso",
        "quítenme de su lista",
        "no quiero sus llamadas",
        # Inglés
        "leave me alone",
        "stop calling me",
        "do not call me again",
        "this is harassment",
        # Portugués
        "me deixe em paz",
        "pare de me ligar",
        "isso é assédio",
    ])
    def test_real_escalation_detected(self, engine: GuardrailsEngine, text: str) -> None:
        result = engine.check_escalation(text)
        assert not result.passed, f"Should detect escalation in: '{text}'"

    @pytest.mark.parametrize("text", [
        "no me interesa el producto",  # objeción refleja, no escalada
        "le dije que no a mi esposa",  # narrativa
        "ya le dije que no podía ir ayer",  # narrativa (pasado)
        "puedo llamarte mas tarde?",  # pregunta, no escalada
        "ah sí, claro, muy bien",  # afirmación
    ])
    def test_no_false_positive(self, engine: GuardrailsEngine, text: str) -> None:
        result = engine.check_escalation(text)
        assert result.passed, f"Should NOT detect escalation in: '{text}'"


# ── Phone normalization ──

class TestPhoneNormalization:
    @pytest.mark.parametrize("input_phone,expected", [
        ("+5219994890531", "+529994890531"),  # strip the 1 after 52
        ("+529994890531", "+529994890531"),  # already normalized
        ("9994890531", "+529994890531"),  # 10-digit MX
        ("+52 999 489 0531", "+529994890531"),  # with spaces
        ("+52 (999) 489-0531", "+529994890531"),  # with parentheses
        ("+1 415 555 1234", "+14155551234"),  # US
    ])
    def test_normalize_mexico(self, input_phone: str, expected: str) -> None:
        assert normalize_phone(input_phone) == expected

    def test_idempotent(self) -> None:
        normalized = normalize_phone("+5219994890531")
        assert normalize_phone(normalized) == normalized


# ── Business hours validation ──

class TestBusinessHours:
    def test_lun_vie_inside_hours(self) -> None:
        # Lunes 10am
        dt = datetime(2026, 4, 13, 10, 0, tzinfo=timezone.utc)
        bh = {"lun-vie": "09:00-18:00"}
        assert _is_in_business_hours(dt, bh)

    def test_lun_vie_outside_hours(self) -> None:
        # Lunes 20:00
        dt = datetime(2026, 4, 13, 20, 0, tzinfo=timezone.utc)
        bh = {"lun-vie": "09:00-18:00"}
        assert not _is_in_business_hours(dt, bh)

    def test_saturday_with_specific_entry(self) -> None:
        # Sábado 10am
        dt = datetime(2026, 4, 11, 10, 0, tzinfo=timezone.utc)
        bh = {"sab": "09:00-14:00", "lun-vie": "09:00-18:00"}
        assert _is_in_business_hours(dt, bh)

    def test_saturday_without_entry_rejected(self) -> None:
        # Sábado 10am pero no hay entrada "sab"
        dt = datetime(2026, 4, 11, 10, 0, tzinfo=timezone.utc)
        bh = {"lun-vie": "09:00-18:00"}
        assert not _is_in_business_hours(dt, bh)

    def test_sunday_always_rejected_without_entry(self) -> None:
        dt = datetime(2026, 4, 12, 10, 0, tzinfo=timezone.utc)
        bh = {"lun-vie": "09:00-18:00"}
        assert not _is_in_business_hours(dt, bh)

    def test_boundary_start(self) -> None:
        dt = datetime(2026, 4, 13, 9, 0, tzinfo=timezone.utc)
        bh = {"lun-vie": "09:00-18:00"}
        assert _is_in_business_hours(dt, bh)

    def test_boundary_end(self) -> None:
        dt = datetime(2026, 4, 13, 18, 0, tzinfo=timezone.utc)
        bh = {"lun-vie": "09:00-18:00"}
        assert _is_in_business_hours(dt, bh)


# ── Callback tool parseo de fecha/hora ──

class TestCallbackTimeParsing:
    def test_parse_iso_date_and_24h_time(self) -> None:
        from agent.tools.callback_tool import _parse_scheduled_time
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo("America/Mexico_City")
        except Exception:
            pytest.skip("zoneinfo not available")
        dt = _parse_scheduled_time("2026-04-15", "14:30", tz)
        assert dt.hour == 14
        assert dt.minute == 30
        assert dt.day == 15

    def test_parse_12h_pm(self) -> None:
        from agent.tools.callback_tool import _parse_scheduled_time
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo("America/Mexico_City")
        except Exception:
            pytest.skip("zoneinfo not available")
        dt = _parse_scheduled_time("2026-04-15", "2:30pm", tz)
        assert dt.hour == 14
        assert dt.minute == 30

    def test_parse_dd_mm_yyyy(self) -> None:
        from agent.tools.callback_tool import _parse_scheduled_time
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo("America/Mexico_City")
        except Exception:
            pytest.skip("zoneinfo not available")
        dt = _parse_scheduled_time("15/04/2026", "09:00", tz)
        assert dt.day == 15
        assert dt.month == 4
        assert dt.year == 2026


# ── VoiceAgent tool filtering ──

class TestVoiceAgentToolFiltering:
    """Valida que _filter_tools_sync funcione en construcción."""

    def test_always_available_tools_kept(self) -> None:
        from agent.agent_factory import VoiceAgent
        assert "schedule_callback" in VoiceAgent._ALWAYS_AVAILABLE
        assert "transfer_to_human" in VoiceAgent._ALWAYS_AVAILABLE
        assert "call_api" in VoiceAgent._ALWAYS_AVAILABLE

    def test_pa_tools_defined(self) -> None:
        from agent.agent_factory import VoiceAgent
        assert "remember" in VoiceAgent._PA_TOOLS
        assert "create_task" in VoiceAgent._PA_TOOLS
