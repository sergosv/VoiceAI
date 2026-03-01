"""Factory para construir componentes del voice pipeline según config BYOK del agente."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.config_loader import AgentConfig

logger = logging.getLogger(__name__)


def build_stt(config: AgentConfig, language: str):
    """Construye el STT según el provider del cliente."""
    provider = config.stt_provider
    api_key = config.stt_api_key  # None = env var fallback

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
    api_key = config.llm_api_key

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
    api_key = config.tts_api_key
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
