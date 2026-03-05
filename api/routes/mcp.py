"""Rutas CRUD de MCP servers (sub-recurso de clients)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_supabase
from api.middleware.auth import CurrentUser, get_current_user
from api.schemas import (
    McpServerCreateRequest,
    McpServerOut,
    McpServerTemplateOut,
    McpServerUpdateRequest,
    McpTestResult,
    MessageResponse,
    mcp_server_out_from_row,
)

router = APIRouter()


def _check_client_access(user: CurrentUser, client_id: str) -> None:
    """Verifica que el usuario tenga acceso al cliente."""
    if user.role == "client" and user.client_id != client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")


# ── CRUD ─────────────────────────────────────────────


@router.get("/{client_id}/mcp-servers", response_model=list[McpServerOut])
async def list_mcp_servers(
    client_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> list[McpServerOut]:
    _check_client_access(user, client_id)
    sb = get_supabase()
    result = (
        sb.table("mcp_servers")
        .select("*")
        .eq("client_id", client_id)
        .order("created_at")
        .execute()
    )
    return [mcp_server_out_from_row(r) for r in result.data]


@router.post("/{client_id}/mcp-servers", response_model=McpServerOut, status_code=201)
async def create_mcp_server(
    client_id: str,
    req: McpServerCreateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> McpServerOut:
    _check_client_access(user, client_id)
    sb = get_supabase()

    data: dict = {
        "client_id": client_id,
        "name": req.name,
        "description": req.description,
        "connection_type": req.connection_type,
        "url": req.url,
        "transport_type": req.transport_type,
        "headers": req.headers or {},
        "command": req.command,
        "command_args": req.command_args or [],
        "env_vars": req.env_vars or {},
        "allowed_tools": req.allowed_tools,
        "agent_ids": req.agent_ids,
    }

    # Si se creó desde un template, aplicar defaults
    if req.template_id:
        tmpl_result = (
            sb.table("mcp_server_templates")
            .select("*")
            .eq("id", req.template_id)
            .limit(1)
            .execute()
        )
        if tmpl_result.data:
            tmpl = tmpl_result.data[0]
            if not data.get("url"):
                data["url"] = tmpl.get("default_url")
            if not data.get("description"):
                data["description"] = tmpl.get("description")
            data["connection_type"] = tmpl.get("connection_type", "http")
            data["transport_type"] = tmpl.get("default_transport_type", "sse")
            if not data.get("command"):
                data["command"] = tmpl.get("default_command")
            if not data.get("command_args"):
                data["command_args"] = tmpl.get("default_command_args") or []

    result = sb.table("mcp_servers").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=400, detail="Error creando MCP server")
    return mcp_server_out_from_row(result.data[0])


@router.patch("/{client_id}/mcp-servers/{server_id}", response_model=McpServerOut)
async def update_mcp_server(
    client_id: str,
    server_id: str,
    req: McpServerUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> McpServerOut:
    _check_client_access(user, client_id)
    sb = get_supabase()

    updates = req.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    result = (
        sb.table("mcp_servers")
        .update(updates)
        .eq("id", server_id)
        .eq("client_id", client_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="MCP server no encontrado")
    return mcp_server_out_from_row(result.data[0])


@router.delete("/{client_id}/mcp-servers/{server_id}", response_model=MessageResponse)
async def delete_mcp_server(
    client_id: str,
    server_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> MessageResponse:
    _check_client_access(user, client_id)
    sb = get_supabase()

    result = (
        sb.table("mcp_servers")
        .delete()
        .eq("id", server_id)
        .eq("client_id", client_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="MCP server no encontrado")
    return MessageResponse(message="MCP server eliminado")


# ── Test connection ──────────────────────────────────


@router.post("/{client_id}/mcp-servers/{server_id}/test", response_model=McpTestResult)
async def test_mcp_server(
    client_id: str,
    server_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> McpTestResult:
    """Prueba la conexión a un MCP server y descubre sus tools."""
    _check_client_access(user, client_id)
    sb = get_supabase()

    result = (
        sb.table("mcp_servers")
        .select("*")
        .eq("id", server_id)
        .eq("client_id", client_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="MCP server no encontrado")

    row = result.data[0]

    try:
        from agent.mcp_builder import build_mcp_servers

        servers = build_mcp_servers([row])
        if not servers:
            # Intentar import directo para dar un error más específico
            import_error = None
            try:
                from livekit.agents.llm.mcp import MCPServerHTTP  # noqa: F401
            except ImportError as ie:
                import_error = f"{ie} (causa: {ie.__cause__})"
            return McpTestResult(
                success=False,
                error=import_error or f"No se pudo construir el servidor MCP con config: "
                f"type={row.get('connection_type')}, url={row.get('url')}, cmd={row.get('command')}",
            )

        server = servers[0]

        # Inicializar y descubrir tools
        await server.initialize()
        tools = await server.list_tools()

        from livekit.agents.llm.tool_context import get_raw_function_info

        tools_list = []
        for t in tools:
            info = get_raw_function_info(t)
            tool_entry = {
                "name": info.name,
                "description": info.raw_schema.get("description", ""),
            }
            # Guardar inputSchema para que chat/WhatsApp pueda crear declarations correctas
            raw_params = info.raw_schema.get("parameters") or info.raw_schema.get("inputSchema")
            if raw_params:
                tool_entry["parameters"] = raw_params
            tools_list.append(tool_entry)

        # Actualizar cache y timestamp en DB
        sb.table("mcp_servers").update({
            "tools_cache": tools_list,
            "last_connected_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", server_id).execute()

        # Cerrar la conexión
        await server.aclose()

        return McpTestResult(success=True, tools=tools_list)

    except Exception as e:
        error_msg = str(e)
        # "Connection closed" sin más contexto no ayuda — dar pistas
        if "Connection closed" in error_msg:
            conn_type = row.get("connection_type", "http")
            if conn_type == "stdio":
                error_msg = (
                    f"Connection closed — el proceso '{row.get('command')} "
                    f"{' '.join(row.get('command_args') or [])}' terminó inesperadamente. "
                    "Verifica que el comando y paquete existan (ej: npm install -g <paquete>)."
                )
            else:
                error_msg = (
                    f"Connection closed — no se pudo conectar a {row.get('url')}. "
                    "Verifica que la URL sea correcta y el servidor esté activo."
                )
        return McpTestResult(success=False, error=error_msg)


# ── Templates (router separado, montado en /api) ────

templates_router = APIRouter()


@templates_router.get("/mcp-templates", response_model=list[McpServerTemplateOut])
async def list_templates(
    user: CurrentUser = Depends(get_current_user),
) -> list[McpServerTemplateOut]:
    """Lista templates de MCP servers disponibles."""
    sb = get_supabase()
    result = (
        sb.table("mcp_server_templates")
        .select("*")
        .order("category")
        .order("name")
        .execute()
    )
    return [McpServerTemplateOut(**r) for r in result.data]
