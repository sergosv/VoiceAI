"""Lógica de negocio para gestión de clientes."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from google import genai
from supabase import Client

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
    return result.data[0]
