"""Servicio para gestión de grabaciones de llamadas via Cloudflare R2."""

from __future__ import annotations

import logging
import os

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

logger = logging.getLogger("recordings")

_R2_ACCESS_KEY = os.environ.get("R2_ACCESS_KEY_ID", "")
_R2_SECRET_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")
_R2_ENDPOINT = os.environ.get("R2_ENDPOINT", "")
_R2_BUCKET = os.environ.get("R2_BUCKET", "voiceai-recordings")


def _get_s3_client():
    """Crea un cliente S3 compatible con Cloudflare R2."""
    return boto3.client(
        "s3",
        endpoint_url=_R2_ENDPOINT,
        aws_access_key_id=_R2_ACCESS_KEY,
        aws_secret_access_key=_R2_SECRET_KEY,
        config=BotoConfig(s3={"addressing_style": "path"}),
        region_name="auto",
    )


def generate_presigned_url(key: str, expires_in: int = 3600) -> str | None:
    """Genera una URL pre-firmada para descargar una grabación.

    Args:
        key: Object key en R2 (e.g. "client_id/agent_id/room.ogg").
        expires_in: Tiempo de expiración en segundos (default 1 hora).

    Returns:
        URL pre-firmada o None si falla.
    """
    try:
        client = _get_s3_client()
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": _R2_BUCKET, "Key": key},
            ExpiresIn=expires_in,
        )
    except Exception:
        logger.exception("Failed to generate presigned URL for: %s", key)
        return None


def delete_recording(key: str) -> bool:
    """Elimina una grabación de R2.

    Args:
        key: Object key en R2.

    Returns:
        True si se eliminó correctamente, False en caso de error.
    """
    try:
        client = _get_s3_client()
        client.delete_object(Bucket=_R2_BUCKET, Key=key)
        logger.info("Recording deleted from R2: %s", key)
        return True
    except Exception:
        logger.exception("Failed to delete recording: %s", key)
        return False


def check_exists(key: str) -> bool:
    """Verifica si un archivo de grabación existe en R2.

    Args:
        key: Object key en R2.

    Returns:
        True si el archivo existe, False si no existe o hay error.
    """
    try:
        client = _get_s3_client()
        client.head_object(Bucket=_R2_BUCKET, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        logger.exception("Error checking recording existence: %s", key)
        return False
    except Exception:
        logger.exception("Error checking recording existence: %s", key)
        return False


def get_egress_s3_config() -> dict:
    """Retorna la configuración S3 para LiveKit Egress API.

    Usado por el agente para iniciar grabaciones via Egress.
    """
    return {
        "access_key": _R2_ACCESS_KEY,
        "secret": _R2_SECRET_KEY,
        "bucket": _R2_BUCKET,
        "endpoint": _R2_ENDPOINT,
        "region": "auto",
        "force_path_style": True,
    }


def is_configured() -> bool:
    """Verifica si R2 está configurado con las credenciales necesarias."""
    return bool(_R2_ACCESS_KEY and _R2_SECRET_KEY and _R2_ENDPOINT)
