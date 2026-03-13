"""Módulo centralizado de rates y clasificación de costos plataforma vs externo.

Los costos reales se calculan en el agente (session_handler.py) usando métricas
de uso real (caracteres TTS, tokens LLM estimados, minutos de audio STT).
Este módulo se usa para:
1. Clasificar servicios como plataforma/externo en el dashboard
2. Estimar costos a priori cuando no hay datos reales (estimador de precios)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

# ── Rates reales por proveedor (USD) ─────────────────────────
# Deben coincidir con los rates en agent/session_handler.py

# Infra: cobran por minuto de conexión
PLATFORM_RATES: dict[str, Decimal] = {
    "livekit": Decimal("0.004"),       # LiveKit Cloud ~$0.004/min
    "telephony": Decimal("0.013"),     # Twilio SIP ~$0.013/min (MX)
}

# Servicios incluidos: rates promedio por minuto (para estimaciones)
# Los costos reales se calculan en el agente con métricas de uso
SERVICE_RATES: dict[str, Decimal] = {
    "stt": Decimal("0.0043"),          # Deepgram Nova-3
    "llm": Decimal("0.003"),           # Gemini Flash (promedio por minuto)
    "tts": Decimal("0.006"),           # Cartesia Sonic-3 (promedio por minuto)
}

# Proveedores incluidos en la plataforma (usan nuestras API keys)
INCLUDED_PROVIDERS: dict[str, set[str]] = {
    "stt": {"deepgram"},
    "llm": {"google"},
    "tts": {"cartesia"},
}

# Rates estimados por proveedor BYOK (USD/min equivalente)
EXTERNAL_RATES: dict[str, Decimal] = {
    "deepgram": Decimal("0.0043"),
    "google_stt": Decimal("0.006"),
    "openai_stt": Decimal("0.006"),
    "google_llm": Decimal("0.003"),
    "openai_llm": Decimal("0.015"),
    "anthropic": Decimal("0.012"),
    "cartesia": Decimal("0.006"),
    "elevenlabs": Decimal("0.018"),    # ~150 chars/min × $0.12/1K
    "openai_tts": Decimal("0.0023"),   # ~150 chars/min × $0.015/1K
}

# Labels legibles por servicio
SERVICE_LABELS: dict[str, str] = {
    "livekit": "LiveKit",
    "telephony": "Telefonía",
    "stt": "Speech-to-Text",
    "llm": "Modelo de lenguaje",
    "tts": "Text-to-Speech",
}


def classify_service(service: str, provider: str | None) -> str:
    """Clasifica un servicio como 'platform' o 'external'."""
    if service in PLATFORM_RATES:
        return "platform"
    included = INCLUDED_PROVIDERS.get(service, set())
    if provider and provider in included:
        return "platform"
    return "external"


def _external_rate_key(service: str, provider: str) -> str:
    """Construye la key para buscar en EXTERNAL_RATES."""
    ambiguous = {"google", "openai"}
    if provider in ambiguous:
        return f"{provider}_{service}"
    return provider


def get_external_rate(service: str, provider: str) -> Decimal:
    """Retorna el rate estimado para un proveedor externo."""
    key = _external_rate_key(service, provider)
    return EXTERNAL_RATES.get(key, Decimal("0.01"))


def build_cost_breakdown(call: dict[str, Any]) -> dict[str, Any]:
    """Construye el desglose de costos para una llamada.

    Los costos ya vienen calculados correctamente del agente usando métricas
    reales (caracteres TTS, tokens LLM, minutos STT). Este método los lee
    de la DB y los clasifica como plataforma/externo para el dashboard.
    """
    meta = call.get("metadata") or {}
    usage = meta.get("usage") or {}
    duration_min = (call.get("duration_seconds") or 0) / 60

    stt_provider = meta.get("stt_provider", "deepgram")
    llm_provider = meta.get("llm_provider", "google")
    tts_provider = meta.get("tts_provider", "cartesia")

    lines: list[dict[str, Any]] = []
    platform_total = Decimal("0")
    external_total = Decimal("0")

    # Servicios de plataforma fijos (livekit, telephony)
    for svc in ("livekit", "telephony"):
        cost_field = f"cost_{svc}"
        amount = Decimal(str(call.get(cost_field, 0)))
        lines.append({
            "service": svc,
            "label": SERVICE_LABELS.get(svc, svc),
            "amount": float(amount),
            "classification": "platform",
            "provider": svc,
            "is_estimate": False,
        })
        platform_total += amount

    # Servicios variables (stt, llm, tts) — costos ya calculados por el agente
    providers = {"stt": stt_provider, "llm": llm_provider, "tts": tts_provider}
    for svc, provider in providers.items():
        cost_field = f"cost_{svc}"
        amount = Decimal(str(call.get(cost_field, 0)))
        classification = classify_service(svc, provider)
        is_estimate = False

        # Fallback: si no hay costo registrado, estimar por duración
        if float(amount) == 0 and duration_min > 0:
            if classification == "platform":
                rate = SERVICE_RATES.get(svc, Decimal("0.005"))
            else:
                rate = get_external_rate(svc, provider)
            amount = (rate * Decimal(str(duration_min))).quantize(Decimal("0.0001"))
            is_estimate = True

        # Agregar detalle de uso si está disponible
        detail = ""
        if svc == "tts" and usage.get("tts_characters"):
            detail = f"{usage['tts_characters']:,} chars"
        elif svc == "llm" and usage.get("llm_input_tokens_est"):
            total_tokens = usage["llm_input_tokens_est"] + usage.get("llm_output_tokens_est", 0)
            detail = f"~{total_tokens:,} tokens"

        entry: dict[str, Any] = {
            "service": svc,
            "label": SERVICE_LABELS.get(svc, svc),
            "amount": float(amount),
            "classification": classification,
            "provider": provider,
            "is_estimate": is_estimate,
        }
        if detail:
            entry["detail"] = detail

        lines.append(entry)

        if classification == "platform":
            platform_total += amount
        else:
            external_total += amount

    return {
        "platform_cost": float(platform_total),
        "external_cost_estimate": float(external_total),
        "total": float(platform_total + external_total),
        "lines": lines,
    }


def estimate_cost(
    stt_provider: str,
    llm_provider: str,
    tts_provider: str,
    minutes: float,
) -> dict[str, Any]:
    """Estima costos para una combinación de proveedores y duración."""
    lines: list[dict[str, Any]] = []
    platform_total = Decimal("0")
    external_total = Decimal("0")
    mins = Decimal(str(minutes))

    # Plataforma fija
    for svc, rate in PLATFORM_RATES.items():
        amount = (rate * mins).quantize(Decimal("0.0001"))
        lines.append({
            "service": svc,
            "label": SERVICE_LABELS.get(svc, svc),
            "amount": float(amount),
            "classification": "platform",
            "provider": svc,
            "is_estimate": False,
        })
        platform_total += amount

    # Servicios variables
    providers = {"stt": stt_provider, "llm": llm_provider, "tts": tts_provider}
    for svc, provider in providers.items():
        classification = classify_service(svc, provider)
        if classification == "platform":
            rate = SERVICE_RATES[svc]
            is_estimate = False
        else:
            rate = get_external_rate(svc, provider)
            is_estimate = True

        amount = (rate * mins).quantize(Decimal("0.0001"))
        lines.append({
            "service": svc,
            "label": SERVICE_LABELS.get(svc, svc),
            "amount": float(amount),
            "classification": classification,
            "provider": provider,
            "is_estimate": is_estimate,
        })

        if classification == "platform":
            platform_total += amount
        else:
            external_total += amount

    return {
        "minutes": minutes,
        "platform_cost": float(platform_total),
        "external_cost_estimate": float(external_total),
        "total_estimate": float(platform_total + external_total),
        "lines": lines,
        "note": "Los costos de APIs externas son estimados y pueden variar.",
    }
