"""Entrypoint del agente de voz LiveKit.

Un solo worker que se adapta dinámicamente por llamada,
cargando la configuración del agente + cliente desde Supabase.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import AgentSession, AgentServer, room_io
from livekit.agents.llm import ChatMessage
from livekit.plugins import silero, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from agent.agent_factory import build_agent, build_orchestrated_agent
from agent.billing import CallBilling
from agent.guardrails import GuardrailsConfig, GuardrailsEngine
from agent.intent import IntentConfig, RealtimeIntentExtractor
from agent.language_detect import LanguageDetectionConfig, LanguageDetector
from agent.memory import AgentMemory
from agent.quality import QualityConfig, score_call_quality
from agent.sentiment import RealtimeSentimentAnalyzer, SentimentConfig
from agent.config_loader import (
    AgentConfig,
    ResolvedConfig,
    SlimClientConfig,
    load_api_integrations,
    load_config_by_agent_id,
    load_config_by_client_id,
    load_config_by_phone,
    load_mcp_servers,
    load_orchestrated_configs,
)
from agent.mcp_builder import build_mcp_servers
from agent.pipeline_builder import build_llm, build_realtime_model, build_stt, build_tts
from agent.session_handler import SessionHandler
from agent.voice_quality import (
    BACKCHANNEL_FIRST_DELAY,
    BACKCHANNEL_INTERVAL,
    FILLER_DELAY_SECONDS,
    random_backchannel,
    random_filler,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(room)s] %(name)s — %(message)s",
)
# Filter que inyecta room_name en cada log record
_old_factory = logging.getLogRecordFactory()


def _record_factory(*args: object, **kwargs: object) -> logging.LogRecord:
    record = _old_factory(*args, **kwargs)
    if not hasattr(record, "room"):
        record.room = "-"  # type: ignore[attr-defined]
    return record


logging.setLogRecordFactory(_record_factory)
logger = logging.getLogger("voice-ai")

server = AgentServer()


@server.rtc_session(agent_name="voice-ai-platform")
async def entrypoint(ctx: agents.JobContext) -> None:
    """Punto de entrada para cada llamada."""
    await ctx.connect(auto_subscribe=agents.AutoSubscribe.AUDIO_ONLY)

    # Setear room como correlation ID para todos los logs de esta llamada
    _old = logging.getLogRecordFactory()
    _room = ctx.room.name

    def _room_factory(*a: object, **kw: object) -> logging.LogRecord:
        r = _old(*a, **kw)
        r.room = _room  # type: ignore[attr-defined]
        return r

    logging.setLogRecordFactory(_room_factory)

    logger.info("Nueva sesión en room: %s", ctx.room.name)

    # Esperar al participante SIP
    caller_number: str | None = None
    called_number: str | None = None

    def on_participant_connected(participant: rtc.RemoteParticipant) -> None:
        nonlocal caller_number, called_number
        if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
            caller_number = participant.attributes.get("sip.phoneNumber")
            called_number = participant.attributes.get("sip.trunkPhoneNumber")
            logger.info(
                "SIP participante: caller=%s, called=%s",
                caller_number,
                called_number,
            )

    ctx.room.on("participant_connected", on_participant_connected)

    # Verificar participantes ya conectados
    for p in ctx.room.remote_participants.values():
        if p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
            caller_number = p.attributes.get("sip.phoneNumber")
            called_number = p.attributes.get("sip.trunkPhoneNumber")
            break

    # Si no hay SIP (ej: test desde web), esperar un momento
    if not called_number:
        await asyncio.sleep(2)
        for p in ctx.room.remote_participants.values():
            if p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
                caller_number = p.attributes.get("sip.phoneNumber")
                called_number = p.attributes.get("sip.trunkPhoneNumber")
                break

    # Detectar modo outbound desde metadata del room
    outbound_mode = False
    campaign_script: str | None = None
    outbound_client_id: str | None = None
    outbound_agent_id: str | None = None
    campaign_id: str | None = None
    room_metadata = ctx.room.metadata or ""
    if room_metadata:
        try:
            meta = json.loads(room_metadata)
            if meta.get("type") == "outbound":
                outbound_mode = True
                campaign_script = meta.get("script")
                outbound_client_id = meta.get("client_id")
                outbound_agent_id = meta.get("agent_id")
                campaign_id = meta.get("campaign_id")
                logger.info(
                    "Modo outbound detectado, campaign_id: %s, agent_id: %s",
                    campaign_id, outbound_agent_id,
                )
        except (json.JSONDecodeError, AttributeError):
            pass

    # Cargar config del agente + cliente
    config: ResolvedConfig | None = None
    if outbound_mode:
        # Outbound: preferir agent_id, fallback a client_id
        if outbound_agent_id:
            config = await load_config_by_agent_id(outbound_agent_id)
        if not config and outbound_client_id:
            config = await load_config_by_client_id(outbound_client_id)
    elif called_number:
        config = await load_config_by_phone(called_number)

    if not config:
        logger.warning(
            "No se encontró agente para número '%s'. Usando config por defecto.",
            called_number,
        )
        # Config por defecto para testing
        config = ResolvedConfig(
            agent=AgentConfig(
                id="00000000-0000-0000-0000-000000000000",
                client_id="00000000-0000-0000-0000-000000000000",
                name="Asistente",
                slug="test",
                phone_number=None,
                phone_sid=None,
                livekit_sip_trunk_id=None,
                system_prompt="Eres un asistente virtual de prueba. Responde en español de forma amable y concisa.",
                greeting="Hola, soy un asistente virtual de prueba. ¿En qué puedo ayudarle?",
                examples=None,
            ),
            client=SlimClientConfig(
                id="00000000-0000-0000-0000-000000000000",
                name="Test",
                slug="test",
                business_type="generic",
                language="es",
                file_search_store_id=None,
            ),
        )

    # ========= BILLING: Check ANTES de atender =========
    billing = CallBilling(config.client.id)
    credit_check = await billing.check_can_take_call()

    if not credit_check["allowed"]:
        logger.warning("Client %s no credits, rejecting call", config.client.id)
        # Intentar reproducir mensaje antes de colgar
        try:
            from livekit.agents import tts as _tts_mod
            session_reject = AgentSession(vad=silero.VAD.load())
            await session_reject.start(room=ctx.room)
            await session_reject.say(
                "Lo sentimos, en este momento no podemos atender tu llamada. "
                "Por favor comunícate directamente al número del negocio. Gracias.",
                allow_interruptions=False,
            )
            await asyncio.sleep(3)
        except Exception:
            logger.exception("Error playing rejection message")
        return

    # Override del system prompt para outbound con script de campaña
    if outbound_mode and campaign_script:
        from dataclasses import replace
        updated_agent = replace(config.agent, system_prompt=campaign_script)
        config = ResolvedConfig(agent=updated_agent, client=config.client)

    # Cargar MCP servers configurados para este cliente/agente
    mcp_configs = await load_mcp_servers(config.client.id, config.agent.id)
    mcp_servers = build_mcp_servers(mcp_configs) if mcp_configs else None
    if mcp_servers:
        logger.info(
            "MCP servers cargados para '%s/%s': %d servidor(es)",
            config.client.slug, config.agent.slug, len(mcp_servers),
        )

    # Cargar API integrations configuradas para este cliente/agente
    api_integrations = await load_api_integrations(config.client.id, config.agent.id)
    if api_integrations:
        logger.info(
            "API integrations cargadas para '%s/%s': %d integración(es)",
            config.client.slug, config.agent.slug, len(api_integrations),
        )

    # Memoria de largo plazo: identificar contacto y cargar contexto
    memory_context = ""
    memory: AgentMemory | None = None
    contact_phone_for_memory = caller_number
    if outbound_mode and caller_number:
        # En outbound, caller_number es el destino
        contact_phone_for_memory = caller_number

    if contact_phone_for_memory:
        try:
            channel = "outbound_call" if outbound_mode else "call"
            memory = AgentMemory(config.client.id, channel=channel)
            await memory.identify(contact_phone_for_memory, "phone")
            memory_context = memory.build_memory_context()
            if memory_context:
                logger.info(
                    "Contexto de memoria cargado para '%s' (%d memorias)",
                    contact_phone_for_memory,
                    len(memory.memories),
                )
        except Exception:
            logger.exception("Error cargando memoria, continuando sin contexto")
            memory = None

    # Sentimiento en tiempo real
    sentiment_cfg = SentimentConfig.from_dict(config.agent.sentiment_config)
    sentiment_analyzer: RealtimeSentimentAnalyzer | None = None
    if sentiment_cfg.enabled:
        sentiment_analyzer = RealtimeSentimentAnalyzer(
            config=sentiment_cfg,
            language=config.client.language,
        )
        logger.info(
            "Sentimiento en tiempo real activado para '%s/%s' (umbral=%d, auto_transfer=%s)",
            config.client.slug, config.agent.slug,
            sentiment_cfg.escalation_threshold, sentiment_cfg.auto_transfer,
        )

    # Intent extraction en tiempo real
    intent_cfg = IntentConfig.from_dict(config.agent.intent_config)
    intent_extractor: RealtimeIntentExtractor | None = None
    if intent_cfg.enabled:
        intent_extractor = RealtimeIntentExtractor(config=intent_cfg)
        logger.info(
            "Intent extraction activado para '%s/%s' (%d intents)",
            config.client.slug, config.agent.slug, len(intent_cfg.intents),
        )

    # Guardrails
    guardrails_cfg = GuardrailsConfig.from_dict(config.agent.guardrails_config)
    guardrails: GuardrailsEngine | None = None
    if guardrails_cfg.enabled:
        guardrails = GuardrailsEngine(guardrails_cfg)
        logger.info(
            "Guardrails activados para '%s/%s' (%d temas prohibidos)",
            config.client.slug, config.agent.slug, len(guardrails_cfg.prohibited_topics),
        )

    # Detección de idioma dinámica
    lang_cfg = LanguageDetectionConfig.from_dict(config.agent.language_detection_config)
    language_detector: LanguageDetector | None = None
    if lang_cfg.enabled:
        language_detector = LanguageDetector(
            config=lang_cfg,
            default_language=config.client.language,
        )
        logger.info(
            "Detección de idioma activada para '%s/%s' (idiomas: %s)",
            config.client.slug, config.agent.slug, lang_cfg.supported_languages,
        )

    # Quality scoring config
    quality_cfg = QualityConfig.from_dict(config.agent.quality_config)

    # Construir agente dinámico
    is_orchestrated = False
    if (
        not outbound_mode
        and config.client.orchestration_mode == "intelligent"
    ):
        # Modo inteligente: cargar todos los agentes del cliente
        all_configs = await load_orchestrated_configs(config.client.id)
        if len(all_configs) >= 2:
            voice_agent = build_orchestrated_agent(
                all_configs, config, memory_context=memory_context,
                mcp_servers=mcp_servers, api_integrations=api_integrations,
            )
            is_orchestrated = True
            logger.info(
                "Modo inteligente activado para '%s' — %d agentes",
                config.client.name,
                len(all_configs),
            )
        else:
            voice_agent = build_agent(
                config, memory_context=memory_context,
                mcp_servers=mcp_servers, api_integrations=api_integrations,
            )
            logger.info(
                "Modo inteligente solicitado pero solo %d agente(s), usando simple",
                len(all_configs),
            )
    else:
        voice_agent = build_agent(
            config, memory_context=memory_context,
            mcp_servers=mcp_servers, api_integrations=api_integrations,
        )

    # Configurar pipeline de voz (BYOK)
    stt_language = "es" if config.client.language in ("es", "es-en") else "en"

    vad = silero.VAD.load(
        activation_threshold=0.5,
        min_speech_duration=0.1,
        min_silence_duration=0.5,
        sample_rate=8000,
    )

    if config.agent.agent_mode == "realtime":
        logger.info(
            "Modo realtime: model=%s, voice=%s",
            config.agent.realtime_model, config.agent.realtime_voice,
        )
        session = AgentSession(
            llm=build_realtime_model(config.agent),
            vad=vad,
            turn_detection=MultilingualModel(),
            min_endpointing_delay=0.5,
            max_endpointing_delay=4.0,
            min_interruption_duration=0.6,
            min_interruption_words=1,
        )
    else:
        logger.info(
            "Modo pipeline: stt=%s, llm=%s, tts=%s",
            config.agent.stt_provider, config.agent.llm_provider, config.agent.tts_provider,
        )
        session = AgentSession(
            stt=build_stt(config.agent, stt_language),
            llm=build_llm(config.agent),
            tts=build_tts(config.agent, stt_language),
            vad=vad,
            turn_detection=MultilingualModel(),
            min_endpointing_delay=0.5,
            max_endpointing_delay=4.0,
            min_interruption_duration=0.6,
            min_interruption_words=1,
        )

    # Para outbound, los números van al revés:
    # - caller_number = nuestro número (el que llama)
    # - callee_number = el número destino (sip.phoneNumber del participante SIP)
    if outbound_mode:
        outbound_callee = caller_number  # sip.phoneNumber = a quién llamamos
        outbound_caller = called_number or config.agent.phone_number
    else:
        outbound_callee = None
        outbound_caller = None

    # Session handler para tracking
    handler = SessionHandler(
        config=config,
        direction="outbound" if outbound_mode else "inbound",
        caller_number=outbound_caller if outbound_mode else caller_number,
        callee_number=outbound_callee if outbound_mode else called_number,
        room_name=ctx.room.name,
        campaign_id=campaign_id,
        campaign_script=campaign_script,
        memory_contact_id=memory.contact_id if memory else None,
    )

    # ========= BILLING: Start tracking =========
    billing.start_tracking(
        call_id=ctx.room.name,
        agent_id=config.agent.id,
    )

    # ── Filler phrases (solo Pipeline mode) ─────────────────
    # Cuando el usuario termina de hablar y el LLM tarda en responder,
    # reproducimos un filler corto para que no haya silencio.
    _filler_task: asyncio.Task | None = None

    if config.agent.agent_mode != "realtime":
        lang = config.client.language

        @session.on("user_state_changed")
        def _on_user_state_for_filler(ev) -> None:
            nonlocal _filler_task
            if ev.new_state == "listening":
                # Usuario dejó de hablar → programar filler
                async def _maybe_filler() -> None:
                    await asyncio.sleep(FILLER_DELAY_SECONDS)
                    # No disparar si el agente ya está procesando o hablando
                    if session.agent_state in ("thinking", "speaking"):
                        return
                    try:
                        session.say(
                            random_filler(lang),
                            allow_interruptions=True,
                            add_to_chat_ctx=False,
                        )
                    except Exception:
                        pass  # sesión pudo haber cerrado
                _filler_task = asyncio.ensure_future(_maybe_filler())
            elif ev.new_state == "speaking":
                # Usuario empezó a hablar de nuevo → cancelar filler
                if _filler_task and not _filler_task.done():
                    _filler_task.cancel()
                    _filler_task = None

        @session.on("agent_state_changed")
        def _on_agent_state_for_filler(ev) -> None:
            nonlocal _filler_task
            if ev.new_state in ("thinking", "speaking"):
                # Agente procesando o respondiendo → cancelar filler pendiente
                if _filler_task and not _filler_task.done():
                    _filler_task.cancel()
                    _filler_task = None

    # ── Backchanneling (solo Pipeline mode) ─────────────────
    # Mientras el usuario habla largo, emitir "Ajá", "Mjm" para
    # mostrar escucha activa (como haría un humano).
    _backchannel_task: asyncio.Task | None = None

    if config.agent.agent_mode != "realtime":

        def _cancel_backchannel() -> None:
            nonlocal _backchannel_task
            if _backchannel_task and not _backchannel_task.done():
                _backchannel_task.cancel()
                _backchannel_task = None

        @session.on("user_state_changed")
        def _on_user_state_for_backchannel(ev) -> None:
            nonlocal _backchannel_task
            if ev.new_state == "speaking":
                # Usuario empezó a hablar → programar backchannels periódicos
                async def _backchannel_loop() -> None:
                    await asyncio.sleep(BACKCHANNEL_FIRST_DELAY)
                    while True:
                        # No emitir si el agente ya está procesando
                        if session.agent_state in ("thinking", "speaking"):
                            break
                        try:
                            session.say(
                                random_backchannel(lang),
                                allow_interruptions=True,
                                add_to_chat_ctx=False,
                            )
                        except Exception:
                            break  # sesión pudo haber cerrado
                        await asyncio.sleep(BACKCHANNEL_INTERVAL)

                _backchannel_task = asyncio.ensure_future(_backchannel_loop())
            else:
                # Usuario dejó de hablar → cancelar backchannels
                _cancel_backchannel()

        @session.on("agent_state_changed")
        def _on_agent_state_for_backchannel(ev) -> None:
            if ev.new_state in ("thinking", "speaking"):
                _cancel_backchannel()

    # ── Registrar transcripción ─────────────────────────────
    @session.on("user_input_transcribed")
    def on_user_input(ev) -> None:
        if ev.is_final:
            handler.add_transcript_entry("user", ev.transcript)
            # Guardrails: detectar prompt injection
            if guardrails:
                injection = guardrails.check_user_input(ev.transcript)
                if not injection.passed:
                    logger.warning(
                        "Prompt injection detectado: %s", injection.violations
                    )
            # Analizar sentimiento, intent y idioma en background
            if sentiment_analyzer or intent_extractor or language_detector:
                asyncio.ensure_future(_analyze_user_turn(ev.transcript))

    async def _analyze_user_turn(text: str) -> None:
        """Analiza sentimiento, intent e idioma del turno del usuario."""
        # Ejecutar análisis en paralelo
        tasks = []
        task_names = []
        if sentiment_analyzer:
            tasks.append(sentiment_analyzer.analyze_turn(text))
            task_names.append("sentiment")
        if intent_extractor:
            tasks.append(intent_extractor.extract_intent(text))
            task_names.append("intent")
        if language_detector:
            tasks.append(language_detector.detect_turn(text))
            task_names.append("language")

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Mapear resultados por nombre
        result_map = {}
        for name, result in zip(task_names, results):
            if not isinstance(result, Exception):
                result_map[name] = result

        # Language detection: si se decidió un switch, loggear
        if "language" in result_map and result_map["language"]:
            detected_lang = result_map["language"]
            logger.info(
                "Switch de idioma detectado: %s → actualizar pipeline",
                detected_lang,
            )
            # El prompt override se puede inyectar si está configurado
            if language_detector:
                override = language_detector.get_language_prompt_override()
                if override and hasattr(voice_agent, "instructions"):
                    voice_agent.instructions = override
                    logger.info("System prompt actualizado por cambio de idioma")

        # Sentimiento: inyectar directiva si cambió
        sentiment = result_map.get("sentiment")
        if not sentiment_analyzer or sentiment is None:
            return
        directive = sentiment_analyzer.get_empathy_directive()

        # Inyectar directiva emocional al agente si cambió
        if directive and hasattr(voice_agent, "instructions"):
            # Limpiar directiva anterior si existe
            base = voice_agent.instructions
            for marker in ("## ALERTA:", "## ALERT:", "## ALERTA URGENTE:", "## URGENT ALERT:"):
                idx = base.find(marker)
                if idx != -1:
                    base = base[:idx].rstrip()
            voice_agent.instructions = base + directive
            logger.info(
                "Directiva emocional inyectada al prompt (sentiment=%s)",
                sentiment,
            )

        # Auto-transferir si se alcanzó el umbral
        if sentiment_analyzer.should_auto_transfer():
            sentiment_analyzer.mark_transfer_done()
            logger.warning("Auto-transfer por frustración sostenida")
            await session.generate_reply(
                instructions=(
                    "El cliente está muy frustrado. Discúlpate brevemente y "
                    "dile que lo vas a transferir con un supervisor para que "
                    "lo atiendan mejor. Luego usa transfer_to_human."
                )
            )

    @session.on("conversation_item_added")
    def on_conversation_item(ev) -> None:
        try:
            msg = ev.item
            if not isinstance(msg, ChatMessage):
                return
            if msg.role == "assistant" and msg.text_content:
                handler.add_transcript_entry("assistant", msg.text_content)
        except Exception:
            logger.exception("Error procesando conversation_item_added")

    # Cleanup al terminar
    async def on_shutdown() -> None:
        logger.info(
            "Finalizando sesión para '%s/%s'",
            config.client.slug, config.agent.slug,
        )
        # Pasar agent_turns si es modo orquestado
        if is_orchestrated and hasattr(voice_agent, "agent_turns"):
            handler.set_agent_turns(voice_agent.agent_turns)
        # Pasar resúmenes de inteligencia si están activos
        if sentiment_analyzer:
            handler.set_sentiment_summary(
                sentiment_analyzer.get_call_sentiment_summary()
            )
        if intent_extractor:
            handler.set_intent_summary(
                intent_extractor.get_call_intent_summary()
            )
        await handler.finalize(status="completed")

        # Quality scoring async (no bloquea el shutdown)
        if quality_cfg.enabled and len(handler._transcript) >= 2:
            asyncio.create_task(
                _async_quality_score(
                    call_id=handler._transcript,
                    transcript=list(handler._transcript),
                    business_type=config.client.business_type,
                    room_name=ctx.room.name,
                )
            )

        # Billing: consumir créditos por la llamada
        duration = int(
            (datetime.now(timezone.utc) - handler._started_at).total_seconds()
        )
        await billing.finish_call(duration_seconds=duration)

        # Almacenar memoria de largo plazo
        if memory and memory.contact_id and handler._transcript and len(handler._transcript) >= 2:
            try:
                transcript_text = "\n".join(
                    f"{'Cliente' if e['role'] == 'user' else 'Agente'}: {e['text']}"
                    for e in handler._transcript
                )
                await memory.store(
                    transcript=transcript_text,
                    agent_id=config.agent.id,
                    agent_name=config.agent.name,
                    duration_seconds=int(
                        (datetime.now(timezone.utc) - handler._started_at).total_seconds()
                    ),
                )
            except Exception:
                logger.exception("Error almacenando memoria de largo plazo")

    async def _async_quality_score(
        call_id: list,
        transcript: list[dict],
        business_type: str | None,
        room_name: str,
    ) -> None:
        """Ejecuta quality scoring async y guarda en DB."""
        try:
            from agent.db import get_supabase

            result = await score_call_quality(transcript, business_type)
            if result and result.get("quality_score") is not None:
                sb = get_supabase()
                # Buscar el call por room name para actualizar
                calls = (
                    sb.table("calls")
                    .select("id")
                    .eq("livekit_room_name", room_name)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if calls.data:
                    sb.table("calls").update({
                        "quality_score": result["quality_score"],
                    }).eq("id", calls.data[0]["id"]).execute()
                    logger.info(
                        "Quality score guardado: %d para room %s",
                        result["quality_score"],
                        room_name,
                    )
        except Exception:
            logger.exception("Error en quality scoring async")

    ctx.add_shutdown_callback(on_shutdown)

    # Iniciar sesión
    await session.start(
        room=ctx.room,
        agent=voice_agent,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )

    # Saludo inicial
    if outbound_mode:
        await session.generate_reply(
            instructions="Saluda al usuario e identifícate. Recuerda que TÚ estás llamando al cliente."
        )
    elif hasattr(voice_agent, '_flow_engine') and hasattr(voice_agent, '_flow_state'):
        # Modo flow: usar greeting del nodo Start
        flow_greeting = voice_agent.flow_engine.get_greeting(voice_agent.flow_state)
        await session.generate_reply(
            instructions=f"Saluda al usuario con: {flow_greeting}"
        )
    elif memory and memory.contact_id and not memory._is_new_contact and memory.contact and memory.contact.get("name"):
        contact_name = memory.contact["name"].split()[0]  # Primer nombre
        await session.generate_reply(
            instructions=(
                f"Este es un cliente que ya conoces. Se llama {memory.contact['name']}. "
                f"Salúdalo de forma cálida y personal, por ejemplo: "
                f"'¡Qué gusto saludarle, {contact_name}! ¿En qué puedo ayudarle hoy?' "
                f"NO digas tu nombre ni te presentes, ya te conoce. Sé breve y natural."
            )
        )
    else:
        await session.generate_reply(instructions=f"Saluda al usuario con: {config.agent.greeting}")


if __name__ == "__main__":
    agents.cli.run_app(server)
