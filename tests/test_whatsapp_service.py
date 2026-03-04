"""Tests para el servicio orquestador de WhatsApp."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.whatsapp.history import deserialize_history, serialize_history
from api.services.whatsapp.provider import InboundMessage


# ── History Serialization ──────────────────────────────


class TestHistorySerialization:
    """Tests para serialize/deserialize de historial Gemini."""

    def test_roundtrip_text(self):
        from google.genai import types

        original = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text="Hola, ¿tienen citas disponibles?")],
            ),
            types.Content(
                role="model",
                parts=[types.Part.from_text(text="¡Claro! Tenemos citas el lunes y martes.")],
            ),
        ]

        serialized = serialize_history(original)
        assert len(serialized) == 2
        assert serialized[0]["role"] == "user"
        assert serialized[0]["parts"][0]["type"] == "text"
        assert serialized[0]["parts"][0]["text"] == "Hola, ¿tienen citas disponibles?"

        deserialized = deserialize_history(serialized)
        assert len(deserialized) == 2
        assert deserialized[0].role == "user"
        assert deserialized[0].parts[0].text == "Hola, ¿tienen citas disponibles?"
        assert deserialized[1].role == "model"

    def test_roundtrip_function_call(self):
        from google.genai import types

        original = [
            types.Content(
                role="model",
                parts=[types.Part(
                    function_call=types.FunctionCall(
                        name="search_knowledge",
                        args={"query": "horarios"},
                    )
                )],
            ),
        ]

        serialized = serialize_history(original)
        assert serialized[0]["parts"][0]["type"] == "function_call"
        assert serialized[0]["parts"][0]["name"] == "search_knowledge"
        assert serialized[0]["parts"][0]["args"]["query"] == "horarios"

        deserialized = deserialize_history(serialized)
        assert deserialized[0].parts[0].function_call is not None
        assert deserialized[0].parts[0].function_call.name == "search_knowledge"

    def test_roundtrip_function_response(self):
        from google.genai import types

        original = [
            types.Content(
                role="user",
                parts=[types.Part.from_function_response(
                    name="search_knowledge",
                    response={"result": "Horario: 9am-5pm"},
                )],
            ),
        ]

        serialized = serialize_history(original)
        assert serialized[0]["parts"][0]["type"] == "function_response"
        assert serialized[0]["parts"][0]["name"] == "search_knowledge"

        deserialized = deserialize_history(serialized)
        assert deserialized[0].parts[0].function_response is not None

    def test_empty_history(self):
        assert serialize_history([]) == []
        assert deserialize_history([]) == []

    def test_deserialize_empty_parts(self):
        data = [{"role": "user", "parts": []}]
        result = deserialize_history(data)
        assert result == []  # No content sin parts


# ── InboundMessage ─────────────────────────────────────


class TestInboundMessage:
    def test_text_message(self):
        msg = InboundMessage(
            remote_phone="5215551234567",
            text="Hola",
            message_type="text",
        )
        assert msg.remote_phone == "5215551234567"
        assert msg.text == "Hola"
        assert msg.message_type == "text"
        assert msg.ghl_location_id is None
        assert msg.evo_instance_id is None

    def test_media_message(self):
        msg = InboundMessage(
            remote_phone="5215551234567",
            text="",
            message_type="image",
            provider_message_id="img001",
            evo_instance_id="mi-inst",
        )
        assert msg.message_type == "image"
        assert msg.evo_instance_id == "mi-inst"


# ── WhatsApp System Prompt ─────────────────────────────


class TestWhatsAppSystemPrompt:
    """Test que el prompt de WhatsApp no incluye reglas de voz."""

    def test_prompt_has_whatsapp_rules(self):
        from dataclasses import field
        from agent.config_loader import AgentConfig, SlimClientConfig, ResolvedConfig
        from api.services.whatsapp.service import build_whatsapp_system_prompt

        agent = AgentConfig(
            id="test-agent",
            client_id="test-client",
            name="Valeria",
            slug="valeria",
            phone_number=None,
            phone_sid=None,
            livekit_sip_trunk_id=None,
            system_prompt="Eres Valeria, asistente de Clinica Test.",
            greeting="Hola!",
            examples="Paciente: Hola\nAgente: Hola!",
        )
        client = SlimClientConfig(
            id="test-client",
            name="Clinica Test",
            slug="clinica-test",
            business_type="dental",
            language="es",
            file_search_store_id=None,
            enabled_tools=["search_knowledge"],
        )
        config = ResolvedConfig(agent=agent, client=client)

        prompt = build_whatsapp_system_prompt(config)
        assert "Canal: WhatsApp" in prompt
        assert "conciso" in prompt.lower()
        assert "Valeria" in prompt
        # No debe tener reglas de voz típicas
        assert "audio" not in prompt.lower() or "reglas" not in prompt.lower()

    def test_prompt_includes_examples(self):
        from agent.config_loader import AgentConfig, SlimClientConfig, ResolvedConfig
        from api.services.whatsapp.service import build_whatsapp_system_prompt

        agent = AgentConfig(
            id="a1", client_id="c1", name="Bot", slug="bot",
            phone_number=None, phone_sid=None, livekit_sip_trunk_id=None,
            system_prompt="Hola.", greeting="Hi",
            examples="User: Test\nBot: Response",
        )
        client = SlimClientConfig(
            id="c1", name="Test", slug="test",
            business_type="generic", language="es",
            file_search_store_id=None,
        )
        config = ResolvedConfig(agent=agent, client=client)

        prompt = build_whatsapp_system_prompt(config)
        assert "User: Test" in prompt
        assert "Ejemplos" in prompt
