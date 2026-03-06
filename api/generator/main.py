"""Orquestador de generación: template + config -> system prompt o builder flow."""

from __future__ import annotations

import logging

from supabase import Client

from .builder_flow import generate_builder_flow
from .system_prompt import generate_system_prompt

logger = logging.getLogger(__name__)


async def generate_agent_from_template(
    supabase: Client,
    template_id: str,
    client_config: dict,
    mode: str = "system_prompt",
) -> dict:
    """Genera un agente completo desde un template.

    Args:
        supabase: Cliente de Supabase.
        template_id: UUID del agent_template.
        client_config: {business_name, agent_name, tone, transfer_phone, ...}
        mode: "system_prompt" o "builder_flow".

    Returns:
        {"mode": str, "result": str | dict, "template_info": dict}
    """
    tpl = (
        supabase.table("agent_templates")
        .select("*, industry_verticals(*), qualification_frameworks(*)")
        .eq("id", template_id)
        .limit(1)
        .execute()
    )

    if not tpl.data:
        raise ValueError(f"Template {template_id} no encontrado")

    template = tpl.data[0]
    vertical = template.pop("industry_verticals", {}) or {}
    framework = template.pop("qualification_frameworks", {}) or {}

    if mode == "system_prompt":
        result = generate_system_prompt(template, vertical, framework, client_config)
    elif mode == "builder_flow":
        result = generate_builder_flow(template, vertical, framework, client_config)
    else:
        raise ValueError(f"Modo invalido: {mode}. Usa 'system_prompt' o 'builder_flow'")

    # Incrementar contador de uso
    supabase.table("agent_templates").update(
        {"usage_count": template.get("usage_count", 0) + 1}
    ).eq("id", template_id).execute()

    return {
        "mode": mode,
        "result": result,
        "template_info": {
            "name": template["name"],
            "vertical": vertical.get("name"),
            "framework": framework.get("name"),
            "direction": template["direction"],
            "objective": template["objective"],
        },
    }
