# PROMPT PARA CLAUDE CODE - Template Store y Generador de Agentes (PARTE 1 de 2)
## Frameworks de Calificacion + Verticales + Generador Dual (System Prompt / Builder Flow)

Lee CLAUDE.md y ARCHITECTURE.md primero. Este prompt (2 partes) implementa un sistema de plantillas que genera agentes pre-configurados combinando: framework de ventas + vertical de industria + direccion (inbound/outbound) + modo (system prompt o builder flow).

PARTE 1: Base de datos, estructura de templates, motor generador.
PARTE 2: API endpoints, wizard del dashboard, templates iniciales de cada vertical.

---

## CONCEPTO

Cuando un cliente crea un agente, en vez de empezar de cero, selecciona:
1. Objetivo (calificar leads, agendar citas, soporte, cobranza, etc.)
2. Industria (inmobiliaria, educacion, salud, servicios, etc.)
3. Direccion (inbound / outbound / ambos)
4. Modo (system prompt conversacional O builder flow con nodos)

El sistema combina todo y genera automaticamente un agente listo para personalizar.

Los 2 modos salen de la MISMA receta base. La receta tiene: preguntas, scoring, objeciones, reglas, tono. Lo que cambia es el formato de salida.

---

## PARTE 1: FRAMEWORKS DE CALIFICACION

El sistema soporta multiples frameworks de ventas. Cada uno define QUE preguntar y en que ORDEN.

### BANT (clasico, ideal para PyMEs)
- Budget: tiene presupuesto definido?
- Authority: es el decisor?
- Need: que necesita exactamente?
- Timeline: para cuando lo necesita?
Mejor para: ventas directas, servicios, educacion.

### CHAMP (moderno, menos agresivo)
- Challenges: cual es su problema/necesidad?
- Authority: quien decide?
- Money: rango de inversion?
- Prioritization: que tan urgente es?
Mejor para: inmobiliaria, salud, servicios premium. Empieza por dolor, no por dinero. Ideal para Latam.

### SPIN (consultivo)
- Situation: cual es su situacion actual?
- Problem: que problemas tiene?
- Implication: que pasa si no lo resuelve?
- Need-Payoff: como se beneficiaria de resolverlo?
Mejor para: ventas consultivas, B2B, servicios de alto valor.

### SIMPLE (solo captura)
- Solo recoge datos basicos: nombre, contacto, interes
- Sin scoring complejo
- Para agentes de soporte o recepcion que no califican

---

## PARTE 2: BASE DE DATOS

### 2.1 Frameworks disponibles

```sql
CREATE TABLE IF NOT EXISTS qualification_frameworks (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,          -- 'bant', 'champ', 'spin', 'simple'
    name TEXT NOT NULL,                 -- 'BANT', 'CHAMP', etc.
    description TEXT,
    best_for TEXT,                      -- 'Ventas directas, servicios'
    steps JSONB NOT NULL,              -- Array de pasos del framework
    is_active BOOLEAN DEFAULT true,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

El campo `steps` contiene la estructura generica del framework:
```json
[
    {
        "id": "challenges",
        "letter": "C",
        "name": "Challenges",
        "purpose": "Descubrir la necesidad o problema real",
        "generic_questions": [
            "Que es lo que estas buscando exactamente?",
            "Que problema intentas resolver?"
        ],
        "score_rules": {
            "specific_clear": 15,
            "vague_exploring": 5
        }
    },
    {
        "id": "authority",
        "letter": "A",
        "name": "Authority",
        "purpose": "Identificar si es el decisor",
        "generic_questions": [
            "Tu tomarias la decision o lo ves con alguien mas?"
        ],
        "score_rules": {
            "is_decider": 20,
            "not_decider": 5
        }
    }
]
```

### 2.2 Verticales de industria

```sql
CREATE TABLE IF NOT EXISTS industry_verticals (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,          -- 'inmobiliaria', 'educacion', 'salud'
    name TEXT NOT NULL,                 -- 'Inmobiliaria', 'Educacion'
    description TEXT,
    icon TEXT,                          -- Emoji o nombre de icono
    default_framework_slug TEXT REFERENCES qualification_frameworks(slug),
    custom_fields JSONB DEFAULT '[]',  -- Campos especificos de la vertical
    objections JSONB DEFAULT '[]',     -- Objeciones comunes y respuestas
    terminology JSONB DEFAULT '{}',    -- Terminos especificos
    is_active BOOLEAN DEFAULT true,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

El campo `custom_fields` define que datos capturar por industria:
```json
[
    {"key": "tipo_propiedad", "label": "Tipo de propiedad", "type": "text"},
    {"key": "recamaras", "label": "Recamaras", "type": "number"},
    {"key": "zona", "label": "Zona preferida", "type": "text"},
    {"key": "presupuesto_min", "label": "Presupuesto minimo", "type": "number"},
    {"key": "presupuesto_max", "label": "Presupuesto maximo", "type": "number"}
]
```

El campo `objections` tiene objeciones comunes y sus respuestas:
```json
[
    {
        "trigger": "solo estoy viendo",
        "keywords": ["solo viendo", "nomas viendo", "explorando", "no se si"],
        "response": "Perfecto, sin compromiso. Te gustaria que te avise cuando haya algo en tu zona ideal?"
    },
    {
        "trigger": "es muy caro",
        "keywords": ["caro", "mucho dinero", "no me alcanza", "fuera de presupuesto"],
        "response": "Entiendo. Tenemos opciones en diferentes rangos. Cual seria un monto comodo para ti?"
    }
]
```

### 2.3 Plantillas de agentes

```sql
CREATE TABLE IF NOT EXISTS agent_templates (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    vertical_slug TEXT REFERENCES industry_verticals(slug),
    framework_slug TEXT REFERENCES qualification_frameworks(slug),
    slug TEXT NOT NULL,                  -- 'calificar_leads', 'agendar_citas'
    name TEXT NOT NULL,                  -- 'Calificador de Leads'
    description TEXT,
    objective TEXT NOT NULL,             -- 'Calificar prospectos y clasificarlos por potencial'
    direction TEXT NOT NULL,             -- 'inbound', 'outbound', 'both'
    agent_role TEXT NOT NULL,            -- 'Asesor inmobiliario digital'
    greeting TEXT,                       -- Saludo inicial
    farewell TEXT,                       -- Despedida
    -- Pasos de calificacion adaptados a la vertical
    qualification_steps JSONB NOT NULL,
    -- Scoring
    scoring_tiers JSONB NOT NULL DEFAULT '[
        {"tier": "hot", "min_score": 70, "action": "transfer_human", "label": "Lead caliente"},
        {"tier": "warm", "min_score": 40, "action": "schedule_followup", "label": "Lead tibio"},
        {"tier": "cold", "min_score": 0, "action": "nurturing", "label": "Lead frio"}
    ]',
    -- Reglas y tono
    rules JSONB DEFAULT '[]',           -- Reglas absolutas del agente
    tone_description TEXT,              -- 'Profesional pero cercano, nunca presiona'
    -- Outbound especifico
    outbound_opener TEXT,               -- Justificacion de la llamada (primeros 10 seg)
    outbound_permission TEXT,           -- Pedir permiso para continuar
    -- Metadata
    tags TEXT[] DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    sort_order INTEGER DEFAULT 0,
    usage_count INTEGER DEFAULT 0,      -- Cuantas veces se ha usado
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(vertical_slug, slug)
);

CREATE INDEX idx_templates_vertical ON agent_templates(vertical_slug, is_active);
CREATE INDEX idx_templates_direction ON agent_templates(direction);
```

El campo `qualification_steps` es el corazon. Es el framework adaptado a la vertical:
```json
[
    {
        "id": "challenges",
        "framework_step": "C",
        "purpose": "Descubrir que tipo de propiedad busca",
        "questions": [
            "Que tipo de propiedad te interesa? Casa, departamento, terreno?",
            "Cuantas recamaras necesitas?",
            "Que zona de la ciudad prefieres?"
        ],
        "extract_fields": ["tipo_propiedad", "recamaras", "zona"],
        "score_rules": {
            "specific_need": {"points": 15, "condition": "Da detalles claros y especificos"},
            "vague": {"points": 5, "condition": "Respuestas vagas o no sabe"}
        },
        "tips": "No hagas las 3 preguntas seguidas. Integralas en la conversacion."
    },
    {
        "id": "authority",
        "framework_step": "A",
        "purpose": "Saber si decide solo o con pareja/familia",
        "questions": [
            "La decision la tomarias tu o la ves con tu pareja o familia?"
        ],
        "extract_fields": ["es_decisor"],
        "score_rules": {
            "is_decider": {"points": 20, "condition": "Decide solo o es el principal"},
            "not_decider": {"points": 5, "condition": "Necesita consultar"}
        },
        "tips": "Si no es decisor, sugiere que la otra persona asista a la visita."
    },
    {
        "id": "money",
        "framework_step": "M",
        "purpose": "Obtener rango de presupuesto",
        "questions": [
            "Tienes un rango de inversion en mente?",
            "Te pregunto para mostrarte solo opciones que apliquen y no hacerte perder tiempo."
        ],
        "extract_fields": ["presupuesto_min", "presupuesto_max"],
        "score_rules": {
            "defined_budget": {"points": 25, "condition": "Da rango claro"},
            "no_budget": {"points": -5, "condition": "No quiere decir o no sabe"}
        },
        "tips": "Justifica la pregunta: es para no mostrar opciones fuera de rango."
    },
    {
        "id": "priority",
        "framework_step": "P",
        "purpose": "Determinar urgencia de la compra",
        "questions": [
            "Para cuando estas buscando mudarte?"
        ],
        "extract_fields": ["timeline"],
        "score_rules": {
            "urgent": {"points": 30, "condition": "Este mes o ya"},
            "soon": {"points": 15, "condition": "1-3 meses"},
            "exploring": {"points": 5, "condition": "No tiene fecha, solo explorando"}
        },
        "tips": "La urgencia es el predictor mas fuerte de conversion."
    }
]
```

### 2.4 Objetivos predefinidos

```sql
CREATE TABLE IF NOT EXISTS agent_objectives (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,          -- 'qualify_leads', 'schedule_appointments'
    name TEXT NOT NULL,                 -- 'Calificar leads'
    description TEXT,
    icon TEXT,
    requires_framework BOOLEAN DEFAULT true,  -- false para soporte/FAQ
    compatible_directions TEXT[] DEFAULT '{inbound,outbound}',
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO agent_objectives (slug, name, description, icon, requires_framework, compatible_directions, sort_order) VALUES
    ('qualify_leads', 'Calificar leads', 'Evaluar prospectos y clasificarlos por potencial de compra', '🎯', true, '{inbound,outbound}', 1),
    ('schedule_appointments', 'Agendar citas', 'Gestionar agendamiento de citas, visitas o reuniones', '📅', false, '{inbound,outbound}', 2),
    ('customer_support', 'Atender soporte', 'Responder preguntas frecuentes y resolver dudas', '💬', false, '{inbound}', 3),
    ('follow_up', 'Seguimiento a prospectos', 'Recontactar prospectos que no cerraron', '🔄', true, '{outbound}', 4),
    ('collections', 'Cobranza amable', 'Recordar pagos pendientes de forma profesional', '💰', false, '{outbound}', 5),
    ('reminders', 'Recordatorios', 'Avisar de citas, eventos o fechas importantes', '⏰', false, '{outbound}', 6),
    ('reception', 'Recepcion general', 'Atender llamadas entrantes y dirigir al area correcta', '📞', false, '{inbound}', 7)
ON CONFLICT (slug) DO NOTHING;
```

---

## PARTE 3: MOTOR GENERADOR

El generador toma una receta (template + datos del cliente) y produce la salida en el modo elegido.

### 3.1 Generador de System Prompt (api/generator/system_prompt.py)

```python
"""
api/generator/system_prompt.py - Genera system prompt completo desde template.

Input: template + datos del cliente (nombre empresa, tono, etc.)
Output: String con el system prompt completo listo para usar
"""
import logging
from typing import Optional

logger = logging.getLogger("generator")


def generate_system_prompt(
    template: dict,
    vertical: dict,
    framework: dict,
    client_config: dict,
) -> str:
    """
    Genera un system prompt completo combinando template + vertical + framework.

    client_config espera:
    {
        "business_name": "Inmobiliaria Patria",
        "agent_name": "Sofia",
        "tone": "Profesional pero cercana",  # opcional, usa default del template
        "custom_greeting": None,  # opcional
        "custom_rules": [],  # reglas adicionales del cliente
        "tool_calls_enabled": true,
        "transfer_phone": "+529991234567",  # para transferir leads hot
    }
    """
    business = client_config.get("business_name", "la empresa")
    agent_name = client_config.get("agent_name", "el asistente")
    tone = client_config.get("tone", template.get("tone_description", "Profesional y amable"))
    greeting = client_config.get("custom_greeting", template.get("greeting", ""))
    transfer_phone = client_config.get("transfer_phone", "")
    custom_rules = client_config.get("custom_rules", [])

    # Construir secciones
    sections = []

    # --- IDENTIDAD ---
    sections.append(f"""## IDENTIDAD
Eres {agent_name}, {template['agent_role']} de {business}.
Tu objetivo principal: {template['objective']}.
Tu tono: {tone}.""")

    # --- SALUDO ---
    if template.get("direction") in ("outbound", "both") and template.get("outbound_opener"):
        sections.append(f"""## SALUDO
Para llamadas ENTRANTES (inbound):
{greeting}

Para llamadas SALIENTES (outbound):
{template['outbound_opener']}
Siempre pide permiso para continuar: {template.get('outbound_permission', 'Tienes un momento para platicar?')}""")
    else:
        sections.append(f"""## SALUDO
{greeting}""")

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
        import json
        rules = json.loads(rules)
    all_rules = rules + custom_rules + [
        "Si el prospecto pide hablar con un humano, transfiere inmediatamente",
        "No hagas mas de 2 preguntas seguidas sin aportar valor",
        "Confirma datos importantes antes de guardarlos",
    ]
    rules_text = "## REGLAS ABSOLUTAS\n" + "\n".join(f"- {r}" for r in all_rules)
    sections.append(rules_text)

    # --- DESPEDIDA ---
    if template.get("farewell"):
        sections.append(f"""## DESPEDIDA
{template['farewell']}""")

    return "\n\n".join(sections)


def _build_qualification_section(steps: list, framework: dict) -> str:
    """Construye la seccion de flujo de calificacion."""
    fw_name = framework.get("name", "")
    lines = [f"## FLUJO DE CONVERSACION ({fw_name})"]
    lines.append("Sigue este orden natural, NO como interrogatorio.")
    lines.append("Integra las preguntas en la conversacion de forma fluida.\n")

    for i, step in enumerate(steps, 1):
        letter = step.get("framework_step", "")
        purpose = step.get("purpose", "")
        lines.append(f"### Paso {i}: {step['id'].upper()} ({letter}) - {purpose}")

        # Preguntas
        questions = step.get("questions", [])
        for q in questions:
            lines.append(f'  Pregunta: "{q}"')

        # Que extraer
        fields = step.get("extract_fields", [])
        if fields:
            lines.append(f"  Capturar: {', '.join(fields)}")

        # Scoring
        rules = step.get("score_rules", {})
        for key, rule in rules.items():
            if isinstance(rule, dict):
                lines.append(f"  Scoring: +{rule['points']} si {rule['condition']}")

        # Tips
        if step.get("tips"):
            lines.append(f"  Tip: {step['tips']}")
        lines.append("")

    return "\n".join(lines)


def _build_scoring_section(tiers: list, transfer_phone: str = "") -> str:
    """Construye la seccion de scoring y acciones."""
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

        lines.append(
            f"- {tier['label']} (score >= {tier['min_score']}): {action_detail}"
        )
    return "\n".join(lines)


def _build_objections_section(objections: list) -> str:
    """Construye la seccion de manejo de objeciones."""
    lines = ["## MANEJO DE OBJECIONES"]
    for obj in objections:
        lines.append(f'- "{obj["trigger"]}" -> "{obj["response"]}"')
    return "\n".join(lines)


def _build_fields_section(fields: list) -> str:
    """Construye la seccion de datos a capturar via tool calling."""
    lines = ["## DATOS A CAPTURAR"]
    lines.append("Al finalizar la conversacion, guarda estos datos del prospecto:\n")
    field_names = [f["key"] for f in fields]
    field_names.extend(["nombre", "telefono", "email", "lead_score", "lead_tier"])
    lines.append("Campos: " + ", ".join(field_names))
    lines.append("\nUsa la herramienta save_lead_data para guardar toda la informacion recopilada.")
    return "\n".join(lines)
```

### 3.2 Generador de Builder Flow (api/generator/builder_flow.py)

```python
"""
api/generator/builder_flow.py - Genera set de nodos desde template.

Input: template + datos del cliente
Output: Array de nodos conectados listos para el Builder Flow
"""
import logging
from typing import Optional
import uuid

logger = logging.getLogger("generator")


def generate_builder_flow(
    template: dict,
    vertical: dict,
    framework: dict,
    client_config: dict,
) -> dict:
    """
    Genera un flow completo de nodos.

    Retorna:
    {
        "nodes": [...],
        "edges": [...],
        "metadata": {...}
    }
    """
    business = client_config.get("business_name", "la empresa")
    agent_name = client_config.get("agent_name", "el asistente")
    tone = client_config.get("tone", template.get("tone_description", ""))
    greeting = client_config.get("custom_greeting", template.get("greeting", ""))
    transfer_phone = client_config.get("transfer_phone", "")

    nodes = []
    edges = []
    y_position = 0
    Y_SPACING = 150

    # --- NODO START ---
    start_id = _make_id()
    nodes.append({
        "id": start_id,
        "type": "start",
        "data": {
            "label": "Inicio",
        },
        "position": {"x": 250, "y": y_position},
    })
    y_position += Y_SPACING

    # --- NODO GREETING ---
    greeting_id = _make_id()
    greeting_prompt = f"Eres {agent_name}, {template['agent_role']} de {business}. Tu tono: {tone}.\n\n"

    if template.get("direction") == "outbound" and template.get("outbound_opener"):
        greeting_prompt += f"OUTBOUND: {template['outbound_opener']}\n"
        greeting_prompt += f"Pide permiso: {template.get('outbound_permission', 'Tienes un momento?')}\n"
    else:
        greeting_prompt += f"Saluda: {greeting}"

    nodes.append({
        "id": greeting_id,
        "type": "conversation",
        "data": {
            "label": "Bienvenida",
            "prompt": greeting_prompt,
            "extract_fields": [],
        },
        "position": {"x": 250, "y": y_position},
    })
    edges.append({"source": start_id, "target": greeting_id})
    y_position += Y_SPACING

    # --- NODOS DE CALIFICACION (uno por step del framework) ---
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

        # Construir score_config para el nodo
        score_config = {}
        for key, rule in step.get("score_rules", {}).items():
            if isinstance(rule, dict):
                score_config[key] = {
                    "points": rule["points"],
                    "condition": rule["condition"],
                }

        nodes.append({
            "id": step_id,
            "type": "conversation",
            "data": {
                "label": f"{step.get('framework_step', '')} - {step['id'].replace('_', ' ').title()}",
                "prompt": prompt,
                "extract_fields": extract,
                "score_rules": score_config,
            },
            "position": {"x": 250, "y": y_position},
        })
        edges.append({"source": prev_node_id, "target": step_id})
        prev_node_id = step_id
        y_position += Y_SPACING

    # --- NODO DE CLASIFICACION (scoring) ---
    classify_id = _make_id()
    tiers = template.get("scoring_tiers", [])

    nodes.append({
        "id": classify_id,
        "type": "condition",
        "data": {
            "label": "Clasificar Lead",
            "condition_type": "lead_score",
            "description": "Clasificar segun score acumulado",
        },
        "position": {"x": 250, "y": y_position},
    })
    edges.append({"source": prev_node_id, "target": classify_id})
    y_position += Y_SPACING

    # --- NODOS DE RESULTADO (uno por tier) ---
    x_offset = 0
    for tier in tiers:
        tier_id = _make_id()
        action = tier.get("action", "")
        label = tier.get("label", tier["tier"])

        # Construir prompt del nodo resultado
        if action == "transfer_human":
            prompt = f"El prospecto tiene alto potencial. "
            if transfer_phone:
                prompt += f"Transfiere a {transfer_phone}. "
            prompt += "Di algo como: 'Tengo opciones perfectas para ti. Te comunico con un asesor que te puede ayudar ahora mismo.'"
        elif action == "schedule_followup":
            prompt = "El prospecto tiene interes moderado. Ofrece agendar una cita o visita. Di algo como: 'Te gustaria agendar una visita este fin de semana para conocer opciones?'"
        elif action == "nurturing":
            prompt = "El prospecto esta explorando. No presiones. Ofrece enviar informacion. Di algo como: 'Te envio un catalogo personalizado. A que correo te lo mando?'"
        else:
            prompt = f"Accion: {action}"

        nodes.append({
            "id": tier_id,
            "type": "conversation",
            "data": {
                "label": f"Resultado: {label}",
                "prompt": prompt,
                "action": action,
                "min_score": tier.get("min_score", 0),
            },
            "position": {"x": x_offset, "y": y_position},
        })
        edges.append({
            "source": classify_id,
            "target": tier_id,
            "label": f"score >= {tier.get('min_score', 0)}",
        })
        x_offset += 300

    y_position += Y_SPACING

    # --- NODO OBJECIONES (global, se puede invocar desde cualquier nodo) ---
    if vertical.get("objections"):
        objection_id = _make_id()
        obj_prompt = "MANEJO DE OBJECIONES:\n"
        for obj in vertical["objections"]:
            obj_prompt += f'Si dice "{obj["trigger"]}": responde "{obj["response"]}"\n'
        obj_prompt += "\nDespues de manejar la objecion, regresa al punto donde estabas."

        nodes.append({
            "id": objection_id,
            "type": "conversation",
            "data": {
                "label": "Manejo de Objeciones",
                "prompt": obj_prompt,
                "is_global": True,
            },
            "position": {"x": 600, "y": 300},
        })

    # --- NODO SAVE DATA ---
    save_id = _make_id()
    all_fields = [f["key"] for f in vertical.get("custom_fields", [])]
    all_fields.extend(["nombre", "telefono", "email", "lead_score", "lead_tier"])

    nodes.append({
        "id": save_id,
        "type": "action",
        "data": {
            "label": "Guardar Datos",
            "action_type": "save_lead_data",
            "fields": all_fields,
        },
        "position": {"x": 250, "y": y_position},
    })

    return {
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "framework": framework.get("slug"),
            "vertical": vertical.get("slug"),
            "template": template.get("slug"),
            "direction": template.get("direction"),
            "generated_at": "auto",
        },
    }


def _make_id() -> str:
    """Genera ID unico para nodo."""
    return f"node_{uuid.uuid4().hex[:8]}"
```

### 3.3 Generador principal (api/generator/main.py)

```python
"""
api/generator/main.py - Orquesta la generacion combinando template + config.

Flujo:
1. Recibe: template_id + client_config + mode (system_prompt | builder_flow)
2. Carga template, vertical, framework de DB
3. Llama al generador correspondiente
4. Retorna resultado listo para usar
"""
import logging
from .system_prompt import generate_system_prompt
from .builder_flow import generate_builder_flow

logger = logging.getLogger("generator")


async def generate_agent_from_template(
    supabase,
    template_id: str,
    client_config: dict,
    mode: str = "system_prompt",
) -> dict:
    """
    Genera un agente completo desde un template.

    Args:
        template_id: UUID del agent_template
        client_config: {business_name, agent_name, tone, transfer_phone, ...}
        mode: "system_prompt" o "builder_flow"

    Returns:
        {
            "mode": "system_prompt" | "builder_flow",
            "result": string | {nodes, edges, metadata},
            "template_info": {...},
        }
    """
    # Cargar template
    tpl = supabase.table("agent_templates") \
        .select("*, industry_verticals(*), qualification_frameworks(*)") \
        .eq("id", template_id) \
        .single() \
        .execute()

    if not tpl.data:
        raise ValueError(f"Template {template_id} not found")

    template = tpl.data
    vertical = template.get("industry_verticals", {})
    framework = template.get("qualification_frameworks", {})

    # Generar segun modo
    if mode == "system_prompt":
        result = generate_system_prompt(template, vertical, framework, client_config)
    elif mode == "builder_flow":
        result = generate_builder_flow(template, vertical, framework, client_config)
    else:
        raise ValueError(f"Invalid mode: {mode}. Use 'system_prompt' or 'builder_flow'")

    # Incrementar contador de uso
    supabase.table("agent_templates") \
        .update({"usage_count": template.get("usage_count", 0) + 1}) \
        .eq("id", template_id) \
        .execute()

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
```

---

## PARTE 4: LEAD SCORING UNIVERSAL

El scoring se integra con el CRM existente. Cada conversacion acumula puntos.

### 4.1 Tabla de leads scored

```sql
CREATE TABLE IF NOT EXISTS lead_scores (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    contact_id UUID,                    -- Referencia al contacto del CRM
    agent_id UUID REFERENCES agents(id),
    -- Score
    total_score INTEGER DEFAULT 0,
    tier TEXT DEFAULT 'cold',           -- 'hot', 'warm', 'cold'
    -- Datos capturados
    captured_data JSONB DEFAULT '{}',
    qualification_steps_completed JSONB DEFAULT '[]',
    -- Tracking
    source_channel TEXT,                -- 'call', 'whatsapp', 'web'
    source_template_id UUID REFERENCES agent_templates(id),
    -- Estado
    status TEXT DEFAULT 'new',          -- 'new','contacted','qualified','converted','lost'
    assigned_to TEXT,                   -- Email del vendedor asignado
    notes TEXT,
    -- Timestamps
    first_contact_at TIMESTAMPTZ DEFAULT NOW(),
    last_contact_at TIMESTAMPTZ DEFAULT NOW(),
    converted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_lead_scores_client ON lead_scores(client_id, tier, status);
CREATE INDEX idx_lead_scores_agent ON lead_scores(agent_id, created_at DESC);
```

### 4.2 Funcion para actualizar score

```sql
CREATE OR REPLACE FUNCTION update_lead_score(
    p_client_id UUID,
    p_contact_id UUID,
    p_agent_id UUID,
    p_score INTEGER,
    p_tier TEXT,
    p_captured_data JSONB,
    p_steps_completed JSONB,
    p_channel TEXT DEFAULT 'call',
    p_template_id UUID DEFAULT NULL
) RETURNS UUID LANGUAGE plpgsql AS $$
DECLARE v_id UUID;
BEGIN
    INSERT INTO lead_scores (
        client_id, contact_id, agent_id,
        total_score, tier, captured_data,
        qualification_steps_completed,
        source_channel, source_template_id
    ) VALUES (
        p_client_id, p_contact_id, p_agent_id,
        p_score, p_tier, p_captured_data,
        p_steps_completed,
        p_channel, p_template_id
    )
    ON CONFLICT (id) DO UPDATE SET
        total_score = p_score,
        tier = p_tier,
        captured_data = lead_scores.captured_data || p_captured_data,
        qualification_steps_completed = p_steps_completed,
        last_contact_at = NOW(),
        updated_at = NOW()
    RETURNING id INTO v_id;
    RETURN v_id;
END; $$;
```

---

Continua en PARTE 2 (prompt-template-store-part2.md): API endpoints, wizard del dashboard, templates iniciales completos de cada vertical.
