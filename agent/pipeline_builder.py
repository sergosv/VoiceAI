"""Factory para construir componentes del voice pipeline según config BYOK del agente."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from agent.circuit_breaker import get_circuit, resolve_provider

if TYPE_CHECKING:
    from agent.config_loader import AgentConfig

logger = logging.getLogger(__name__)

# Prefijos válidos por provider para validación de API keys
_KEY_PREFIXES: dict[str, tuple[str, ...]] = {
    "cartesia": ("sk_car_",),
    "openai": ("sk-",),
    "elevenlabs": (),  # Sin prefijo fijo — keys alfanuméricas, validación por cross-check
}


def _validate_api_key(provider: str, api_key: str | None) -> str | None:
    """Valida que el formato de la API key corresponda al provider.

    Retorna la key si es válida, None si es inválida (fallback a env var).
    """
    if api_key is None:
        return None

    prefixes = _KEY_PREFIXES.get(provider)
    if prefixes is None:
        # Provider sin validación conocida (google, deepgram, anthropic, etc.)
        return api_key

    if provider == "elevenlabs":
        # ElevenLabs keys son alfanuméricas sin prefijo fijo.
        # Solo rechazar si claramente es de otro provider.
        if api_key.startswith("sk_car_"):
            logger.warning(
                "API key para %s parece ser de Cartesia. Usando env var como fallback.",
                provider,
            )
            return None
        if api_key.startswith("sk-"):
            logger.warning(
                "API key para %s parece ser de OpenAI. Usando env var como fallback.",
                provider,
            )
            return None
        return api_key

    # Validación genérica por prefijo (cartesia, openai)
    if any(api_key.startswith(p) for p in prefixes):
        return api_key

    logger.warning(
        "API key para %s no inicia con %s. Usando env var como fallback.",
        provider,
        "/".join(prefixes),
    )
    return None


def build_stt(
    config: AgentConfig,
    language: str,
    multi_lang: list[str] | None = None,
):
    """Construye el STT según el provider del cliente.

    Args:
        config: Configuración del agente.
        language: Idioma principal (ISO 639-1).
        multi_lang: Lista de idiomas soportados para auto-detección.
                    Si tiene más de 1 idioma, habilita detect_language en Deepgram.
    """
    provider = resolve_provider("stt", config.stt_provider)
    if provider != config.stt_provider:
        logger.warning("STT fallback: %s → %s", config.stt_provider, provider)
    api_key = _validate_api_key(provider, config.stt_api_key if provider == config.stt_provider else None)

    if provider == "deepgram":
        from livekit.plugins import deepgram
        kwargs = {
            "model": "nova-3",
            "language": language,
            "filler_words": True,
            "smart_format": True,
            "punctuate": True,
            "no_delay": True,
        }
        # Multi-idioma: habilitar auto-detección de Deepgram
        if multi_lang and len(multi_lang) > 1:
            kwargs["detect_language"] = True
            del kwargs["language"]
            logger.info(
                "STT multi-idioma habilitado: detect_language=True (idiomas: %s)",
                multi_lang,
            )
        if api_key:
            kwargs["api_key"] = api_key
        return deepgram.STT(**kwargs)

    if provider == "google":
        from livekit.plugins import google
        kwargs = {"languages": [language]}
        if api_key:
            kwargs["api_key"] = api_key
        return google.STT(**kwargs)

    if provider == "openai":
        from livekit.plugins import openai
        kwargs = {"model": "whisper-1", "language": language}
        if api_key:
            kwargs["api_key"] = api_key
        return openai.STT(**kwargs)

    logger.warning("STT provider desconocido '%s', usando deepgram", provider)
    from livekit.plugins import deepgram
    return deepgram.STT(model="nova-3", language=language)


def build_llm(config: AgentConfig):
    """Construye el LLM según el provider del cliente."""
    provider = resolve_provider("llm", config.llm_provider)
    if provider != config.llm_provider:
        logger.warning("LLM fallback: %s → %s", config.llm_provider, provider)
    api_key = _validate_api_key(provider, config.llm_api_key if provider == config.llm_provider else None)

    if provider == "google":
        from livekit.plugins import google
        kwargs = {"model": "gemini-2.5-flash"}
        if api_key:
            kwargs["api_key"] = api_key
        return google.LLM(**kwargs)

    if provider == "openai":
        from livekit.plugins import openai
        kwargs = {"model": "gpt-4o"}
        if api_key:
            kwargs["api_key"] = api_key
        return openai.LLM(**kwargs)

    if provider == "anthropic":
        from livekit.plugins import anthropic
        kwargs = {"model": "claude-sonnet-4-20250514"}
        if api_key:
            kwargs["api_key"] = api_key
        return anthropic.LLM(**kwargs)

    logger.warning("LLM provider desconocido '%s', usando google", provider)
    from livekit.plugins import google
    return google.LLM(model="gemini-2.5-flash")


def build_tts(config: AgentConfig, language: str):
    """Construye el TTS según el provider del cliente."""
    provider = resolve_provider("tts", config.tts_provider)
    if provider != config.tts_provider:
        logger.warning("TTS fallback: %s → %s", config.tts_provider, provider)
    api_key = _validate_api_key(provider, config.tts_api_key if provider == config.tts_provider else None)
    voice_id = config.voice_id if config.voice_id != "default" else None

    if provider == "cartesia":
        from livekit.plugins import cartesia
        kwargs = {
            "model": "sonic-3",
            "language": language,
            "speed": 1.0,
        }
        if voice_id:
            kwargs["voice"] = voice_id
        if api_key:
            kwargs["api_key"] = api_key
        return cartesia.TTS(**kwargs)

    if provider == "elevenlabs":
        from livekit.plugins import elevenlabs
        kwargs = {"model": "eleven_turbo_v2_5"}
        if voice_id:
            kwargs["voice_id"] = voice_id
        if api_key:
            kwargs["api_key"] = api_key
        return elevenlabs.TTS(**kwargs)

    if provider == "openai":
        from livekit.plugins import openai
        kwargs = {"model": "tts-1"}
        if voice_id:
            kwargs["voice"] = voice_id
        else:
            kwargs["voice"] = "alloy"
        if api_key:
            kwargs["api_key"] = api_key
        return openai.TTS(**kwargs)

    logger.warning("TTS provider desconocido '%s', usando cartesia", provider)
    from livekit.plugins import cartesia
    kwargs = {"model": "sonic-3", "language": language}
    if voice_id:
        kwargs["voice"] = voice_id
    return cartesia.TTS(**kwargs)


def build_realtime_model(config: AgentConfig):
    """Construye el modelo OpenAI Realtime para modo realtime."""
    from livekit.plugins import openai

    kwargs = {"model": config.realtime_model, "voice": config.realtime_voice}
    api_key = config.realtime_api_key
    if api_key:
        kwargs["api_key"] = api_key
    return openai.realtime.RealtimeModel(**kwargs)
