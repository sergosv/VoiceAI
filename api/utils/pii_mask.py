"""Utilidades para enmascarar PII en logs.

Enmascara teléfonos, emails y otros datos sensibles para prevenir
exposición en logs de producción.
"""

from __future__ import annotations

import re


def mask_phone(phone: str | None) -> str:
    """Enmascara un número de teléfono dejando solo los últimos 4 dígitos.

    Ejemplo: "+5219994890531" → "***0531"
    """
    if not phone:
        return "***"
    digits = re.sub(r"\D", "", phone)
    if len(digits) <= 4:
        return "***"
    return f"***{digits[-4:]}"


def mask_email(email: str | None) -> str:
    """Enmascara un email dejando primera letra y dominio.

    Ejemplo: "sergio@gmail.com" → "s***@gmail.com"
    """
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if len(local) <= 1:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"
