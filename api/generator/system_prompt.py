"""Genera system prompt completo desde template + vertical + framework."""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


def generate_system_prompt(
    template: dict,
    vertical: dict,
    framework: dict,
    client_config: dict,
) -> str:
    """Genera un system prompt combinando template + vertical + framework."""
    business = client_config.get("business_name", "la empresa")
    agent_name = client_config.get("agent_name", "el asistente")
    tone = client_config.get("tone") or template.get("tone_description", "Profesional y amable")
    greeting = client_config.get("custom_greeting") or template.get("greeting", "")
    transfer_phone = client_config.get("transfer_phone", "")
    custom_rules = client_config.get("custom_rules", [])

    sections: list[str] = []

    # --- IDENTIDAD ---
    sections.append(
        f"## IDENTIDAD\n"
        f"Eres {agent_name}, {template['agent_role']} de {business}.\n"
        f"Tu objetivo principal: {template['objective']}.\n"
        f"Tu tono: {tone}."
    )

    # --- SALUDO ---
    if template.get("direction") in ("outbound", "both") and template.get("outbound_opener"):
        sections.append(
            f"## SALUDO\n"
            f"Para llamadas ENTRANTES (inbound):\n{greeting}\n\n"
            f"Para llamadas SALIENTES (outbound):\n{template['outbound_opener']}\n"
            f"Siempre pide permiso para continuar: "
            f"{template.get('outbound_permission', 'Tienes un momento para platicar?')}"
        )
    elif greeting:
        sections.append(f"## SALUDO\n{greeting}")

    # --- FLUJO DE CALIFICACION ---
    if template.get("qualification_steps"):
        steps_text = _build_qualification_section(template["qualification_steps"], framework)
        sections.append(steps_text)

    # --- SCORING ---
    if template.get("scoring_tiers"):
        scoring_text = _build_scoring_section(template["scoring_tiers"], transfer_phone)
        sections.append(scoring_text)

    # --- MANEJO DE OBJECIONES ---
    if vertical.get("objections"):
        objections_text = _build_objections_section(vertical["objections"])
        sections.append(objections_text)

    # --- DATOS A CAPTURAR ---
    if vertical.get("custom_fields"):
        fields_text = _build_fields_section(vertical["custom_fields"])
        sections.append(fields_text)

    # --- REGLAS ---
    rules = template.get("rules", [])
    if isinstance(rules, str):
        rules = json.loads(rules)
    all_rules = rules + custom_rules + [
        "Si el prospecto pide hablar con un humano, transfiere inmediatamente",
        "No hagas mas de 2 preguntas seguidas sin aportar valor",
        "Confirma datos importantes antes de guardarlos",
    ]
    sections.append("## REGLAS ABSOLUTAS\n" + "\n".join(f"- {r}" for r in all_rules))

    # --- DESPEDIDA ---
    if template.get("farewell"):
        sections.append(f"## DESPEDIDA\n{template['farewell']}")

    return "\n\n".join(sections)


def _build_qualification_section(steps: list, framework: dict) -> str:
    fw_name = framework.get("name", "")
    lines = [f"## FLUJO DE CONVERSACION ({fw_name})"]
    lines.append("Sigue este orden natural, NO como interrogatorio.")
    lines.append("Integra las preguntas en la conversacion de forma fluida.\n")

    for i, step in enumerate(steps, 1):
        letter = step.get("framework_step", "")
        purpose = step.get("purpose", "")
        lines.append(f"### Paso {i}: {step['id'].upper()} ({letter}) - {purpose}")

        for q in step.get("questions", []):
            lines.append(f'  Pregunta: "{q}"')

        fields = step.get("extract_fields", [])
        if fields:
            lines.append(f"  Capturar: {', '.join(fields)}")

        for key, rule in step.get("score_rules", {}).items():
            if isinstance(rule, dict):
                lines.append(f"  Scoring: +{rule['points']} si {rule['condition']}")

        if step.get("tips"):
            lines.append(f"  Tip: {step['tips']}")
        lines.append("")

    return "\n".join(lines)


def _build_scoring_section(tiers: list, transfer_phone: str = "") -> str:
    lines = ["## SCORING Y ACCIONES"]
    lines.append("Calcula el score durante la conversacion sumando puntos de cada paso.\n")

    for tier in tiers:
        action_detail = ""
        if tier["action"] == "transfer_human" and transfer_phone:
            action_detail = f" Transfiere a {transfer_phone}."
        elif tier["action"] == "schedule_followup":
            action_detail = " Ofrece agendar una cita/visita."
        elif tier["action"] == "nurturing":
            action_detail = " Ofrece enviar informacion y dar seguimiento despues."

        lines.append(f"- {tier['label']} (score >= {tier['min_score']}): {action_detail}")
    return "\n".join(lines)


def _build_objections_section(objections: list) -> str:
    lines = ["## MANEJO DE OBJECIONES"]
    for obj in objections:
        lines.append(f'- "{obj["trigger"]}" -> "{obj["response"]}"')
    return "\n".join(lines)


def _build_fields_section(fields: list) -> str:
    lines = ["## DATOS A CAPTURAR"]
    lines.append("Al finalizar la conversacion, guarda estos datos del prospecto:\n")
    field_names = [f["key"] for f in fields]
    field_names.extend(["nombre", "telefono", "email", "lead_score", "lead_tier"])
    lines.append("Campos: " + ", ".join(field_names))
    lines.append("\nUsa la herramienta save_lead_data para guardar toda la informacion recopilada.")
    return "\n".join(lines)
