"""Genera nodos de Builder Flow desde template + vertical + framework.

Usa los tipos de nodo reales del FlowBuilder:
start, message, collectInput, condition, action, end, transfer
"""

from __future__ import annotations

import logging
import uuid

logger = logging.getLogger(__name__)

Y_SPACING = 150


def generate_builder_flow(
    template: dict,
    vertical: dict,
    framework: dict,
    client_config: dict,
) -> dict:
    """Genera un flow completo de nodos compatible con el FlowBuilder."""
    business = client_config.get("business_name", "la empresa")
    agent_name = client_config.get("agent_name", "el asistente")
    tone = client_config.get("tone") or template.get("tone_description", "")
    greeting = client_config.get("custom_greeting") or template.get("greeting", "")
    transfer_phone = client_config.get("transfer_phone", "")

    nodes: list[dict] = []
    edges: list[dict] = []
    y_position = 0

    # --- NODO START ---
    start_id = _make_id()
    nodes.append({
        "id": start_id,
        "type": "start",
        "data": {"label": "Inicio"},
        "position": {"x": 250, "y": y_position},
    })
    y_position += Y_SPACING

    # --- NODO GREETING (message) ---
    greeting_id = _make_id()
    identity = f"Eres {agent_name}, {template['agent_role']} de {business}. Tu tono: {tone}."

    if template.get("direction") == "outbound" and template.get("outbound_opener"):
        greeting_text = (
            f"{identity}\n\n"
            f"OUTBOUND: {template['outbound_opener']}\n"
            f"Pide permiso: {template.get('outbound_permission', 'Tienes un momento?')}"
        )
    else:
        greeting_text = f"{identity}\n\nSaluda: {greeting}"

    nodes.append({
        "id": greeting_id,
        "type": "message",
        "data": {"label": "Bienvenida", "message": greeting_text},
        "position": {"x": 250, "y": y_position},
    })
    edges.append({"id": _edge_id(), "source": start_id, "target": greeting_id})
    y_position += Y_SPACING

    # --- NODOS DE CALIFICACION (collectInput por paso del framework) ---
    prev_node_id = greeting_id

    for step in (template.get("qualification_steps") or []):
        step_id = _make_id()
        questions = step.get("questions", [])
        extract = step.get("extract_fields", [])
        tips = step.get("tips", "")

        prompt = f"Objetivo: {step.get('purpose', '')}\n\n"
        prompt += "Preguntas a hacer (integra naturalmente, NO como interrogatorio):\n"
        for q in questions:
            prompt += f"- {q}\n"
        if tips:
            prompt += f"\nTip: {tips}"

        letter = step.get("framework_step", "")
        label = f"{letter} - {step['id'].replace('_', ' ').title()}" if letter else step["id"].replace("_", " ").title()

        nodes.append({
            "id": step_id,
            "type": "collectInput",
            "data": {
                "label": label,
                "prompt": prompt,
                "variableName": extract[0] if extract else step["id"],
                "extractFields": extract,
            },
            "position": {"x": 250, "y": y_position},
        })
        edges.append({"id": _edge_id(), "source": prev_node_id, "target": step_id})
        prev_node_id = step_id
        y_position += Y_SPACING

    # --- NODO DE CLASIFICACION (condition) ---
    tiers = template.get("scoring_tiers", [])
    if tiers:
        classify_id = _make_id()
        nodes.append({
            "id": classify_id,
            "type": "condition",
            "data": {
                "label": "Clasificar Lead",
                "condition": "lead_score",
                "description": "Clasificar segun score acumulado",
            },
            "position": {"x": 250, "y": y_position},
        })
        edges.append({"id": _edge_id(), "source": prev_node_id, "target": classify_id})
        y_position += Y_SPACING

        # --- NODOS DE RESULTADO (uno por tier) ---
        x_offset = 0
        for tier in tiers:
            tier_id = _make_id()
            action = tier.get("action", "")
            label = tier.get("label", tier["tier"])

            if action == "transfer_human" and transfer_phone:
                # Nodo transfer
                nodes.append({
                    "id": tier_id,
                    "type": "transfer",
                    "data": {
                        "label": f"Transferir: {label}",
                        "phoneNumber": transfer_phone,
                        "message": "Tengo opciones perfectas para ti. Te comunico con un asesor que te puede ayudar ahora mismo.",
                    },
                    "position": {"x": x_offset, "y": y_position},
                })
            elif action == "schedule_followup":
                nodes.append({
                    "id": tier_id,
                    "type": "message",
                    "data": {
                        "label": f"Resultado: {label}",
                        "message": "El prospecto tiene interes moderado. Ofrece agendar una cita o visita.",
                    },
                    "position": {"x": x_offset, "y": y_position},
                })
            else:
                nodes.append({
                    "id": tier_id,
                    "type": "message",
                    "data": {
                        "label": f"Resultado: {label}",
                        "message": "El prospecto esta explorando. Ofrece enviar informacion y dar seguimiento.",
                    },
                    "position": {"x": x_offset, "y": y_position},
                })

            edges.append({
                "id": _edge_id(),
                "source": classify_id,
                "target": tier_id,
                "label": f"score >= {tier.get('min_score', 0)}",
            })
            x_offset += 300

        y_position += Y_SPACING

    # --- NODO SAVE DATA (action) ---
    all_fields = [f["key"] for f in vertical.get("custom_fields", [])]
    all_fields.extend(["nombre", "telefono", "email", "lead_score", "lead_tier"])

    save_id = _make_id()
    nodes.append({
        "id": save_id,
        "type": "action",
        "data": {
            "label": "Guardar Datos",
            "action": "save_lead_data",
            "fields": all_fields,
        },
        "position": {"x": 250, "y": y_position},
    })
    y_position += Y_SPACING

    # --- NODO END ---
    end_id = _make_id()
    farewell = template.get("farewell", "Gracias por tu tiempo. Que tengas excelente dia.")
    nodes.append({
        "id": end_id,
        "type": "end",
        "data": {"label": "Fin", "message": farewell},
        "position": {"x": 250, "y": y_position},
    })
    edges.append({"id": _edge_id(), "source": save_id, "target": end_id})

    return {
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "framework": framework.get("slug"),
            "vertical": vertical.get("slug"),
            "template": template.get("slug"),
            "direction": template.get("direction"),
        },
    }


def _make_id() -> str:
    return f"node_{uuid.uuid4().hex[:8]}"


def _edge_id() -> str:
    return f"edge_{uuid.uuid4().hex[:8]}"
