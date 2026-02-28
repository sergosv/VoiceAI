"""Utilidades para normalización de números telefónicos."""

from __future__ import annotations

import re


def normalize_phone(phone: str) -> str:
    """Normaliza teléfono a formato E.164. México: +52XXXXXXXXXX.

    Reglas:
    - Elimina espacios, guiones, paréntesis, puntos
    - Si 10 dígitos → agrega +52 (México)
    - Si 11 dígitos empezando con 1 después de 52 → quita el 1 viejo
    - Si ya tiene +52 con 10 dígitos → OK
    - Preserva otros prefijos de país
    """
    # Limpiar caracteres no numéricos excepto el + inicial
    cleaned = re.sub(r"[^\d+]", "", phone)

    # Extraer el + si existe
    has_plus = cleaned.startswith("+")
    digits = cleaned.lstrip("+")

    if not digits:
        return phone  # Devolver original si no hay dígitos

    # Caso: 10 dígitos puros → número mexicano sin código de país
    if len(digits) == 10:
        return f"+52{digits}"

    # Caso: 12 dígitos empezando con 52 → formato +52XXXXXXXXXX
    if len(digits) == 12 and digits.startswith("52"):
        return f"+{digits}"

    # Caso: 13 dígitos empezando con 521 → formato viejo +521XXXXXXXXXX
    # Quitar el 1 intermedio (ya no se usa en México)
    if len(digits) == 13 and digits.startswith("521"):
        return f"+52{digits[3:]}"

    # Caso: 11 dígitos empezando con 1 → podría ser +1 (USA/Canada)
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"

    # Otros formatos internacionales: agregar + si no lo tiene
    if has_plus:
        return f"+{digits}"

    # Si no tiene + y no es reconocible, intentar como mexicano
    if len(digits) > 10:
        return f"+{digits}"

    return f"+{digits}" if digits else phone
