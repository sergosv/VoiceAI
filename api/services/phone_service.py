"""Lógica de negocio para asignación de teléfonos."""

from __future__ import annotations

import logging
import os

from livekit import api as lk_api
from supabase import Client
from twilio.rest import Client as TwilioClient

logger = logging.getLogger(__name__)


def _get_twilio_client() -> TwilioClient:
    """Crea instancia de TwilioClient con credenciales del entorno."""
    return TwilioClient(
        os.environ["TWILIO_ACCOUNT_SID"],
        os.environ["TWILIO_AUTH_TOKEN"],
    )


def search_available_numbers(
    country_code: str = "MX",
    area_code: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Busca números disponibles en Twilio por país y código de área."""
    twilio = _get_twilio_client()
    kwargs: dict = {"limit": limit}
    if area_code:
        kwargs["area_code"] = area_code

    # Intentar local primero, luego mobile (MX suele ser mobile)
    numbers = twilio.available_phone_numbers(country_code).local.list(**kwargs)
    if not numbers:
        numbers = twilio.available_phone_numbers(country_code).mobile.list(**kwargs)

    return [
        {
            "phone_number": n.phone_number,
            "friendly_name": n.friendly_name,
            "locality": getattr(n, "locality", None),
            "region": getattr(n, "region", None),
        }
        for n in numbers
    ]


def purchase_phone_number(phone_number: str) -> tuple[str, str]:
    """Compra un número en Twilio. Retorna (phone_sid, phone_number normalizado)."""
    twilio = _get_twilio_client()
    incoming = twilio.incoming_phone_numbers.create(phone_number=phone_number)
    return incoming.sid, incoming.phone_number


def verify_twilio_number(phone_number: str) -> str:
    """Verifica que el número existe en Twilio. Retorna phone_sid."""
    twilio = _get_twilio_client()
    incoming = twilio.incoming_phone_numbers.list(phone_number=phone_number)
    if not incoming:
        raise ValueError(f"Número {phone_number} no encontrado en tu cuenta Twilio")
    return incoming[0].sid


async def setup_livekit_sip(phone_number: str) -> tuple[str, str]:
    """Crea SIP trunk y dispatch rule en LiveKit. Retorna (trunk_id, rule_id)."""
    lk = lk_api.LiveKitAPI(
        url=os.environ["LIVEKIT_URL"],
        api_key=os.environ["LIVEKIT_API_KEY"],
        api_secret=os.environ["LIVEKIT_API_SECRET"],
    )

    trunk = await lk.sip.create_sip_inbound_trunk(
        lk_api.CreateSIPInboundTrunkRequest(
            trunk=lk_api.SIPInboundTrunkInfo(
                name=f"twilio-{phone_number}",
                numbers=[phone_number],
                allowed_addresses=[
                    "54.172.60.0/23",
                    "54.244.51.0/24",
                    "34.203.250.0/23",
                ],
            )
        )
    )
    trunk_id = trunk.sip_trunk_id

    rule = await lk.sip.create_sip_dispatch_rule(
        lk_api.CreateSIPDispatchRuleRequest(
            name=f"route-{phone_number}",
            rule=lk_api.SIPDispatchRule(
                dispatch_rule_individual=lk_api.SIPDispatchRuleIndividual(
                    room_prefix="call-",
                )
            ),
            trunk_ids=[trunk_id],
        )
    )

    await lk.aclose()
    return trunk_id, rule.sip_dispatch_rule_id


def assign_phone_to_client(
    sb: Client,
    *,
    client_id: str,
    phone_number: str,
    phone_sid: str,
    trunk_id: str | None = None,
) -> dict:
    """Actualiza el cliente con el número de teléfono."""
    update_data: dict = {
        "phone_number": phone_number,
        "twilio_phone_sid": phone_sid,
    }
    if trunk_id:
        update_data["sip_trunk_id"] = trunk_id

    result = sb.table("clients").update(update_data).eq("id", client_id).execute()
    return result.data[0] if result.data else {}


def assign_phone_to_agent(
    sb: Client,
    *,
    agent_id: str,
    phone_number: str,
    phone_sid: str,
    trunk_id: str | None = None,
) -> dict:
    """Actualiza un agente con el número de teléfono."""
    update_data: dict = {
        "phone_number": phone_number,
        "phone_sid": phone_sid,
    }
    if trunk_id:
        update_data["livekit_sip_trunk_id"] = trunk_id

    result = sb.table("agents").update(update_data).eq("id", agent_id).execute()
    return result.data[0] if result.data else {}
