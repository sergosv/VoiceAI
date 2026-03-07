"""Tests para api/cost_rates.py — rates, clasificación y desglose de costos."""

from __future__ import annotations

from decimal import Decimal

import pytest

from api.cost_rates import (
    build_cost_breakdown,
    classify_service,
    estimate_cost,
    get_external_rate,
)


class TestClassifyService:
    def test_platform_services(self):
        assert classify_service("livekit", None) == "platform"
        assert classify_service("telephony", None) == "platform"

    def test_included_provider_is_platform(self):
        assert classify_service("stt", "deepgram") == "platform"
        assert classify_service("llm", "google") == "platform"
        assert classify_service("tts", "cartesia") == "platform"

    def test_external_provider(self):
        assert classify_service("stt", "openai") == "external"
        assert classify_service("llm", "openai") == "external"
        assert classify_service("tts", "elevenlabs") == "external"

    def test_unknown_provider_is_external(self):
        assert classify_service("stt", "whisper-local") == "external"

    def test_no_provider_non_platform(self):
        assert classify_service("stt", None) == "external"


class TestGetExternalRate:
    def test_known_providers(self):
        assert get_external_rate("stt", "deepgram") == Decimal("0.0043")
        assert get_external_rate("llm", "anthropic") == Decimal("0.012")
        assert get_external_rate("tts", "elevenlabs") == Decimal("0.030")

    def test_ambiguous_providers(self):
        # google_stt vs google_llm
        assert get_external_rate("stt", "google") == Decimal("0.006")
        assert get_external_rate("llm", "google") == Decimal("0.004")
        # openai_stt vs openai_tts vs openai_llm
        assert get_external_rate("stt", "openai") == Decimal("0.006")
        assert get_external_rate("tts", "openai") == Decimal("0.015")
        assert get_external_rate("llm", "openai") == Decimal("0.015")

    def test_unknown_provider_defaults(self):
        result = get_external_rate("stt", "unknown-provider")
        assert result == Decimal("0.01")


class TestBuildCostBreakdown:
    def test_basic_call(self):
        call = {
            "duration_seconds": 120,
            "cost_livekit": "0.02",
            "cost_telephony": "0.02",
            "cost_stt": "0.01",
            "cost_llm": "0.02",
            "cost_tts": "0.02",
            "metadata": {
                "stt_provider": "deepgram",
                "llm_provider": "google",
                "tts_provider": "cartesia",
            },
        }
        result = build_cost_breakdown(call)
        assert "platform_cost" in result
        assert "external_cost_estimate" in result
        assert "total" in result
        assert len(result["lines"]) == 5
        # All included providers → all platform
        for line in result["lines"]:
            assert line["classification"] == "platform"
        assert result["external_cost_estimate"] == 0

    def test_external_provider(self):
        call = {
            "duration_seconds": 60,
            "cost_livekit": "0.01",
            "cost_telephony": "0.01",
            "cost_stt": "0.006",
            "cost_llm": "0",
            "cost_tts": "0",
            "metadata": {
                "stt_provider": "deepgram",
                "llm_provider": "openai",
                "tts_provider": "elevenlabs",
            },
        }
        result = build_cost_breakdown(call)
        external_lines = [l for l in result["lines"] if l["classification"] == "external"]
        assert len(external_lines) == 2  # llm + tts
        assert result["external_cost_estimate"] > 0

    def test_no_metadata(self):
        call = {"duration_seconds": 60, "metadata": None}
        result = build_cost_breakdown(call)
        assert len(result["lines"]) == 5

    def test_zero_duration(self):
        call = {"duration_seconds": 0, "metadata": {}}
        result = build_cost_breakdown(call)
        assert result["total"] == 0


class TestEstimateCost:
    def test_platform_providers(self):
        result = estimate_cost("deepgram", "google", "cartesia", 1.0)
        assert result["minutes"] == 1.0
        assert result["platform_cost"] > 0
        assert result["external_cost_estimate"] == 0
        assert len(result["lines"]) == 5

    def test_external_providers(self):
        result = estimate_cost("openai", "openai", "elevenlabs", 1.0)
        assert result["external_cost_estimate"] > 0
        # platform still has livekit + telephony
        assert result["platform_cost"] > 0

    def test_zero_minutes(self):
        result = estimate_cost("deepgram", "google", "cartesia", 0)
        assert result["total_estimate"] == 0

    def test_scales_with_minutes(self):
        r1 = estimate_cost("deepgram", "google", "cartesia", 1.0)
        r5 = estimate_cost("deepgram", "google", "cartesia", 5.0)
        assert r5["total_estimate"] == pytest.approx(r1["total_estimate"] * 5, rel=1e-4)

    def test_has_note(self):
        result = estimate_cost("deepgram", "google", "cartesia", 1.0)
        assert "note" in result
