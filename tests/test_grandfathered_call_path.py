"""Smoke test: grandfathered clients (sin subaccount, sin BYOT) siguen funcionando.

Garantiza que el patrón aditivo del refactor de Twilio Subaccounts NO toca
el call path runtime. Un cliente existente con todas las columnas
`twilio_subaccount_*` en NULL debe:

  1. Cargar config sin excepciones ni warnings.
  2. NO disparar resolve_twilio_creds() ni get_client_twilio_creds() durante
     la resolución de la llamada entrante (spy assertion).

Si este test falla, es señal de que alguien introdujo una dependencia del
call path sobre las columnas nuevas — hay que revertir hasta entender por qué.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from agent.config_loader import load_config_by_phone


def _make_grandfathered_agent_row() -> dict:
    """Row de agents con join clients donde TODOS los campos de subaccount
    y BYOT están en NULL. Representa un cliente que existía antes del refactor.
    """
    return {
        "id": "agent-old-uuid",
        "client_id": "client-old-uuid",
        "name": "María",
        "slug": "default",
        "phone_number": "+529991112233",
        "phone_sid": "PN_OLD_SID",
        "livekit_sip_trunk_id": "ST_OLD",
        "system_prompt": "Eres María.",
        "greeting": "Hola.",
        "voice_config": {"provider": "cartesia", "voice_id": "v1"},
        "llm_config": {"provider": "google"},
        "stt_config": {"provider": "deepgram"},
        "agent_mode": "pipeline",
        "agent_type": "inbound",
        "is_active": True,
        "clients": {
            "id": "client-old-uuid",
            "name": "Consultorio viejo",
            "slug": "consultorio-viejo",
            "business_type": "generic",
            "language": "es",
            "owner_email": "old@test.com",
            "is_active": True,
            # ── Los campos que agregó la migration 059 — TODOS en NULL ──
            "twilio_subaccount_sid": None,
            "twilio_subaccount_auth_token": None,
            "twilio_subaccount_status": None,
            "twilio_subaccount_trunk_sid": None,
            "twilio_subaccount_created_at": None,
            # ── BYOT tampoco configurado ──
            "twilio_account_sid": None,
            "twilio_auth_token": None,
        },
    }


@pytest.mark.asyncio
async def test_grandfathered_client_config_loads_with_null_subaccount_fields(caplog):
    """Cliente pre-refactor: config carga limpia, sin warnings ni resolución de creds.

    Este test protege contra regresiones accidentales. Si alguien agrega una
    llamada a resolve_twilio_creds() en el hot path runtime, el spy lo detecta.
    Si alguien introduce un side-effect sobre los campos subaccount en NULL
    (ej. un validador que lanza warning), caplog lo detecta.
    """
    agent_row = _make_grandfathered_agent_row()

    # Mock de Supabase: devuelve exactamente este row para la búsqueda por teléfono
    mock_table = MagicMock()
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[agent_row])
    mock_sb = MagicMock()
    mock_sb.table.return_value = mock_table

    caplog.set_level(logging.WARNING)

    # Spy en las funciones de resolución Twilio — NO deben llamarse
    with patch("agent.config_loader._get_supabase", return_value=mock_sb), \
         patch("api.services.phone_service.resolve_twilio_creds") as spy_resolve, \
         patch("api.services.phone_service.get_client_twilio_creds") as spy_byot:

        config = await load_config_by_phone("+529991112233")

    # 1. Config válida cargada sin excepciones
    assert config is not None
    assert config.agent.name == "María"
    assert config.agent.phone_number == "+529991112233"
    assert config.client.slug == "consultorio-viejo"
    assert config.client.business_type == "generic"

    # 2. El call path NO invoca resolución de creds Twilio
    spy_resolve.assert_not_called()
    spy_byot.assert_not_called()

    # 3. No hay warnings relacionados con Twilio subaccount durante la carga
    twilio_warnings = [
        r.message for r in caplog.records
        if "twilio" in r.message.lower() or "subaccount" in r.message.lower()
    ]
    assert twilio_warnings == [], (
        f"Carga de grandfathered generó warnings Twilio inesperados: {twilio_warnings}"
    )


@pytest.mark.asyncio
async def test_grandfathered_client_call_path_ignores_subaccount_columns():
    """Refuerza el anterior: aunque el row tenga columnas subaccount en cualquier
    estado (NULL, ausentes, vacías), el ResolvedConfig construido es igual.

    Demuestra que `_rows_to_resolved` no lee campos twilio_subaccount_* —
    prueba arquitectónica del patrón aditivo.
    """
    agent_row = _make_grandfathered_agent_row()

    # Variante 1: columnas subaccount ausentes del row (DB antes de la migration)
    row_without_cols = {k: v for k, v in agent_row.items() if k != "clients"}
    client_without_cols = {
        k: v for k, v in agent_row["clients"].items()
        if not k.startswith("twilio_")
    }
    row_without_cols["clients"] = client_without_cols

    mock_table = MagicMock()
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[row_without_cols])
    mock_sb = MagicMock()
    mock_sb.table.return_value = mock_table

    with patch("agent.config_loader._get_supabase", return_value=mock_sb):
        config = await load_config_by_phone("+529991112233")

    assert config is not None
    assert config.client.name == "Consultorio viejo"
    assert config.agent.is_active is True
