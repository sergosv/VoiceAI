"""Construye agentes de voz dinámicos según la configuración del cliente."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterable, AsyncIterator
from typing import Any, Coroutine

from livekit import rtc
from livekit.agents import Agent, RunContext, llm, tts
from livekit.agents.llm import FunctionCallOutput, function_tool

from agent.config_loader import ResolvedConfig
from agent.flow_engine import FlowEngine, FlowState
from agent.language_detect import LanguageDetectionConfig, LanguageDetector, LANGUAGE_CONFIGS
from agent.mode_engine import ModeEngine, ModeState
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
        language_detector: LanguageDetector | None = None,
        usage_metrics: Any | None = None,
    ) -> None:
        kwargs: dict = {"instructions": config.agent.system_prompt}
        if mcp_servers:
            kwargs["mcp_servers"] = mcp_servers
        super().__init__(**kwargs)
        self._config = config
        self._api_integrations = {
            integ["name"]: integ for integ in (api_integrations or [])
        }
        # Datos de la llamada — se inyectan desde main.py antes de session.start()
        self._caller_phone: str = ""
        self._memory_contact_id: str | None = None
        # Métricas de uso real (caracteres TTS, tokens LLM)
        self._usage_metrics = usage_metrics
        # Soporte de cambio de idioma en vivo
        self._language_detector = language_detector
        self._current_language: str = config.client.language
        self._dynamic_tts: tts.TTS | None = None
        self._tts_cache: dict[str, tts.TTS] = {}  # Cache TTS por idioma
        # Lifecycle hooks — inyectado desde main.py
        self._hook_engine: Any | None = None
        self._hook_channel: str = "voice"

    @property
    def config(self) -> ResolvedConfig:
        return self._config

    @property
    def current_language(self) -> str:
        return self._current_language

    def switch_language(self, new_lang: str) -> None:
        """Cambia el idioma del pipeline TTS en vivo.

        Reconstruye la instancia TTS para el nuevo idioma y opcionalmente
        aplica un prompt override si está configurado.
        """
        if new_lang == self._current_language:
            return

        from agent.pipeline_builder import build_tts

        old_lang = self._current_language
        self._current_language = new_lang

        # Obtener idioma TTS del mapeo
        lang_config = LANGUAGE_CONFIGS.get(new_lang, {})
        tts_lang = lang_config.get("tts_lang", new_lang)

        # Usar cache para no reconstruir TTS si ya se usó este idioma
        if tts_lang not in self._tts_cache:
            self._tts_cache[tts_lang] = build_tts(self._config.agent, tts_lang)

        self._dynamic_tts = self._tts_cache[tts_lang]

        # Aplicar prompt override si está configurado
        if self._language_detector:
            override = self._language_detector.get_language_prompt_override()
            if override:
                self._instructions = override
                logger.info(
                    "System prompt actualizado por cambio de idioma: %s → %s",
                    old_lang, new_lang,
                )

        logger.info(
            "Idioma del pipeline cambiado: %s → %s (tts_lang=%s)",
            old_lang, new_lang, tts_lang,
        )

    async def _metered_text(self, text: AsyncIterable[str]) -> AsyncIterator[str]:
        """Wrapper que cuenta caracteres TTS y evalúa hooks PreResponse."""
        # Si hay hooks PreResponse, acumular el primer segmento para evaluar
        if self._hook_engine and self._hook_engine.has_hooks_for("PreResponse"):
            full_text = ""
            chunks: list[str] = []
            async for chunk in text:
                chunks.append(chunk)
                full_text += chunk
                # Evaluar después de acumular suficiente texto (primera oración)
                if len(full_text) > 20 and any(c in full_text for c in ".!?"):
                    break

            # Evaluar hooks PreResponse con el texto acumulado
            try:
                from agent.hook_engine import HookAction, HookContext
                hctx = HookContext(
                    event="PreResponse",
                    channel=self._hook_channel,
                    agent_id=self._config.agent.id,
                    client_id=self._config.client.id,
                    response_text=full_text,
                )
                results = await self._hook_engine.evaluate("PreResponse", hctx)
                for r in results:
                    if r.action == HookAction.BLOCK and r.message:
                        # Reemplazar toda la respuesta
                        if self._usage_metrics:
                            self._usage_metrics.add_tts_text(r.message)
                        yield r.message
                        return
                    if r.action == HookAction.REGENERATE and r.message:
                        # Evaluator-optimizer: inyectar feedback para siguiente respuesta
                        # En streaming no podemos regenerar, pero inyectamos el feedback
                        # para que la PRÓXIMA respuesta sea correcta
                        if hasattr(self, "_instructions"):
                            self._instructions = self.instructions + (
                                f"\n\n## CORRECCIÓN URGENTE\n{r.message}\n"
                                f"Aplica esta corrección en tu próxima respuesta."
                            )
                        logger.info("Evaluator inyectó feedback: %s", r.message[:100])
                # Aplicar append de transforms
                transforms = self._hook_engine.collect_transforms(results)
                append_text = transforms.get("append") if transforms else None
                # Pasar contexto inyectado (se agrega al prompt para la siguiente respuesta)
                extra = self._hook_engine.collect_context(results)
                if extra and hasattr(self, "_instructions"):
                    base = self.instructions
                    if "## Contexto hooks:" not in base:
                        self._instructions = base + f"\n\n## Contexto hooks:\n{extra}"
            except Exception:
                logger.exception("Error en hooks PreResponse (voz)")
                append_text = None

            # Emitir chunks acumulados
            for c in chunks:
                if self._usage_metrics and c:
                    self._usage_metrics.add_tts_text(c)
                yield c

            # Continuar con el resto del stream
            async for chunk in text:
                if self._usage_metrics and chunk:
                    self._usage_metrics.add_tts_text(chunk)
                yield chunk

            # Append al final si hay
            if append_text:
                if self._usage_metrics:
                    self._usage_metrics.add_tts_text(f" {append_text}")
                yield f" {append_text}"
        else:
            # Sin hooks — flujo normal
            async for chunk in text:
                if self._usage_metrics and chunk:
                    self._usage_metrics.add_tts_text(chunk)
                yield chunk

    def tts_node(
        self,
        text: AsyncIterable[str],
        model_settings: Any,
    ) -> (
        AsyncIterable[rtc.AudioFrame]
        | Coroutine[Any, Any, AsyncIterable[rtc.AudioFrame]]
        | Coroutine[Any, Any, None]
    ):
        """Override del nodo TTS para contar caracteres y usar TTS dinámico."""
        metered = self._metered_text(text)
        if self._dynamic_tts is not None:
            return self._dynamic_tts_node(metered, model_settings)
        return Agent.default.tts_node(self, metered, model_settings)

    async def _dynamic_tts_node(
        self,
        text: AsyncIterable[str],
        model_settings: Any,
    ) -> AsyncIterator[rtc.AudioFrame]:
        """Nodo TTS que usa la instancia dinámica por idioma."""
        from livekit.agents import tokenize, tts as tts_module, utils

        current_tts = self._dynamic_tts
        assert current_tts is not None

        wrapped = current_tts
        if not current_tts.capabilities.streaming:
            wrapped = tts_module.StreamAdapter(
                tts=wrapped,
                sentence_tokenizer=tokenize.blingfire.SentenceTokenizer(
                    retain_format=True
                ),
            )

        activity = self._get_activity_or_raise()
        conn_options = activity.session.conn_options.tts_conn_options
        async with wrapped.stream(conn_options=conn_options) as stream:

            async def _forward_input() -> None:
                async for chunk in text:
                    stream.push_text(chunk)
                stream.end_input()

            forward_task = asyncio.create_task(_forward_input())
            try:
                async for ev in stream:
                    yield ev.frame
            finally:
                await utils.aio.cancel_and_wait(forward_task)

    def _tool_enabled(self, tool_name: str) -> bool:
        """Verifica si una herramienta está habilitada para este cliente."""
        return tool_name in self._config.client.enabled_tools

    # Herramientas que siempre están disponibles (no requieren enabled_tools)
    _ALWAYS_AVAILABLE = {"transfer_to_human", "recall_memory", "call_api"}

    def filter_disabled_tools(self) -> None:
        """Elimina tools deshabilitados del schema visible al LLM."""
        enabled = self._config.client.enabled_tools or []
        filtered = [
            t for t in self.tools
            if t.id in self._ALWAYS_AVAILABLE or t.id in enabled
        ]
        self.update_tools(filtered)
        logger.info(
            "Tools activos para '%s': %s",
            self._config.agent.slug,
            [t.id for t in filtered],
        )

    # ── Hook helpers para tools ─────────────────────────────

    async def _run_pre_tool_hooks(
        self, tool_name: str, tool_input: dict
    ) -> tuple[bool, str, dict]:
        """Evalúa hooks PreToolCall antes de ejecutar una tool.

        Returns:
            (allowed, message, updated_input):
                allowed: True si la tool puede ejecutarse.
                message: Mensaje de bloqueo o contexto adicional.
                updated_input: Input modificado por transforms.
        """
        if not self._hook_engine:
            return True, "", tool_input

        from agent.hook_engine import HookAction, HookContext

        hctx = HookContext(
            event="PreToolCall",
            channel=self._hook_channel,
            agent_id=self._config.agent.id,
            client_id=self._config.client.id,
            tool_name=tool_name,
            tool_input=tool_input,
            caller_phone=self._caller_phone,
        )

        results = await self._hook_engine.evaluate("PreToolCall", hctx)
        for r in results:
            if r.action == HookAction.BLOCK:
                logger.info("Hook PreToolCall bloqueó '%s': %s", tool_name, r.message)
                return False, r.message or "Acción no permitida.", tool_input

        # Aplicar transformaciones
        transforms = self._hook_engine.collect_transforms(results)
        if transforms:
            merged = {**tool_input, **transforms}
            return True, "", merged

        return True, "", tool_input

    async def _run_post_tool_hooks(
        self, tool_name: str, tool_input: dict, result: str
    ) -> None:
        """Evalúa hooks PostToolCall después de ejecutar una tool."""
        if not self._hook_engine:
            return

        from agent.hook_engine import HookContext

        hctx = HookContext(
            event="PostToolCall",
            channel=self._hook_channel,
            agent_id=self._config.agent.id,
            client_id=self._config.client.id,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_result={"text": result},
            caller_phone=self._caller_phone,
        )

        try:
            results = await self._hook_engine.evaluate("PostToolCall", hctx)
            notifications = self._hook_engine.collect_notifications(results)
            for notif in notifications:
                # Fire-and-forget notification
                asyncio.ensure_future(self._fire_hook_notification(notif))
        except Exception:
            logger.exception("Error en hooks PostToolCall para '%s'", tool_name)

    async def _fire_hook_notification(self, notif_config: dict) -> None:
        """Envía notificación de hook (best-effort)."""
        try:
            from api.services.hook_notifier import send_hook_notification
            await send_hook_notification(notif_config)
        except ImportError:
            logger.info(
                "Hook notification [%s] via %s: %s",
                notif_config.get("hook_name"),
                notif_config.get("channel", "webhook"),
                notif_config.get("template"),
            )
        except Exception:
            logger.exception("Error enviando hook notification")

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
            return (
                "No hay base de conocimientos configurada para este negocio. "
                "Responde con lo que sepas del system prompt. Si no tienes la información, "
                "dile al usuario que con gusto le pueden dar más detalles llamando directamente."
            )

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
        # Hook: PreToolCall
        tool_input = {"reason": reason}
        allowed, msg, tool_input = await self._run_pre_tool_hooks("transfer_to_human", tool_input)
        if not allowed:
            return msg

        # Hook: OnEscalation — disparar antes de transferir
        if self._hook_engine:
            try:
                from agent.hook_engine import HookAction, HookContext
                hctx = HookContext(
                    event="OnEscalation",
                    channel=self._hook_channel,
                    agent_id=self._config.agent.id,
                    client_id=self._config.client.id,
                    tool_name="transfer_to_human",
                    tool_input=tool_input,
                    caller_phone=self._caller_phone,
                )
                esc_results = await self._hook_engine.evaluate("OnEscalation", hctx)
                for r in esc_results:
                    if r.action == HookAction.BLOCK:
                        return r.message or "No se puede transferir en este momento."
                # Disparar notificaciones (ej: avisar al humano que va a recibir transfer)
                notifications = self._hook_engine.collect_notifications(esc_results)
                for notif in notifications:
                    asyncio.ensure_future(self._fire_hook_notification(notif))
            except Exception:
                logger.exception("Error en hooks OnEscalation")

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
        result = (
            f"Transferencia solicitada al número {transfer_number}. "
            f"Motivo: {reason}. "
            "Informa al cliente que lo estás transfiriendo."
        )

        # Hook: PostToolCall
        await self._run_post_tool_hooks("transfer_to_human", tool_input, result)
        return result

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
            return (
                "La función de citas no está habilitada. "
                "Dile al usuario que anotes sus datos y que el negocio le confirmará la cita. "
                "Pídele nombre, fecha preferida y teléfono para que lo contacten."
            )

        # Hook: PreToolCall
        tool_input = {
            "patient_name": patient_name,
            "date": date,
            "time": time,
            "duration_minutes": duration_minutes,
            "description": description,
        }
        allowed, msg, tool_input = await self._run_pre_tool_hooks("schedule_appointment", tool_input)
        if not allowed:
            return msg

        caller_phone = self._caller_phone

        result = await schedule_appointment(
            client_id=self._config.client.id,
            caller_phone=caller_phone,
            patient_name=tool_input.get("patient_name", patient_name),
            date=tool_input.get("date", date),
            time=tool_input.get("time", time),
            duration_minutes=tool_input.get("duration_minutes", duration_minutes),
            description=tool_input.get("description", description),
            google_calendar_id=self._config.client.google_calendar_id,
            google_service_account_key=self._config.client.google_service_account_key,
        )

        # Hook: PostToolCall
        await self._run_post_tool_hooks("schedule_appointment", tool_input, result)
        return result

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
            return (
                "WhatsApp no está habilitado para este agente. "
                "Ofrece al usuario darle la información de otra forma: "
                "dictarle los datos, o decirle que el negocio se los enviará."
            )

        # Hook: PreToolCall
        tool_input = {"phone_number": phone_number, "message": message}
        allowed, msg, tool_input = await self._run_pre_tool_hooks("send_whatsapp", tool_input)
        if not allowed:
            return msg

        # Cargar config de WhatsApp desde whatsapp_configs (por agente)
        wa_config = await load_whatsapp_config_by_agent_id(self._config.agent.id)
        if not wa_config:
            return (
                "WhatsApp no está configurado todavía. "
                "Dile al usuario que por el momento no puedes enviar mensajes, "
                "pero que le puedes dictar la información que necesite."
            )

        provider = wa_config.get("provider")
        if provider == "evolution":
            evo_url = wa_config.get("evo_api_url")
            evo_key = wa_config.get("evo_api_key")
            evo_instance = wa_config.get("evo_instance_id")
            if not evo_url or not evo_key or not evo_instance:
                return (
                    "La configuración de WhatsApp está incompleta — falta URL o API key. "
                    "Dile al usuario que no puedes enviar el mensaje en este momento, "
                    "pero que puedes dictarle la información."
                )
            result = await send_whatsapp_message(
                api_url=evo_url,
                api_key=evo_key,
                instance_id=evo_instance,
                phone_number=tool_input.get("phone_number", phone_number),
                message=tool_input.get("message", message),
            )
        elif provider == "gohighlevel":
            result = "El envío de WhatsApp vía GoHighLevel aún no está disponible como herramienta."
        else:
            result = "Proveedor de WhatsApp no soportado."

        # Hook: PostToolCall
        await self._run_post_tool_hooks("send_whatsapp", tool_input, result)
        return result

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
            return (
                "La captura de contactos no está habilitada. "
                "Continúa la conversación normalmente. Los datos del usuario "
                "se guardarán automáticamente al finalizar la llamada."
            )

        contact_phone = phone or self._caller_phone
        if not contact_phone:
            return (
                "No tengo el teléfono del contacto para guardarlo. "
                "Pídele su número de teléfono al usuario antes de guardar."
            )

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
            return (
                "La función de notas no está habilitada. "
                "Continúa la conversación. Las notas se capturarán "
                "automáticamente en el resumen al final."
            )

        caller_phone = self._caller_phone
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
        contact_id = self._memory_contact_id or ""
        if not contact_id:
            return (
                "No hay historial previo de este contacto — es la primera interacción. "
                "Trata al usuario como nuevo y pregúntale lo que necesites saber."
            )

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
            return (
                "Los recordatorios no están habilitados. "
                "Dile al usuario que anote la fecha y que el negocio "
                "se encargará de recordarle directamente."
            )

        caller_phone = self._caller_phone
        if not caller_phone:
            return (
                "No tengo el teléfono del usuario para programar el recordatorio. "
                "Pídele su número antes de intentar agendar el recordatorio."
            )

        contact_id = self._memory_contact_id

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
            return (
                "No hay APIs externas configuradas para este negocio. "
                "Responde con la información que tengas disponible. "
                "Si el usuario necesita datos de un sistema externo, "
                "dile que se comunique directamente con el negocio."
            )

        integ = self._api_integrations.get(integration_name)
        if not integ:
            available = ", ".join(self._api_integrations.keys())
            return (
                f"La integración '{integration_name}' no existe. "
                f"Las APIs disponibles son: {available}. "
                f"Usa el nombre exacto. Si ninguna sirve, dile al usuario "
                f"que esa consulta no está disponible por este canal."
            )

        import json
        try:
            params = json.loads(parameters) if isinstance(parameters, str) else parameters
        except json.JSONDecodeError:
            params = {}

        # Hook: PreToolCall
        tool_input = {"integration_name": integration_name, "parameters": params}
        allowed, msg, tool_input = await self._run_pre_tool_hooks("call_api", tool_input)
        if not allowed:
            return msg

        from agent.api_executor import execute_api_call

        logger.info(
            "API call '%s' para '%s': params=%s",
            integration_name, self._config.client.slug, params,
        )

        status_code, response_text = await execute_api_call(integ, params)

        if status_code == 0:
            result = (
                f"No se pudo conectar con la API '{integration_name}': {response_text}. "
                f"Dile al usuario que no puedes consultar esa información en este momento "
                f"y ofrece una alternativa (llamar directamente, intentar después)."
            )
        elif status_code >= 400:
            result = (
                f"La API '{integration_name}' respondió con error (HTTP {status_code}). "
                f"Detalle: {response_text[:200]}. "
                f"Informa al usuario que hubo un problema técnico consultando esa información "
                f"y que puede intentar más tarde o contactar directamente al negocio."
            )
        else:
            result = response_text

        # Hook: PostToolCall
        await self._run_post_tool_hooks("call_api", tool_input, result)
        return result


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


class ModeVoiceAgent(VoiceAgent):
    """Agente de voz que opera en un modo estructurado (survey, quiz, negotiation, interview).

    Usa ModeEngine para manejar progresión de preguntas, scoring y prompts
    dinámicos por turno via _swap_system_prompt().
    """

    def __init__(
        self,
        config: ResolvedConfig,
        mode_engine: ModeEngine,
        base_rules: str = "",
        mcp_servers: list | None = None,
        api_integrations: list[dict] | None = None,
    ) -> None:
        super().__init__(config, mcp_servers=mcp_servers, api_integrations=api_integrations)
        self._mode_engine = mode_engine
        self._mode_state: ModeState = mode_engine.start()
        self._base_rules = base_rules
        self._turn_count = 0

    @property
    def mode_state(self) -> ModeState:
        return self._mode_state

    @property
    def mode_engine(self) -> ModeEngine:
        return self._mode_engine

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

    async def llm_node(
        self,
        chat_ctx: llm.ChatContext,
        tools: list,
        model_settings: llm.ModelSettings,
    ) -> AsyncIterator:
        """Intercepta el LLM para inyectar el prompt del modo actual.

        En el primer turno, genera el prompt inicial (primera pregunta).
        En turnos subsecuentes, procesa la respuesta del usuario y avanza.
        """
        self._turn_count += 1

        if self._turn_count > 1 and not self._mode_state.completed:
            user_msg = self._extract_last_user_message(chat_ctx)
            if user_msg:
                self._mode_state, feedback = self._mode_engine.process_answer(
                    self._mode_state, user_msg
                )
                logger.info(
                    "Mode '%s' avanzó a pregunta %d/%d (completed=%s)",
                    self._mode_state.mode,
                    self._mode_state.current_question_idx,
                    self._mode_engine.question_count,
                    self._mode_state.completed,
                )
                # Inyectar feedback como mensaje del sistema si hay
                if feedback:
                    from livekit.agents.llm import ChatMessage
                    chat_ctx.items.append(
                        ChatMessage(role="system", content=f"[Feedback]: {feedback}")
                    )

        # Generar prompt dinámico del modo actual
        mode_prompt = self._mode_engine.build_system_prompt(
            self._mode_state, self._base_rules
        )
        self._swap_system_prompt(chat_ctx, mode_prompt)

        return Agent.llm_node(self, chat_ctx, tools, model_settings)


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
    """Genera instrucciones automáticas según las herramientas habilitadas.

    NOTA: Desde Phase 25, las tool descriptions ya están en los docstrings de
    @function_tool(). Solo agregamos hints mínimos sobre cuándo ofrecer cada tool
    al usuario, NO repetimos lo que el LLM ya ve en el tool schema.
    """
    lines = []
    for tool_name in enabled_tools:
        if tool_name in TOOL_INSTRUCTIONS:
            lines.append(f"- {TOOL_INSTRUCTIONS[tool_name]}")
    if not lines:
        return ""
    return "\n\n## Capacidades\n" + "\n".join(lines)


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
    language_detector: LanguageDetector | None = None,
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

    # Si el agente está en modo estructurado (survey/quiz/negotiation/interview)
    if config.agent.conversation_mode in ("survey", "quiz", "negotiation", "interview"):
        return _build_mode_agent(
            config, memory_context, mcp_servers, api_integrations
        )

    # Progressive Context Disclosure (Anthropic best practice):
    # Core prompt = personalidad + contexto temporal + reglas de voz (compactas)
    # Just-in-time = memory, API instructions, examples (se cargan cuando se necesitan)
    tool_instructions = _build_tool_instructions(config.client.enabled_tools)
    augmented_prompt = config.agent.system_prompt
    augmented_prompt += _voice_rules(config) + tool_instructions

    # Memory: solo resumen corto en prompt, detalle vía recall_memory tool
    if memory_context:
        # Extraer solo las primeras 2 líneas como hint
        memory_lines = memory_context.strip().split("\n")
        if len(memory_lines) > 3:
            memory_hint = "\n".join(memory_lines[:3])
            augmented_prompt += (
                f"\n\n## Contexto del contacto\n{memory_hint}\n"
                f"(Usa la herramienta recall_memory para más detalles si los necesitas.)"
            )
        else:
            augmented_prompt += f"\n\n## Contexto del contacto\n{memory_context}"

    # API instructions: solo si hay pocas. Si hay muchas, se cargan just-in-time
    api_instructions = _build_api_instructions(api_integrations or [])
    if api_instructions and len(api_instructions) < 500:
        augmented_prompt += api_instructions
    elif api_instructions:
        # Demasiado largo — solo hint, el agente ve las APIs en call_api tool
        api_names = [i.get("name", "") for i in (api_integrations or [])]
        augmented_prompt += (
            f"\n\n## APIs externas\nTienes acceso a estas APIs vía call_api: "
            f"{', '.join(api_names)}. Usa call_api con el nombre de la integración."
        )

    # Examples: solo si son cortos (< 500 chars)
    if config.agent.examples:
        if len(config.agent.examples) < 500:
            augmented_prompt += f"\n\n## Ejemplos de conversación\n{config.agent.examples}"
        else:
            augmented_prompt += (
                "\n\n## Estilo de conversación\n"
                "Tienes ejemplos de conversación configurados. "
                "Sigue el tono y estilo que ya conoces del negocio."
            )
    # Crear copia con prompt aumentado
    updated_agent = replace(config.agent, system_prompt=augmented_prompt)
    config = ResolvedConfig(agent=updated_agent, client=config.client)

    agent = VoiceAgent(
        config,
        mcp_servers=mcp_servers,
        api_integrations=api_integrations,
        language_detector=language_detector,
    )
    logger.info(
        "Agente creado para '%s' / '%s' — voz: %s, tools: %s, apis: %d, lang_detect: %s",
        config.client.name,
        config.agent.name,
        config.agent.voice_id,
        config.client.enabled_tools,
        len(api_integrations or []),
        language_detector is not None,
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


def _build_mode_agent(
    config: ResolvedConfig,
    memory_context: str = "",
    mcp_servers: list | None = None,
    api_integrations: list[dict] | None = None,
) -> ModeVoiceAgent:
    """Construye un ModeVoiceAgent para modos estructurados (survey/quiz/negotiation/interview)."""
    base_rules = config.agent.system_prompt
    if memory_context:
        base_rules += "\n" + memory_context
    base_rules += _voice_rules(config)
    base_rules += _build_tool_instructions(config.client.enabled_tools)
    base_rules += _build_api_instructions(api_integrations or [])
    if config.agent.examples:
        base_rules += f"\n\n## Ejemplos de conversación\n{config.agent.examples}"

    mode_engine = ModeEngine(
        mode=config.agent.conversation_mode,
        config=config.agent.mode_config or {},
    )

    agent = ModeVoiceAgent(
        config=config,
        mode_engine=mode_engine,
        base_rules=base_rules,
        mcp_servers=mcp_servers,
        api_integrations=api_integrations,
    )
    logger.info(
        "ModeVoiceAgent creado para '%s' / '%s' — modo %s (%d preguntas), apis: %d",
        config.client.name,
        config.agent.name,
        config.agent.conversation_mode,
        mode_engine.question_count,
        len(api_integrations or []),
    )
    return agent
