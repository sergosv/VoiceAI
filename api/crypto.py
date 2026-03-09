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
    """Encrypt a string. Returns 'enc:' prefixed base64 if encryption available,
    otherwise returns plaintext."""
    if not plaintext:
        return plaintext
    f = _get_fernet()
    if not f:
        return plaintext
    encrypted = f.encrypt(plaintext.encode())
    return f"enc:{base64.urlsafe_b64encode(encrypted).decode()}"


def decrypt_value(stored: str) -> str:
    """Decrypt a stored value. Handles both encrypted ('enc:' prefix) and legacy plaintext."""
    if not stored:
        return stored
    if not stored.startswith("enc:"):
        return stored  # Legacy plaintext — return as-is
    f = _get_fernet()
    if not f:
        logger.error("Cannot decrypt: ENCRYPTION_KEY not available")
        return ""
    try:
        encrypted = base64.urlsafe_b64decode(stored[4:])
        return f.decrypt(encrypted).decode()
    except Exception as e:
        logger.error("Decryption failed: %s", e)
        return ""
