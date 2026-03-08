"""Factory para construir componentes del voice pipeline según config BYOK del agente."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.config_loader import AgentConfig

logger = logging.getLogger(__name__)

# Prefijos válidos por provider para validación de API keys
_KEY_PREFIXES: dict[str, tuple[str, ...]] = {
    "cartesia": ("sk_car_",),
    "elevenlabs": ("sk_",),
    "openai": ("sk-",),
}
# Prefijos que NO son de ElevenLabs aunque empiecen con "sk_"
_ELEVENLABS_EXCLUDED = ("sk_car_", "sk-proj-", "sk-")


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
        # ElevenLabs: empieza con "sk_" pero NO con prefijos de otros providers
        if api_key.startswith("sk_") and not any(
            api_key.startswith(ex) for ex in ("sk_car_",)
        ):
            return api_key
        if api_key.startswith("sk-"):
            # Esto es una key de OpenAI, no ElevenLabs
            logger.warning(
                "API key para %s tiene formato incorrecto (parece OpenAI). "
                "Usando env var como fallback.",
                provider,
            )
            return None
        logger.warning(
            "API key para %s no inicia con 'sk_'. Usando env var como fallback.",
            provider,
        )
        return None

    # Validación genérica por prefijo (cartesia, openai)
    if any(api_key.startswith(p) for p in prefixes):
        return api_key

    logger.warning(
        "API key para %s no inicia con %s. Usando env var como fallback.",
        provider,
        "/".join(prefixes),
    )
    return None


def build_stt(config: AgentConfig, language: str):
    """Construye el STT según el provider del cliente."""
    provider = config.stt_provider
    api_key = _validate_api_key(provider, config.stt_api_key)

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
    provider = config.llm_provider
    api_key = _validate_api_key(provider, config.llm_api_key)

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
    provider = config.tts_provider
    api_key = _validate_api_key(provider, config.tts_api_key)
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
