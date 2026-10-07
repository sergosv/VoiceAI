"""Lógica de negocio para asignación de teléfonos."""

from __future__ import annotations

import logging
import os
import re

from livekit import api as lk_api
from supabase import Client
logger = logging.getLogger(__name__)


def _slugify_for_twilio(value: str) -> str:
    """Normaliza un string a formato compatible con Twilio friendly_name.

    Solo a-z, 0-9 y guiones. Max 64 chars (límite seguro).
    """
    slug = value.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "-", slug).strip("-")
    return slug[:64] or "client"


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


def resolve_twilio_creds(sb: Client, client_id: str) -> tuple[str, str]:
    """Resuelve credenciales Twilio con prioridad BYOT > Subaccount > Main.

    Fallback silencioso a las env vars MAIN para clientes grandfathered sin BYOT
    ni subaccount configurada. Solo lanza ValueError cuando alguna de las dos
    alternativas está marcada pero resulta malformada (sid sin token, o token
    que no puede desencriptarse).

    TODO (Fase 2): consolidar con `get_client_twilio_creds` en una sola función.
    Coexisten hoy porque `get_client_twilio_creds` devuelve (None, None) cuando
    no hay BYOT (útil como flag), mientras esta siempre devuelve creds resueltas.
    Unificar con un parámetro `include_fallback: bool` para evitar divergencia.
    """
    from api.crypto import decrypt_value

    result = (
        sb.table("clients")
        .select(
            "twilio_account_sid, twilio_auth_token, "
            "twilio_subaccount_sid, twilio_subaccount_auth_token"
        )
        .eq("id", client_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        return os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"]

    row = result.data[0]

    byot_sid = row.get("twilio_account_sid")
    byot_token_enc = row.get("twilio_auth_token")
    if byot_sid and byot_token_enc:
        byot_token = decrypt_value(byot_token_enc)
        if not byot_token:
            raise ValueError(
                f"BYOT auth_token no pudo desencriptarse para cliente {client_id}"
            )
        return byot_sid, byot_token
    if byot_sid or byot_token_enc:
        raise ValueError(
            f"BYOT parcialmente configurado para cliente {client_id}: "
            "requiere account_sid y auth_token"
        )

    sub_sid = row.get("twilio_subaccount_sid")
    sub_token_enc = row.get("twilio_subaccount_auth_token")
    if sub_sid and sub_token_enc:
        sub_token = decrypt_value(sub_token_enc)
        if not sub_token:
            raise ValueError(
                f"Subaccount auth_token no pudo desencriptarse para cliente {client_id}"
            )
        return sub_sid, sub_token
    if sub_sid or sub_token_enc:
        raise ValueError(
            f"Subaccount parcialmente configurada para cliente {client_id}: "
            "requiere sid y auth_token"
        )

    return os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"]


def create_twilio_subaccount(friendly_name: str) -> tuple[str, str]:
    """Crea una subaccount Twilio bajo la cuenta parent (env TWILIO_ACCOUNT_SID).

    Args:
        friendly_name: Nombre visible en Twilio Console (ej. 'voiceai-prod-dr-garcia').
            Se recomienda usar `_slugify_for_twilio()` en el caller.

    Retorna (subaccount_sid, subaccount_auth_token) en texto plano.
    El caller debe encriptar el token con `api.crypto.encrypt_value` antes de guardarlo.
    """
    master_client = _get_twilio_client()
    account = master_client.api.v2010.accounts.create(friendly_name=friendly_name)
    logger.info(
        "Twilio subaccount creada: sid=%s friendly_name=%s",
        account.sid, friendly_name,
    )
    return account.sid, account.auth_token


def associate_number_to_trunk(
    phone_sid: str,
    trunk_sid: str,
    *,
    account_sid: str,
    auth_token: str,
) -> None:
    """Asocia un IncomingPhoneNumber a un Elastic SIP Trunk.

    Requerido después de comprar (o transferir) un número dentro de una subaccount
    para que el ruteo de llamadas entrantes use el trunk LiveKit.
    """
    client = _get_twilio_client(account_sid, auth_token)
    client.incoming_phone_numbers(phone_sid).update(trunk_sid=trunk_sid)
    logger.info("Number %s asociado a trunk %s", phone_sid, trunk_sid)


def transfer_number_to_subaccount(
    phone_sid: str,
    subaccount_sid: str,
    *,
    master_account_sid: str | None = None,
    master_auth_token: str | None = None,
) -> str:
    """Transfiere un IncomingPhoneNumber desde la cuenta master a una subaccount.

    Usa credenciales MASTER para autenticar (no las de la subaccount). Es una
    operación instantánea — sin port-out, sin cambio de número. Solo aplica a
    subaccounts bajo la misma master account.

    Retorna el phone_sid (igual al input, por si el SDK lo renueva).
    """
    client = _get_twilio_client(master_account_sid, master_auth_token)
    incoming = client.incoming_phone_numbers(phone_sid).update(
        account_sid=subaccount_sid
    )
    logger.info(
        "Número transferido: phone_sid=%s → subaccount=%s",
        phone_sid, subaccount_sid,
    )
    return incoming.sid


def update_subaccount_twilio_status(
    subaccount_sid: str,
    status: str,
    *,
    master_account_sid: str | None = None,
    master_auth_token: str | None = None,
) -> str:
    """Cambia el status de una subaccount Twilio (via API del parent).

    Args:
        subaccount_sid: SID de la subaccount.
        status: 'active' | 'suspended' | 'closed'.
            - 'suspended' deshabilita llamadas entrantes/salientes inmediatamente.
            - 'closed' es PERMANENTE e irreversible — Twilio no permite reactivar.
            - 'active' revierte una subaccount previamente suspendida.

    NOTA: el servicio acepta 'closed' aunque la UI admin NO lo expone. Reservado
    para flujo administrativo fuera de MVP — requiere typed-confirmation (escribir
    el nombre del cliente) antes de llegar a producción. Fase 2 debe implementar
    ese flujo aquí, no duplicar la función.

    Usa credenciales master para autenticar; Twilio requiere que el parent
    administre el ciclo de vida de sus subaccounts.

    Retorna el status retornado por Twilio (debería igualar al solicitado).
    """
    if status not in ("active", "suspended", "closed"):
        raise ValueError(f"status inválido: {status}")
    client = _get_twilio_client(master_account_sid, master_auth_token)
    account = client.api.v2010.accounts(subaccount_sid).update(status=status)
    logger.info(
        "Twilio subaccount %s status → %s (api devolvió %s)",
        subaccount_sid, status, account.status,
    )
    return account.status


def ensure_client_subaccount(
    sb: Client, client_id: str
) -> tuple[str, str, str]:
    """Garantiza que el cliente tenga subaccount + Elastic SIP Trunk.

    Máquina de estados `twilio_subaccount_status`:
      NULL            — nunca se intentó crear subaccount
      'provisioning'  — subaccount creada en Twilio, trunk pendiente
      'active'        — subaccount + trunk listos para recibir/hacer llamadas
      'suspended'     — admin la suspendió desde UI
      'closed'        — admin la cerró (permanente)

    Idempotente:
      - Si existen ambos y status='active', retorna.
      - Si existe subaccount sin trunk (fallo previo), crea trunk y transiciona
        'provisioning' → 'active'.
      - Si no existe nada, crea subaccount (status='provisioning'), luego trunk,
        luego transiciona a 'active'. Si falla antes del trunk, el estado queda
        en 'provisioning' y el próximo intento solo crea el trunk.

    Retorna (subaccount_sid, subaccount_auth_token_plaintext, trunk_sid).

    No debe llamarse para clientes con BYOT activo — esos usan sus propias creds.
    El caller debe resolver BYOT primero.
    """
    from api.crypto import decrypt_value, encrypt_value

    result = (
        sb.table("clients")
        .select(
            "slug, twilio_subaccount_sid, twilio_subaccount_auth_token, "
            "twilio_subaccount_trunk_sid, twilio_subaccount_status"
        )
        .eq("id", client_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise ValueError(f"Cliente {client_id} no encontrado")

    row = result.data[0]
    sid = row.get("twilio_subaccount_sid")
    token_enc = row.get("twilio_subaccount_auth_token")
    trunk_sid = row.get("twilio_subaccount_trunk_sid")
    current_status = row.get("twilio_subaccount_status")

    # Subaccounts cerradas/suspendidas no deben reutilizarse silenciosamente:
    # el admin debe decidir explícitamente reactivar.
    if current_status in ("suspended", "closed"):
        raise ValueError(
            f"Cliente {client_id} tiene subaccount Twilio en estado "
            f"'{current_status}' — requiere reactivación explícita por admin"
        )

    token: str | None = None
    if sid and token_enc:
        token = decrypt_value(token_enc)
        if not token:
            raise ValueError(
                f"Subaccount existente para cliente {client_id} pero token "
                "no pudo desencriptarse — revisa ENCRYPTION_KEY"
            )

    if not sid:
        friendly = f"voiceai-prod-{_slugify_for_twilio(row['slug'])}"
        sid, token = create_twilio_subaccount(friendly)
        from datetime import datetime, timezone
        sb.table("clients").update({
            "twilio_subaccount_sid": sid,
            "twilio_subaccount_auth_token": encrypt_value(token),
            "twilio_subaccount_status": "provisioning",
            "twilio_subaccount_created_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", client_id).execute()

    assert token is not None  # invariante tras el bloque anterior

    if not trunk_sid:
        trunk_sid = setup_twilio_elastic_sip_trunk(
            account_sid=sid, auth_token=token,
        )
        # Transición provisioning → active al completar el trunk
        sb.table("clients").update({
            "twilio_subaccount_trunk_sid": trunk_sid,
            "twilio_subaccount_status": "active",
        }).eq("id", client_id).execute()
    elif current_status == "provisioning":
        # Self-heal: trunk existe pero status quedó inconsistente
        sb.table("clients").update({
            "twilio_subaccount_status": "active",
        }).eq("id", client_id).execute()

    return sid, token, trunk_sid


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
