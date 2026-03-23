"""Templates predefinidos de hooks para activar con un click.

Cada template define un hook completo listo para insertar,
organizado por categoría y caso de uso.
"""

from __future__ import annotations

HOOK_TEMPLATES: list[dict] = [
    # ── Reglas de agendamiento ──────────────────────────
    {
        "id": "no_schedule_sundays",
        "category": "Agendamiento",
        "name": "No agendar domingos",
        "description": "Bloquea intentos de agendar citas los domingos",
        "hook_event": "PreToolCall",
        "hook_type": "rule",
        "matcher": "schedule_appointment",
        "config": {
            "conditions": [
                {"field": "input.day_of_week", "operator": "equals", "value": "domingo"}
            ],
            "action": "block",
            "message": "No agendamos citas los domingos. Ofrece otro día al cliente.",
        },
    },
    {
        "id": "require_full_name",
        "category": "Agendamiento",
        "name": "Requerir nombre completo",
        "description": "Exige nombre completo antes de permitir agendar",
        "hook_event": "PreToolCall",
        "hook_type": "validate",
        "matcher": "schedule_appointment",
        "config": {
            "validate": {
                "required_fields": ["patient_name", "date", "time"],
                "message": "Necesitas el nombre completo, fecha y hora antes de agendar. Pide los datos faltantes.",
            },
        },
    },

    # ── Reglas de contenido ─────────────────────────────
    {
        "id": "price_disclaimer",
        "category": "Contenido",
        "name": "Disclaimer en precios",
        "description": "Agrega aviso cuando se mencionan precios",
        "hook_event": "PreResponse",
        "hook_type": "rule",
        "config": {
            "conditions": [
                {"field": "response.contains_price", "operator": "equals", "value": True}
            ],
            "action": "inject_context",
            "context": "IMPORTANTE: Si mencionaste un precio, agrega al final: 'Los precios pueden variar, confirma directamente con nosotros.'",
        },
    },
    {
        "id": "no_competitor_talk",
        "category": "Contenido",
        "name": "No hablar de competencia",
        "description": "Redirige cuando el usuario pregunta por competidores",
        "hook_event": "OnUserMessage",
        "hook_type": "rule",
        "config": {
            "conditions": [
                {"field": "input.text", "operator": "contains_any", "value": ["competencia", "otro doctor", "otra clínica", "más barato", "mejor precio"]}
            ],
            "action": "inject_context",
            "context": "El usuario preguntó sobre la competencia. NO compares con otros negocios. Enfócate en tus propias ventajas y servicios.",
        },
    },
    {
        "id": "no_medical_advice",
        "category": "Contenido",
        "name": "No dar consejos médicos",
        "description": "Bloquea respuestas con diagnósticos o recetas",
        "hook_event": "PreResponse",
        "hook_type": "prompt",
        "config": {
            "prompt": "¿Esta respuesta contiene un diagnóstico médico, receta, o consejo de tratamiento específico? Solo evalúa si da consejo médico directo, no si menciona servicios del negocio.",
            "on_fail": "block",
            "message": "No puedo darte un diagnóstico o recomendación médica por este medio. Te sugiero agendar una cita para que el especialista te evalúe personalmente.",
        },
    },

    # ── Reglas de seguridad ─────────────────────────────
    {
        "id": "legal_escalate",
        "category": "Seguridad",
        "name": "Escalar temas legales",
        "description": "Transfiere a humano cuando se mencionan temas legales",
        "hook_event": "OnUserMessage",
        "hook_type": "rule",
        "config": {
            "conditions": [
                {"field": "input.text", "operator": "contains_any", "value": ["demanda", "abogado", "demandar", "legal", "denuncia", "profeco"]}
            ],
            "action": "inject_context",
            "context": "ALERTA: El usuario mencionó temas legales. NO des opiniones legales. Si insiste, ofrece transferirlo a un representante del negocio.",
        },
    },
    {
        "id": "block_personal_data_request",
        "category": "Seguridad",
        "name": "No revelar datos de otros clientes",
        "description": "Bloquea cuando piden datos de otros pacientes/clientes",
        "hook_event": "OnUserMessage",
        "hook_type": "rule",
        "config": {
            "conditions": [
                {"field": "input.text", "operator": "contains_any", "value": ["datos de otro", "información de otro", "historial de", "expediente de"]}
            ],
            "action": "inject_context",
            "context": "El usuario pidió información de otro cliente/paciente. NUNCA reveles datos de terceros. Explica que esa información es confidencial.",
        },
    },

    # ── Horario y disponibilidad ────────────────────────
    {
        "id": "business_hours_whatsapp",
        "category": "Horario",
        "name": "Auto-respuesta fuera de horario (WhatsApp)",
        "description": "Responde automáticamente fuera de horario en WhatsApp",
        "hook_event": "OnConversationStart",
        "channel": "whatsapp",
        "hook_type": "validate",
        "config": {
            "validate": {
                "check": "business_hours",
                "timezone": "America/Mexico_City",
                "hours": {"mon-fri": "9:00-18:00", "sat": "9:00-14:00"},
                "outside_hours_action": "auto_reply",
                "outside_hours_message": "Gracias por escribir. Nuestro horario de atención es Lunes a Viernes de 9am a 6pm y Sábados de 9am a 2pm. Te responderemos en cuanto abramos.",
            },
        },
    },

    # ── Notificaciones ──────────────────────────────────
    {
        "id": "notify_owner_appointment",
        "category": "Notificaciones",
        "name": "Notificar al dueño cuando se agenda cita",
        "description": "Envía WhatsApp al dueño cada vez que se agenda una cita",
        "hook_event": "PostToolCall",
        "hook_type": "notify",
        "matcher": "schedule_appointment",
        "config": {
            "channel": "whatsapp",
            "to": "owner",
            "template": "Nueva cita agendada por el agente. Teléfono del cliente: {{caller_phone}}",
        },
    },
    {
        "id": "notify_owner_transfer",
        "category": "Notificaciones",
        "name": "Notificar al dueño cuando se transfiere",
        "description": "Avisa al dueño que una llamada fue transferida",
        "hook_event": "OnEscalation",
        "hook_type": "notify",
        "config": {
            "channel": "whatsapp",
            "to": "owner",
            "template": "Llamada transferida a humano. Cliente: {{caller_phone}}. Canal: {{channel}}",
        },
    },
    {
        "id": "notify_call_end_webhook",
        "category": "Notificaciones",
        "name": "Webhook al terminar conversación",
        "description": "Envía datos de la conversación a un webhook externo al terminar",
        "hook_event": "PostConversationEnd",
        "hook_type": "notify",
        "config": {
            "channel": "webhook",
            "url": "",
            "template": "Conversación finalizada",
            "payload": ["caller_phone", "contact_name", "agent_id", "channel"],
        },
    },

    # ── Canal específico ────────────────────────────────
    {
        "id": "voice_short_responses",
        "category": "Canal",
        "name": "Respuestas cortas en voz",
        "description": "Limita las respuestas a máximo 2 oraciones en llamadas",
        "hook_event": "PreResponse",
        "channel": "voice",
        "hook_type": "transform",
        "config": {
            "transform": {"max_sentences": 2, "no_urls": True, "no_markdown": True},
        },
    },
    {
        "id": "whatsapp_emoji_friendly",
        "category": "Canal",
        "name": "Formato WhatsApp amigable",
        "description": "Permite emojis y formato en respuestas de WhatsApp",
        "hook_event": "PreResponse",
        "channel": "whatsapp",
        "hook_type": "transform",
        "config": {
            "transform": {"allow_emojis": True, "allow_formatting": True, "max_length": 500},
        },
    },
    {
        "id": "whatsapp_inactivity_close",
        "category": "Canal",
        "name": "Cerrar chat WhatsApp tras 30 min",
        "description": "Cierra la sesión de WhatsApp después de 30 minutos de inactividad",
        "hook_event": "OnInactivity",
        "channel": "whatsapp",
        "hook_type": "rule",
        "config": {
            "conditions": [
                {"field": "inactive_minutes", "operator": "gte", "value": 30}
            ],
            "action": "close_session",
            "message": "Parece que ya no necesitas ayuda. Cierro la conversación por ahora. Escríbeme cuando gustes.",
        },
    },

    # ── Inactividad en voz ──────────────────────────────
    {
        "id": "voice_silence_prompt",
        "category": "Canal",
        "name": "Preguntar en silencio (voz)",
        "description": "Si hay 5 segundos de silencio, pregunta si sigue ahí",
        "hook_event": "OnInactivity",
        "channel": "voice",
        "hook_type": "rule",
        "config": {
            "conditions": [
                {"field": "silence_seconds", "operator": "gte", "value": 5}
            ],
            "action": "speak",
            "message": "¿Sigue ahí? ¿En qué más puedo ayudarle?",
        },
    },
    {
        "id": "voice_silence_hangup",
        "category": "Canal",
        "name": "Colgar tras 15s de silencio (voz)",
        "description": "Si hay 15 segundos de silencio, despedirse y colgar",
        "hook_event": "OnInactivity",
        "channel": "voice",
        "hook_type": "rule",
        "config": {
            "conditions": [
                {"field": "silence_seconds", "operator": "gte", "value": 15}
            ],
            "action": "close_session",
            "message": "Parece que se cortó la comunicación. Puede volver a llamar cuando guste. Hasta luego.",
        },
        "priority": 200,
    },

    # ── Evaluator-Optimizer ─────────────────────────────
    {
        "id": "evaluator_no_medical_diagnosis",
        "category": "Evaluador",
        "name": "Evaluar: no diagnósticos médicos",
        "description": "Un segundo LLM verifica que la respuesta no contenga diagnósticos ni recetas médicas",
        "hook_event": "PreResponse",
        "hook_type": "evaluator",
        "config": {
            "criteria": (
                "La respuesta NO debe contener: diagnósticos médicos, recetas, "
                "recomendaciones de medicamentos, ni tratamientos específicos. "
                "Puede mencionar servicios del negocio, agendar citas, y dar info general."
            ),
            "feedback_prefix": "Tu respuesta incluía contenido médico inapropiado.",
            "max_retries": 1,
        },
    },
    {
        "id": "evaluator_price_accuracy",
        "category": "Evaluador",
        "name": "Evaluar: precios verificados",
        "description": "Verifica que los precios mencionados sean coherentes y no inventados",
        "hook_event": "PreResponse",
        "hook_type": "evaluator",
        "config": {
            "criteria": (
                "Si la respuesta menciona precios o costos, verifica que: "
                "1) No sean números absurdos (ej: $1 peso o $1,000,000). "
                "2) Incluyan un disclaimer como 'aproximado' o 'sujeto a cambio'. "
                "3) No prometan descuentos no autorizados."
            ),
            "feedback_prefix": "Corrige los precios mencionados:",
            "max_retries": 1,
        },
    },
    {
        "id": "evaluator_no_commitments",
        "category": "Evaluador",
        "name": "Evaluar: no compromisos contractuales",
        "description": "Verifica que el agente no haga promesas vinculantes en nombre del negocio",
        "hook_event": "PreResponse",
        "hook_type": "evaluator",
        "config": {
            "criteria": (
                "La respuesta NO debe hacer compromisos contractuales como: "
                "garantías específicas, promesas de devolución, descuentos no estándar, "
                "plazos de entrega fijos, ni acuerdos de precio especial. "
                "Puede decir 'normalmente', 'generalmente', o 'consulte con nosotros'."
            ),
            "feedback_prefix": "Tu respuesta incluía compromisos que no debes hacer.",
            "max_retries": 1,
        },
    },
]


def get_hook_templates() -> list[dict]:
    """Retorna todos los templates disponibles."""
    return HOOK_TEMPLATES


def get_templates_by_category() -> dict[str, list[dict]]:
    """Retorna templates agrupados por categoría."""
    grouped: dict[str, list[dict]] = {}
    for t in HOOK_TEMPLATES:
        cat = t.get("category", "Otro")
        grouped.setdefault(cat, []).append(t)
    return grouped
