"""Lógica de negocio para gestión de clientes."""

from __future__ import annotations

import json
import logging
import os
import secrets
import string
from pathlib import Path

from google import genai
from supabase import Client, create_client as create_supabase_client

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


def load_voice_id(voice_key: str) -> str:
    """Obtiene voice_id del catálogo de voces. Lanza ValueError si no existe."""
    voices_file = CONFIG_DIR / "voices.json"
    with open(voices_file) as f:
        voices = json.load(f)
    voice = voices["voices"].get(voice_key)
    if not voice:
        available = list(voices["voices"].keys())
        raise ValueError(f"Voz '{voice_key}' no encontrada. Disponibles: {available}")
    return voice["id"]


def load_prompt_template(business_type: str) -> str:
    """Carga template de prompt por tipo de negocio."""
    prompt_file = CONFIG_DIR / "prompts" / f"{business_type}.md"
    if not prompt_file.exists():
        prompt_file = CONFIG_DIR / "prompts" / "generic.md"
    return prompt_file.read_text(encoding="utf-8")


def build_greeting(name: str, agent_name: str) -> str:
    """Genera un saludo por defecto."""
    return (
        f"Hola, bienvenido a {name}. Soy {agent_name}, su asistente virtual. "
        f"¿En qué puedo ayudarle?"
    )


def build_system_prompt(
    business_type: str,
    agent_name: str,
    business_name: str,
    language: str,
) -> str:
    """Genera system prompt a partir de template."""
    template = load_prompt_template(business_type)
    lang_text = (
        "español" if language == "es"
        else "English" if language == "en"
        else "español e inglés"
    )
    return template.format(
        agent_name=agent_name,
        business_name=business_name,
        business_type=business_type,
        language=lang_text,
        tone="cálido" if business_type == "dental" else "amable",
    )


def create_gemini_store(slug: str, google_api_key: str) -> tuple[str, str]:
    """Crea FileSearchStore en Gemini. Retorna (store_id, store_name)."""
    client = genai.Client(api_key=google_api_key)
    store = client.file_search_stores.create(
        config={"display_name": f"store-{slug}"}
    )
    store_id = store.name
    store_name = f"store-{slug}"
    logger.info("FileSearchStore creado: %s", store_id)
    return store_id, store_name


def create_client_in_db(
    sb: Client,
    *,
    name: str,
    slug: str,
    business_type: str,
    agent_name: str,
    language: str,
    voice_id: str,
    greeting: str,
    system_prompt: str,
    store_id: str | None,
    store_name: str | None,
    owner_email: str | None,
) -> dict:
    """Inserta un cliente en Supabase y retorna el row creado."""
    data = {
        "name": name,
        "slug": slug,
        "business_type": business_type,
        "agent_name": agent_name,
        "language": language,
        "voice_id": voice_id,
        "greeting": greeting,
        "system_prompt": system_prompt,
        "file_search_store_id": store_id,
        "file_search_store_name": store_name,
        "owner_email": owner_email,
    }
    result = sb.table("clients").insert(data).execute()
    client_row = result.data[0]

    # Otorgar créditos de bienvenida
    try:
        grant_welcome_credits(sb, client_row["id"])
    except Exception:
        logger.warning("No se pudieron otorgar créditos de bienvenida a %s", client_row["id"])

    return client_row


def delete_gemini_store(store_id: str, google_api_key: str) -> None:
    """Borra un FileSearchStore en Gemini. Usado para rollback.

    No lanza excepción — si falla el cleanup se loggea pero no propaga,
    porque el rollback ya está respondiendo a otro error.
    """
    try:
        client = genai.Client(api_key=google_api_key)
        client.file_search_stores.delete(name=store_id, config={"force": True})
        logger.info("FileSearchStore borrado (rollback): %s", store_id)
    except Exception:
        logger.exception("Error borrando FileSearchStore %s durante rollback", store_id)


def generate_temp_password(length: int = 16) -> str:
    """Genera una contraseña temporal segura para nuevos clientes.

    Incluye mayúsculas, minúsculas, dígitos y símbolos seguros.
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%&*"
    # Garantizar al menos un char de cada categoría para cumplir políticas comunes
    chars = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%&*"),
    ]
    chars += [secrets.choice(alphabet) for _ in range(length - 4)]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def create_owner_user(
    sb: Client,
    *,
    email: str,
    password: str,
    client_id: str,
) -> dict:
    """Crea un usuario en Supabase Auth + tabla users, asociado al cliente.

    Retorna el row insertado en users. Lanza ValueError si el email ya existe
    o si hay error creando en Auth.
    """
    sb_admin = create_supabase_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )

    try:
        auth_response = sb_admin.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
        })
    except Exception as e:
        msg = str(e).lower()
        if "already" in msg or "exists" in msg or "registered" in msg:
            raise ValueError(f"El email {email} ya está registrado") from e
        raise ValueError(f"Error creando usuario en Auth: {e}") from e

    auth_uid = auth_response.user.id

    try:
        result = sb.table("users").insert({
            "auth_user_id": str(auth_uid),
            "email": email,
            "role": "client",
            "client_id": client_id,
        }).execute()
    except Exception as e:
        # Si falla el insert en users, borrar el auth user para no dejar huérfano
        try:
            sb_admin.auth.admin.delete_user(auth_uid)
        except Exception:
            logger.exception("No se pudo borrar auth user %s tras fallo de insert", auth_uid)
        raise ValueError(f"Error insertando usuario en DB: {e}") from e

    logger.info("Owner user creado: %s (client=%s)", email, client_id)
    return result.data[0]


def delete_owner_user(email: str) -> None:
    """Borra un usuario de Supabase Auth por email. Usado para rollback.

    No propaga excepciones — el rollback ya está en flujo de error.
    """
    try:
        sb_admin = create_supabase_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_KEY"],
        )
        resp = sb_admin.auth.admin.list_users()
        users = getattr(resp, "users", None) or resp
        for u in users:
            if getattr(u, "email", None) == email:
                sb_admin.auth.admin.delete_user(u.id)
                logger.info("Auth user borrado (rollback): %s", email)
                return
    except Exception:
        logger.exception("Error borrando auth user %s durante rollback", email)


def grant_welcome_credits(sb: Client, client_id: str) -> None:
    """Otorga créditos de bienvenida a un cliente nuevo."""
    config = (
        sb.table("pricing_config")
        .select("free_credits_new_account")
        .limit(1)
        .execute()
    )
    free_credits = config.data[0]["free_credits_new_account"] if config.data else 10

    if free_credits > 0:
        sb.rpc("add_credits", {
            "p_client_id": client_id,
            "p_credits": free_credits,
            "p_type": "gift",
            "p_reason": "Créditos de bienvenida",
        }).execute()
        logger.info("Client %s: %d free credits added", client_id, free_credits)
