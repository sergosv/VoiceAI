"""Tests para el módulo de sentimiento en tiempo real."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.sentiment import (
    EMPATHY_DIRECTIVES,
    SENTIMENT_LEVELS,
    RealtimeSentimentAnalyzer,
    SentimentConfig,
    SentimentState,
)


# ── SentimentConfig ──────────────────────────────────────

class TestSentimentConfig:
    def test_default_config(self):
        cfg = SentimentConfig()
        assert cfg.enabled is False
        assert cfg.escalation_threshold == 3
        assert cfg.auto_transfer is False
        assert cfg.notify_on_negative is True

    def test_from_dict_none(self):
        cfg = SentimentConfig.from_dict(None)
        assert cfg.enabled is False

    def test_from_dict_empty(self):
        cfg = SentimentConfig.from_dict({})
        assert cfg.enabled is False

    def test_from_dict_full(self):
        cfg = SentimentConfig.from_dict({
            "enabled": True,
            "escalation_threshold": 5,
            "auto_transfer": True,
            "notify_on_negative": False,
        })
        assert cfg.enabled is True
        assert cfg.escalation_threshold == 5
        assert cfg.auto_transfer is True
        assert cfg.notify_on_negative is False

    def test_from_dict_partial(self):
        cfg = SentimentConfig.from_dict({"enabled": True})
        assert cfg.enabled is True
        assert cfg.escalation_threshold == 3  # default


# ── SentimentState ───────────────────────────────────────

class TestSentimentState:
    def test_empty_state(self):
        state = SentimentState()
        assert state.last_sentiment is None
        assert state.average_score == 0.0
        assert state.timeline == []

    def test_last_sentiment(self):
        state = SentimentState(history=["positive", "negative", "neutral"])
        assert state.last_sentiment == "neutral"

    def test_average_score(self):
        state = SentimentState(history=["positive", "negative"])
        # positive=1, negative=-1 → avg=0
        assert state.average_score == 0.0

    def test_average_score_negative(self):
        state = SentimentState(history=["frustrated", "angry", "negative"])
        # -2, -2, -1 → -5/3
        assert round(state.average_score, 2) == -1.67

    def test_timeline(self):
        state = SentimentState(history=["positive", "frustrated"])
        timeline = state.timeline
        assert len(timeline) == 2
        assert timeline[0] == {"turn": 1, "sentiment": "positive", "score": 1}
        assert timeline[1] == {"turn": 2, "sentiment": "frustrated", "score": -2}


# ── RealtimeSentimentAnalyzer ────────────────────────────

class TestRealtimeSentimentAnalyzer:
    def _make_analyzer(self, **kwargs):
        cfg = SentimentConfig(enabled=True, **kwargs)
        return RealtimeSentimentAnalyzer(config=cfg, language="es")

    @pytest.mark.asyncio
    async def test_short_text_returns_neutral(self):
        analyzer = self._make_analyzer()
        result = await analyzer.analyze_turn("ok")
        assert result == "neutral"

    @pytest.mark.asyncio
    async def test_empty_text_returns_neutral(self):
        analyzer = self._make_analyzer()
        result = await analyzer.analyze_turn("")
        assert result == "neutral"

    @pytest.mark.asyncio
    @patch("agent.sentiment.RealtimeSentimentAnalyzer._classify_sync")
    async def test_analyze_positive(self, mock_classify):
        mock_classify.return_value = "positive"
        analyzer = self._make_analyzer()
        result = await analyzer.analyze_turn("Muchas gracias, excelente servicio!")
        assert result == "positive"
        assert analyzer.state.history == ["positive"]
        assert analyzer.state.consecutive_negative == 0

    @pytest.mark.asyncio
    @patch("agent.sentiment.RealtimeSentimentAnalyzer._classify_sync")
    async def test_analyze_negative_increments_counter(self, mock_classify):
        mock_classify.return_value = "negative"
        analyzer = self._make_analyzer()
        await analyzer.analyze_turn("No me sirve esto")
        assert analyzer.state.consecutive_negative == 1
        await analyzer.analyze_turn("Sigo esperando")
        assert analyzer.state.consecutive_negative == 2

    @pytest.mark.asyncio
    @patch("agent.sentiment.RealtimeSentimentAnalyzer._classify_sync")
    async def test_positive_resets_counter(self, mock_classify):
        analyzer = self._make_analyzer()
        mock_classify.return_value = "negative"
        await analyzer.analyze_turn("Malo")
        await analyzer.analyze_turn("Peor")
        assert analyzer.state.consecutive_negative == 2
        mock_classify.return_value = "positive"
        await analyzer.analyze_turn("Bueno, gracias")
        assert analyzer.state.consecutive_negative == 0

    @pytest.mark.asyncio
    @patch("agent.sentiment.RealtimeSentimentAnalyzer._classify_sync")
    async def test_mild_directive_at_2_consecutive(self, mock_classify):
        mock_classify.return_value = "negative"
        analyzer = self._make_analyzer()
        await analyzer.analyze_turn("No me gusta")
        assert analyzer.state.current_directive is None
        await analyzer.analyze_turn("Sigo molesto")
        assert analyzer.state.current_directive == "mild"

    @pytest.mark.asyncio
    @patch("agent.sentiment.RealtimeSentimentAnalyzer._classify_sync")
    async def test_severe_directive_at_threshold(self, mock_classify):
        mock_classify.return_value = "frustrated"
        analyzer = self._make_analyzer(escalation_threshold=3)
        for i in range(3):
            await analyzer.analyze_turn(f"Esto es terrible {i}")
        assert analyzer.state.current_directive == "severe"
        assert analyzer.state.escalation_triggered is True

    @pytest.mark.asyncio
    @patch("agent.sentiment.RealtimeSentimentAnalyzer._classify_sync")
    async def test_empathy_directive_content(self, mock_classify):
        mock_classify.return_value = "frustrated"
        analyzer = self._make_analyzer(escalation_threshold=2)
        await analyzer.analyze_turn("Malo")
        await analyzer.analyze_turn("Peor")
        directive = analyzer.get_empathy_directive()
        assert "ALERTA URGENTE" in directive
        assert "frustrado" in directive.lower() or "frustración" in directive.lower()

    @pytest.mark.asyncio
    @patch("agent.sentiment.RealtimeSentimentAnalyzer._classify_sync")
    async def test_empathy_directive_english(self, mock_classify):
        mock_classify.return_value = "angry"
        cfg = SentimentConfig(enabled=True, escalation_threshold=2)
        analyzer = RealtimeSentimentAnalyzer(config=cfg, language="en")
        await analyzer.analyze_turn("This is terrible")
        await analyzer.analyze_turn("I want to cancel")
        directive = analyzer.get_empathy_directive()
        assert "URGENT ALERT" in directive

    @pytest.mark.asyncio
    @patch("agent.sentiment.RealtimeSentimentAnalyzer._classify_sync")
    async def test_no_directive_when_positive(self, mock_classify):
        mock_classify.return_value = "positive"
        analyzer = self._make_analyzer()
        await analyzer.analyze_turn("Todo bien")
        assert analyzer.get_empathy_directive() == ""

    @pytest.mark.asyncio
    @patch("agent.sentiment.RealtimeSentimentAnalyzer._classify_sync")
    async def test_auto_transfer(self, mock_classify):
        mock_classify.return_value = "frustrated"
        analyzer = self._make_analyzer(auto_transfer=True, escalation_threshold=2)
        await analyzer.analyze_turn("Terrible")
        assert not analyzer.should_auto_transfer()
        await analyzer.analyze_turn("Horrible")
        assert analyzer.should_auto_transfer()
        analyzer.mark_transfer_done()
        assert not analyzer.should_auto_transfer()

    @pytest.mark.asyncio
    @patch("agent.sentiment.RealtimeSentimentAnalyzer._classify_sync")
    async def test_no_auto_transfer_when_disabled(self, mock_classify):
        mock_classify.return_value = "frustrated"
        analyzer = self._make_analyzer(auto_transfer=False, escalation_threshold=2)
        await analyzer.analyze_turn("Terrible")
        await analyzer.analyze_turn("Horrible")
        assert not analyzer.should_auto_transfer()

    @pytest.mark.asyncio
    @patch("agent.sentiment.RealtimeSentimentAnalyzer._classify_sync")
    async def test_call_sentiment_summary(self, mock_classify):
        analyzer = self._make_analyzer()
        mock_classify.return_value = "positive"
        await analyzer.analyze_turn("Genial")
        mock_classify.return_value = "negative"
        await analyzer.analyze_turn("Malo")
        mock_classify.return_value = "neutral"
        await analyzer.analyze_turn("Bueno ok")

        summary = analyzer.get_call_sentiment_summary()
        assert summary["total_turns"] == 3
        assert len(summary["timeline"]) == 3
        assert summary["escalation_triggered"] is False
        assert "average_score" in summary
        assert "avg_analysis_ms" in summary

    @pytest.mark.asyncio
    @patch("agent.sentiment.RealtimeSentimentAnalyzer._classify_sync")
    async def test_max_consecutive_negative(self, mock_classify):
        analyzer = self._make_analyzer(escalation_threshold=10)
        mock_classify.return_value = "negative"
        await analyzer.analyze_turn("Esto es malo")
        await analyzer.analyze_turn("Sigo molesto")
        await analyzer.analyze_turn("No me gusta nada")
        mock_classify.return_value = "positive"
        await analyzer.analyze_turn("Bueno, gracias")
        mock_classify.return_value = "negative"
        await analyzer.analyze_turn("Otra queja más")

        summary = analyzer.get_call_sentiment_summary()
        assert summary["consecutive_negative_max"] == 3

    @pytest.mark.asyncio
    async def test_classify_sync_fallback_on_error(self):
        analyzer = self._make_analyzer()
        with patch.object(
            analyzer, "_classify_sync", side_effect=Exception("API error")
        ):
            result = await analyzer.analyze_turn("Esto debería fallar gracefully")
            assert result == "neutral"

    def test_classify_sync_validates_response(self):
        analyzer = self._make_analyzer()
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "fake"}):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "   Positive.  "
            mock_client.models.generate_content.return_value = mock_response
            analyzer._client = mock_client

            result = analyzer._classify_sync("Great service!")
            assert result == "positive"

    def test_classify_sync_handles_unknown(self):
        analyzer = self._make_analyzer()
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "fake"}):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "confused_and_uncertain"
            mock_client.models.generate_content.return_value = mock_response
            analyzer._client = mock_client

            result = analyzer._classify_sync("hmm")
            assert result == "neutral"

    def test_classify_sync_partial_match(self):
        analyzer = self._make_analyzer()
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "fake"}):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "The user seems frustrated"
            mock_client.models.generate_content.return_value = mock_response
            analyzer._client = mock_client

            result = analyzer._classify_sync("terrible service")
            assert result == "frustrated"

    def test_classify_sync_no_api_key(self):
        analyzer = self._make_analyzer()
        analyzer._client = None
        with patch.dict("os.environ", {}, clear=True):
            result = analyzer._classify_sync("hello")
            assert result == "neutral"


# ── Constantes ───────────────────────────────────────────

class TestConstants:
    def test_sentiment_levels_coverage(self):
        assert "frustrated" in SENTIMENT_LEVELS
        assert "angry" in SENTIMENT_LEVELS
        assert "negative" in SENTIMENT_LEVELS
        assert "neutral" in SENTIMENT_LEVELS
        assert "positive" in SENTIMENT_LEVELS
        assert "happy" in SENTIMENT_LEVELS

    def test_empathy_directives_languages(self):
        assert "es" in EMPATHY_DIRECTIVES
        assert "en" in EMPATHY_DIRECTIVES
        for lang in ("es", "en"):
            assert "mild" in EMPATHY_DIRECTIVES[lang]
            assert "severe" in EMPATHY_DIRECTIVES[lang]
