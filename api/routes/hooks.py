"""Rutas CRUD de lifecycle hooks para agentes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.audit import log_audit
from api.deps import get_supabase
from api.middleware.auth import CurrentUser, get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

# Eventos válidos del lifecycle
VALID_EVENTS = {
    "OnConversationStart", "OnGreeting",
    "OnUserMessage", "PreResponse", "PostResponse",
    "PreToolCall", "PostToolCall",
    "OnInactivity", "OnSentimentShift", "OnLanguageSwitch", "OnGuardrailHit",
    "OnEscalation", "OnConversationEnd", "PostConversationEnd",
}

VALID_TYPES = {"rule", "validate", "prompt", "notify", "transform", "evaluator"}
VALID_CHANNELS = {"voice", "whatsapp", "widget", "ghl", None}


# ── Schemas ──────────────────────────────────────────────


class HookOut(BaseModel):
    id: str
    client_id: str
    agent_id: str
    hook_event: str
    name: str = ""
    channel: str | None = None
    hook_type: str
    matcher: str = "*"
    config: dict = Field(default_factory=dict)
    priority: int = 100
    enabled: bool = True
    created_at: str | None = None
    updated_at: str | None = None


class HookCreateRequest(BaseModel):
    hook_event: str
    name: str = Field("", max_length=200)
    channel: str | None = None
    hook_type: str
    matcher: str = "*"
    config: dict = Field(default_factory=dict)
    priority: int = 100
    enabled: bool = True


class HookUpdateRequest(BaseModel):
    hook_event: str | None = None
    name: str | None = None
    channel: str | None = Field(None)
    hook_type: str | None = None
    matcher: str | None = None
    config: dict | None = None
    priority: int | None = None
    enabled: bool | None = None


class HookBulkSaveRequest(BaseModel):
    """Guardar todos los hooks de un agente de una vez (reemplaza todos)."""
    hooks: list[HookCreateRequest]


# ── Helpers ──────────────────────────────────────────────


def _check_access(user: CurrentUser, client_id: str) -> None:
    if user.role == "client" and user.client_id != client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")


def _validate_hook(req: HookCreateRequest | HookUpdateRequest) -> None:
    """Valida campos del hook."""
    if hasattr(req, "hook_event") and req.hook_event is not None:
        if req.hook_event not in VALID_EVENTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Evento inválido: {req.hook_event}. Válidos: {sorted(VALID_EVENTS)}",
            )
    if hasattr(req, "hook_type") and req.hook_type is not None:
        if req.hook_type not in VALID_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo inválido: {req.hook_type}. Válidos: {sorted(VALID_TYPES)}",
            )
    if hasattr(req, "channel") and req.channel is not None:
        if req.channel not in VALID_CHANNELS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Canal inválido: {req.channel}. Válidos: voice, whatsapp, widget, ghl",
            )


def _verify_agent_belongs_to_client(sb, agent_id: str, client_id: str) -> None:
    """Verifica que el agente pertenezca al cliente."""
    result = (
        sb.table("agents")
        .select("id")
        .eq("id", agent_id)
        .eq("client_id", client_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente no encontrado")


# ── Endpoints ────────────────────────────────────────────


@router.get("/{client_id}/agents/{agent_id}/hooks", response_model=list[HookOut])
async def list_hooks(
    client_id: str,
    agent_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> list[HookOut]:
    """Lista todos los hooks de un agente."""
    _check_access(user, client_id)
    sb = get_supabase()
    _verify_agent_belongs_to_client(sb, agent_id, client_id)

    result = (
        sb.table("agent_hooks")
        .select("*")
        .eq("agent_id", agent_id)
        .order("priority")
        .order("created_at")
        .execute()
    )
    return [HookOut(**row) for row in result.data]


@router.post("/{client_id}/agents/{agent_id}/hooks", response_model=HookOut, status_code=201)
async def create_hook(
    client_id: str,
    agent_id: str,
    req: HookCreateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> HookOut:
    """Crea un nuevo hook para un agente."""
    _check_access(user, client_id)
    _validate_hook(req)
    sb = get_supabase()
    _verify_agent_belongs_to_client(sb, agent_id, client_id)

    data = {
        "client_id": client_id,
        "agent_id": agent_id,
        "hook_event": req.hook_event,
        "name": req.name,
        "channel": req.channel,
        "hook_type": req.hook_type,
        "matcher": req.matcher,
        "config": req.config,
        "priority": req.priority,
        "enabled": req.enabled,
    }

    result = sb.table("agent_hooks").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creando hook")

    log_audit(
        action="hook.create",
        user_id=user.id,
        client_id=client_id,
        resource_type="agent_hook",
        resource_id=result.data[0]["id"],
        details={"agent_id": agent_id, "event": req.hook_event, "name": req.name},
    )
    return HookOut(**result.data[0])


@router.put("/{client_id}/agents/{agent_id}/hooks/{hook_id}", response_model=HookOut)
async def update_hook(
    client_id: str,
    agent_id: str,
    hook_id: str,
    req: HookUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> HookOut:
    """Actualiza un hook existente."""
    _check_access(user, client_id)
    _validate_hook(req)
    sb = get_supabase()
    _verify_agent_belongs_to_client(sb, agent_id, client_id)

    # Construir update dict excluyendo None
    update_data = {k: v for k, v in req.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nada que actualizar")

    result = (
        sb.table("agent_hooks")
        .update(update_data)
        .eq("id", hook_id)
        .eq("agent_id", agent_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hook no encontrado")

    log_audit(
        action="hook.update",
        user_id=user.id,
        client_id=client_id,
        resource_type="agent_hook",
        resource_id=hook_id,
        details={"agent_id": agent_id, "changes": list(update_data.keys())},
    )
    return HookOut(**result.data[0])


@router.delete("/{client_id}/agents/{agent_id}/hooks/{hook_id}")
async def delete_hook(
    client_id: str,
    agent_id: str,
    hook_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Elimina un hook."""
    _check_access(user, client_id)
    sb = get_supabase()
    _verify_agent_belongs_to_client(sb, agent_id, client_id)

    result = (
        sb.table("agent_hooks")
        .delete()
        .eq("id", hook_id)
        .eq("agent_id", agent_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hook no encontrado")

    log_audit(
        action="hook.delete",
        user_id=user.id,
        client_id=client_id,
        resource_type="agent_hook",
        resource_id=hook_id,
        details={"agent_id": agent_id},
    )
    return {"ok": True}


@router.put("/{client_id}/agents/{agent_id}/hooks/{hook_id}/toggle")
async def toggle_hook(
    client_id: str,
    agent_id: str,
    hook_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> HookOut:
    """Activa/desactiva un hook."""
    _check_access(user, client_id)
    sb = get_supabase()
    _verify_agent_belongs_to_client(sb, agent_id, client_id)

    # Leer estado actual
    current = (
        sb.table("agent_hooks")
        .select("enabled")
        .eq("id", hook_id)
        .eq("agent_id", agent_id)
        .limit(1)
        .execute()
    )
    if not current.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hook no encontrado")

    new_enabled = not current.data[0]["enabled"]
    result = (
        sb.table("agent_hooks")
        .update({"enabled": new_enabled})
        .eq("id", hook_id)
        .execute()
    )
    return HookOut(**result.data[0])


@router.post("/{client_id}/agents/{agent_id}/hooks/bulk", response_model=list[HookOut])
async def bulk_save_hooks(
    client_id: str,
    agent_id: str,
    req: HookBulkSaveRequest,
    user: CurrentUser = Depends(get_current_user),
) -> list[HookOut]:
    """Guarda todos los hooks de un agente (reemplaza todos los existentes).

    Útil para el editor visual que envía la config completa de hooks.
    """
    _check_access(user, client_id)
    sb = get_supabase()
    _verify_agent_belongs_to_client(sb, agent_id, client_id)

    # Validar todos los hooks
    for hook in req.hooks:
        _validate_hook(hook)

    # Borrar hooks existentes
    sb.table("agent_hooks").delete().eq("agent_id", agent_id).execute()

    if not req.hooks:
        return []

    # Insertar nuevos
    rows = [
        {
            "client_id": client_id,
            "agent_id": agent_id,
            "hook_event": h.hook_event,
            "name": h.name,
            "channel": h.channel,
            "hook_type": h.hook_type,
            "matcher": h.matcher,
            "config": h.config,
            "priority": h.priority,
            "enabled": h.enabled,
        }
        for h in req.hooks
    ]
    result = sb.table("agent_hooks").insert(rows).execute()

    log_audit(
        action="hook.bulk_save",
        user_id=user.id,
        client_id=client_id,
        resource_type="agent_hook",
        resource_id=agent_id,
        details={"count": len(req.hooks)},
    )
    return [HookOut(**row) for row in result.data]


# ── Templates ────────────────────────────────────────────


@router.get("/hook-templates")
async def list_hook_templates(
    user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    """Retorna templates de hooks predefinidos."""
    from api.services.hook_templates import get_hook_templates
    return get_hook_templates()


@router.post("/{client_id}/agents/{agent_id}/hooks/from-template", response_model=HookOut, status_code=201)
async def create_hook_from_template(
    client_id: str,
    agent_id: str,
    template_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> HookOut:
    """Crea un hook a partir de un template predefinido."""
    from api.services.hook_templates import get_hook_templates

    _check_access(user, client_id)
    sb = get_supabase()
    _verify_agent_belongs_to_client(sb, agent_id, client_id)

    # Buscar template
    templates = get_hook_templates()
    template = next((t for t in templates if t["id"] == template_id), None)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template no encontrado")

    data = {
        "client_id": client_id,
        "agent_id": agent_id,
        "hook_event": template["hook_event"],
        "name": template["name"],
        "channel": template.get("channel"),
        "hook_type": template["hook_type"],
        "matcher": template.get("matcher", "*"),
        "config": template["config"],
        "priority": template.get("priority", 100),
        "enabled": True,
    }

    result = sb.table("agent_hooks").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creando hook")

    log_audit(
        action="hook.create_from_template",
        user_id=user.id,
        client_id=client_id,
        resource_type="agent_hook",
        resource_id=result.data[0]["id"],
        details={"template_id": template_id, "name": template["name"]},
    )
    return HookOut(**result.data[0])
