"""Módulo centralizado de rates y clasificación de costos plataforma vs externo."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

# Costos siempre cobrados por la plataforma (USD/min)
PLATFORM_RATES: dict[str, Decimal] = {
    "livekit": Decimal("0.01"),
    "telephony": Decimal("0.01"),
}

# Costos de servicios cuando están incluidos en la plataforma (USD/min)
SERVICE_RATES: dict[str, Decimal] = {
    "stt": Decimal("0.005"),
    "llm": Decimal("0.01"),
    "tts": Decimal("0.01"),
}

# Proveedores incluidos en la plataforma (usan nuestras API keys)
INCLUDED_PROVIDERS: dict[str, set[str]] = {
    "stt": {"deepgram"},
    "llm": {"google"},
    "tts": {"cartesia"},
}

# Rates estimados por proveedor BYOK (USD/min)
EXTERNAL_RATES: dict[str, Decimal] = {
    "deepgram": Decimal("0.0043"),
    "google_stt": Decimal("0.006"),
    "openai_stt": Decimal("0.006"),
    "google_llm": Decimal("0.004"),
    "openai_llm": Decimal("0.015"),
    "anthropic": Decimal("0.012"),
    "cartesia": Decimal("0.010"),
    "elevenlabs": Decimal("0.030"),
    "openai_tts": Decimal("0.015"),
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
    # Para evitar ambigüedad, los providers que existen en múltiples servicios
    # se buscan con sufijo: google_stt, google_llm, openai_stt, openai_tts, openai_llm
    ambiguous = {"google", "openai"}
    if provider in ambiguous:
        return f"{provider}_{service}"
    return provider


def get_external_rate(service: str, provider: str) -> Decimal:
    """Retorna el rate estimado para un proveedor externo."""
    key = _external_rate_key(service, provider)
    return EXTERNAL_RATES.get(key, Decimal("0.01"))


def build_cost_breakdown(call: dict[str, Any]) -> dict[str, Any]:
    """Construye el desglose de costos para una llamada con clasificación plataforma/externo."""
    meta = call.get("metadata") or {}
    duration_min = (call.get("duration_seconds") or 0) / 60

    stt_provider = meta.get("stt_provider", "deepgram")
    llm_provider = meta.get("llm_provider", "google")
    tts_provider = meta.get("tts_provider", "cartesia")

    lines: list[dict[str, Any]] = []
    platform_total = Decimal("0")
    external_total = Decimal("0")

    # Servicios de plataforma fijos (livekit, telephony)
    for svc, rate in PLATFORM_RATES.items():
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

    # Servicios variables (stt, llm, tts)
    providers = {"stt": stt_provider, "llm": llm_provider, "tts": tts_provider}
    for svc, provider in providers.items():
        cost_field = f"cost_{svc}"
        amount = Decimal(str(call.get(cost_field, 0)))
        classification = classify_service(svc, provider)
        is_estimate = classification == "external"

        if is_estimate and float(amount) == 0 and duration_min > 0:
            # Si no hay costo registrado pero hay duración, estimar
            amount = get_external_rate(svc, provider) * Decimal(str(duration_min))
            amount = amount.quantize(Decimal("0.0001"))

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
