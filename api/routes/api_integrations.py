"""Rutas CRUD de API Integrations (sub-recurso de clients)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_supabase
from api.middleware.auth import CurrentUser, get_current_user
from api.schemas import (
    ApiIntegrationCreateRequest,
    ApiIntegrationOut,
    ApiIntegrationTestResult,
    ApiIntegrationUpdateRequest,
    MessageResponse,
    api_integration_out_from_row,
)

router = APIRouter()


def _check_client_access(user: CurrentUser, client_id: str) -> None:
    """Verifica que el usuario tenga acceso al cliente."""
    if user.role == "client" and user.client_id != client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")


# ── CRUD ─────────────────────────────────────────────


@router.get("/{client_id}/api-integrations", response_model=list[ApiIntegrationOut])
async def list_api_integrations(
    client_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> list[ApiIntegrationOut]:
    _check_client_access(user, client_id)
    sb = get_supabase()
    result = (
        sb.table("api_integrations")
        .select("*")
        .eq("client_id", client_id)
        .order("created_at")
        .execute()
    )
    return [api_integration_out_from_row(r) for r in result.data]


@router.post("/{client_id}/api-integrations", response_model=ApiIntegrationOut, status_code=201)
async def create_api_integration(
    client_id: str,
    req: ApiIntegrationCreateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> ApiIntegrationOut:
    _check_client_access(user, client_id)
    sb = get_supabase()

    data: dict = {
        "client_id": client_id,
        "name": req.name,
        "description": req.description,
        "url": req.url,
        "method": req.method,
        "headers": req.headers or {},
        "body_template": req.body_template,
        "query_params": req.query_params or {},
        "auth_type": req.auth_type,
        "auth_config": req.auth_config or {},
        "response_type": req.response_type,
        "response_path": req.response_path,
        "agent_ids": req.agent_ids,
        "input_schema": req.input_schema or {"parameters": []},
    }

    result = sb.table("api_integrations").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=400, detail="Error creando API integration")
    return api_integration_out_from_row(result.data[0])


@router.patch("/{client_id}/api-integrations/{integration_id}", response_model=ApiIntegrationOut)
async def update_api_integration(
    client_id: str,
    integration_id: str,
    req: ApiIntegrationUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> ApiIntegrationOut:
    _check_client_access(user, client_id)
    sb = get_supabase()

    updates = req.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    result = (
        sb.table("api_integrations")
        .update(updates)
        .eq("id", integration_id)
        .eq("client_id", client_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="API integration no encontrada")
    return api_integration_out_from_row(result.data[0])


@router.delete("/{client_id}/api-integrations/{integration_id}", response_model=MessageResponse)
async def delete_api_integration(
    client_id: str,
    integration_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> MessageResponse:
    _check_client_access(user, client_id)
    sb = get_supabase()

    result = (
        sb.table("api_integrations")
        .delete()
        .eq("id", integration_id)
        .eq("client_id", client_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="API integration no encontrada")
    return MessageResponse(message="API integration eliminada")


# ── Test endpoint ────────────────────────────────────


@router.post(
    "/{client_id}/api-integrations/{integration_id}/test",
    response_model=ApiIntegrationTestResult,
)
async def test_api_integration(
    client_id: str,
    integration_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> ApiIntegrationTestResult:
    """Prueba el endpoint configurado con datos de ejemplo."""
    _check_client_access(user, client_id)
    sb = get_supabase()

    result = (
        sb.table("api_integrations")
        .select("*")
        .eq("id", integration_id)
        .eq("client_id", client_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="API integration no encontrada")

    row = result.data[0]

    try:
        from agent.api_executor import execute_api_call

        # Construir parámetros de prueba vacíos
        test_params: dict[str, str] = {}
        input_schema = row.get("input_schema") or {}
        for param in input_schema.get("parameters", []):
            name = param.get("name", "")
            ptype = param.get("type", "string")
            if ptype == "number":
                test_params[name] = "0"
            else:
                test_params[name] = "test"

        status_code, response_text = await execute_api_call(row, test_params, timeout=15)

        # Actualizar estado del test en DB
        sb.table("api_integrations").update({
            "last_tested_at": datetime.now(timezone.utc).isoformat(),
            "last_test_status": "success" if 200 <= status_code < 400 else f"error_{status_code}",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", integration_id).execute()

        success = 200 <= status_code < 400
        return ApiIntegrationTestResult(
            success=success,
            status_code=status_code,
            response_preview=response_text[:500] if response_text else None,
            error=None if success else f"HTTP {status_code}",
        )

    except Exception as e:
        # Guardar estado de error
        sb.table("api_integrations").update({
            "last_tested_at": datetime.now(timezone.utc).isoformat(),
            "last_test_status": f"error: {str(e)[:100]}",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", integration_id).execute()

        return ApiIntegrationTestResult(
            success=False,
            error=str(e),
        )
