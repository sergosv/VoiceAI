"""Motor de ejecución HTTP para API Integrations.

Ejecuta llamadas HTTP configuradas como tools del agente,
con interpolación de variables, autenticación y extracción de respuesta.
"""

from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

MAX_RESPONSE_LENGTH = 2000


def _interpolate(template: str, params: dict[str, str]) -> str:
    """Reemplaza {{variable}} en un string con los valores de params."""
    if not template:
        return template

    def replacer(match: re.Match) -> str:
        key = match.group(1).strip()
        return str(params.get(key, match.group(0)))

    return re.sub(r"\{\{(\w+)\}\}", replacer, template)


def _interpolate_json(obj: Any, params: dict[str, str]) -> Any:
    """Interpolación recursiva en estructuras JSON."""
    if isinstance(obj, str):
        return _interpolate(obj, params)
    if isinstance(obj, dict):
        return {k: _interpolate_json(v, params) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_interpolate_json(item, params) for item in obj]
    return obj


def _build_auth_headers(auth_type: str, auth_config: dict) -> dict[str, str]:
    """Construye headers de autenticación según el tipo configurado."""
    if auth_type == "bearer":
        token = auth_config.get("token", "")
        if token:
            return {"Authorization": f"Bearer {token}"}

    elif auth_type == "api_key":
        header_name = auth_config.get("header_name", "X-API-Key")
        api_key = auth_config.get("api_key", "")
        if api_key:
            return {header_name: api_key}

    elif auth_type == "basic":
        username = auth_config.get("username", "")
        password = auth_config.get("password", "")
        if username:
            credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
            return {"Authorization": f"Basic {credentials}"}

    elif auth_type == "custom_header":
        header_name = auth_config.get("header_name", "")
        header_value = auth_config.get("header_value", "")
        if header_name and header_value:
            return {header_name: header_value}

    return {}


def _extract_response(data: Any, path: str) -> str:
    """Extrae un valor usando dot-notation path, trunca a MAX_RESPONSE_LENGTH."""
    if not path:
        result = json.dumps(data, ensure_ascii=False) if not isinstance(data, str) else data
        return result[:MAX_RESPONSE_LENGTH]

    current = data
    for key in path.split("."):
        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, list):
            try:
                current = current[int(key)]
            except (ValueError, IndexError):
                current = None
        else:
            current = None

        if current is None:
            return f"No se encontró la ruta '{path}' en la respuesta."

    result = json.dumps(current, ensure_ascii=False) if not isinstance(current, str) else current
    return result[:MAX_RESPONSE_LENGTH]


async def execute_api_call(
    config: dict,
    params: dict[str, str],
    timeout: int = 15,
) -> tuple[int, str]:
    """Ejecuta una llamada HTTP según la configuración de una API integration.

    Args:
        config: Row de la tabla api_integrations.
        params: Parámetros proporcionados por el LLM.
        timeout: Timeout en segundos.

    Returns:
        Tupla (status_code, response_text).
    """
    method = (config.get("method") or "GET").upper()
    url = _interpolate(config.get("url", ""), params)

    # Headers: custom + auth
    headers: dict[str, str] = {}
    custom_headers = config.get("headers") or {}
    for k, v in custom_headers.items():
        headers[k] = _interpolate(v, params)

    auth_type = config.get("auth_type", "none")
    auth_config = config.get("auth_config") or {}
    auth_headers = _build_auth_headers(auth_type, auth_config)
    headers.update(auth_headers)

    # Query params
    query_params: dict[str, str] = {}
    raw_qp = config.get("query_params") or {}
    for k, v in raw_qp.items():
        query_params[k] = _interpolate(str(v), params)

    # Body
    body: Any = None
    body_template = config.get("body_template")
    if body_template and method in ("POST", "PUT", "PATCH"):
        body = _interpolate_json(body_template, params)
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"

    response_type = config.get("response_type", "json")
    response_path = config.get("response_path", "")

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                params=query_params if query_params else None,
                json=body if isinstance(body, (dict, list)) else None,
                content=str(body) if body and not isinstance(body, (dict, list)) else None,
            )

            status_code = response.status_code

            if response_type == "json":
                try:
                    data = response.json()
                    extracted = _extract_response(data, response_path)
                except (json.JSONDecodeError, ValueError):
                    extracted = response.text[:MAX_RESPONSE_LENGTH]
            else:
                extracted = response.text[:MAX_RESPONSE_LENGTH]

            if status_code >= 400:
                logger.warning(
                    "API call to %s returned %d: %s",
                    url, status_code, extracted[:200],
                )

            return status_code, extracted

    except httpx.TimeoutException:
        logger.warning("API call to %s timed out after %ds", url, timeout)
        return 0, f"Error: timeout después de {timeout} segundos."

    except httpx.ConnectError as e:
        logger.warning("API call to %s connection error: %s", url, e)
        return 0, f"Error de conexión: {e}"

    except Exception as e:
        logger.exception("API call to %s failed: %s", url, e)
        return 0, f"Error: {e}"
