"""Tests para api/services/chat_store.py — store en memoria para chat tester."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from api.services.chat_store import (
    MAX_TTL,
    Conversation,
    _cleanup_expired,
    _store,
    create_conversation,
    delete_conversation,
    get_conversation,
)


def _make_mock_config(agent_name: str = "TestAgent", client_id: str = "c1") -> MagicMock:
    """Crea un mock de ResolvedConfig."""
    config = MagicMock()
    config.agent.name = agent_name
    config.client.id = client_id
    return config


@pytest.fixture(autouse=True)
def clear_store():
    """Limpia el store antes y después de cada test."""
    _store.clear()
    yield
    _store.clear()


class TestCreateConversation:
    def test_creates_and_stores(self):
        config = _make_mock_config()
        conv = create_conversation(config, "Eres un asistente.")
        assert conv.id in _store
        assert conv.system_prompt == "Eres un asistente."
        assert conv.config is config
        assert conv.history == []
        assert conv.turn_count == 0
        assert conv.client_id == "c1"

    def test_with_contact_name(self):
        config = _make_mock_config()
        conv = create_conversation(config, "prompt", contact_name="Juan")
        assert conv.contact_name == "Juan"

    def test_unique_ids(self):
        config = _make_mock_config()
        c1 = create_conversation(config, "p1")
        c2 = create_conversation(config, "p2")
        assert c1.id != c2.id
        assert len(_store) == 2


class TestGetConversation:
    def test_existing(self):
        config = _make_mock_config()
        conv = create_conversation(config, "prompt")
        fetched = get_conversation(conv.id)
        assert fetched is conv

    def test_not_found(self):
        result = get_conversation("nonexistent-id")
        assert result is None

    def test_expired_returns_none_and_removes(self):
        config = _make_mock_config()
        conv = create_conversation(config, "prompt")
        # Forzar expiración
        object.__setattr__(conv, "created_at", time.time() - MAX_TTL - 10)
        result = get_conversation(conv.id)
        assert result is None
        assert conv.id not in _store


class TestDeleteConversation:
    def test_delete_existing(self):
        config = _make_mock_config()
        conv = create_conversation(config, "prompt")
        assert delete_conversation(conv.id) is True
        assert conv.id not in _store

    def test_delete_nonexistent(self):
        assert delete_conversation("nonexistent") is False


class TestCleanupExpired:
    def test_no_expired(self):
        config = _make_mock_config()
        create_conversation(config, "prompt")
        removed = _cleanup_expired()
        assert removed == 0
        assert len(_store) == 1

    def test_removes_expired(self):
        config = _make_mock_config()
        c1 = create_conversation(config, "prompt1")
        c2 = create_conversation(config, "prompt2")
        c3 = create_conversation(config, "prompt3")

        # Expirar c1 y c2
        object.__setattr__(c1, "created_at", time.time() - MAX_TTL - 100)
        object.__setattr__(c2, "created_at", time.time() - MAX_TTL - 50)

        removed = _cleanup_expired()
        assert removed == 2
        assert len(_store) == 1
        assert c3.id in _store

    def test_empty_store(self):
        removed = _cleanup_expired()
        assert removed == 0


class TestConversationDataclass:
    def test_fields(self):
        conv = Conversation(
            id="test-id",
            config=MagicMock(),
            system_prompt="Hola",
            history=[],
            created_at=time.time(),
            turn_count=3,
            contact_name="Ana",
            client_id="c1",
        )
        assert conv.id == "test-id"
        assert conv.turn_count == 3
        assert conv.contact_name == "Ana"
        assert conv.client_id == "c1"
