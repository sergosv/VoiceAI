"""Construye agentes de voz dinámicos según la configuración del cliente."""

from __future__ import annotations

import logging

from livekit.agents import Agent, RunContext
from livekit.agents.llm import function_tool

from agent.config_loader import ResolvedConfig
from agent.tools.file_search import search_knowledge_base
from agent.tools.calendar_tool import schedule_appointment
from agent.tools.whatsapp_tool import send_whatsapp_message
from agent.tools.crm_tool import save_contact, update_contact_notes

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
    ) -> None:
        kwargs: dict = {"instructions": config.agent.system_prompt}
        if mcp_servers:
            kwargs["mcp_servers"] = mcp_servers
        super().__init__(**kwargs)
        self._config = config

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
        transfer_number = self._config.agent.transfer_number
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

        cfg = self._config.client
        if not cfg.whatsapp_instance_id or not cfg.whatsapp_api_url or not cfg.whatsapp_api_key:
            return "WhatsApp no está configurado para este negocio."

        return await send_whatsapp_message(
            api_url=cfg.whatsapp_api_url,
            api_key=cfg.whatsapp_api_key,
            instance_id=cfg.whatsapp_instance_id,
            phone_number=phone_number,
            message=message,
        )

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


def build_orchestrated_agent(
    configs: list[ResolvedConfig],
    primary_config: ResolvedConfig,
    mcp_servers: list | None = None,
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
        augmented_prompt = cfg.agent.system_prompt + _voice_rules(cfg) + tool_instructions
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
    mcp_servers: list | None = None,
) -> VoiceAgent:
    """Construye un VoiceAgent configurado para un cliente + agente específico."""
    from dataclasses import replace

    # Inyectar contexto temporal + reglas de voz + instrucciones de herramientas
    tool_instructions = _build_tool_instructions(config.client.enabled_tools)
    augmented_prompt = config.agent.system_prompt + _voice_rules(config) + tool_instructions
    # Agregar ejemplos de conversación si existen
    if config.agent.examples:
        augmented_prompt += f"\n\n## Ejemplos de conversación\n{config.agent.examples}"
    # Crear copia con prompt aumentado
    updated_agent = replace(config.agent, system_prompt=augmented_prompt)
    config = ResolvedConfig(agent=updated_agent, client=config.client)

    agent = VoiceAgent(config, mcp_servers=mcp_servers)
    logger.info(
        "Agente creado para '%s' / '%s' — voz: %s, tools: %s",
        config.client.name,
        config.agent.name,
        config.agent.voice_id,
        config.client.enabled_tools,
    )
    return agent
