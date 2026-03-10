"""Encryption at rest for sensitive data (API keys, secrets)."""

from __future__ import annotations

import base64
import logging
import os

from cryptography.fernet import Fernet

logger = logging.getLogger("api.crypto")

# Encryption key from env var. Generate with:
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
_ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")


def _get_fernet() -> Fernet | None:
    """Retorna instancia Fernet si ENCRYPTION_KEY está configurada."""
    if not _ENCRYPTION_KEY:
        logger.warning("ENCRYPTION_KEY not set — API keys stored WITHOUT encryption")
        return None
    try:
        key = _ENCRYPTION_KEY.encode() if isinstance(_ENCRYPTION_KEY, str) else _ENCRYPTION_KEY
        return Fernet(key)
    except Exception as e:
        logger.error("Invalid ENCRYPTION_KEY: %s", e)
        return None


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string. Returns 'enc:' prefixed token if encryption available,
    otherwise returns plaintext.

    Fernet.encrypt() already returns url-safe base64, so we use it directly
    (no extra base64 layer).
    """
    if not plaintext:
        return plaintext
    f = _get_fernet()
    if not f:
        return plaintext
    encrypted = f.encrypt(plaintext.encode())
    return f"enc:{encrypted.decode()}"


def decrypt_value(stored: str) -> str:
    """Decrypt a stored value. Handles encrypted ('enc:' prefix), legacy plaintext,
    and old double-base64 format for backward compatibility."""
    if not stored:
        return stored
    if not stored.startswith("enc:"):
        return stored  # Legacy plaintext — return as-is
    f = _get_fernet()
    if not f:
        logger.error("Cannot decrypt: ENCRYPTION_KEY not available")
        return ""
    token = stored[4:]
    # Intentar formato nuevo (Fernet token directo)
    try:
        return f.decrypt(token.encode()).decode()
    except Exception:
        pass
    # Fallback: formato viejo con doble base64
    try:
        encrypted = base64.urlsafe_b64decode(token)
        return f.decrypt(encrypted).decode()
    except Exception as e:
        logger.error("Decryption failed (both formats): %s", e)
        return ""
