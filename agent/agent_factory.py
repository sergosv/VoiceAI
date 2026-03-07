"""Construye agentes de voz dinámicos según la configuración del cliente."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from livekit.agents import Agent, RunContext, llm
from livekit.agents.llm import FunctionCallOutput, function_tool

from agent.config_loader import ResolvedConfig
from agent.flow_engine import FlowEngine, FlowState
from agent.tools.file_search import search_knowledge_base
from agent.tools.calendar_tool import schedule_appointment
from agent.tools.memory_tool import recall_memory_search
from agent.tools.schedule_tool import schedule_reminder_action
from agent.tools.whatsapp_tool import send_whatsapp_message
from agent.tools.crm_tool import save_contact, update_contact_notes
from agent.config_loader import load_whatsapp_config_by_agent_id

logger = logging.getLogger(__name__)


class VoiceAgent(Agent):
    """Agente de voz personalizado por cliente.

    Cada instancia se configura dinámicamente según el ResolvedConfig
    del negocio + agente al que pertenece la llamada. Las herramientas
    se habilitan según `enabled_tools` del cliente.
    """

    def __init__(
        self,
        config: ResolvedConfig,
        mcp_servers: list | None = None,
        api_integrations: list[dict] | None = None,
    ) -> None:
        kwargs: dict = {"instructions": config.agent.system_prompt}
        if mcp_servers:
            kwargs["mcp_servers"] = mcp_servers
        super().__init__(**kwargs)
        self._config = config
        self._api_integrations = {
            integ["name"]: integ for integ in (api_integrations or [])
        }

    @property
    def config(self) -> ResolvedConfig:
        return self._config

    def _tool_enabled(self, tool_name: str) -> bool:
        """Verifica si una herramienta está habilitada para este cliente."""
        return tool_name in self._config.client.enabled_tools

    # ── Herramientas del agente ─────────────────────────────

    @function_tool()
    async def search_knowledge(self, context: RunContext, query: str) -> str:
        """Busca información en la base de conocimientos del negocio.

        Usa esta herramienta cuando el usuario pregunte sobre servicios,
        precios, horarios, menú, o cualquier información específica del negocio.

        Args:
            query: La pregunta o tema a buscar en los documentos del negocio.
        """
        if not self._tool_enabled("search_knowledge"):
            return "Herramienta de búsqueda no disponible."

        store_id = self._config.client.file_search_store_id
        if not store_id:
            return "No hay base de conocimientos configurada."

        logger.info("File Search query para '%s': %s", self._config.client.slug, query)
        return await search_knowledge_base(query, store_id)

    @function_tool()
    async def transfer_to_human(self, context: RunContext, reason: str) -> str:
        """Transfiere la llamada a un agente humano.

        Usa esta herramienta cuando el cliente lo solicite explícitamente
        o cuando no puedas resolver su consulta.

        Args:
            reason: Motivo de la transferencia.
        """
        # Flow mode puede setear un número de transferencia por nodo
        transfer_number = (
            getattr(self, "_flow_transfer_number", None)
            or self._config.agent.transfer_number
        )
        if not transfer_number:
            return (
                "No hay número de transferencia configurado. "
                "Informa al cliente que el equipo se comunicará con él."
            )

        logger.info(
            "Solicitud de transferencia para '%s': %s",
            self._config.agent.slug,
            reason,
        )
        return (
            f"Transferencia solicitada al número {transfer_number}. "
            f"Motivo: {reason}. "
            "Informa al cliente que lo estás transfiriendo."
        )

    @function_tool()
    async def schedule_appointment(
        self,
        context: RunContext,
        patient_name: str,
        date: str,
        time: str,
        duration_minutes: int = 60,
        description: str | None = None,
    ) -> str:
        """Agenda una cita para el paciente o cliente.

        Usa esta herramienta cuando el usuario quiera agendar, programar
        o reservar una cita. Necesitas nombre, fecha y hora.

        Args:
            patient_name: Nombre completo del paciente/cliente.
            date: Fecha de la cita en formato YYYY-MM-DD.
            time: Hora de la cita en formato HH:MM (24 horas).
            duration_minutes: Duración en minutos (default 60).
            description: Descripción o motivo de la cita.
        """
        if not self._tool_enabled("schedule_appointment"):
            return "La función de agendar citas no está habilitada."

        caller_phone = getattr(context, "_caller_phone", None) or ""

        return await schedule_appointment(
            client_id=self._config.client.id,
            caller_phone=caller_phone,
            patient_name=patient_name,
            date=date,
            time=time,
            duration_minutes=duration_minutes,
            description=description,
            google_calendar_id=self._config.client.google_calendar_id,
            google_service_account_key=self._config.client.google_service_account_key,
        )

    @function_tool()
    async def send_whatsapp(
        self,
        context: RunContext,
        phone_number: str,
        message: str,
    ) -> str:
        """Envía un mensaje de WhatsApp al número indicado.

        Usa esta herramienta para enviar confirmaciones, información
        o recordatorios por WhatsApp.

        Args:
            phone_number: Número de teléfono destino con código de país.
            message: Texto del mensaje a enviar.
        """
        if not self._tool_enabled("send_whatsapp"):
            return "El envío de WhatsApp no está habilitado."

        # Cargar config de WhatsApp desde whatsapp_configs (por agente)
        wa_config = await load_whatsapp_config_by_agent_id(self._config.agent.id)
        if not wa_config:
            return "WhatsApp no está configurado para este agente."

        provider = wa_config.get("provider")
        if provider == "evolution":
            evo_url = wa_config.get("evo_api_url")
            evo_key = wa_config.get("evo_api_key")
            evo_instance = wa_config.get("evo_instance_id")
            if not evo_url or not evo_key or not evo_instance:
                return "La configuración de Evolution API está incompleta."
            return await send_whatsapp_message(
                api_url=evo_url,
                api_key=evo_key,
                instance_id=evo_instance,
                phone_number=phone_number,
                message=message,
            )
        elif provider == "gohighlevel":
            return "El envío de WhatsApp vía GoHighLevel aún no está disponible como herramienta."
        else:
            return "Proveedor de WhatsApp no soportado."

    @function_tool()
    async def save_contact_info(
        self,
        context: RunContext,
        name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        notes: str | None = None,
    ) -> str:
        """Guarda la información de contacto del cliente/paciente.

        Usa esta herramienta para capturar datos del contacto como
        nombre, correo electrónico o notas importantes.

        Args:
            name: Nombre completo del contacto.
            phone: Número de teléfono (si diferente al de la llamada).
            email: Correo electrónico.
            notes: Notas o comentarios sobre el contacto.
        """
        if not self._tool_enabled("save_contact"):
            return "La captura de contactos no está habilitada."

        contact_phone = phone or getattr(context, "_caller_phone", None) or ""
        if not contact_phone:
            return "No tengo un número de teléfono para guardar el contacto."

        return await save_contact(
            client_id=self._config.client.id,
            phone=contact_phone,
            name=name,
            email=email,
            notes=notes,
        )

    @function_tool()
    async def update_contact_notes(
        self,
        context: RunContext,
        notes: str,
    ) -> str:
        """Actualiza las notas del contacto actual.

        Usa esta herramienta para agregar notas importantes
        sobre la conversación o el contacto.

        Args:
            notes: Las notas a guardar sobre el contacto.
        """
        if not self._tool_enabled("save_contact"):
            return "La función de notas no está habilitada."

        caller_phone = getattr(context, "_caller_phone", None) or ""
        if not caller_phone:
            return "No puedo identificar el contacto para actualizar notas."

        return await update_contact_notes(
            client_id=self._config.client.id,
            phone=caller_phone,
            notes=notes,
        )

    @function_tool()
    async def recall_memory(
        self,
        context: RunContext,
        query: str,
    ) -> str:
        """Busca en el historial de interacciones pasadas con este contacto.

        Usa esta herramienta cuando el usuario pregunte sobre conversaciones
        anteriores, acuerdos previos, o información que ya compartió antes.

        Args:
            query: Pregunta o tema a buscar en el historial (ej: "cita anterior", "último pedido").
        """
        contact_id = getattr(context, "_memory_contact_id", None) or ""
        if not contact_id:
            return "No tengo historial previo de este contacto."

        return await recall_memory_search(
            query=query,
            client_id=self._config.client.id,
            contact_id=contact_id,
        )

    @function_tool()
    async def schedule_reminder(
        self,
        context: RunContext,
        description: str,
        datetime_str: str,
        channel: str = "call",
    ) -> str:
        """Programa un recordatorio o seguimiento para el contacto.

        Usa esta herramienta cuando el usuario pida que le recuerdes algo,
        que lo llames después, o que le mandes un mensaje en cierta fecha.

        Args:
            description: Qué recordar (ej: "Cita con el doctor", "Pago de factura").
            datetime_str: Fecha y hora en formato YYYY-MM-DDTHH:MM:SS (ej: "2026-03-08T14:00:00").
            channel: Canal del recordatorio: "call" para llamada, "whatsapp" para mensaje.
        """
        if not self._tool_enabled("schedule_reminder"):
            return "La función de recordatorios no está habilitada."

        caller_phone = getattr(context, "_caller_phone", None) or ""
        if not caller_phone:
            return "No tengo un número de teléfono para programar el recordatorio."

        contact_id = getattr(context, "_memory_contact_id", None)

        return await schedule_reminder_action(
            description=description,
            datetime_str=datetime_str,
            channel=channel,
            agent_id=self._config.agent.id,
            client_id=self._config.client.id,
            target_number=caller_phone,
            target_contact_id=contact_id,
        )

    @function_tool()
    async def call_api(
        self,
        context: RunContext,
        integration_name: str,
        parameters: str = "{}",
    ) -> str:
        """Llama a una API externa configurada para este negocio.

        Usa esta herramienta cuando necesites consultar o enviar datos
        a un sistema externo (stock, precios, CRM, etc.).

        Args:
            integration_name: Nombre de la integración API a llamar.
            parameters: JSON string con los parámetros requeridos por la API.
        """
        if not self._api_integrations:
            return "No hay integraciones API configuradas."

        integ = self._api_integrations.get(integration_name)
        if not integ:
            available = ", ".join(self._api_integrations.keys())
            return f"Integración '{integration_name}' no encontrada. Disponibles: {available}"

        import json
        try:
            params = json.loads(parameters) if isinstance(parameters, str) else parameters
        except json.JSONDecodeError:
            params = {}

        from agent.api_executor import execute_api_call

        logger.info(
            "API call '%s' para '%s': params=%s",
            integration_name, self._config.client.slug, params,
        )

        status_code, response_text = await execute_api_call(integ, params)

        if status_code == 0:
            return f"Error al llamar a la API: {response_text}"
        if status_code >= 400:
            return f"La API respondió con error (HTTP {status_code}): {response_text}"

        return response_text


class FlowVoiceAgent(VoiceAgent):
    """Agente de voz que sigue un flujo de conversación visual.

    Usa FlowEngine para generar prompts dinámicos por nodo,
    cambiando el system prompt en cada turno via _swap_system_prompt()
    (mismo patrón que el orchestrator).
    """

    def __init__(
        self,
        config: ResolvedConfig,
        flow_engine: FlowEngine,
        base_rules: str = "",
        mcp_servers: list | None = None,
        api_integrations: list[dict] | None = None,
        initial_variables: dict | None = None,
    ) -> None:
        super().__init__(config, mcp_servers=mcp_servers, api_integrations=api_integrations)
        self._flow_engine = flow_engine
        self._flow_state: FlowState = flow_engine.start(initial_variables)
        self._base_rules = base_rules
        self._turn_count = 0
        self._awaiting_tool_result: bool = False

    @property
    def flow_state(self) -> FlowState:
        return self._flow_state

    @property
    def flow_engine(self) -> FlowEngine:
        return self._flow_engine

    def _swap_system_prompt(self, chat_ctx: llm.ChatContext, new_instructions: str) -> None:
        """Reemplaza el system prompt en el chat context."""
        for item in chat_ctx.items:
            if hasattr(item, "role") and item.role == "system":
                if hasattr(item, "content"):
                    item.content = new_instructions
                return
        from livekit.agents.llm import ChatMessage
        chat_ctx.items.insert(0, ChatMessage(role="system", content=new_instructions))

    def _extract_last_user_message(self, chat_ctx: llm.ChatContext) -> str | None:
        """Extrae el último mensaje del usuario del chat context."""
        for item in reversed(chat_ctx.items):
            if hasattr(item, "role") and item.role == "user":
                if hasattr(item, "content"):
                    content = item.content
                    if isinstance(content, str):
                        return content
                    if isinstance(content, list):
                        for part in content:
                            if isinstance(part, str):
                                return part
                            if hasattr(part, "text"):
                                return part.text
        return None

    def _is_current_node_type(self, node_type: str) -> bool:
        """Verifica si el nodo actual es del tipo dado."""
        node = self._flow_engine._nodes.get(self._flow_state.current_node_id)
        return node is not None and node.get("type") == node_type

    async def llm_node(
        self,
        chat_ctx: llm.ChatContext,
        tools: list,
        model_settings: llm.ModelSettings,
    ) -> AsyncIterator:
        """Intercepta el LLM para inyectar el prompt del nodo actual del flujo.

        Maneja 3 ramas:
        1. Post-tool pass: FunctionCallOutput en chat_ctx + _awaiting_tool_result → avanza con resultado
        2. User message + nodo action: setea _awaiting_tool_result, NO avanza (deja que LLM llame tool)
        3. User message + nodo no-action: avanza normalmente
        """
        self._turn_count += 1
        action = None

        # ── Rama 1: Post-tool — el LLM ya ejecutó la herramienta ──
        if self._awaiting_tool_result:
            # Buscar el último FunctionCallOutput en el contexto
            last_output: FunctionCallOutput | None = None
            for item in reversed(chat_ctx.items):
                if isinstance(item, FunctionCallOutput):
                    last_output = item
                    break

            if last_output is not None:
                self._awaiting_tool_result = False
                extracted = "_error_" if last_output.is_error else last_output.output
                self._flow_state, action = self._flow_engine.process_user_input(
                    self._flow_state, "", extracted_value=extracted
                )
                logger.info(
                    "Flow post-tool avanzó a '%s' (action=%s, error=%s)",
                    self._flow_state.current_node_id,
                    action.type,
                    last_output.is_error,
                )
                # Auto-avanzar wait nodes
                await self._auto_advance_wait()

        # ── Rama 2 y 3: User message ──
        elif self._turn_count > 1:
            user_msg = self._extract_last_user_message(chat_ctx)
            if user_msg:
                if self._is_current_node_type("action"):
                    # Rama 2: nodo action — no avanzar, dejar que LLM llame la tool
                    self._awaiting_tool_result = True
                    logger.info(
                        "Flow nodo action '%s' — esperando resultado de tool",
                        self._flow_state.current_node_id,
                    )
                else:
                    # Rama 3: nodo normal — avanzar con input del usuario
                    self._flow_state, action = self._flow_engine.process_user_input(
                        self._flow_state, user_msg
                    )
                    logger.info(
                        "Flow avanzó a nodo '%s' (action=%s, completed=%s)",
                        self._flow_state.current_node_id,
                        action.type,
                        self._flow_state.completed,
                    )
                    # Auto-avanzar wait nodes
                    await self._auto_advance_wait()

        # ── Acciones especiales según resultado del avance ──
        if action is not None:
            # Transfer: inyectar número de transferencia para que transfer_to_human lo use
            if action.type == "transfer" and action.transfer_number:
                self._flow_transfer_number = action.transfer_number
                logger.info(
                    "Flow transfer — número inyectado: %s", action.transfer_number
                )

            # Hangup: programar desconexión después de que el LLM responda
            if action.hangup:
                self._should_hangup = True
                logger.info("Flow hangup programado tras respuesta del LLM")

        # Generar prompt dinámico del nodo actual
        flow_prompt = self._flow_engine.build_system_prompt(
            self._flow_state, self._base_rules
        )
        self._swap_system_prompt(chat_ctx, flow_prompt)

        # Programar hangup si es necesario (da tiempo al TTS de terminar)
        if getattr(self, "_should_hangup", False):
            self._should_hangup = False
            asyncio.create_task(self._delayed_hangup())

        # Delegar al LLM base
        return Agent.llm_node(self, chat_ctx, tools, model_settings)

    async def _delayed_hangup(self) -> None:
        """Espera a que el TTS termine de hablar y desconecta la llamada."""
        await asyncio.sleep(6.0)
        try:
            session = getattr(self, "session", None)
            if session:
                await session.aclose()
                logger.info("Flow hangup — sesión cerrada")
        except Exception as exc:
            logger.warning("Error al desconectar por hangup: %s", exc)

    async def _auto_advance_wait(self) -> None:
        """Si el nodo actual es 'wait', pausa y auto-avanza."""
        while self._is_current_node_type("wait"):
            node = self._flow_engine._nodes.get(self._flow_state.current_node_id)
            seconds = (node or {}).get("data", {}).get("seconds", 2)
            logger.info("Flow wait node — pausando %ds", seconds)
            await asyncio.sleep(seconds)
            self._flow_state, _ = self._flow_engine.process_user_input(
                self._flow_state, ""
            )
            if self._flow_state.completed:
                break


def _voice_rules(config: ResolvedConfig) -> str:
    """Genera reglas de voz con fecha/hora actual y datos del agente."""
    from datetime import datetime, timezone, timedelta
    try:
        from zoneinfo import ZoneInfo
        tz_mx = ZoneInfo("America/Mexico_City")
    except ImportError:
        tz_mx = timezone(timedelta(hours=-6))
    now = datetime.now(tz_mx)
    today = now.strftime("%A %d de %B de %Y")
    current_time = now.strftime("%H:%M")
    day_map = {
        "Monday": "lunes", "Tuesday": "martes", "Wednesday": "miércoles",
        "Thursday": "jueves", "Friday": "viernes", "Saturday": "sábado", "Sunday": "domingo",
    }
    month_map = {
        "January": "enero", "February": "febrero", "March": "marzo", "April": "abril",
        "May": "mayo", "June": "junio", "July": "julio", "August": "agosto",
        "September": "septiembre", "October": "octubre", "November": "noviembre", "December": "diciembre",
    }
    for eng, esp in day_map.items():
        today = today.replace(eng, esp)
    for eng, esp in month_map.items():
        today = today.replace(eng, esp)

    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    agent_name = config.agent.name
    business_name = config.client.name

    return (
        f"\n\n## Contexto temporal\n"
        f"- Hoy es {today}. Fecha: {now.strftime('%Y-%m-%d')}. Hora actual: {current_time} (hora de México).\n"
        f"- Mañana es {tomorrow}.\n"
        f"- Cuando el usuario diga 'mañana', 'pasado mañana', 'el lunes', etc., calcula la fecha EXACTA "
        f"basándote en que hoy es {now.strftime('%Y-%m-%d')}.\n"
        f"\n## Reglas de voz (OBLIGATORIAS)\n"
        "- MÁXIMO 2 frases por respuesta. Si necesitas decir más, pregunta si quieren que continúes.\n"
        "- SIEMPRE termina con pregunta corta: '¿le parece?', '¿verdad?', '¿qué dice?', '¿le queda bien?'\n"
        "- SIEMPRE empieza con muletilla natural: 'Claro', 'Ah ok', 'Mire', 'Sí', 'Ajá', "
        "'Perfecto', 'Con gusto', 'Fíjese que'\n"
        "- Si te interrumpen, cede la palabra inmediatamente.\n"
        '- Confirma datos repitiendo: "Su nombre es Juan Pérez, ¿verdad?"\n'
        "- Números de teléfono: di dígito por dígito con pausa: 'nueve-nueve-nueve, uno-dos-tres'.\n"
        "- Precios: redondea natural: 'son como mil doscientos pesos', NO 'mil doscientos pesos con cero centavos'.\n"
        "- Fechas: di natural: 'el martes que viene', NO 'el martes 15 de abril de 2026'.\n"
        "- Horarios: di simple: 'a las diez de la mañana', NO 'a las 10:00 horas'.\n"
        "- Despedida siempre con resumen de lo acordado.\n"
        "- NUNCA digas que eres inteligencia artificial, asistente virtual ni robot.\n"
        f'- Si preguntan si eres robot, di que eres {agent_name} de {business_name}.\n'
        "- NUNCA deletrees palabras ni nombres.\n"
        "- No uses siglas ni abreviaturas.\n"
        "- NUNCA generes listas con números o bullets. Di opciones de forma conversacional: "
        "'Tenemos martes a las 10 o jueves a las 3, ¿cuál le queda?'\n"
        "- NUNCA uses estas palabras: 'permítame', 'con mucho gusto le informo', "
        "'nuestro sistema', 'base de datos', 'procesando'.\n"
        "- Si no sabes algo: 'Déjeme verificar' o 'No tengo esa info ahorita, ¿quiere que le averigüe?'\n"
        "- Si el usuario se oye molesto, cambia a tono empático: "
        "'Entiendo, tiene toda la razón, déjeme ayudarle'.\n"
        "- Si necesitas pensar o buscar información, empieza diciendo 'Déjeme ver...', "
        "'Un momento...' o 'Ok, déjeme checar...' para llenar el silencio.\n"
    )

TOOL_INSTRUCTIONS = {
    "schedule_appointment": (
        "Puedes AGENDAR CITAS. Cuando el usuario quiera programar, reservar o agendar una cita, "
        "pregúntale su nombre completo, la fecha y hora que prefiere, y el motivo. "
        "Luego usa la herramienta schedule_appointment para registrarla."
    ),
    "send_whatsapp": (
        "Puedes ENVIAR MENSAJES por WhatsApp. Ofrece enviar confirmaciones, "
        "direcciones o información importante al WhatsApp del usuario."
    ),
    "save_contact": (
        "Puedes GUARDAR DATOS DE CONTACTO. Si el usuario te da su nombre, correo "
        "o información relevante, guárdala con save_contact_info."
    ),
    "search_knowledge": (
        "Tienes acceso a la BASE DE CONOCIMIENTOS del negocio. Cuando te pregunten "
        "sobre servicios, precios, horarios o información del negocio, busca en ella."
    ),
    "schedule_reminder": (
        "Puedes PROGRAMAR RECORDATORIOS. Si el usuario te pide que le recuerdes algo, "
        "que lo llames después, o que le mandes un mensaje en cierta fecha, usa "
        "schedule_reminder. Pregúntale qué quiere que le recuerdes, cuándo, y si "
        "prefiere llamada o WhatsApp."
    ),
}


def _build_tool_instructions(enabled_tools: list[str]) -> str:
    """Genera instrucciones automáticas según las herramientas habilitadas."""
    lines = []
    for tool_name in enabled_tools:
        if tool_name in TOOL_INSTRUCTIONS:
            lines.append(f"- {TOOL_INSTRUCTIONS[tool_name]}")
    if not lines:
        return ""
    return "\n\n## Herramientas disponibles\n" + "\n".join(lines)


def _build_api_instructions(api_integrations: list[dict]) -> str:
    """Genera instrucciones para las API integrations configuradas."""
    if not api_integrations:
        return ""
    lines = ["\n\n## APIs externas disponibles"]
    lines.append(
        "Usa la herramienta `call_api` para llamar a estas APIs. "
        "Pasa el nombre exacto de la integración y los parámetros como JSON."
    )
    for integ in api_integrations:
        name = integ.get("name", "")
        desc = integ.get("description", "")
        input_schema = integ.get("input_schema") or {}
        params = input_schema.get("parameters", [])

        param_strs = []
        for p in params:
            pname = p.get("name", "")
            ptype = p.get("type", "string")
            pdesc = p.get("description", "")
            required = "requerido" if p.get("required") else "opcional"
            param_strs.append(f"  - {pname} ({ptype}, {required}): {pdesc}")

        lines.append(f"- **{name}**: {desc}")
        if param_strs:
            lines.append("  Parámetros:")
            lines.extend(param_strs)

    return "\n".join(lines)


def build_orchestrated_agent(
    configs: list[ResolvedConfig],
    primary_config: ResolvedConfig,
    memory_context: str = "",
    mcp_servers: list | None = None,
    api_integrations: list[dict] | None = None,
) -> "OrchestratorAgent":
    """Construye un OrchestratorAgent con múltiples sub-agentes.

    Cada sub-agente tiene su propio LLM y TTS. El coordinador ADK
    decide qué agente responde en cada turno.
    """
    from agent.orchestrator import OrchestratorAgent, SubAgent
    from agent.pipeline_builder import build_llm, build_tts

    sub_agents: dict[str, SubAgent] = {}
    agents_metadata: list[dict] = []
    default_agent_id: str | None = None

    for cfg in configs:
        agent_id = cfg.agent.id

        # Augmentar instrucciones igual que build_agent
        tool_instructions = _build_tool_instructions(cfg.client.enabled_tools)
        api_instructions = _build_api_instructions(api_integrations or [])
        augmented_prompt = cfg.agent.system_prompt
        if memory_context:
            augmented_prompt += "\n" + memory_context
        augmented_prompt += _voice_rules(cfg) + tool_instructions + api_instructions
        if cfg.agent.examples:
            augmented_prompt += f"\n\n## Ejemplos de conversación\n{cfg.agent.examples}"

        stt_language = "es" if cfg.client.language in ("es", "es-en") else "en"

        sub = SubAgent(
            id=agent_id,
            name=cfg.agent.name,
            instructions=augmented_prompt,
            role_description=cfg.agent.role_description or f"Agente {cfg.agent.name}",
            llm_instance=build_llm(cfg.agent),
            tts_instance=build_tts(cfg.agent, stt_language),
            tools=[],  # Tools se manejan a nivel del Agent base
            config=cfg,
            priority=cfg.agent.orchestrator_priority,
        )
        sub_agents[agent_id] = sub
        agents_metadata.append({
            "id": agent_id,
            "name": cfg.agent.name,
            "role_description": sub.role_description,
        })

        # El agente con mayor prioridad es el default
        if default_agent_id is None:
            default_agent_id = agent_id

    if not default_agent_id:
        raise ValueError("No hay agentes disponibles para orquestación")

    orchestrator = OrchestratorAgent(
        primary_config=primary_config,
        sub_agents=sub_agents,
        agents_metadata=agents_metadata,
        default_agent_id=default_agent_id,
        coordinator_model=primary_config.client.orchestrator_model,
        coordinator_prompt=primary_config.client.orchestrator_prompt,
        mcp_servers=mcp_servers,
    )

    logger.info(
        "OrchestratorAgent creado para '%s' — %d sub-agentes, default: '%s'",
        primary_config.client.name,
        len(sub_agents),
        sub_agents[default_agent_id].name,
    )
    return orchestrator


def build_agent(
    config: ResolvedConfig,
    memory_context: str = "",
    mcp_servers: list | None = None,
    api_integrations: list[dict] | None = None,
    caller_number: str | None = None,
) -> VoiceAgent:
    """Construye un VoiceAgent configurado para un cliente + agente específico."""
    from dataclasses import replace

    # Si el agente está en modo flow, construir FlowVoiceAgent
    if (
        config.agent.conversation_mode == "flow"
        and config.agent.conversation_flow
    ):
        return _build_flow_agent(
            config, memory_context, mcp_servers, api_integrations, caller_number
        )

    # Inyectar contexto temporal + memoria + reglas de voz + instrucciones de herramientas
    tool_instructions = _build_tool_instructions(config.client.enabled_tools)
    api_instructions = _build_api_instructions(api_integrations or [])
    augmented_prompt = config.agent.system_prompt
    if memory_context:
        augmented_prompt += "\n" + memory_context
    augmented_prompt += _voice_rules(config) + tool_instructions + api_instructions
    # Agregar ejemplos de conversación si existen
    if config.agent.examples:
        augmented_prompt += f"\n\n## Ejemplos de conversación\n{config.agent.examples}"
    # Crear copia con prompt aumentado
    updated_agent = replace(config.agent, system_prompt=augmented_prompt)
    config = ResolvedConfig(agent=updated_agent, client=config.client)

    agent = VoiceAgent(config, mcp_servers=mcp_servers, api_integrations=api_integrations)
    logger.info(
        "Agente creado para '%s' / '%s' — voz: %s, tools: %s, apis: %d",
        config.client.name,
        config.agent.name,
        config.agent.voice_id,
        config.client.enabled_tools,
        len(api_integrations or []),
    )
    return agent


def _build_flow_agent(
    config: ResolvedConfig,
    memory_context: str = "",
    mcp_servers: list | None = None,
    api_integrations: list[dict] | None = None,
    caller_number: str | None = None,
) -> FlowVoiceAgent:
    """Construye un FlowVoiceAgent que sigue un flujo de conversación visual."""
    # Base rules = voice rules + tool instructions + api instructions + memory
    base_rules = config.agent.system_prompt
    if memory_context:
        base_rules += "\n" + memory_context
    base_rules += _voice_rules(config)
    base_rules += _build_tool_instructions(config.client.enabled_tools)
    base_rules += _build_api_instructions(api_integrations or [])
    if config.agent.examples:
        base_rules += f"\n\n## Ejemplos de conversación\n{config.agent.examples}"

    flow_engine = FlowEngine(
        config.agent.conversation_flow,
        enabled_tools=config.client.enabled_tools,
    )

    # Variables iniciales del contexto de la llamada
    initial_variables: dict = {}
    if caller_number:
        initial_variables["caller_number"] = caller_number

    agent = FlowVoiceAgent(
        config=config,
        flow_engine=flow_engine,
        base_rules=base_rules,
        mcp_servers=mcp_servers,
        api_integrations=api_integrations,
        initial_variables=initial_variables or None,
    )
    logger.info(
        "FlowVoiceAgent creado para '%s' / '%s' — modo flujo, apis: %d",
        config.client.name,
        config.agent.name,
        len(api_integrations or []),
    )
    return agent
