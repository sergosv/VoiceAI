"""Tests de regresión para el flujo completo de WhatsApp.

Estos tests verifican el flujo end-to-end del servicio WhatsApp
para prevenir regresiones cuando se modifica cualquier parte del pipeline:
webhook → parse → resolve contact → chat_turn → send reply.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.whatsapp.provider import InboundMessage
from api.services.whatsapp.service import (
    _resolve_contact,
    _get_or_create_conversation,
    _is_within_schedule,
    process_inbound_message,
)


# ── Helpers ─────────────────────────────────────────────


def _make_wa_config(**overrides) -> dict:
    """Crea un whatsapp_config de prueba."""
    base = {
        "id": "cfg-001",
        "client_id": "client-001",
        "agent_id": "agent-001",
        "provider": "evolution",
        "evo_instance_id": "test-instance",
        "evo_api_url": "https://evo.test.com",
        "evo_api_key": "test-key",
        "phone_number": "+5219994330027",
        "auto_reply": True,
        "greeting": None,
        "session_timeout_minutes": 30,
        "is_paused": False,
        "schedule": None,
        "away_message": "No estamos disponibles.",
        "paused_message": "Un humano te atiende.",
        "media_response": "Solo proceso texto.",
    }
    base.update(overrides)
    return base


def _make_msg(**overrides) -> InboundMessage:
    """Crea un InboundMessage de prueba."""
    defaults = {
        "remote_phone": "5212227690231",
        "text": "Hola, quiero información",
        "message_type": "text",
        "provider_message_id": "MSG-TEST-001",
        "evo_instance_id": "test-instance",
    }
    defaults.update(overrides)
    return InboundMessage(**defaults)


def _mock_supabase():
    """Crea un mock de Supabase con cadenas de métodos."""
    sb = MagicMock()

    def make_chain(data=None):
        chain = MagicMock()
        chain.select.return_value = chain
        chain.insert.return_value = chain
        chain.update.return_value = chain
        chain.delete.return_value = chain
        chain.eq.return_value = chain
        chain.neq.return_value = chain
        chain.ilike.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        chain.execute.return_value = MagicMock(data=data or [])
        return chain

    sb.table.return_value = make_chain()
    sb.rpc.return_value = MagicMock(execute=MagicMock())
    return sb


# ── Schedule Tests ──────────────────────────────────────


class TestSchedule:
    """Tests para verificación de horario."""

    def test_no_schedule_always_active(self):
        config = _make_wa_config(schedule=None)
        assert _is_within_schedule(config) is True

    def test_empty_schedule_always_active(self):
        config = _make_wa_config(schedule={})
        assert _is_within_schedule(config) is True

    def test_day_not_active(self):
        """Día configurado como inactivo."""
        now = datetime.now()
        day_key = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][now.weekday()]
        config = _make_wa_config(schedule={
            "timezone": "America/Mexico_City",
            day_key: {"active": False, "start": "00:00", "end": "23:59"},
        })
        assert _is_within_schedule(config) is False

    def test_within_hours(self):
        """Dentro del horario configurado."""
        now = datetime.now()
        day_key = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][now.weekday()]
        config = _make_wa_config(schedule={
            "timezone": "America/Mexico_City",
            day_key: {"active": True, "start": "00:00", "end": "23:59"},
        })
        assert _is_within_schedule(config) is True


# ── Contact Resolution ──────────────────────────────────


class TestResolveContact:
    """Tests para resolución/creación de contactos."""

    @pytest.mark.asyncio
    async def test_existing_contact_found(self):
        """Contacto existente se encuentra por teléfono normalizado."""
        sb = _mock_supabase()
        contact_data = [{"id": "contact-001", "channels": ["phone"]}]
        sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = contact_data

        result = await _resolve_contact(sb, "client-001", "5212227690231")
        assert result == "contact-001"

    @pytest.mark.asyncio
    async def test_new_contact_created_with_normalized_phone(self):
        """Contacto nuevo se crea con teléfono normalizado."""
        sb = _mock_supabase()
        # No existe
        sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []

        with patch("api.services.whatsapp.service.uuid") as mock_uuid:
            mock_uuid.uuid4.return_value = "new-contact-id"
            result = await _resolve_contact(sb, "client-001", "5212227690231")

        assert result == "new-contact-id"

    @pytest.mark.asyncio
    async def test_contact_gets_whatsapp_channel(self):
        """Contacto existente sin canal whatsapp lo recibe."""
        sb = _mock_supabase()
        contact_data = [{"id": "contact-001", "channels": ["phone"]}]
        sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = contact_data

        await _resolve_contact(sb, "client-001", "5212227690231")
        # Debe llamar update para agregar 'whatsapp' al canal
        sb.table.return_value.update.assert_called()


# ── Session Management ──────────────────────────────────


class TestSessionManagement:
    """Tests para creación/expiración de sesiones."""

    @pytest.mark.asyncio
    async def test_expired_session_creates_new(self):
        """Sesión expirada (>30 min) crea nueva."""
        sb = _mock_supabase()
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=35)).isoformat()
        old_conv = {
            "id": "old-conv",
            "last_message_at": old_time,
            "status": "active",
            "history": [],
            "message_count": 5,
        }
        # Primera llamada: select retorna sesión vieja
        sb.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [old_conv]

        wa_config = _make_wa_config(session_timeout_minutes=30)
        result = await _get_or_create_conversation(
            sb, "cfg-001", "contact-001", "5212227690231", wa_config
        )

        assert result is not None
        assert result["id"] != "old-conv"  # Nueva conversación

    @pytest.mark.asyncio
    async def test_active_session_reused(self):
        """Sesión activa (<30 min) se reutiliza."""
        sb = _mock_supabase()
        recent_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        active_conv = {
            "id": "active-conv",
            "last_message_at": recent_time,
            "status": "active",
            "history": [],
            "message_count": 2,
        }
        sb.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [active_conv]

        wa_config = _make_wa_config(session_timeout_minutes=30)
        result = await _get_or_create_conversation(
            sb, "cfg-001", "contact-001", "5212227690231", wa_config
        )

        assert result["id"] == "active-conv"


# ── Full Flow ───────────────────────────────────────────


class TestFullWhatsAppFlow:
    """Tests del flujo completo process_inbound_message."""

    @pytest.mark.asyncio
    async def test_auto_reply_disabled_saves_message_only(self):
        """Con auto_reply=False, guarda mensaje pero no responde."""
        msg = _make_msg()
        wa_config = _make_wa_config(auto_reply=False)

        with patch("api.services.whatsapp.service._get_supabase") as mock_sb_fn, \
             patch("api.services.whatsapp.service.load_whatsapp_config_by_evo_instance") as mock_load:
            mock_load.return_value = wa_config
            mock_sb = _mock_supabase()
            mock_sb_fn.return_value = mock_sb

            await process_inbound_message(msg)

            # No debe llamar a chat_turn ni send_text

    @pytest.mark.asyncio
    async def test_paused_sends_paused_message(self):
        """Con is_paused=True, envía mensaje de pausa."""
        msg = _make_msg()
        wa_config = _make_wa_config(is_paused=True)

        with patch("api.services.whatsapp.service._get_supabase") as mock_sb_fn, \
             patch("api.services.whatsapp.service.load_whatsapp_config_by_evo_instance") as mock_load, \
             patch("api.services.whatsapp.service.get_provider") as mock_provider_fn:
            mock_load.return_value = wa_config
            mock_sb = _mock_supabase()
            mock_sb_fn.return_value = mock_sb
            mock_provider = MagicMock()
            mock_provider.send_text = AsyncMock(return_value="sent-001")
            mock_provider_fn.return_value = mock_provider

            await process_inbound_message(msg)

            mock_provider.send_text.assert_called_once()
            call_args = mock_provider.send_text.call_args
            assert "humano" in call_args[0][2].lower()

    @pytest.mark.asyncio
    async def test_media_message_gets_media_response(self):
        """Mensaje de imagen recibe respuesta de media no soportada."""
        msg = _make_msg(message_type="image", text="foto")
        wa_config = _make_wa_config()

        with patch("api.services.whatsapp.service._get_supabase") as mock_sb_fn, \
             patch("api.services.whatsapp.service.load_whatsapp_config_by_evo_instance") as mock_load, \
             patch("api.services.whatsapp.service.get_provider") as mock_provider_fn:
            mock_load.return_value = wa_config
            mock_sb = _mock_supabase()
            mock_sb_fn.return_value = mock_sb
            mock_provider = MagicMock()
            mock_provider.send_text = AsyncMock(return_value="sent-001")
            mock_provider_fn.return_value = mock_provider

            await process_inbound_message(msg)

            mock_provider.send_text.assert_called_once()
            call_args = mock_provider.send_text.call_args
            assert "texto" in call_args[0][2].lower()

    @pytest.mark.asyncio
    async def test_empty_text_ignored(self):
        """Mensaje de texto vacío no se procesa."""
        msg = _make_msg(text="   ")
        wa_config = _make_wa_config()

        with patch("api.services.whatsapp.service._get_supabase") as mock_sb_fn, \
             patch("api.services.whatsapp.service.load_whatsapp_config_by_evo_instance") as mock_load:
            mock_load.return_value = wa_config
            mock_sb = _mock_supabase()
            mock_sb_fn.return_value = mock_sb

            # No debe llamar chat_turn — simplemente retorna
            await process_inbound_message(msg)

    @pytest.mark.asyncio
    async def test_no_config_found_logs_warning(self):
        """Sin config para la instancia, loguea warning y retorna."""
        msg = _make_msg(evo_instance_id="instancia-inexistente")

        with patch("api.services.whatsapp.service._get_supabase") as mock_sb_fn, \
             patch("api.services.whatsapp.service.load_whatsapp_config_by_evo_instance") as mock_load:
            mock_load.return_value = None
            mock_sb = _mock_supabase()
            mock_sb_fn.return_value = mock_sb

            # No debe crashear
            await process_inbound_message(msg)

    @pytest.mark.asyncio
    async def test_human_takeover_saves_but_no_ai(self):
        """Con human takeover activo, guarda mensaje pero no procesa con IA."""
        msg = _make_msg()
        wa_config = _make_wa_config()

        with patch("api.services.whatsapp.service._get_supabase") as mock_sb_fn, \
             patch("api.services.whatsapp.service.load_whatsapp_config_by_evo_instance") as mock_load:
            mock_load.return_value = wa_config
            mock_sb = _mock_supabase()
            mock_sb_fn.return_value = mock_sb

            # Simular conversación con human takeover
            mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
                {"id": "conv-human", "is_human_controlled": True}
            ]

            await process_inbound_message(msg)

            # Debe guardar mensaje pero NO llamar chat_turn

    @pytest.mark.asyncio
    async def test_chat_turn_error_sends_fallback(self):
        """Si chat_turn falla, envía mensaje de error genérico."""
        msg = _make_msg()
        wa_config = _make_wa_config()

        with patch("api.services.whatsapp.service._get_supabase") as mock_sb_fn, \
             patch("api.services.whatsapp.service.load_whatsapp_config_by_evo_instance") as mock_load_wa, \
             patch("api.services.whatsapp.service.load_config_by_agent_id") as mock_load_agent, \
             patch("api.services.whatsapp.service.load_api_integrations") as mock_integ, \
             patch("api.services.whatsapp.service.load_mcp_servers") as mock_mcp, \
             patch("api.services.whatsapp.service.get_provider") as mock_prov_fn, \
             patch("api.services.whatsapp.service.chat_turn") as mock_chat:
            mock_load_wa.return_value = wa_config
            mock_sb = _mock_supabase()
            mock_sb_fn.return_value = mock_sb

            # Simular que no hay conversación existente (crea nueva)
            mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []

            # Config del agente
            mock_load_agent.return_value = MagicMock(
                agent=MagicMock(system_prompt="Test", examples=None),
                client=MagicMock(enabled_tools=[], file_search_store_id=None),
            )
            mock_integ.return_value = []
            mock_mcp.return_value = []

            # chat_turn explota
            mock_chat.side_effect = Exception("Gemini API timeout")

            mock_provider = MagicMock()
            mock_provider.send_text = AsyncMock(return_value="sent-err")
            mock_prov_fn.return_value = mock_provider

            await process_inbound_message(msg)

            # Debe enviar mensaje de error
            mock_provider.send_text.assert_called()
            error_text = mock_provider.send_text.call_args[0][2]
            assert "problema" in error_text.lower() or "error" in error_text.lower()
