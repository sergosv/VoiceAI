"""Tests para el módulo de quality scoring."""

from unittest.mock import MagicMock, patch

import pytest

from agent.quality import QualityConfig, score_call_quality, _build_transcript_text


class TestQualityConfig:
    def test_default(self):
        cfg = QualityConfig()
        assert cfg.enabled is False
        assert cfg.min_score_alert == 50

    def test_from_dict_none(self):
        cfg = QualityConfig.from_dict(None)
        assert cfg.enabled is False

    def test_from_dict_full(self):
        cfg = QualityConfig.from_dict({
            "enabled": True,
            "min_score_alert": 70,
            "score_criteria": {"resolution": 40, "naturalness": 30},
        })
        assert cfg.enabled is True
        assert cfg.min_score_alert == 70
        assert cfg.score_criteria["resolution"] == 40


class TestBuildTranscript:
    def test_formats_correctly(self):
        transcript = [
            {"role": "user", "text": "Hola"},
            {"role": "assistant", "text": "Bienvenido"},
        ]
        result = _build_transcript_text(transcript)
        assert "user: Hola" in result
        assert "assistant: Bienvenido" in result

    def test_skips_empty(self):
        transcript = [
            {"role": "user", "text": "Hola"},
            {"role": "assistant", "text": "  "},
            {"role": "user", "text": "Test"},
        ]
        result = _build_transcript_text(transcript)
        lines = [l for l in result.split("\n") if l.strip()]
        assert len(lines) == 2


class TestScoreCallQuality:
    @pytest.mark.asyncio
    async def test_short_transcript_returns_none(self):
        result = await score_call_quality([{"role": "user", "text": "hola"}])
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_transcript_returns_none(self):
        result = await score_call_quality([])
        assert result is None

    @pytest.mark.asyncio
    @patch("agent.quality._sync_score")
    async def test_scoring_success(self, mock_score):
        mock_score.return_value = {
            "quality_score": 85,
            "resolution_achieved": True,
            "unanswered_questions": [],
            "knowledge_gaps": [],
            "strengths": ["Empático"],
            "improvement_suggestions": [],
            "adherence_issues": [],
        }
        transcript = [
            {"role": "user", "text": "Quiero una cita"},
            {"role": "assistant", "text": "Claro, para cuándo?"},
        ]
        result = await score_call_quality(transcript, "dental")
        assert result is not None
        assert result["quality_score"] == 85
        assert result["resolution_achieved"] is True

    @pytest.mark.asyncio
    @patch("agent.quality._sync_score", side_effect=Exception("API error"))
    async def test_scoring_error_returns_none(self, mock_score):
        transcript = [
            {"role": "user", "text": "Hola"},
            {"role": "assistant", "text": "Bienvenido"},
        ]
        result = await score_call_quality(transcript)
        assert result is None
