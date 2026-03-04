"""Servicio core del chat tester: prompt, Gemini multi-turn, tool simulation."""

from __future__ import annotations

import logging
import os

from google import genai
from google.genai import types

from agent.agent_factory import _voice_rules, _build_tool_instructions, _build_api_instructions
from agent.config_loader import ResolvedConfig
from agent.flow_engine import FlowEngine, FlowState
from agent.tools.file_search import search_knowledge_base
from api.services.chat_store import Conversation

logger = logging.getLogger(__name__)

# Cliente Gemini singleton
_gemini: genai.Client | None = None


def _get_gemini() -> genai.Client:
    global _gemini
    if _gemini is None:
        _gemini = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    return _gemini


# ── Tool declarations ─────────────────────────────────────

CALL_API_SCHEMA = types.FunctionDeclaration(
    name="call_api",
    description=(
        "Llama a una API externa configurada para este negocio. "
        "Usa esta herramienta cuando necesites consultar o enviar datos "
        "a un sistema externo."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "integration_name": types.Schema(
                type="STRING",
                description="Nombre de la integración API a llamar.",
            ),
            "parameters": types.Schema(
                type="STRING",
                description="JSON string con los parámetros requeridos por la API.",
            ),
        },
        required=["integration_name"],
    ),
)

TOOL_SCHEMAS: dict[str, types.FunctionDeclaration] = {
    "search_knowledge": types.FunctionDeclaration(
        name="search_knowledge",
        description=(
            "Busca información en la base de conocimientos del negocio. "
            "Usa esta herramienta cuando pregunten sobre servicios, precios, "
            "horarios o cualquier información del negocio."
        ),
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "query": types.Schema(
                    type="STRING",
                    description="La pregunta o tema a buscar.",
                ),
            },
            required=["query"],
        ),
    ),
    "transfer_to_human": types.FunctionDeclaration(
        name="transfer_to_human",
        description=(
            "Transfiere la llamada a un agente humano cuando el cliente "
            "lo solicite o no puedas resolver su consulta."
        ),
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "reason": types.Schema(
                    type="STRING",
                    description="Motivo de la transferencia.",
                ),
            },
            required=["reason"],
        ),
    ),
    "schedule_appointment": types.FunctionDeclaration(
        name="schedule_appointment",
        description=(
            "Agenda una cita para el paciente o cliente. "
            "Necesitas nombre, fecha y hora."
        ),
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "patient_name": types.Schema(type="STRING", description="Nombre completo."),
                "date": types.Schema(type="STRING", description="Fecha YYYY-MM-DD."),
                "time": types.Schema(type="STRING", description="Hora HH:MM (24h)."),
                "duration_minutes": types.Schema(type="INTEGER", description="Duración en minutos."),
                "description": types.Schema(type="STRING", description="Motivo de la cita."),
            },
            required=["patient_name", "date", "time"],
        ),
    ),
    "send_whatsapp": types.FunctionDeclaration(
        name="send_whatsapp",
        description="Envía un mensaje de WhatsApp al número indicado.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "phone_number": types.Schema(type="STRING", description="Número destino."),
                "message": types.Schema(type="STRING", description="Texto del mensaje."),
            },
            required=["phone_number", "message"],
        ),
    ),
    "save_contact_info": types.FunctionDeclaration(
        name="save_contact_info",
        description="Guarda la información de contacto del cliente/paciente.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "name": types.Schema(type="STRING", description="Nombre completo."),
                "phone": types.Schema(type="STRING", description="Teléfono."),
                "email": types.Schema(type="STRING", description="Correo electrónico."),
                "notes": types.Schema(type="STRING", description="Notas."),
            },
        ),
    ),
}


def _build_tool_declarations(
    config: ResolvedConfig,
    api_integrations: list[dict] | None = None,
) -> list[types.Tool]:
    """Construye las declaraciones de tools para Gemini según las habilitadas."""
    enabled = config.client.enabled_tools or []
    declarations: list[types.FunctionDeclaration] = []

    # search_knowledge y transfer_to_human siempre disponibles
    for tool_name in ["search_knowledge", "transfer_to_human"]:
        if tool_name in TOOL_SCHEMAS:
            declarations.append(TOOL_SCHEMAS[tool_name])

    # Tools condicionales
    for tool_name in ["schedule_appointment", "send_whatsapp", "save_contact"]:
        fn_name = "save_contact_info" if tool_name == "save_contact" else tool_name
        if tool_name in enabled and fn_name in TOOL_SCHEMAS:
            declarations.append(TOOL_SCHEMAS[fn_name])

    # call_api si hay API integrations
    if api_integrations:
        declarations.append(CALL_API_SCHEMA)

    if not declarations:
        return []
    return [types.Tool(function_declarations=declarations)]


# ── Tool execution ────────────────────────────────────────

async def _execute_tool(
    tool_name: str,
    args: dict,
    config: ResolvedConfig,
    api_integrations: list[dict] | None = None,
) -> str:
    """Ejecuta un tool: search_knowledge y call_api son reales, el resto simulado."""
    if tool_name == "search_knowledge":
        store_id = config.client.file_search_store_id
        if not store_id:
            return "No hay base de conocimientos configurada."
        query = args.get("query", "")
        return await search_knowledge_base(query, store_id)

    if tool_name == "call_api":
        if not api_integrations:
            return "No hay integraciones API configuradas."

        integ_name = args.get("integration_name", "")
        integ = next(
            (i for i in api_integrations if i.get("name") == integ_name), None
        )
        if not integ:
            available = ", ".join(i.get("name", "") for i in api_integrations)
            return f"Integración '{integ_name}' no encontrada. Disponibles: {available}"

        import json
        params_str = args.get("parameters", "{}")
        try:
            params = json.loads(params_str) if isinstance(params_str, str) else params_str
        except json.JSONDecodeError:
            params = {}

        from agent.api_executor import execute_api_call

        status_code, response_text = await execute_api_call(integ, params)
        if status_code == 0:
            return f"Error al llamar a la API: {response_text}"
        if status_code >= 400:
            return f"La API respondió con error (HTTP {status_code}): {response_text}"
        return response_text

    # Simulaciones
    if tool_name == "transfer_to_human":
        reason = args.get("reason", "sin motivo")
        return f"[SIMULACIÓN] Transferencia solicitada. Motivo: {reason}"

    if tool_name == "schedule_appointment":
        name = args.get("patient_name", "?")
        date = args.get("date", "?")
        time_ = args.get("time", "?")
        return f"[SIMULACIÓN] Cita agendada para {name} el {date} a las {time_}"

    if tool_name == "send_whatsapp":
        phone = args.get("phone_number", "?")
        return f"[SIMULACIÓN] WhatsApp enviado a {phone}"

    if tool_name == "save_contact_info":
        name = args.get("name", "?")
        return f"[SIMULACIÓN] Contacto guardado: {name}"

    return f"[SIMULACIÓN] Tool {tool_name} ejecutado"


# ── Prompt building ───────────────────────────────────────

def build_chat_system_prompt(
    config: ResolvedConfig,
    contact_name: str | None = None,
    campaign_script: str | None = None,
    api_integrations: list[dict] | None = None,
) -> str:
    """Construye el system prompt completo para el chat tester."""
    # Si hay script de campaña, reemplaza el prompt base (igual que outbound real)
    base = campaign_script if campaign_script else config.agent.system_prompt
    voice_rules = _voice_rules(config)
    tool_instructions = _build_tool_instructions(config.client.enabled_tools)
    api_instructions = _build_api_instructions(api_integrations or [])

    prompt = base + voice_rules + tool_instructions + api_instructions

    # Ejemplos de conversación
    if config.agent.examples:
        prompt += f"\n\n## Ejemplos de conversación\n{config.agent.examples}"

    # Nota de modo texto (chat tester)
    prompt += (
        "\n\n## Modo de prueba (texto)\n"
        "Esta es una conversación de texto para probar tu comportamiento. "
        "Responde como lo harías en una llamada telefónica real, pero en texto. "
        "Ignora las reglas sobre duración de audio ya que esto es texto."
    )

    # Contexto outbound
    if config.agent.agent_type in ("outbound", "both") and contact_name:
        prompt += (
            f"\n\n## Contexto de llamada saliente\n"
            f"Estás haciendo una llamada saliente al contacto: {contact_name}. "
            f"Inicia la conversación presentándote y explicando el motivo de la llamada."
        )

    return prompt


# ── Flow mode helpers ────────────────────────────────────

def init_flow_state(conversation: Conversation) -> None:
    """Inicializa el FlowEngine y FlowState en la conversación si es flow mode."""
    config = conversation.config
    if config.agent.conversation_mode != "flow" or not config.agent.conversation_flow:
        return

    if hasattr(conversation, "_flow_engine"):
        return  # Ya inicializado

    engine = FlowEngine(config.agent.conversation_flow)
    state = engine.start()
    conversation._flow_engine = engine  # type: ignore[attr-defined]
    conversation._flow_state = state  # type: ignore[attr-defined]

    # Actualizar system prompt con instrucciones del nodo actual
    base_rules = _voice_rules(config)
    flow_prompt = engine.build_system_prompt(state, base_rules)
    flow_prompt += (
        "\n\n## Modo de prueba (texto)\n"
        "Esta es una conversación de texto para probar tu comportamiento. "
        "Responde como lo harías en una llamada telefónica real, pero en texto."
    )
    conversation.system_prompt = flow_prompt


def _advance_flow(
    conversation: Conversation,
    user_message: str,
    extracted_value: str | None = None,
) -> None:
    """Avanza el flow state después de cada turno del usuario."""
    if not hasattr(conversation, "_flow_engine"):
        return

    engine: FlowEngine = conversation._flow_engine  # type: ignore[attr-defined]
    state: FlowState = conversation._flow_state  # type: ignore[attr-defined]

    if state.completed:
        return

    # Procesar input del usuario y avanzar
    state, action = engine.process_user_input(
        state, user_message, extracted_value=extracted_value
    )
    conversation._flow_state = state  # type: ignore[attr-defined]

    # Auto-avanzar wait nodes (sin pausa en modo texto)
    while not state.completed:
        node = engine._nodes.get(state.current_node_id)
        if not node or node.get("type") != "wait":
            break
        state, _ = engine.process_user_input(state, "")
        conversation._flow_state = state  # type: ignore[attr-defined]

    # Reconstruir system prompt para el nuevo nodo
    _rebuild_flow_prompt(conversation)


def _rebuild_flow_prompt(conversation: Conversation) -> None:
    """Reconstruye el system prompt del flow para el nodo actual."""
    engine: FlowEngine = conversation._flow_engine  # type: ignore[attr-defined]
    state: FlowState = conversation._flow_state  # type: ignore[attr-defined]
    base_rules = _voice_rules(conversation.config)
    flow_prompt = engine.build_system_prompt(state, base_rules)
    flow_prompt += (
        "\n\n## Modo de prueba (texto)\n"
        "Esta es una conversación de texto para probar tu comportamiento. "
        "Responde como lo harías en una llamada telefónica real, pero en texto."
    )
    conversation.system_prompt = flow_prompt


def _is_flow_action_node(conversation: Conversation) -> bool:
    """Verifica si el nodo actual del flow es un nodo action."""
    if not hasattr(conversation, "_flow_engine"):
        return False
    engine: FlowEngine = conversation._flow_engine  # type: ignore[attr-defined]
    state: FlowState = conversation._flow_state  # type: ignore[attr-defined]
    node = engine._nodes.get(state.current_node_id)
    return node is not None and node.get("type") == "action"


# ── Chat turn ─────────────────────────────────────────────

async def chat_turn(
    conversation: Conversation,
    user_message: str,
    api_integrations: list[dict] | None = None,
) -> tuple[str, list[dict]]:
    """Ejecuta un turno de chat. Retorna (agent_text, tool_calls)."""
    client = _get_gemini()
    config = conversation.config

    # Inicializar flow si es primera vez
    init_flow_state(conversation)

    # Determinar si el nodo actual es action ANTES de avanzar
    is_action_node = _is_flow_action_node(conversation)

    # Avanzar flow con el input del usuario (si aplica y no es action node)
    if conversation.turn_count > 0 and not is_action_node:
        _advance_flow(conversation, user_message)

    # Agregar mensaje del usuario al historial
    conversation.history.append(
        types.Content(role="user", parts=[types.Part.from_text(text=user_message)])
    )

    tool_declarations = _build_tool_declarations(config, api_integrations=api_integrations)
    tool_calls_log: list[dict] = []
    last_tool_result: str | None = None
    last_tool_is_error: bool = False
    max_tool_rounds = 5

    for _ in range(max_tool_rounds):
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=conversation.history,
            config=types.GenerateContentConfig(
                system_instruction=conversation.system_prompt,
                tools=tool_declarations or None,
                temperature=0.7,
            ),
        )

        # Verificar si hay function calls
        candidate = response.candidates[0] if response.candidates else None
        if not candidate or not candidate.content or not candidate.content.parts:
            return "No pude generar una respuesta.", tool_calls_log

        parts = candidate.content.parts
        function_calls = [p for p in parts if p.function_call]

        if not function_calls:
            # Respuesta de texto normal — fin del turno
            conversation.history.append(candidate.content)
            text = "".join(p.text for p in parts if p.text)
            conversation.turn_count += 1

            # Si era un action node, ahora avanzar el flow con el resultado de la tool
            if is_action_node and last_tool_result is not None:
                extracted = "_error_" if last_tool_is_error else last_tool_result
                _advance_flow(conversation, "", extracted_value=extracted)

            return text, tool_calls_log

        # Hay function calls — ejecutar y continuar
        conversation.history.append(candidate.content)

        function_response_parts: list[types.Part] = []
        for fc_part in function_calls:
            fc = fc_part.function_call
            tool_name = fc.name
            tool_args = dict(fc.args) if fc.args else {}

            logger.info("Chat tool call: %s(%s)", tool_name, tool_args)
            result = await _execute_tool(
                tool_name, tool_args, config, api_integrations=api_integrations
            )

            # Trackear resultado de la última tool para action nodes
            last_tool_result = result
            last_tool_is_error = result.startswith("Error") or result.startswith("[ERROR")

            tool_calls_log.append({
                "name": tool_name,
                "args": tool_args,
                "result": result,
            })

            function_response_parts.append(
                types.Part.from_function_response(
                    name=tool_name,
                    response={"result": result},
                )
            )

        conversation.history.append(
            types.Content(role="user", parts=function_response_parts)
        )

    # Si se acabaron los rounds de tools, extraer lo que haya
    return "Disculpa, tuve un problema procesando tu consulta.", tool_calls_log
