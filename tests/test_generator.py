"""Tests para api/generator — system_prompt.py, builder_flow.py, main.py."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from api.generator.builder_flow import generate_builder_flow
from api.generator.main import generate_agent_from_template
from api.generator.system_prompt import generate_system_prompt


# Fixtures compartidos
TEMPLATE_BASE = {
    "id": "tpl-1",
    "name": "Test Template",
    "slug": "test-template",
    "agent_role": "asistente de ventas",
    "objective": "Calificar leads de inmobiliaria",
    "direction": "inbound",
    "greeting": "Hola, bienvenido a nuestra empresa.",
    "farewell": "Gracias por tu interes, que tengas buen dia.",
    "tone_description": "Profesional y amigable",
    "qualification_steps": [
        {
            "id": "presupuesto",
            "framework_step": "B",
            "purpose": "Conocer presupuesto",
            "questions": ["Tienes un rango de presupuesto definido?"],
            "extract_fields": ["budget"],
            "score_rules": {"budget_ok": {"points": 3, "condition": "tiene presupuesto"}},
            "tips": "No preguntar directamente, integrar en conversacion",
        },
        {
            "id": "autoridad",
            "framework_step": "A",
            "purpose": "Identificar tomador de decision",
            "questions": ["Quien mas participa en la decision?"],
            "extract_fields": ["authority"],
            "score_rules": {},
        },
    ],
    "scoring_tiers": [
        {"tier": "hot", "label": "Lead Caliente", "min_score": 8, "action": "transfer_human"},
        {"tier": "warm", "label": "Lead Tibio", "min_score": 4, "action": "schedule_followup"},
        {"tier": "cold", "label": "Lead Frio", "min_score": 0, "action": "nurturing"},
    ],
    "rules": ["Responde siempre en espanol", "No inventes datos"],
    "usage_count": 5,
}

VERTICAL = {
    "name": "Inmobiliaria",
    "slug": "real-estate",
    "objections": [
        {"trigger": "Es muy caro", "response": "Tenemos opciones para todos los presupuestos"},
    ],
    "custom_fields": [
        {"key": "tipo_propiedad"},
        {"key": "zona_preferida"},
    ],
}

FRAMEWORK = {
    "name": "BANT",
    "slug": "bant",
}

CLIENT_CONFIG = {
    "business_name": "Inmobiliaria Norte",
    "agent_name": "Sofia",
    "tone": "Amable y cercana",
    "custom_greeting": "Hola! Soy Sofia de Inmobiliaria Norte.",
    "custom_rules": ["Ofrece visita virtual"],
    "transfer_phone": "+525551234567",
}


class TestGenerateSystemPrompt:
    def test_basic_generation(self):
        result = generate_system_prompt(TEMPLATE_BASE, VERTICAL, FRAMEWORK, CLIENT_CONFIG)
        assert isinstance(result, str)
        assert "Sofia" in result
        assert "Inmobiliaria Norte" in result
        assert "asistente de ventas" in result

    def test_includes_identity_section(self):
        result = generate_system_prompt(TEMPLATE_BASE, VERTICAL, FRAMEWORK, CLIENT_CONFIG)
        assert "## IDENTIDAD" in result
        assert "Calificar leads" in result

    def test_includes_greeting(self):
        result = generate_system_prompt(TEMPLATE_BASE, VERTICAL, FRAMEWORK, CLIENT_CONFIG)
        assert "## SALUDO" in result
        assert "Hola! Soy Sofia" in result

    def test_includes_qualification_section(self):
        result = generate_system_prompt(TEMPLATE_BASE, VERTICAL, FRAMEWORK, CLIENT_CONFIG)
        assert "FLUJO DE CONVERSACION" in result
        assert "BANT" in result
        assert "presupuesto" in result

    def test_includes_scoring(self):
        result = generate_system_prompt(TEMPLATE_BASE, VERTICAL, FRAMEWORK, CLIENT_CONFIG)
        assert "SCORING Y ACCIONES" in result
        assert "Lead Caliente" in result
        assert "+525551234567" in result

    def test_includes_objections(self):
        result = generate_system_prompt(TEMPLATE_BASE, VERTICAL, FRAMEWORK, CLIENT_CONFIG)
        assert "MANEJO DE OBJECIONES" in result
        assert "Es muy caro" in result

    def test_includes_custom_fields(self):
        result = generate_system_prompt(TEMPLATE_BASE, VERTICAL, FRAMEWORK, CLIENT_CONFIG)
        assert "DATOS A CAPTURAR" in result
        assert "tipo_propiedad" in result

    def test_includes_rules(self):
        result = generate_system_prompt(TEMPLATE_BASE, VERTICAL, FRAMEWORK, CLIENT_CONFIG)
        assert "REGLAS ABSOLUTAS" in result
        assert "Ofrece visita virtual" in result
        assert "Responde siempre en espanol" in result

    def test_includes_farewell(self):
        result = generate_system_prompt(TEMPLATE_BASE, VERTICAL, FRAMEWORK, CLIENT_CONFIG)
        assert "DESPEDIDA" in result
        assert "Gracias por tu interes" in result

    def test_outbound_greeting(self):
        tpl = {**TEMPLATE_BASE, "direction": "outbound", "outbound_opener": "Hola, llamo de...",
               "outbound_permission": "Tienes un momento?"}
        result = generate_system_prompt(tpl, VERTICAL, FRAMEWORK, CLIENT_CONFIG)
        assert "OUTBOUND" in result or "outbound" in result.lower() or "SALIENTES" in result

    def test_default_values(self):
        result = generate_system_prompt(TEMPLATE_BASE, {}, {}, {})
        assert "la empresa" in result
        assert "el asistente" in result

    def test_no_scoring_tiers(self):
        tpl = {**TEMPLATE_BASE, "scoring_tiers": None}
        result = generate_system_prompt(tpl, {}, {}, {})
        assert "SCORING" not in result

    def test_no_qualification_steps(self):
        tpl = {**TEMPLATE_BASE, "qualification_steps": None}
        result = generate_system_prompt(tpl, {}, {}, {})
        assert "FLUJO DE CONVERSACION" not in result

    def test_rules_as_string(self):
        import json
        tpl = {**TEMPLATE_BASE, "rules": json.dumps(["Regla JSON"])}
        result = generate_system_prompt(tpl, {}, {}, {})
        assert "Regla JSON" in result


class TestGenerateBuilderFlow:
    def test_basic_flow(self):
        result = generate_builder_flow(TEMPLATE_BASE, VERTICAL, FRAMEWORK, CLIENT_CONFIG)
        assert "nodes" in result
        assert "edges" in result
        assert "metadata" in result

    def test_has_start_and_end_nodes(self):
        result = generate_builder_flow(TEMPLATE_BASE, VERTICAL, FRAMEWORK, CLIENT_CONFIG)
        types = [n["type"] for n in result["nodes"]]
        assert "start" in types
        assert "end" in types

    def test_has_greeting_message(self):
        result = generate_builder_flow(TEMPLATE_BASE, VERTICAL, FRAMEWORK, CLIENT_CONFIG)
        message_nodes = [n for n in result["nodes"] if n["type"] == "message"]
        assert len(message_nodes) >= 1
        # First message should be greeting
        greeting_node = message_nodes[0]
        assert "Sofia" in greeting_node["data"]["message"]

    def test_has_collect_input_nodes(self):
        result = generate_builder_flow(TEMPLATE_BASE, VERTICAL, FRAMEWORK, CLIENT_CONFIG)
        collect_nodes = [n for n in result["nodes"] if n["type"] == "collectInput"]
        assert len(collect_nodes) == 2  # presupuesto + autoridad

    def test_has_condition_node_for_scoring(self):
        result = generate_builder_flow(TEMPLATE_BASE, VERTICAL, FRAMEWORK, CLIENT_CONFIG)
        condition_nodes = [n for n in result["nodes"] if n["type"] == "condition"]
        assert len(condition_nodes) == 1

    def test_has_transfer_node_for_hot(self):
        result = generate_builder_flow(TEMPLATE_BASE, VERTICAL, FRAMEWORK, CLIENT_CONFIG)
        transfer_nodes = [n for n in result["nodes"] if n["type"] == "transfer"]
        assert len(transfer_nodes) == 1
        assert transfer_nodes[0]["data"]["phoneNumber"] == "+525551234567"

    def test_has_action_save_node(self):
        result = generate_builder_flow(TEMPLATE_BASE, VERTICAL, FRAMEWORK, CLIENT_CONFIG)
        action_nodes = [n for n in result["nodes"] if n["type"] == "action"]
        assert len(action_nodes) == 1
        assert action_nodes[0]["data"]["action"] == "save_lead_data"
        assert "tipo_propiedad" in action_nodes[0]["data"]["fields"]

    def test_edges_connect_nodes(self):
        result = generate_builder_flow(TEMPLATE_BASE, VERTICAL, FRAMEWORK, CLIENT_CONFIG)
        node_ids = {n["id"] for n in result["nodes"]}
        for edge in result["edges"]:
            assert edge["source"] in node_ids
            assert edge["target"] in node_ids

    def test_metadata(self):
        result = generate_builder_flow(TEMPLATE_BASE, VERTICAL, FRAMEWORK, CLIENT_CONFIG)
        assert result["metadata"]["framework"] == "bant"
        assert result["metadata"]["vertical"] == "real-estate"

    def test_outbound_direction(self):
        tpl = {**TEMPLATE_BASE, "direction": "outbound", "outbound_opener": "Llamo de...",
               "outbound_permission": "Un momento?"}
        result = generate_builder_flow(tpl, VERTICAL, FRAMEWORK, CLIENT_CONFIG)
        message_nodes = [n for n in result["nodes"] if n["type"] == "message"]
        assert any("OUTBOUND" in n["data"]["message"] for n in message_nodes)

    def test_no_scoring_tiers(self):
        tpl = {**TEMPLATE_BASE, "scoring_tiers": []}
        result = generate_builder_flow(tpl, {}, {}, CLIENT_CONFIG)
        condition_nodes = [n for n in result["nodes"] if n["type"] == "condition"]
        assert len(condition_nodes) == 0

    def test_no_qualification_steps(self):
        tpl = {**TEMPLATE_BASE, "qualification_steps": []}
        result = generate_builder_flow(tpl, {}, {}, CLIENT_CONFIG)
        collect_nodes = [n for n in result["nodes"] if n["type"] == "collectInput"]
        assert len(collect_nodes) == 0


class TestGenerateAgentFromTemplate:
    @pytest.mark.asyncio
    async def test_system_prompt_mode(self):
        sb = MagicMock()
        template_data = {
            **TEMPLATE_BASE,
            "industry_verticals": VERTICAL,
            "qualification_frameworks": FRAMEWORK,
        }
        (sb.table.return_value
         .select.return_value
         .eq.return_value
         .limit.return_value
         .execute.return_value.data) = [template_data]

        # Mock update for usage_count
        sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        result = await generate_agent_from_template(
            supabase=sb,
            template_id="tpl-1",
            client_config=CLIENT_CONFIG,
            mode="system_prompt",
        )
        assert result["mode"] == "system_prompt"
        assert isinstance(result["result"], str)
        assert "Sofia" in result["result"]
        assert result["template_info"]["name"] == "Test Template"

    @pytest.mark.asyncio
    async def test_builder_flow_mode(self):
        sb = MagicMock()
        template_data = {
            **TEMPLATE_BASE,
            "industry_verticals": VERTICAL,
            "qualification_frameworks": FRAMEWORK,
        }
        (sb.table.return_value
         .select.return_value
         .eq.return_value
         .limit.return_value
         .execute.return_value.data) = [template_data]

        sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        result = await generate_agent_from_template(
            supabase=sb,
            template_id="tpl-1",
            client_config=CLIENT_CONFIG,
            mode="builder_flow",
        )
        assert result["mode"] == "builder_flow"
        assert "nodes" in result["result"]
        assert "edges" in result["result"]

    @pytest.mark.asyncio
    async def test_template_not_found(self):
        sb = MagicMock()
        (sb.table.return_value
         .select.return_value
         .eq.return_value
         .limit.return_value
         .execute.return_value.data) = []

        with pytest.raises(ValueError, match="no encontrado"):
            await generate_agent_from_template(sb, "bad-id", {})

    @pytest.mark.asyncio
    async def test_invalid_mode(self):
        sb = MagicMock()
        template_data = {
            **TEMPLATE_BASE,
            "industry_verticals": {},
            "qualification_frameworks": {},
        }
        (sb.table.return_value
         .select.return_value
         .eq.return_value
         .limit.return_value
         .execute.return_value.data) = [template_data]

        with pytest.raises(ValueError, match="Modo invalido"):
            await generate_agent_from_template(sb, "tpl-1", {}, mode="invalid")
