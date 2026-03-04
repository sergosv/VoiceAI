"""ABC para proveedores de WhatsApp + dataclass InboundMessage."""

from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass
class InboundMessage:
    """Mensaje entrante normalizado de cualquier proveedor."""

    remote_phone: str  # Número del remitente (con código país, sin +)
    text: str
    message_type: str = "text"  # text | image | audio | video | document
    provider_message_id: str | None = None
    # Identificador del proveedor para resolver la config
    ghl_location_id: str | None = None
    evo_instance_id: str | None = None


class WhatsAppProvider(abc.ABC):
    """Interfaz abstracta para proveedores de WhatsApp."""

    @abc.abstractmethod
    def parse_webhook(self, payload: dict) -> InboundMessage | None:
        """Parsea el payload del webhook y retorna InboundMessage o None si no aplica."""
        ...

    @abc.abstractmethod
    async def send_text(self, config: dict, to_phone: str, text: str) -> str | None:
        """Envía mensaje de texto. Retorna provider_message_id o None en error."""
        ...

    @abc.abstractmethod
    def validate_webhook(self, headers: dict, body: bytes) -> bool:
        """Valida firma/autenticidad del webhook. True = válido."""
        ...
