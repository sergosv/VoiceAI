"""Tests exhaustivos de normalización de teléfonos.

Estos tests previenen regresiones en phone_utils.normalize_phone(),
que es usado tanto por el agente de voz como por WhatsApp para
resolver contactos y enviar mensajes.
"""

from __future__ import annotations

import pytest

from agent.phone_utils import normalize_phone


class TestMexicanNumbers:
    """Números mexicanos — el caso más común."""

    def test_10_digits_queretaro(self):
        """10 dígitos → agrega +52."""
        assert normalize_phone("4722333334") == "+524722333334"

    def test_10_digits_merida(self):
        assert normalize_phone("9994890531") == "+529994890531"

    def test_10_digits_cdmx(self):
        assert normalize_phone("5551234567") == "+525551234567"

    def test_12_digits_with_52(self):
        """Ya tiene código de país 52."""
        assert normalize_phone("525551234567") == "+525551234567"

    def test_12_digits_with_plus_52(self):
        """Ya tiene +52."""
        assert normalize_phone("+525551234567") == "+525551234567"

    def test_13_digits_old_521_format(self):
        """Formato viejo +521 → quitar el 1."""
        assert normalize_phone("5215551234567") == "+525551234567"

    def test_13_digits_with_plus_521(self):
        assert normalize_phone("+5215551234567") == "+525551234567"

    def test_with_spaces(self):
        assert normalize_phone("52 555 123 4567") == "+525551234567"

    def test_with_hyphens(self):
        assert normalize_phone("52-555-123-4567") == "+525551234567"

    def test_with_parens(self):
        assert normalize_phone("(52) 555 1234567") == "+525551234567"

    def test_with_dots(self):
        assert normalize_phone("52.555.123.4567") == "+525551234567"

    def test_idempotent(self):
        """Normalizar un número ya normalizado no lo cambia."""
        assert normalize_phone("+529994890531") == "+529994890531"

    def test_idempotent_old_format(self):
        """Normalizar +521... siempre quita el 1."""
        result = normalize_phone("+5219994890531")
        assert result == "+529994890531"
        # Segunda pasada no cambia
        assert normalize_phone(result) == "+529994890531"


class TestColombianNumbers:
    """Números colombianos con default_country='CO'."""

    def test_10_digits_colombia(self):
        assert normalize_phone("3246800989", default_country="CO") == "+573246800989"

    def test_already_with_57(self):
        assert normalize_phone("+573246800989") == "+573246800989"


class TestUSNumbers:
    """Números de USA/Canada."""

    def test_11_digits_with_1(self):
        assert normalize_phone("15551234567") == "+15551234567"

    def test_with_plus_1(self):
        assert normalize_phone("+15551234567") == "+15551234567"

    def test_10_digits_us_default(self):
        assert normalize_phone("5551234567", default_country="US") == "+15551234567"


class TestEdgeCases:
    """Casos borde que han causado problemas."""

    def test_empty_string(self):
        assert normalize_phone("") == ""

    def test_no_digits(self):
        assert normalize_phone("abc") == "abc"

    def test_only_plus(self):
        result = normalize_phone("+")
        assert result == "+"  # Sin dígitos, devuelve original

    def test_14_digit_lid_number(self):
        """Números tipo LID no deben crashear."""
        result = normalize_phone("47223333253334")
        assert result == "+47223333253334"

    def test_15_digit_number(self):
        """Números de 15 dígitos (máximo E.164)."""
        result = normalize_phone("123456789012345")
        assert result == "+123456789012345"

    def test_10_digits_starting_with_1(self):
        """10 dígitos empezando con 1 — NO es código de área MX válido."""
        result = normalize_phone("1234567890")
        # Empieza con 1, no está en rango 2-9, no agrega +52
        assert result == "+1234567890"

    def test_mixed_special_chars(self):
        assert normalize_phone("+(52) 999-489-0531") == "+529994890531"

    def test_whatsapp_jid_number(self):
        """Número extraído de un JID de WhatsApp."""
        assert normalize_phone("5212227690231") == "+522227690231"

    def test_norway_format(self):
        """Número noruego con +47 — 10 dígitos con + se preserva."""
        # Con +, se preserva como internacional
        result = normalize_phone("+4722334455")
        # 10 dígitos con + → preserva el +
        assert result.startswith("+")

    def test_international_12_digits(self):
        """Número internacional de 12 dígitos se preserva."""
        result = normalize_phone("+447911123456")
        assert result == "+447911123456"
