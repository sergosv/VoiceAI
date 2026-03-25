"""Tests para autenticación del Asistente Personal (caller whitelist)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from api.schemas_pa import PaCallerCreateRequest, PaEmailConfigRequest


class TestPaCallerValidation:
    def test_valid_phone(self):
        req = PaCallerCreateRequest(phone_number="+5215551234567", label="Mi cel")
        assert req.phone_number == "+5215551234567"

    def test_invalid_phone(self):
        with pytest.raises(ValidationError, match="teléfono"):
            PaCallerCreateRequest(phone_number="abc")

    def test_valid_delivery(self):
        req = PaCallerCreateRequest(phone_number="+521555123", reminder_delivery="whatsapp")
        assert req.reminder_delivery == "whatsapp"

    def test_invalid_delivery(self):
        with pytest.raises(ValidationError, match="Delivery"):
            PaCallerCreateRequest(phone_number="+521555123", reminder_delivery="sms")


class TestPaEmailConfigValidation:
    def test_valid_config(self):
        req = PaEmailConfigRequest(
            from_name="Asistente",
            from_email="asistente@test.com",
            reply_to="owner@test.com",
        )
        assert req.from_email == "asistente@test.com"

    def test_invalid_email(self):
        with pytest.raises(ValidationError, match="email"):
            PaEmailConfigRequest(from_name="Test", from_email="not-an-email")


class TestAgentCategoryInSchema:
    def test_agent_out_has_category(self):
        from api.schemas import AgentOut
        fields = AgentOut.model_fields
        assert "agent_category" in fields
        assert fields["agent_category"].default == "service"

    def test_agent_create_has_category(self):
        from api.schemas import AgentCreateRequest
        fields = AgentCreateRequest.model_fields
        assert "agent_category" in fields

    def test_sample_row_has_category(self):
        """Verifica que SAMPLE_AGENT_ROW incluye agent_category."""
        from tests.test_api_agents import SAMPLE_AGENT_ROW
        assert "agent_category" in SAMPLE_AGENT_ROW
        assert SAMPLE_AGENT_ROW["agent_category"] == "service"
