"""Lógica de negocio para asignación de teléfonos."""

from __future__ import annotations

import logging
import os

from livekit import api as lk_api
from supabase import Client
logger = logging.getLogger(__name__)


def _get_twilio_client(
    account_sid: str | None = None,
    auth_token: str | None = None,
):
    """Crea instancia de TwilioClient. Usa creds BYOT si se pasan, sino env vars."""
    from twilio.rest import Client as TwilioClient
    return TwilioClient(
        account_sid or os.environ["TWILIO_ACCOUNT_SID"],
        auth_token or os.environ["TWILIO_AUTH_TOKEN"],
    )


def search_available_numbers(
    country_code: str = "MX",
    area_code: str | None = None,
    limit: int = 10,
    *,
    account_sid: str | None = None,
    auth_token: str | None = None,
) -> list[dict]:
    """Busca números disponibles en Twilio por país y código de área."""
    twilio = _get_twilio_client(account_sid, auth_token)
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


def purchase_phone_number(
    phone_number: str,
    *,
    account_sid: str | None = None,
    auth_token: str | None = None,
) -> tuple[str, str]:
    """Compra un número en Twilio. Retorna (phone_sid, phone_number normalizado)."""
    twilio = _get_twilio_client(account_sid, auth_token)
    incoming = twilio.incoming_phone_numbers.create(phone_number=phone_number)
    return incoming.sid, incoming.phone_number


def verify_twilio_number(
    phone_number: str,
    *,
    account_sid: str | None = None,
    auth_token: str | None = None,
) -> str:
    """Verifica que el número existe en Twilio. Retorna phone_sid."""
    twilio = _get_twilio_client(account_sid, auth_token)
    incoming = twilio.incoming_phone_numbers.list(phone_number=phone_number)
    if not incoming:
        raise ValueError(f"Número {phone_number} no encontrado en tu cuenta Twilio")
    return incoming[0].sid


def validate_twilio_credentials(account_sid: str, auth_token: str) -> bool:
    """Valida credenciales de Twilio haciendo una llamada ligera a la API."""
    try:
        client = _get_twilio_client(account_sid, auth_token)
        account = client.api.v2010.accounts(account_sid).fetch()
        return account.status == "active"
    except Exception as e:
        logger.warning("Twilio credential validation failed: %s", e)
        return False


def enable_geo_permission(
    country_code: str,
    *,
    account_sid: str | None = None,
    auth_token: str | None = None,
) -> None:
    """Habilita permisos de voz para un país en la cuenta Twilio."""
    client = _get_twilio_client(account_sid, auth_token)
    client.voice.v1.dialing_permissions.countries(country_code).update(
        low_risk_numbers_enabled=True,
        high_risk_special_numbers_enabled=False,
        high_risk_tollfraud_numbers_enabled=False,
    )
    logger.info("Geo permission enabled for %s", country_code)


def setup_twilio_elastic_sip_trunk(
    *,
    account_sid: str,
    auth_token: str,
    sip_uri: str | None = None,
) -> str:
    """Crea Elastic SIP Trunk en la cuenta del cliente apuntando a LiveKit.
    Retorna el Twilio trunk SID."""
    if not sip_uri:
        lk_url = os.environ.get("LIVEKIT_URL", "")
        # Extraer host del URL de LiveKit (wss://xxx.livekit.cloud → xxx.sip.livekit.cloud)
        sip_uri = "2r172cwux9u.sip.livekit.cloud"

    client = _get_twilio_client(account_sid, auth_token)
    trunk = client.trunking.v1.trunks.create(
        friendly_name="VoiceAI Platform",
    )
    trunk.origination_urls.create(
        friendly_name="LiveKit SIP",
        sip_url=f"sip:{sip_uri};transport=tcp",
        priority=10,
        weight=10,
        enabled=True,
    )
    logger.info("Created Elastic SIP Trunk %s on account %s", trunk.sid, account_sid)
    return trunk.sid


def get_client_twilio_creds(
    sb: Client, client_id: str
) -> tuple[str | None, str | None]:
    """Carga y desencripta credenciales BYOT de Twilio de un cliente.
    Retorna (account_sid, auth_token) o (None, None)."""
    from api.crypto import decrypt_value

    result = (
        sb.table("clients")
        .select("twilio_account_sid, twilio_auth_token")
        .eq("id", client_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None, None
    row = result.data[0]
    sid = row.get("twilio_account_sid")
    token_enc = row.get("twilio_auth_token")
    if not sid or not token_enc:
        return None, None
    return sid, decrypt_value(token_enc)


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
            room_config=lk_api.RoomConfiguration(
                agents=[
                    lk_api.RoomAgentDispatch(agent_name="voice-ai-platform"),
                ],
            ),
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
