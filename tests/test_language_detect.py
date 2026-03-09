"""Tests para el módulo de detección de idioma y live language switching."""

from unittest.mock import MagicMock, patch

import pytest

from agent.config_loader import AgentConfig, ResolvedConfig, SlimClientConfig
from agent.language_detect import (
    LANGUAGE_CONFIGS,
    LanguageDetectionConfig,
    LanguageDetector,
    LanguageState,
)


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


# ── Helpers para tests de live switching ──────────────────


def _make_resolved_config(
    language: str = "es",
    tts_provider: str = "cartesia",
    voice_id: str = "default",
    language_detection_config: dict | None = None,
) -> ResolvedConfig:
    agent = AgentConfig(
        id="agent-1",
        client_id="client-1",
        name="Test Agent",
        slug="test-agent",
        phone_number=None,
        phone_sid=None,
        livekit_sip_trunk_id=None,
        system_prompt="Eres un agente de prueba.",
        greeting="Hola",
        examples=None,
        voice_config={"provider": tts_provider, "voice_id": voice_id},
        language_detection_config=language_detection_config,
    )
    client = SlimClientConfig(
        id="client-1",
        name="Test Client",
        slug="test-client",
        business_type="generic",
        language=language,
        file_search_store_id=None,
    )
    return ResolvedConfig(agent=agent, client=client)


# ── Tests de live language switching en VoiceAgent ────────


class TestVoiceAgentLanguageSwitching:
    """Tests para switch_language() y tts_node dinámico en VoiceAgent."""

    def _make_agent(
        self,
        language: str = "es",
        language_detector: LanguageDetector | None = None,
    ):
        from agent.agent_factory import VoiceAgent
        config = _make_resolved_config(language=language)
        return VoiceAgent(
            config,
            language_detector=language_detector,
        )

    @patch("agent.pipeline_builder.build_tts")
    def test_switch_language_updates_tts(self, mock_build_tts):
        """switch_language() debe crear un nuevo TTS y actualizar el idioma."""
        mock_tts = MagicMock()
        mock_build_tts.return_value = mock_tts

        agent = self._make_agent(language="es")
        assert agent.current_language == "es"
        assert agent._dynamic_tts is None

        agent.switch_language("en")

        assert agent.current_language == "en"
        assert agent._dynamic_tts is mock_tts
        mock_build_tts.assert_called_once()
        # Verificar que se pasó "en" como idioma TTS
        call_args = mock_build_tts.call_args
        assert call_args[0][1] == "en"

    @patch("agent.pipeline_builder.build_tts")
    def test_switch_same_language_noop(self, mock_build_tts):
        """switch_language() con mismo idioma no debe hacer nada."""
        agent = self._make_agent(language="es")
        agent.switch_language("es")

        assert agent._dynamic_tts is None
        mock_build_tts.assert_not_called()

    @patch("agent.pipeline_builder.build_tts")
    def test_switch_language_caches_tts(self, mock_build_tts):
        """TTS debe cachearse por idioma, no reconstruirse cada vez."""
        mock_tts_en = MagicMock()
        mock_tts_pt = MagicMock()
        mock_build_tts.side_effect = [mock_tts_en, mock_tts_pt]

        agent = self._make_agent(language="es")

        # Primera vez: construye TTS para "en"
        agent.switch_language("en")
        assert mock_build_tts.call_count == 1

        # Cambiar a "pt": construye TTS para "pt-BR"
        agent.switch_language("pt")
        assert mock_build_tts.call_count == 2

        # Volver a "en": usa cache, no reconstruye
        agent.switch_language("en")
        assert mock_build_tts.call_count == 2
        assert agent._dynamic_tts is mock_tts_en

    @patch("agent.pipeline_builder.build_tts")
    def test_switch_language_applies_prompt_override(self, mock_build_tts):
        """switch_language() debe aplicar prompt override si está configurado."""
        mock_build_tts.return_value = MagicMock()

        lang_cfg = LanguageDetectionConfig(
            enabled=True,
            supported_languages=["es", "en"],
            prompts_by_language={"en": "You are a helpful assistant."},
        )
        detector = LanguageDetector(config=lang_cfg, default_language="es")
        # Simular que el detector ya decidió "en"
        detector._state.detected_language = "en"

        agent = self._make_agent(language="es", language_detector=detector)
        agent.switch_language("en")

        assert agent.instructions == "You are a helpful assistant."

    @patch("agent.pipeline_builder.build_tts")
    def test_switch_language_no_prompt_override_when_not_configured(self, mock_build_tts):
        """Sin prompts_by_language, el prompt no debe cambiar."""
        mock_build_tts.return_value = MagicMock()

        lang_cfg = LanguageDetectionConfig(
            enabled=True,
            supported_languages=["es", "en"],
        )
        detector = LanguageDetector(config=lang_cfg, default_language="es")
        detector._state.detected_language = "en"

        agent = self._make_agent(language="es", language_detector=detector)
        original_prompt = agent.instructions
        agent.switch_language("en")

        # El prompt no debe haber cambiado
        assert agent.instructions == original_prompt

    def test_tts_node_returns_default_when_no_dynamic_tts(self):
        """Sin switch de idioma, tts_node() debe delegar al default."""
        from livekit.agents.voice.agent import Agent as BaseAgent
        agent = self._make_agent()
        text = MagicMock()
        settings = MagicMock()

        with patch.object(BaseAgent, "default") as mock_default:
            mock_default.tts_node.return_value = MagicMock()
            agent.tts_node(text, settings)
            mock_default.tts_node.assert_called_once()

    @patch("agent.pipeline_builder.build_tts")
    def test_tts_node_uses_dynamic_after_switch(self, mock_build_tts):
        """Después de switch_language(), tts_node() debe usar _dynamic_tts_node."""
        mock_tts = MagicMock()
        mock_build_tts.return_value = mock_tts

        agent = self._make_agent()
        agent.switch_language("en")

        text = MagicMock()
        settings = MagicMock()
        result = agent.tts_node(text, settings)
        # Debe retornar una coroutine (de _dynamic_tts_node)
        assert result is not None

    def test_language_configs_mapping(self):
        """Verificar que LANGUAGE_CONFIGS tiene mapeos correctos."""
        assert LANGUAGE_CONFIGS["es"]["tts_lang"] == "es"
        assert LANGUAGE_CONFIGS["en"]["tts_lang"] == "en"
        assert LANGUAGE_CONFIGS["pt"]["tts_lang"] == "pt-BR"
        assert LANGUAGE_CONFIGS["fr"]["tts_lang"] == "fr"


class TestMultiLangSTTBuilder:
    """Tests para build_stt con soporte multi-idioma."""

    @patch("livekit.plugins.deepgram.STT")
    def test_single_language_stt(self, mock_stt_cls):
        """Sin multi_lang, STT debe usar un solo idioma fijo."""
        from agent.pipeline_builder import build_stt

        config = _make_resolved_config().agent
        build_stt(config, "es")

        mock_stt_cls.assert_called_once()
        kwargs = mock_stt_cls.call_args[1]
        assert kwargs["language"] == "es"
        assert "detect_language" not in kwargs

    @patch("livekit.plugins.deepgram.STT")
    def test_multi_lang_stt_enables_detection(self, mock_stt_cls):
        """Con multi_lang > 1 idioma, debe habilitar detect_language."""
        from agent.pipeline_builder import build_stt

        config = _make_resolved_config().agent
        build_stt(config, "es", multi_lang=["es", "en"])

        mock_stt_cls.assert_called_once()
        kwargs = mock_stt_cls.call_args[1]
        assert kwargs["detect_language"] is True
        assert "language" not in kwargs

    @patch("livekit.plugins.deepgram.STT")
    def test_multi_lang_single_language_no_detection(self, mock_stt_cls):
        """Con multi_lang de 1 solo idioma, no habilitar detect_language."""
        from agent.pipeline_builder import build_stt

        config = _make_resolved_config().agent
        build_stt(config, "es", multi_lang=["es"])

        kwargs = mock_stt_cls.call_args[1]
        assert kwargs["language"] == "es"
        assert "detect_language" not in kwargs

    @patch("livekit.plugins.deepgram.STT")
    def test_multi_lang_none_no_detection(self, mock_stt_cls):
        """Con multi_lang=None, comportamiento normal."""
        from agent.pipeline_builder import build_stt

        config = _make_resolved_config().agent
        build_stt(config, "en", multi_lang=None)

        kwargs = mock_stt_cls.call_args[1]
        assert kwargs["language"] == "en"
        assert "detect_language" not in kwargs


class TestBuildAgentWithLanguageDetector:
    """Tests para build_agent() con language_detector."""

    @patch("agent.agent_factory._voice_rules", return_value="")
    def test_build_agent_passes_language_detector(self, mock_rules):
        """build_agent() debe pasar el language_detector al VoiceAgent."""
        from agent.agent_factory import build_agent, VoiceAgent

        config = _make_resolved_config()
        lang_cfg = LanguageDetectionConfig(
            enabled=True, supported_languages=["es", "en"]
        )
        detector = LanguageDetector(config=lang_cfg, default_language="es")

        agent = build_agent(config, language_detector=detector)
        assert isinstance(agent, VoiceAgent)
        assert agent._language_detector is detector

    @patch("agent.agent_factory._voice_rules", return_value="")
    def test_build_agent_without_language_detector(self, mock_rules):
        """build_agent() sin detector debe crear agente normal."""
        from agent.agent_factory import build_agent, VoiceAgent

        config = _make_resolved_config()
        agent = build_agent(config)
        assert isinstance(agent, VoiceAgent)
        assert agent._language_detector is None
        assert agent._dynamic_tts is None
