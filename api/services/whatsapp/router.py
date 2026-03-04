"""Factory para obtener el provider de WhatsApp correcto."""

from __future__ import annotations

from api.services.whatsapp.evolution import EvolutionProvider
from api.services.whatsapp.gohighlevel import GoHighLevelProvider
from api.services.whatsapp.provider import WhatsAppProvider

_providers: dict[str, WhatsAppProvider] = {
    "evolution": EvolutionProvider(),
    "gohighlevel": GoHighLevelProvider(),
}


def get_provider(name: str) -> WhatsAppProvider:
    """Retorna instancia del provider por nombre."""
    provider = _providers.get(name)
    if not provider:
        raise ValueError(f"Provider WhatsApp desconocido: {name}")
    return provider
