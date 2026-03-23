"""Reglas de formato para canales de texto (WhatsApp, Widget, GHL).

Equivalente de voice_rules pero para mensajes escritos.
Configurable por agente en voice_config.text_rules.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Defaults por canal
CHANNEL_DEFAULTS: dict[str, dict] = {
    "whatsapp": {
        "max_length": 600,
        "allow_emojis": True,
        "allow_markdown": False,  # WhatsApp tiene su propio formato
        "allow_links": True,
        "split_long_messages": True,
        "tone": "friendly",  # friendly, professional, neutral
    },
    "widget": {
        "max_length": 800,
        "allow_emojis": False,
        "allow_markdown": True,
        "allow_links": True,
        "split_long_messages": False,
        "tone": "professional",
    },
    "ghl": {
        "max_length": 600,
        "allow_emojis": True,
        "allow_markdown": False,
        "allow_links": True,
        "split_long_messages": True,
        "tone": "friendly",
    },
}


@dataclass
class TextRulesConfig:
    """Configuración de reglas de texto para un agente."""

    max_length: int = 600
    allow_emojis: bool = True
    allow_markdown: bool = False
    allow_links: bool = True
    split_long_messages: bool = True
    tone: str = "friendly"  # friendly, professional, neutral

    @classmethod
    def from_agent_config(cls, voice_config: dict, channel: str) -> TextRulesConfig:
        """Carga config de text_rules del agente, con fallback a defaults del canal."""
        defaults = CHANNEL_DEFAULTS.get(channel, CHANNEL_DEFAULTS["widget"])
        custom = voice_config.get("text_rules", {})

        # Custom por canal específico
        channel_custom = custom.get(channel, {})

        # Merge: channel_custom > custom global > defaults
        merged = {**defaults, **custom, **channel_custom}

        return cls(
            max_length=merged.get("max_length", defaults["max_length"]),
            allow_emojis=merged.get("allow_emojis", defaults["allow_emojis"]),
            allow_markdown=merged.get("allow_markdown", defaults["allow_markdown"]),
            allow_links=merged.get("allow_links", defaults["allow_links"]),
            split_long_messages=merged.get("split_long_messages", defaults["split_long_messages"]),
            tone=merged.get("tone", defaults["tone"]),
        )


def build_text_rules_prompt(config: TextRulesConfig, channel: str) -> str:
    """Genera instrucciones de formato para el system prompt de canales de texto."""
    rules = "\n\n## Reglas de formato (canal de texto)\n"

    # Longitud
    rules += f"- Respuestas de máximo {config.max_length} caracteres. Sé conciso y directo.\n"

    # Emojis
    if config.allow_emojis:
        rules += "- Puedes usar emojis con moderación para dar calidez (1-2 por mensaje máximo).\n"
    else:
        rules += "- NO uses emojis en las respuestas.\n"

    # Formato
    if config.allow_markdown:
        rules += "- Puedes usar formato: **negrita** para énfasis, listas con viñetas si es necesario.\n"
    else:
        rules += "- NO uses formato markdown (negritas, listas, headers). Escribe texto plano natural.\n"

    # Links
    if not config.allow_links:
        rules += "- NO incluyas URLs ni links en las respuestas.\n"

    # Tono
    if config.tone == "friendly":
        rules += (
            "- Tono amigable y cercano. Usa 'tú' o 'usted' según el contexto.\n"
            "- Inicia con saludo breve si es el primer mensaje.\n"
        )
    elif config.tone == "professional":
        rules += (
            "- Tono profesional y cortés. Usa 'usted' por default.\n"
            "- Respuestas estructuradas y claras.\n"
        )
    else:
        rules += "- Tono neutral y respetuoso.\n"

    # Específico por canal
    if channel == "whatsapp":
        rules += (
            "- Estás en WhatsApp. Responde como en un chat: mensajes cortos y naturales.\n"
            "- Si la respuesta es larga, divide en párrafos cortos.\n"
            "- NO repitas el nombre del negocio en cada mensaje.\n"
        )
    elif channel == "widget":
        rules += (
            "- Estás en un chat web. El usuario puede estar navegando el sitio.\n"
            "- Sé directo y ofrece ayuda específica.\n"
        )
    elif channel == "ghl":
        rules += (
            "- Estás respondiendo por mensajería. Sé conciso.\n"
        )

    return rules


def format_text_response(text: str, config: TextRulesConfig) -> str:
    """Aplica reglas de formato a una respuesta de texto antes de enviarla.

    A diferencia de las instrucciones en el prompt (que guían al LLM),
    esta función hace enforcement determinístico post-generación.
    """
    if not text:
        return text

    # Truncar si excede longitud máxima
    if len(text) > config.max_length:
        # Cortar en el último punto o espacio antes del límite
        truncated = text[:config.max_length]
        last_period = truncated.rfind(".")
        last_space = truncated.rfind(" ")
        cut_at = max(last_period, last_space)
        if cut_at > config.max_length * 0.5:
            text = truncated[:cut_at + 1].rstrip()
        else:
            text = truncated.rstrip()

    # Eliminar emojis si no permitidos
    if not config.allow_emojis:
        text = _remove_emojis(text)

    # Eliminar markdown si no permitido
    if not config.allow_markdown:
        text = _strip_markdown(text)

    # Eliminar links si no permitidos
    if not config.allow_links:
        text = _remove_urls(text)

    return text.strip()


def _remove_emojis(text: str) -> str:
    """Elimina emojis del texto."""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "\u2640-\u2642"
        "\u2600-\u2B55"
        "\u200d\u23cf\u23e9\u231a\ufe0f\u3030"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text).strip()


def _strip_markdown(text: str) -> str:
    """Elimina formato markdown básico."""
    # Bold **text** → text
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    # Italic *text* → text
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    # Headers ## text → text
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Bullet lists - text → text
    text = re.sub(r"^[\-\*]\s+", "", text, flags=re.MULTILINE)
    return text


def _remove_urls(text: str) -> str:
    """Elimina URLs del texto."""
    return re.sub(r"https?://\S+", "", text).strip()
