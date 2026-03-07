"""Tests para el módulo de intent extraction en tiempo real."""

from unittest.mock import MagicMock, patch

import pytest

from agent.intent import (
    DEFAULT_INTENTS,
    IntentConfig,
    IntentState,
    RealtimeIntentExtractor,
)


class TestIntentConfig:
    def test_default(self):
        cfg = IntentConfig()
        assert cfg.enabled is False
        assert cfg.custom_intents is None
        assert cfg.intents == DEFAULT_INTENTS

    def test_from_dict_none(self):
        cfg = IntentConfig.from_dict(None)
        assert cfg.enabled is False

    def test_from_dict_custom_intents(self):
        cfg = IntentConfig.from_dict({
            "enabled": True,
            "custom_intents": ["venta", "soporte", "otro"],
        })
        assert cfg.enabled is True
        assert cfg.intents == ["venta", "soporte", "otro"]

    def test_from_dict_no_custom(self):
        cfg = IntentConfig.from_dict({"enabled": True})
        assert cfg.intents == DEFAULT_INTENTS


class TestIntentState:
    def test_empty_state(self):
        state = IntentState()
        assert state.primary_intent is None
        assert state.history == []
        assert state.intent_counts == {}

    def test_update_primary(self):
        state = IntentState(intent_counts={
            "agendar_cita": 3,
            "consulta_precio": 5,
            "saludo": 10,  # Se ignora
        })
        state.update_primary()
        assert state.primary_intent == "consulta_precio"

    def test_update_primary_ignores_saludo_despedida(self):
        state = IntentState(intent_counts={
            "saludo": 5,
            "despedida": 3,
            "otro": 2,
        })
        state.update_primary()
        assert state.primary_intent is None  # Todos son ignorados

    def test_update_primary_single(self):
        state = IntentState(intent_counts={"queja": 1})
        state.update_primary()
        assert state.primary_intent == "queja"


class TestRealtimeIntentExtractor:
    def _make_extractor(self, **kwargs):
        cfg = IntentConfig(enabled=True, **kwargs)
        return RealtimeIntentExtractor(config=cfg)

    @pytest.mark.asyncio
    async def test_short_text_returns_otro(self):
        ext = self._make_extractor()
        result = await ext.extract_intent("ok")
        assert result == "otro"

    @pytest.mark.asyncio
    async def test_empty_text_returns_otro(self):
        ext = self._make_extractor()
        result = await ext.extract_intent("")
        assert result == "otro"

    @pytest.mark.asyncio
    @patch("agent.intent.RealtimeIntentExtractor._classify_sync")
    async def test_extract_agendar(self, mock_classify):
        mock_classify.return_value = "agendar_cita"
        ext = self._make_extractor()
        result = await ext.extract_intent("Quiero agendar una cita para mañana")
        assert result == "agendar_cita"
        assert ext.state.history[0]["intent"] == "agendar_cita"
        assert ext.state.intent_counts["agendar_cita"] == 1

    @pytest.mark.asyncio
    @patch("agent.intent.RealtimeIntentExtractor._classify_sync")
    async def test_primary_intent_updates(self, mock_classify):
        ext = self._make_extractor()
        mock_classify.return_value = "saludo"
        await ext.extract_intent("Hola buenos días")
        mock_classify.return_value = "consulta_precio"
        await ext.extract_intent("Cuánto cuesta una limpieza?")
        await ext.extract_intent("Y el blanqueamiento?")
        assert ext.state.primary_intent == "consulta_precio"

    @pytest.mark.asyncio
    @patch("agent.intent.RealtimeIntentExtractor._classify_sync")
    async def test_history_tracks_turns(self, mock_classify):
        ext = self._make_extractor()
        mock_classify.return_value = "queja"
        await ext.extract_intent("El servicio fue terrible")
        mock_classify.return_value = "cancelar"
        await ext.extract_intent("Quiero cancelar")
        assert len(ext.state.history) == 2
        assert ext.state.history[0]["turn"] == 1
        assert ext.state.history[1]["turn"] == 2

    @pytest.mark.asyncio
    @patch("agent.intent.RealtimeIntentExtractor._classify_sync")
    async def test_summary(self, mock_classify):
        ext = self._make_extractor()
        mock_classify.return_value = "agendar_cita"
        await ext.extract_intent("Quiero una cita")
        summary = ext.get_call_intent_summary()
        assert summary["total_turns"] == 1
        assert summary["primary_intent"] == "agendar_cita"
        assert "agendar_cita" in summary["intent_counts"]

    @pytest.mark.asyncio
    async def test_fallback_on_error(self):
        ext = self._make_extractor()
        with patch.object(ext, "_classify_sync", side_effect=Exception("API error")):
            result = await ext.extract_intent("Esto debería fallar gracefully")
            assert result == "otro"

    def test_classify_sync_validates(self):
        ext = self._make_extractor()
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "fake"}):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "  Agendar_Cita.  "
            mock_client.models.generate_content.return_value = mock_response
            ext._client = mock_client
            result = ext._classify_sync("quiero una cita")
            assert result == "agendar_cita"

    def test_classify_sync_partial_match(self):
        ext = self._make_extractor()
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "fake"}):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "The intent is consulta_precio based on context"
            mock_client.models.generate_content.return_value = mock_response
            ext._client = mock_client
            result = ext._classify_sync("cuanto cuesta?")
            assert result == "consulta_precio"

    def test_classify_sync_unknown(self):
        ext = self._make_extractor()
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "fake"}):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "completely_unknown_intent"
            mock_client.models.generate_content.return_value = mock_response
            ext._client = mock_client
            result = ext._classify_sync("abc")
            assert result == "otro"

    def test_classify_sync_no_api_key(self):
        ext = self._make_extractor()
        ext._client = None
        with patch.dict("os.environ", {}, clear=True):
            result = ext._classify_sync("hello")
            assert result == "otro"

    def test_custom_intents(self):
        ext = self._make_extractor(custom_intents=["reservar", "consultar", "otro"])
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "fake"}):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "reservar"
            mock_client.models.generate_content.return_value = mock_response
            ext._client = mock_client
            result = ext._classify_sync("quiero reservar mesa")
            assert result == "reservar"
