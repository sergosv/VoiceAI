"""Tests para Public API — API keys, auth, webhooks, v1 endpoints."""

import hashlib
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set env vars before importing modules that need them
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-key")


class TestApiKeyGeneration:
    def test_generate_key_format(self):
        from api.services.api_key_service import generate_api_key
        full_key, prefix, key_hash = generate_api_key()
        assert full_key.startswith("vai_")
        assert len(full_key) > 20
        assert prefix == full_key[:12]
        assert key_hash == hashlib.sha256(full_key.encode()).hexdigest()

    def test_generate_unique_keys(self):
        from api.services.api_key_service import generate_api_key
        keys = set()
        for _ in range(10):
            full_key, _, _ = generate_api_key()
            keys.add(full_key)
        assert len(keys) == 10

    def test_hash_api_key(self):
        from api.services.api_key_service import hash_api_key
        key = "vai_test123"
        expected = hashlib.sha256(key.encode()).hexdigest()
        assert hash_api_key(key) == expected


class TestWebhookSignature:
    def test_sign_payload(self):
        from api.services.webhook_service import _sign_payload
        signature = _sign_payload('{"event":"test"}', "secret123")
        assert len(signature) == 64
        assert _sign_payload('{"event":"test"}', "secret123") == signature

    def test_different_secrets(self):
        from api.services.webhook_service import _sign_payload
        sig1 = _sign_payload("data", "secret1")
        sig2 = _sign_payload("data", "secret2")
        assert sig1 != sig2


class TestApiKeyAuth:
    @pytest.mark.asyncio
    async def test_missing_key(self):
        from fastapi import HTTPException
        from api.auth_apikey import get_api_key_client
        with pytest.raises(HTTPException) as exc_info:
            await get_api_key_client(MagicMock(), api_key=None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_key(self):
        from fastapi import HTTPException
        from api.auth_apikey import get_api_key_client
        with patch("api.auth_apikey.resolve_api_key", new_callable=AsyncMock, return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await get_api_key_client(MagicMock(), api_key="vai_invalid")
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_key(self):
        from api.auth_apikey import get_api_key_client
        record = {"id": "key1", "client_id": "c1", "scopes": ["*"]}
        with patch("api.auth_apikey.resolve_api_key", new_callable=AsyncMock, return_value=record):
            result = await get_api_key_client(MagicMock(), api_key="vai_valid")
            assert result["client_id"] == "c1"


class TestScopeCheck:
    @pytest.mark.asyncio
    async def test_scope_allowed_wildcard(self):
        from api.auth_apikey import require_scope
        checker = require_scope("calls:read")
        result = await checker({"scopes": ["*"], "client_id": "c1"})
        assert result["client_id"] == "c1"

    @pytest.mark.asyncio
    async def test_scope_allowed_exact(self):
        from api.auth_apikey import require_scope
        checker = require_scope("calls:read")
        result = await checker({"scopes": ["calls:read", "contacts:read"], "client_id": "c1"})
        assert result["client_id"] == "c1"

    @pytest.mark.asyncio
    async def test_scope_denied(self):
        from fastapi import HTTPException
        from api.auth_apikey import require_scope
        checker = require_scope("calls:read")
        with pytest.raises(HTTPException) as exc_info:
            await checker({"scopes": ["contacts:read"], "client_id": "c1"})
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_empty_scopes_allowed(self):
        """Empty scopes = full access."""
        from api.auth_apikey import require_scope
        checker = require_scope("calls:read")
        result = await checker({"scopes": [], "client_id": "c1"})
        assert result["client_id"] == "c1"


class TestWebhookEventMatching:
    @pytest.mark.asyncio
    async def test_wildcard_match(self):
        from api.services.webhook_service import dispatch_event
        with patch("api.services.webhook_service.get_supabase") as mock_sb:
            mock_sb.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"id": "ep1", "url": "https://example.com", "secret": "s", "events": ["*"]}]
            )
            with patch("asyncio.create_task") as mock_task:
                await dispatch_event("c1", "call.completed", {"id": "1"})
                mock_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_exact_match(self):
        from api.services.webhook_service import dispatch_event
        with patch("api.services.webhook_service.get_supabase") as mock_sb:
            mock_sb.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"id": "ep1", "url": "https://example.com", "secret": "s", "events": ["call.completed"]}]
            )
            with patch("asyncio.create_task") as mock_task:
                await dispatch_event("c1", "call.completed", {"id": "1"})
                mock_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_match(self):
        from api.services.webhook_service import dispatch_event
        with patch("api.services.webhook_service.get_supabase") as mock_sb:
            mock_sb.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"id": "ep1", "url": "https://example.com", "secret": "s", "events": ["contact.created"]}]
            )
            with patch("asyncio.create_task") as mock_task:
                await dispatch_event("c1", "call.completed", {"id": "1"})
                mock_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_category_wildcard(self):
        """'call.*' should match 'call.completed'."""
        from api.services.webhook_service import dispatch_event
        with patch("api.services.webhook_service.get_supabase") as mock_sb:
            mock_sb.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"id": "ep1", "url": "https://example.com", "secret": "s", "events": ["call.*"]}]
            )
            with patch("asyncio.create_task") as mock_task:
                await dispatch_event("c1", "call.completed", {"id": "1"})
                mock_task.assert_called_once()
