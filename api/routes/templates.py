"""Template Store y Generador de Agentes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.deps import get_supabase
from api.generator.main import generate_agent_from_template
from api.middleware.auth import CurrentUser, get_current_user

router = APIRouter()


# ===== Schemas =====

class GenerateRequest(BaseModel):
    template_id: str
    mode: str = "system_prompt"
    business_name: str
    agent_name: str = "Asistente"
    tone: Optional[str] = None
    custom_greeting: Optional[str] = None
    custom_rules: Optional[list[str]] = None
    transfer_phone: Optional[str] = None


class CreateTemplateRequest(BaseModel):
    vertical_slug: str
    framework_slug: str
    slug: str
    name: str
    description: Optional[str] = None
    objective: str
    direction: str
    agent_role: str
    greeting: Optional[str] = None
    farewell: Optional[str] = None
    qualification_steps: list
    scoring_tiers: Optional[list] = None
    rules: Optional[list] = None
    tone_description: Optional[str] = None
    outbound_opener: Optional[str] = None
    outbound_permission: Optional[str] = None
    tags: Optional[list[str]] = None


# ===== Wizard endpoints =====

@router.get("/objectives")
async def list_objectives(
    user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    """Lista objetivos disponibles para el wizard."""
    sb = get_supabase()
    result = (
        sb.table("agent_objectives")
        .select("*")
        .eq("is_active", True)
        .order("sort_order")
        .execute()
    )
    return result.data or []


@router.get("/verticals")
async def list_verticals(
    user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    """Lista verticales de industria disponibles."""
    sb = get_supabase()
    result = (
        sb.table("industry_verticals")
        .select("slug, name, description, icon, default_framework_slug, sort_order")
        .eq("is_active", True)
        .order("sort_order")
        .execute()
    )
    return result.data or []


@router.get("/frameworks")
async def list_frameworks(
    user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    """Lista frameworks de calificación disponibles."""
    sb = get_supabase()
    result = (
        sb.table("qualification_frameworks")
        .select("slug, name, description, best_for, sort_order")
        .eq("is_active", True)
        .order("sort_order")
        .execute()
    )
    return result.data or []


@router.get("/search")
async def search_templates(
    user: CurrentUser = Depends(get_current_user),
    vertical: str | None = None,
    objective: str | None = None,
    direction: str | None = None,
) -> list[dict]:
    """Buscar templates filtrados por vertical, objetivo y/o dirección."""
    sb = get_supabase()
    query = (
        sb.table("agent_templates")
        .select("*, industry_verticals(name, icon), qualification_frameworks(name, slug)")
        .eq("is_active", True)
    )

    if vertical:
        query = query.eq("vertical_slug", vertical)
    if direction and direction != "both":
        query = query.in_("direction", [direction, "both"])
    if objective:
        query = query.contains("tags", [objective])

    result = query.order("sort_order").execute()
    return result.data or []


@router.get("/preview/{template_id}")
async def preview_template(
    template_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Ver detalle completo de un template antes de generar."""
    sb = get_supabase()
    result = (
        sb.table("agent_templates")
        .select("*, industry_verticals(*), qualification_frameworks(*)")
        .eq("id", template_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(404, "Template no encontrado")
    return result.data[0]


@router.post("/generate")
async def generate_agent(
    request: GenerateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Genera un agente desde un template (system prompt o builder flow)."""
    sb = get_supabase()
    try:
        result = await generate_agent_from_template(
            supabase=sb,
            template_id=request.template_id,
            client_config={
                "business_name": request.business_name,
                "agent_name": request.agent_name,
                "tone": request.tone,
                "custom_greeting": request.custom_greeting,
                "custom_rules": request.custom_rules or [],
                "transfer_phone": request.transfer_phone,
            },
            mode=request.mode,
        )
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


# ===== Admin endpoints =====

@router.post("/admin/templates", status_code=201)
async def create_template(
    template: CreateTemplateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Crear un nuevo template de agente (admin)."""
    if user.role != "admin":
        raise HTTPException(403, "Solo admin puede crear templates")

    sb = get_supabase()
    data = template.model_dump(exclude_none=True)
    result = sb.table("agent_templates").insert(data).execute()
    if not result.data:
        raise HTTPException(500, "Error creando template")
    return result.data[0]


@router.get("/admin/stats")
async def template_stats(
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Estadísticas de uso de templates (admin)."""
    if user.role != "admin":
        raise HTTPException(403, "Solo admin")

    sb = get_supabase()
    result = (
        sb.table("agent_templates")
        .select("name, vertical_slug, usage_count, direction")
        .eq("is_active", True)
        .order("usage_count", desc=True)
        .execute()
    )
    templates = result.data or []
    return {
        "templates": templates,
        "total_uses": sum(t.get("usage_count", 0) for t in templates),
    }


@router.get("/leads/{client_id}")
async def get_leads_summary(
    client_id: str,
    user: CurrentUser = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365),
) -> dict:
    """Resumen de leads calificados para un cliente."""
    from datetime import datetime, timedelta, timezone

    if user.role == "client" and user.client_id != client_id:
        raise HTTPException(403, "Acceso denegado")

    sb = get_supabase()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    result = (
        sb.table("lead_scores")
        .select("*")
        .eq("client_id", client_id)
        .gte("created_at", since)
        .order("created_at", desc=True)
        .execute()
    )
    leads = result.data or []
    hot = len([l for l in leads if l.get("tier") == "hot"])
    warm = len([l for l in leads if l.get("tier") == "warm"])
    cold = len([l for l in leads if l.get("tier") == "cold"])

    return {
        "total": len(leads),
        "hot": hot,
        "warm": warm,
        "cold": cold,
        "leads": leads,
    }
