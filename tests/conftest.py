"""Fixtures compartidos para tests del Voice AI Platform."""

from __future__ import annotations

import os
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from agent.config_loader import AgentConfig, ResolvedConfig, SlimClientConfig


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Variables de entorno requeridas para todos los tests."""
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "test-anon-key")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-deepgram-key")
    monkeypatch.setenv("CARTESIA_API_KEY", "test-cartesia-key")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest123")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test-twilio-token")
    monkeypatch.setenv("LIVEKIT_URL", "wss://test.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "test-lk-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "test-lk-secret")


@pytest.fixture
def sample_config() -> ResolvedConfig:
    """Config de ejemplo para tests (agente + cliente)."""
    agent = AgentConfig(
        id="aaaa1111-1111-1111-1111-111111111111",
        client_id="11111111-1111-1111-1111-111111111111",
        name="María",
        slug="maria",
        phone_number="+5219991112233",
        phone_sid=None,
        livekit_sip_trunk_id=None,
        system_prompt="Eres María, asistente virtual del Consultorio Dr. García.",
        greeting="Hola, bienvenido al Consultorio Dr. García. Soy María, ¿en qué puedo ayudarle?",
        examples=None,
        voice_config={"provider": "cartesia", "voice_id": "test-voice-id-123"},
        llm_config={"provider": "google"},
        stt_config={"provider": "deepgram"},
        transfer_number="+5219991234567",
        max_call_duration_seconds=300,
        after_hours_message="Estamos fuera de horario. Llame mañana.",
    )
    client = SlimClientConfig(
        id="11111111-1111-1111-1111-111111111111",
        name="Consultorio Dr. García",
        slug="dr-garcia",
        business_type="dental",
        language="es",
        file_search_store_id="stores/test-store-123",
        enabled_tools=["search_knowledge", "transfer_to_human"],
        business_hours={"lun-vie": "9:00-18:00"},
    )
    return ResolvedConfig(agent=agent, client=client)


@pytest.fixture
def sample_config_no_store() -> ResolvedConfig:
    """Config sin FileSearchStore ni transfer number."""
    agent = AgentConfig(
        id="aaaa2222-2222-2222-2222-222222222222",
        client_id="22222222-2222-2222-2222-222222222222",
        name="Asistente",
        slug="asistente",
        phone_number=None,
        phone_sid=None,
        livekit_sip_trunk_id=None,
        system_prompt="Eres un asistente virtual de prueba.",
        greeting="Hola, ¿en qué puedo ayudarle?",
        examples=None,
        voice_config={"provider": "cartesia", "voice_id": "test-voice-456"},
        llm_config={"provider": "google"},
        stt_config={"provider": "deepgram"},
        transfer_number=None,
        max_call_duration_seconds=180,
    )
    client = SlimClientConfig(
        id="22222222-2222-2222-2222-222222222222",
        name="Test Business",
        slug="test-biz",
        business_type="generic",
        language="es",
        file_search_store_id=None,
        enabled_tools=["search_knowledge"],
    )
    return ResolvedConfig(agent=agent, client=client)


@pytest.fixture
def sample_db_row() -> dict:
    """Row de Supabase simulado para un cliente."""
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "name": "Consultorio Dr. García",
        "slug": "dr-garcia",
        "business_type": "dental",
        "agent_name": "María",
        "language": "es",
        "voice_id": "test-voice-id-123",
        "greeting": "Hola, bienvenido al Consultorio Dr. García.",
        "system_prompt": "Eres María, asistente virtual.",
        "file_search_store_id": "stores/test-store-123",
        "tools_enabled": ["search_knowledge"],
        "max_call_duration_seconds": 300,
        "transfer_number": "+5219991234567",
        "business_hours": {"lun-vie": "9:00-18:00"},
        "after_hours_message": "Fuera de horario.",
        "phone_number": "+5219991112233",
        "is_active": True,
    }


@pytest.fixture
def mock_supabase_response():
    """Factory para crear respuestas mock de Supabase."""

    def _make(data: list[dict] | None = None):
        response = MagicMock()
        response.data = data or []
        return response

    return _make
