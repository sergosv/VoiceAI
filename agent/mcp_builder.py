"""Convierte configs de MCP servers (DB rows) a instancias LiveKit MCPServer."""

from __future__ import annotations

import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

# Regex para resolver placeholders ${VAR} en strings
_ENV_PLACEHOLDER = re.compile(r"\$\{([^}]+)\}")


def _resolve_env_vars(value: str, env_vars: dict[str, str]) -> str:
    """Resuelve placeholders ${VAR} usando env_vars del config y os.environ como fallback."""

    def _replace(match: re.Match) -> str:
        var_name = match.group(1)
        return env_vars.get(var_name, os.environ.get(var_name, match.group(0)))

    return _ENV_PLACEHOLDER.sub(_replace, value)


def _resolve_dict_env_vars(d: dict[str, str], env_vars: dict[str, str]) -> dict[str, str]:
    """Resuelve placeholders en todos los valores de un dict."""
    return {k: _resolve_env_vars(v, env_vars) for k, v in d.items()}


def build_mcp_servers(server_configs: list[dict[str, Any]]) -> list[Any]:
    """Convierte rows de la tabla mcp_servers a instancias MCPServerHTTP/MCPServerStdio.

    Cada server se construye de forma aislada: un config malo no afecta a los demás.

    Args:
        server_configs: Lista de dicts con la config de cada MCP server (rows de DB).

    Returns:
        Lista de MCPServerHTTP o MCPServerStdio listos para pasar al Agent.
    """
    from livekit.agents.llm.mcp import MCPServerHTTP, MCPServerStdio

    servers = []

    for cfg in server_configs:
        name = cfg.get("name", "unknown")
        conn_type = cfg.get("connection_type", "http")
        env_vars: dict[str, str] = cfg.get("env_vars") or {}

        try:
            if conn_type == "http":
                url = cfg.get("url")
                if not url:
                    logger.warning("MCP server '%s' sin URL, omitiendo", name)
                    continue

                url = _resolve_env_vars(url, env_vars)
                transport = cfg.get("transport_type", "sse")
                headers = _resolve_dict_env_vars(cfg.get("headers") or {}, env_vars)
                allowed_tools = cfg.get("allowed_tools")  # None = all

                kwargs: dict[str, Any] = {
                    "url": url,
                    "transport_type": transport,
                }
                if headers:
                    kwargs["headers"] = headers
                if allowed_tools is not None:
                    kwargs["allowed_tools"] = allowed_tools

                server = MCPServerHTTP(**kwargs)
                servers.append(server)
                logger.info(
                    "MCP server '%s' (HTTP/%s) configurado: %s",
                    name, transport, url,
                )

            elif conn_type == "stdio":
                command = cfg.get("command")
                if not command:
                    logger.warning("MCP server '%s' sin command, omitiendo", name)
                    continue

                command_args: list[str] = cfg.get("command_args") or []
                allowed_tools = cfg.get("allowed_tools")

                kwargs = {
                    "command": command,
                    "args": command_args,
                }
                if env_vars:
                    kwargs["env"] = env_vars

                server = MCPServerStdio(**kwargs)
                servers.append(server)
                logger.info(
                    "MCP server '%s' (stdio) configurado: %s %s",
                    name, command, " ".join(command_args),
                )

            else:
                logger.warning(
                    "MCP server '%s' con connection_type desconocido: '%s'",
                    name, conn_type,
                )

        except Exception:
            logger.exception("Error construyendo MCP server '%s', omitiendo", name)

    return servers
