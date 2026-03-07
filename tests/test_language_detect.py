"""Tests para el módulo de detección de idioma."""

from unittest.mock import MagicMock, patch

import pytest

from agent.language_detect import LanguageDetectionConfig, LanguageDetector, LanguageState


class TestLanguageDetectionConfig:
    def test_default(self):
        cfg = LanguageDetectionConfig()
        assert cfg.enabled is False
        assert cfg.supported_languages == ["es", "en"]
        assert cfg.detection_turns == 2

    def test_from_dict_none(self):
        cfg = LanguageDetectionConfig.from_dict(None)
        assert cfg.enabled is False

    def test_from_dict_custom(self):
        cfg = LanguageDetectionConfig.from_dict({
            "enabled": True,
            "supported_languages": ["es", "en", "pt"],
            "detection_turns": 3,
            "prompts_by_language": {"en": "You are a helpful assistant."},
        })
        assert cfg.enabled is True
        assert "pt" in cfg.supported_languages
        assert cfg.detection_turns == 3
        assert cfg.prompts_by_language["en"] == "You are a helpful assistant."


class TestLanguageDetector:
    def _make_detector(self, **kwargs):
        cfg = LanguageDetectionConfig(enabled=True, **kwargs)
        return LanguageDetector(config=cfg, default_language="es")

    @pytest.mark.asyncio
    async def test_short_text_ignored(self):
        det = self._make_detector()
        result = await det.detect_turn("ok")
        assert result is None
        assert len(det.state.detections) == 0

    @pytest.mark.asyncio
    @patch("agent.language_detect.LanguageDetector._detect_sync")
    async def test_needs_n_turns(self, mock_detect):
        mock_detect.return_value = "en"
        det = self._make_detector(detection_turns=2)

        # Primer turno: no decide aún
        result = await det.detect_turn("Hello, how are you?")
        assert result is None
        assert not det.state.decided

        # Segundo turno: decide
        result = await det.detect_turn("I need an appointment please")
        assert result == "en"
        assert det.state.decided
        assert det.state.switched is True

    @pytest.mark.asyncio
    @patch("agent.language_detect.LanguageDetector._detect_sync")
    async def test_same_language_no_switch(self, mock_detect):
        mock_detect.return_value = "es"
        det = self._make_detector(detection_turns=1)

        result = await det.detect_turn("Hola, quiero una cita")
        assert result is None  # No switch (ya es español)
        assert det.state.decided
        assert det.state.switched is False

    @pytest.mark.asyncio
    @patch("agent.language_detect.LanguageDetector._detect_sync")
    async def test_unsupported_language_fallback(self, mock_detect):
        mock_detect.return_value = "zh"  # Chino no soportado
        det = self._make_detector(
            supported_languages=["es", "en"],
            detection_turns=1,
        )

        result = await det.detect_turn("你好，我需要预约")
        assert result is None  # No switch
        assert det.state.detected_language == "es"  # Mantiene default

    @pytest.mark.asyncio
    @patch("agent.language_detect.LanguageDetector._detect_sync")
    async def test_majority_vote(self, mock_detect):
        det = self._make_detector(detection_turns=3)

        mock_detect.return_value = "en"
        await det.detect_turn("Hello there")
        mock_detect.return_value = "es"
        await det.detect_turn("Ah sí, necesito ayuda")
        mock_detect.return_value = "en"
        result = await det.detect_turn("Can you help me?")
        assert result == "en"  # 2 en vs 1 es

    @pytest.mark.asyncio
    @patch("agent.language_detect.LanguageDetector._detect_sync")
    async def test_no_more_detection_after_decided(self, mock_detect):
        mock_detect.return_value = "en"
        det = self._make_detector(detection_turns=1)

        await det.detect_turn("Hello")
        result = await det.detect_turn("More text")
        assert result is None  # Ya decidido, no re-detecta

    def test_detect_sync_validates_output(self):
        det = self._make_detector()
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "fake"}):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "  EN  "
            mock_client.models.generate_content.return_value = mock_response
            det._client = mock_client

            result = det._detect_sync("Hello world")
            assert result == "en"

    def test_detect_sync_garbage_returns_default(self):
        det = self._make_detector()
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "fake"}):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "!@#$%^"  # No alpha chars
            mock_client.models.generate_content.return_value = mock_response
            det._client = mock_client

            result = det._detect_sync("something")
            assert result == "es"  # Default

    def test_prompt_override(self):
        det = self._make_detector(
            prompts_by_language={"en": "You are a helpful assistant."}
        )
        det._state.detected_language = "en"
        override = det.get_language_prompt_override()
        assert override == "You are a helpful assistant."

    def test_prompt_override_none(self):
        det = self._make_detector()
        assert det.get_language_prompt_override() is None

    def test_summary(self):
        det = self._make_detector()
        det._state.detections = ["es", "en"]
        det._state.detected_language = "en"
        det._state.switched = True

        summary = det.get_summary()
        assert summary["detected_language"] == "en"
        assert summary["switched"] is True
        assert summary["default_language"] == "es"
