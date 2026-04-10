"""Entrypoint del agente de voz LiveKit.

Un solo worker que se adapta dinámicamente por llamada,
cargando la configuración del agente + cliente desde Supabase.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import os
import signal
from datetime import datetime, timezone

import sentry_sdk
from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import AgentSession, AgentServer, room_io
from livekit.agents.llm import ChatMessage
from livekit.plugins import silero, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from agent.agent_factory import build_agent, build_orchestrated_agent
from agent.billing import CallBilling
from agent.call_lifecycle import CallLifecycleTracker
from agent.hook_engine import HookAction, HookContext, HookEngine, load_hooks_for_agent
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
from agent.pipeline_builder import build_gemini_live_model, build_llm, build_realtime_model, build_stt, build_tts
from agent.session_handler import SessionHandler
from agent.voice_quality import (
    BACKCHANNEL_FIRST_DELAY,
    BACKCHANNEL_INTERVAL,
    FILLER_DELAY_SECONDS,
    random_backchannel,
    random_filler,
)

load_dotenv()


# Sentry — error tracking para el agente de voz
_sentry_dsn = os.environ.get("SENTRY_DSN", "")
if _sentry_dsn:
    sentry_sdk.init(
        dsn=_sentry_dsn,
        environment=os.environ.get("SENTRY_ENV", "production"),
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_RATE", "0.1")),
        send_default_pii=False,
        release=f"voiceai-agent@{os.environ.get('LIVEKIT_AGENT_VERSION', 'dev')}",
    )

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(lk_room)s] %(name)s — %(message)s",
)
# ContextVar para almacenar el room name por tarea async (thread-safe para llamadas concurrentes)
_current_room: contextvars.ContextVar[str] = contextvars.ContextVar("_current_room", default="-")

# Factory que inyecta lk_room en cada log record (NO usar "room" — conflicto con livekit SDK)
# Se setea UNA VEZ a nivel de módulo; lee el room de la ContextVar por tarea.
_old_factory = logging.getLogRecordFactory()


def _record_factory(*args: object, **kwargs: object) -> logging.LogRecord:
    record = _old_factory(*args, **kwargs)
    record.lk_room = _current_room.get("-")  # type: ignore[attr-defined]
    return record


logging.setLogRecordFactory(_record_factory)
logger = logging.getLogger("voice-ai")

server = AgentServer()

# Conjunto para mantener referencias a tasks en background y evitar GC prematuro
_bg_tasks: set[asyncio.Task] = set()

# ── Graceful SIGTERM handler ────────────────────────────
_shutting_down = False


def _handle_sigterm(signum: int, frame: object) -> None:
    """Maneja SIGTERM para drain graceful de llamadas activas."""
    global _shutting_down
    _shutting_down = True
    logger.info("SIGTERM received — draining active calls...")


signal.signal(signal.SIGTERM, _handle_sigterm)


@server.rtc_session(agent_name="voice-ai-platform")
async def entrypoint(ctx: agents.JobContext) -> None:
    """Punto de entrada para cada llamada."""
    await ctx.connect(auto_subscribe=agents.AutoSubscribe.AUDIO_ONLY)

    # Setear lk_room como correlation ID para todos los logs de esta llamada
    _current_room.set(ctx.room.name)

    logger.info("Nueva sesión en room: %s", ctx.room.name)

    # Esperar al participante SIP
    caller_number: str | None = None
    called_number: str | None = None
    _sip_connected = asyncio.Event()

    def on_participant_connected(participant: rtc.RemoteParticipant) -> None:
        nonlocal caller_number, called_number
        if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
            caller_number = participant.attributes.get("sip.phoneNumber")
            called_number = participant.attributes.get("sip.trunkPhoneNumber")
            _sip_connected.set()
            logger.info(
                "SIP participante conectado: caller=%s, called=%s",
                caller_number,
                called_number,
            )

    ctx.room.on("participant_connected", on_participant_connected)

    # Verificar participantes ya conectados
    for p in ctx.room.remote_participants.values():
        if p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
            caller_number = p.attributes.get("sip.phoneNumber")
            called_number = p.attributes.get("sip.trunkPhoneNumber")
            _sip_connected.set()
            break

    # Si no hay SIP (ej: test desde web), esperar un momento
    if not _sip_connected.is_set():
        await asyncio.sleep(2)
        for p in ctx.room.remote_participants.values():
            if p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
                caller_number = p.attributes.get("sip.phoneNumber")
                called_number = p.attributes.get("sip.trunkPhoneNumber")
                _sip_connected.set()
                break

    # Detectar modo outbound desde metadata del room
    outbound_mode = False
    campaign_script: str | None = None
    outbound_client_id: str | None = None
    outbound_agent_id: str | None = None
    campaign_id: str | None = None
    callback_context: str | None = None
    callback_id: str | None = None
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
            elif meta.get("type") == "callback":
                outbound_mode = True
                outbound_client_id = meta.get("client_id")
                outbound_agent_id = meta.get("agent_id")
                callback_context = meta.get("callback_context", "")
                callback_id = meta.get("callback_id")
                # NO setear campaign_script — eso reemplaza todo el prompt del agente.
                # El contexto del callback se inyecta como ADICIÓN al prompt original.
                logger.info(
                    "Modo callback detectado, callback_id: %s, agent_id: %s",
                    callback_id, outbound_agent_id,
                )
        except (json.JSONDecodeError, AttributeError):
            pass

    # Detectar modo widget desde metadata del room o participante
    widget_mode = False
    widget_agent_id: str | None = None
    if not outbound_mode and not called_number:
        # Intentar leer agent_id del room metadata (widget pre-creates room)
        if room_metadata:
            try:
                meta = json.loads(room_metadata)
                if meta.get("type") == "widget" and meta.get("agent_id"):
                    widget_mode = True
                    widget_agent_id = meta["agent_id"]
                    logger.info("Modo widget detectado, agent_id: %s", widget_agent_id)
            except (json.JSONDecodeError, AttributeError):
                pass
        # Fallback: leer del metadata del participante
        if not widget_mode:
            for p in ctx.room.remote_participants.values():
                p_meta = p.metadata or ""
                if p_meta:
                    try:
                        pm = json.loads(p_meta)
                        if pm.get("type") == "widget" and pm.get("agent_id"):
                            widget_mode = True
                            widget_agent_id = pm["agent_id"]
                            logger.info("Modo widget (participant meta), agent_id: %s", widget_agent_id)
                            break
                    except (json.JSONDecodeError, AttributeError):
                        pass

    # ── Inicializar lifecycle tracker ──
    direction = "outbound" if outbound_mode else "inbound"
    lifecycle = CallLifecycleTracker(room_name=ctx.room.name, direction=direction)
    lifecycle.add_event("call_initiated", {
        "direction": direction,
        "outbound_mode": outbound_mode,
        "widget_mode": widget_mode,
    })

    # Si el SIP ya estaba conectado (inbound), registrar el evento
    if _sip_connected.is_set():
        lifecycle.record_sip_connected(caller_number, called_number)

    # Listener: detectar cuando el SIP participant se desconecta (persona colgó)
    def on_participant_disconnected(participant: rtc.RemoteParticipant) -> None:
        if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
            # Capturar disconnect_reason de LiveKit SIP
            # Valores posibles: USER_UNAVAILABLE, USER_REJECTED, SIP_TRUNK_FAILURE
            sip_disconnect = ""
            try:
                sip_disconnect = str(participant.disconnect_reason) if hasattr(participant, 'disconnect_reason') else ""
            except Exception:
                pass

            # Capturar sip.callStatus si disponible
            sip_call_status = participant.attributes.get("sip.callStatus", "")

            # Mapear SIP reasons a nuestro sistema
            if "REJECTED" in sip_disconnect.upper() or "BUSY" in sip_disconnect.upper():
                lifecycle.add_event("sip_rejected", {
                    "sip_reason": sip_disconnect,
                    "sip_call_status": sip_call_status,
                })
                if not lifecycle._disconnect_reason:
                    lifecycle._disconnect_reason = "busy"
                    lifecycle._disconnect_by = "caller"
            elif "UNAVAILABLE" in sip_disconnect.upper():
                lifecycle.add_event("sip_unavailable", {
                    "sip_reason": sip_disconnect,
                })
                if not lifecycle._disconnect_reason:
                    lifecycle._disconnect_reason = "no_answer"
                    lifecycle._disconnect_by = "system"
            elif "TRUNK_FAILURE" in sip_disconnect.upper() or "FAILURE" in sip_disconnect.upper():
                lifecycle.record_error(f"SIP trunk failure: {sip_disconnect}", category="sip")
            else:
                lifecycle.record_sip_disconnected(
                    identity=participant.identity,
                    reason=sip_disconnect,
                )

            logger.info(
                "SIP participant desconectado: %s (identity=%s, reason=%s, callStatus=%s)",
                participant.name, participant.identity, sip_disconnect, sip_call_status,
            )

    ctx.room.on("participant_disconnected", on_participant_disconnected)

    # Cargar config del agente + cliente
    config: ResolvedConfig | None = None
    if outbound_mode:
        # Outbound: preferir agent_id, fallback a client_id
        if outbound_agent_id:
            config = await load_config_by_agent_id(outbound_agent_id)
        if not config and outbound_client_id:
            config = await load_config_by_client_id(outbound_client_id)
    elif widget_mode and widget_agent_id:
        config = await load_config_by_agent_id(widget_agent_id)
        if config:
            logger.info("Widget: agente '%s' cargado", config.agent.name)
    elif called_number:
        config = await load_config_by_phone(called_number)

    if not config:
        logger.error(
            "No se encontró agente para número '%s' / widget_agent='%s' / outbound_agent='%s'. "
            "Rechazando llamada — no se puede procesar sin config válida.",
            called_number, widget_agent_id, outbound_agent_id,
        )
        return

    # ========= SIGTERM: rechazar llamadas si estamos en shutdown =========
    if _shutting_down:
        logger.info("Rejecting call — worker shutting down")
        return

    # ========= PA: CALLER WHITELIST CHECK =========
    if config.agent.agent_category == "personal_assistant":
        if not caller_number:
            logger.warning("PA agent '%s' — no caller number, rejecting", config.agent.slug)
            return
        from agent.db import get_supabase as _get_sb
        _sb = _get_sb()
        try:
            auth_result = await asyncio.to_thread(
                lambda: _sb.table("pa_authorized_callers")
                .select("id")
                .eq("agent_id", config.agent.id)
                .eq("phone_number", caller_number)
                .limit(1)
                .execute()
            )
            if not auth_result.data:
                # Intentar sin prefijo/con prefijo (normalización básica)
                normalized = caller_number.lstrip("+")
                auth_result2 = await asyncio.to_thread(
                    lambda: _sb.table("pa_authorized_callers")
                    .select("id")
                    .ilike("phone_number", f"%{normalized[-10:]}")
                    .eq("agent_id", config.agent.id)
                    .limit(1)
                    .execute()
                )
                if not auth_result2.data:
                    logger.warning(
                        "PA agent '%s' — unauthorized caller %s",
                        config.agent.slug, caller_number,
                    )
                    return
        except Exception:
            logger.exception("Error checking PA authorization — rejecting for safety")
            return

    # ========= CONCURRENT CALL LIMIT =========
    from agent.db import get_supabase
    sb = get_supabase()
    try:
        active = await asyncio.to_thread(
            lambda: sb.table("active_calls")
            .select("id", count="exact")
            .eq("client_id", config.client.id)
            .execute()
        )
        active_count = active.count or 0
    except Exception:
        logger.exception("Error checking concurrent calls — allowing call")
        active_count = 0
    max_concurrent = config.client.max_concurrent_calls

    if active_count >= max_concurrent:
        logger.warning(
            "Client %s exceeded concurrent call limit (%d/%d)",
            config.client.slug, active_count, max_concurrent,
        )
        # Reproducir mensaje de capacidad antes de colgar
        try:
            from livekit.plugins import cartesia
            reject_tts = cartesia.TTS(model="sonic-3")
            session_reject = AgentSession(vad=silero.VAD.load(), tts=reject_tts)
            await session_reject.start(room=ctx.room)
            await session_reject.say(
                "Lo sentimos, en este momento todas nuestras líneas están ocupadas. "
                "Por favor intente de nuevo en unos minutos. Gracias.",
                allow_interruptions=False,
            )
            await asyncio.sleep(1.5)
        except Exception:
            logger.exception("Error playing capacity limit message")
        return

    # ========= BILLING: Check ANTES de atender =========
    billing = CallBilling(config.client.id)
    try:
        credit_check = await billing.check_can_take_call()
    except Exception:
        logger.exception("Error checking billing — allowing call")
        credit_check = {"allowed": True, "balance": 0, "reason": "check_failed"}

    if not credit_check["allowed"]:
        logger.warning("Client %s no credits, rejecting call", config.client.id)
        # Intentar reproducir mensaje antes de colgar
        try:
            from livekit.plugins import cartesia
            reject_tts = cartesia.TTS(model="sonic-3")
            session_reject = AgentSession(vad=silero.VAD.load(), tts=reject_tts)
            await session_reject.start(room=ctx.room)
            await session_reject.say(
                "Lo sentimos, en este momento no podemos atender tu llamada. "
                "Por favor comunícate directamente al número del negocio. Gracias.",
                allow_interruptions=False,
            )
            await asyncio.sleep(1.5)
        except Exception:
            logger.exception("Error playing rejection message")
        return

    # Registrar llamada activa (después de pasar validaciones de concurrencia y créditos)
    try:
        sb.table("active_calls").insert({
            "client_id": config.client.id,
            "agent_id": config.agent.id,
            "room_name": ctx.room.name,
        }).execute()
    except Exception:
        logger.exception("Error registering active call — continuing anyway")

    # ========= RECORDING: Start egress if R2 configured =========
    recording_egress_id: str | None = None
    recording_key: str | None = None
    if os.environ.get("R2_ACCESS_KEY_ID"):
        try:
            from livekit.api import (
                LiveKitAPI,
                RoomCompositeEgressRequest,
                EncodedFileOutput,
                EncodedFileType,
                S3Upload,
            )

            lk_api = LiveKitAPI()
            s3_upload = S3Upload(
                access_key=os.environ["R2_ACCESS_KEY_ID"],
                secret=os.environ["R2_SECRET_ACCESS_KEY"],
                bucket=os.environ.get("R2_BUCKET", "voiceai-recordings"),
                endpoint=os.environ["R2_ENDPOINT"],
                region="auto",
                force_path_style=True,
            )

            recording_key = f"{config.client.id}/{config.agent.id}/{ctx.room.name}.ogg"

            egress_request = RoomCompositeEgressRequest(
                room_name=ctx.room.name,
                file_outputs=[EncodedFileOutput(
                    file_type=EncodedFileType.OGG,
                    filepath=recording_key,
                    s3=s3_upload,
                )],
                audio_only=True,
            )
            egress_info = await lk_api.egress.start_room_composite_egress(
                egress_request
            )
            recording_egress_id = egress_info.egress_id
            logger.info(
                "Recording started: egress_id=%s, key=%s",
                recording_egress_id, recording_key,
            )
            await lk_api.aclose()
        except Exception:
            logger.exception("Failed to start recording — continuing without it")
            recording_egress_id = None
            recording_key = None

    # Override del system prompt para outbound con script de campaña
    if outbound_mode and campaign_script:
        from dataclasses import replace
        updated_agent = replace(config.agent, system_prompt=campaign_script)
        config = ResolvedConfig(agent=updated_agent, client=config.client)

    # ── PARALLELIZAR carga de recursos (latency optimization) ──
    # En vez de 4 awaits secuenciales (~4-8s), cargamos todo en paralelo (~1-2s)
    # Cada loader tiene su propio try/except + retry para no crashear la llamada
    async def _load_with_retry(name: str, coro_fn, default, max_retries: int = 2):
        """Ejecuta coro_fn con retry. Si falla, retorna default en vez de crashear."""
        for attempt in range(max_retries + 1):
            try:
                return await coro_fn()
            except Exception:
                if attempt < max_retries:
                    wait = 0.5 * (attempt + 1)
                    logger.warning(
                        "Retry %d/%d cargando %s (esperando %.1fs)",
                        attempt + 1, max_retries, name, wait,
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.exception("Error cargando %s tras %d intentos — continuando sin datos", name, max_retries + 1)
                    return default

    async def _load_mcp() -> list[dict]:
        return await _load_with_retry(
            "MCP servers",
            lambda: load_mcp_servers(config.client.id, config.agent.id),
            [],
        )

    async def _load_apis() -> list[dict]:
        return await _load_with_retry(
            "API integrations",
            lambda: load_api_integrations(config.client.id, config.agent.id),
            [],
        )

    async def _load_hooks_task() -> list:
        return await _load_with_retry(
            "hooks",
            lambda: load_hooks_for_agent(config.agent.id),
            [],
        )

    async def _load_memory() -> tuple[AgentMemory | None, str]:
        contact_phone = caller_number
        if not contact_phone:
            return None, ""
        try:
            channel = "outbound_call" if outbound_mode else "call"
            mem = AgentMemory(config.client.id, channel=channel)
            await mem.identify(contact_phone, "phone")
            ctx = mem.build_memory_context()
            return mem, ctx
        except Exception:
            logger.exception("Error cargando memoria, continuando sin contexto")
            return None, ""

    # Ejecutar TODO en paralelo — cada uno es resiliente individualmente
    mcp_configs, api_integrations, hook_defs, (memory, memory_context) = await asyncio.gather(
        _load_mcp(), _load_apis(), _load_hooks_task(), _load_memory(),
    )

    mcp_servers = build_mcp_servers(mcp_configs) if mcp_configs else None
    if mcp_servers:
        logger.info("MCP: %d servidor(es)", len(mcp_servers))
    if api_integrations:
        logger.info("API integrations: %d", len(api_integrations))

    hook_engine: HookEngine | None = None
    if hook_defs:
        hook_engine = HookEngine(hook_defs)
        logger.info("Hooks: %d", len(hook_defs))
    if memory and memory_context:
        logger.info("Memoria: %d memorias", len(memory.memories))

    # Hook: OnConversationStart — evaluar antes de construir el agente
    if hook_engine and hook_engine.has_hooks_for("OnConversationStart"):
        try:
            hctx = HookContext(
                event="OnConversationStart",
                channel="voice",
                agent_id=config.agent.id,
                client_id=config.client.id,
                caller_phone=caller_number,
                contact_name=memory.contact.get("name") if memory and memory.contact else None,
                metadata={
                    "direction": "outbound" if outbound_mode else "inbound",
                    "widget_mode": widget_mode,
                },
            )
            start_results = await hook_engine.evaluate("OnConversationStart", hctx)
            for r in start_results:
                if r.action == HookAction.BLOCK:
                    logger.info("Hook OnConversationStart bloqueó la llamada: %s", r.message)
                    return
            # Inyectar contexto extra al memory_context
            extra = hook_engine.collect_context(start_results)
            if extra:
                memory_context = (memory_context + "\n\n" + extra).strip()
                logger.info("Hook OnConversationStart inyectó contexto adicional")
        except Exception:
            logger.exception("Error en hooks OnConversationStart")

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
    try:
        if (
            not outbound_mode
            and config.client.orchestration_mode == "intelligent"
        ):
            # Modo inteligente: cargar todos los agentes del cliente
            try:
                all_configs = await load_orchestrated_configs(config.client.id)
            except Exception:
                logger.exception("Error cargando orchestrated configs — usando modo simple")
                all_configs = []
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
                    language_detector=language_detector,
                )
                logger.info(
                    "Modo inteligente solicitado pero solo %d agente(s), usando simple",
                    len(all_configs),
                )
        else:
            voice_agent = build_agent(
                config, memory_context=memory_context,
                mcp_servers=mcp_servers, api_integrations=api_integrations,
                language_detector=language_detector,
            )
    except Exception:
        logger.exception(
            "Error crítico construyendo agente '%s/%s' — intentando agente minimal",
            config.client.slug, config.agent.slug,
        )
        # Fallback: construir agente mínimo sin MCP ni integraciones
        try:
            voice_agent = build_agent(
                config, memory_context="",
                mcp_servers=None, api_integrations=[],
                language_detector=None,
            )
        except Exception:
            logger.exception("Error fatal construyendo agente minimal — abortando llamada")
            return

    # Inyectar hook engine al agente para PreToolCall/PostToolCall
    if hook_engine and hasattr(voice_agent, "_hook_engine"):
        voice_agent._hook_engine = hook_engine
        voice_agent._hook_channel = "voice"
        logger.info("Hook engine inyectado al agente de voz")

    # Inyectar datos de la llamada al agente para que los tools accedan vía self
    if hasattr(voice_agent, "_caller_phone"):
        voice_agent._caller_phone = caller_number or ""
        voice_agent._memory_contact_id = memory.contact_id if memory else None
        logger.info(
            "Context inyectado al agente: phone=%s, contact_id=%s",
            voice_agent._caller_phone,
            voice_agent._memory_contact_id,
        )

    # Inyectar contexto SIP para transferencia de llamadas
    if hasattr(voice_agent, "_room_name"):
        voice_agent._room_name = ctx.room.name
        # Buscar identity del participante SIP (caller)
        sip_identity = ""
        for p in ctx.room.remote_participants.values():
            if p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
                sip_identity = p.identity
                break
        voice_agent._sip_participant_identity = sip_identity
        logger.info(
            "SIP transfer context: room=%s, participant=%s",
            ctx.room.name,
            sip_identity,
        )

    # Inyectar lifecycle tracker al agente para que transfer_to_human lo use
    if hasattr(voice_agent, "_lifecycle"):
        voice_agent._lifecycle = lifecycle

    # Filtrar tools deshabilitados del schema visible al LLM
    # Gemini Live no soporta update_tools/update_chat_ctx — skip filter
    if config.agent.agent_mode != "gemini_live" and hasattr(voice_agent, "filter_disabled_tools"):
        await voice_agent.filter_disabled_tools()

    # Configurar pipeline de voz (BYOK)
    stt_language = "es" if config.client.language in ("es", "es-en") else "en"
    # Multi-idioma: pasar idiomas soportados al STT si detección está habilitada
    stt_multi_lang: list[str] | None = None
    if lang_cfg.enabled:
        stt_multi_lang = lang_cfg.supported_languages

    vad = silero.VAD.load(
        activation_threshold=0.5,
        min_speech_duration=0.1,
        min_silence_duration=0.4,
        sample_rate=8000,
    )

    try:
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
                max_endpointing_delay=3.0,
                min_interruption_duration=0.6,
                min_interruption_words=1,
            )
        elif config.agent.agent_mode == "gemini_live":
            logger.info(
                "Modo Gemini Live: model=%s, voice=%s, thinking=%s",
                config.agent.gemini_live_model,
                config.agent.gemini_live_voice,
                config.agent.gemini_live_thinking_level,
            )
            session = AgentSession(
                llm=build_gemini_live_model(config.agent),
                vad=vad,
                turn_detection=MultilingualModel(),
                min_endpointing_delay=0.5,
                max_endpointing_delay=3.0,
                min_interruption_duration=0.6,
                min_interruption_words=1,
            )
        else:
            logger.info(
                "Modo pipeline: stt=%s, llm=%s, tts=%s",
                config.agent.stt_provider, config.agent.llm_provider, config.agent.tts_provider,
            )
            session = AgentSession(
                stt=build_stt(config.agent, stt_language, multi_lang=stt_multi_lang),
                llm=build_llm(config.agent),
                tts=build_tts(config.agent, stt_language),
                vad=vad,
                turn_detection=MultilingualModel(),
                min_endpointing_delay=0.5,
                max_endpointing_delay=3.0,
                min_interruption_duration=0.6,
                min_interruption_words=1,
            )
    except Exception:
        logger.exception(
            "Error construyendo pipeline de voz — intentando con defaults"
        )
        # Fallback: pipeline con providers por defecto (sin BYOK keys)
        try:
            from livekit.plugins import cartesia, deepgram, google
            session = AgentSession(
                stt=deepgram.STT(language=stt_language),
                llm=google.LLM(model="gemini-2.5-flash"),
                tts=cartesia.TTS(model="sonic-3"),
                vad=vad,
                turn_detection=MultilingualModel(),
                min_endpointing_delay=0.5,
                max_endpointing_delay=3.0,
                min_interruption_duration=0.6,
                min_interruption_words=1,
            )
        except Exception:
            logger.exception("Error fatal construyendo pipeline default — abortando")
            return

    # Log detallado del pipeline para debugging de BYOK keys
    logger.info(
        "Pipeline config: stt=%s (byok=%s), llm=%s (byok=%s), tts=%s (byok=%s)",
        config.agent.stt_provider, bool(config.agent.stt_api_key),
        config.agent.llm_provider, bool(config.agent.llm_api_key),
        config.agent.tts_provider, bool(config.agent.tts_api_key),
    )

    # Para outbound, los números van al revés:
    # - caller_number = nuestro número (el que llama)
    # - callee_number = el número destino (sip.phoneNumber del participante SIP)
    # NOTA: en outbound los números pueden estar vacíos aquí (SIP participant aún
    # no conectado). Se actualizan después de esperar la conexión (ver más abajo).
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
        recording_key=recording_key,
        lifecycle=lifecycle,
    )

    # Inyectar session handler y origin call ID para scheduled callbacks
    if hasattr(voice_agent, "_session_handler"):
        voice_agent._session_handler = handler
        voice_agent._origin_call_id = None

    # Inyectar métricas de uso para conteo real de TTS/LLM
    # (handler debe existir antes de esta línea)
    if hasattr(voice_agent, "_usage_metrics"):
        voice_agent._usage_metrics = handler.usage
        logger.info("UsageMetrics inyectadas al agente para conteo de TTS/LLM")

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

    # ── Inactivity timer (hooks OnInactivity) ─────────────────
    _inactivity_task: asyncio.Task | None = None

    if hook_engine and hook_engine.has_hooks_for("OnInactivity"):
        # Extraer umbrales de silencio de los hooks configurados
        _inactivity_thresholds: list[float] = []
        for h in hook_engine.hooks:
            if h.hook_event == "OnInactivity" and (h.channel is None or h.channel == "voice"):
                for cond in h.config.get("conditions", []):
                    if cond.get("field") in ("silence_seconds", "inactive_minutes"):
                        try:
                            val = float(cond.get("value", 0))
                            if cond["field"] == "inactive_minutes":
                                val *= 60
                            if val > 0:
                                _inactivity_thresholds.append(val)
                        except (ValueError, TypeError):
                            pass
        # Fallback: si no hay umbrales explícitos, usar 5s
        if not _inactivity_thresholds:
            _inactivity_thresholds = [5.0]
        _inactivity_thresholds.sort()
        _min_threshold = _inactivity_thresholds[0]

        async def _check_inactivity_progressive() -> None:
            """Timer progresivo que evalúa hooks en cada umbral de silencio."""
            elapsed = 0.0
            try:
                for threshold in _inactivity_thresholds:
                    wait = threshold - elapsed
                    if wait > 0:
                        await asyncio.sleep(wait)
                    elapsed = threshold

                    hctx = HookContext(
                        event="OnInactivity",
                        channel="voice",
                        agent_id=config.agent.id,
                        client_id=config.client.id,
                        silence_seconds=elapsed,
                        caller_phone=caller_number,
                        transcript=list(handler._transcript),
                    )
                    results = await hook_engine.evaluate("OnInactivity", hctx)
                    should_close = False
                    for r in results:
                        if r.action == HookAction.SPEAK and r.message:
                            await session.generate_reply(
                                instructions=f"Dile al usuario: {r.message}"
                            )
                        elif r.action == HookAction.CLOSE_SESSION and r.message:
                            await session.generate_reply(
                                instructions=f"Despídete diciendo: {r.message}"
                            )
                            await asyncio.sleep(3)
                            should_close = True
                    if should_close:
                        break
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Error en hooks OnInactivity")

        def _reset_inactivity_timer() -> None:
            nonlocal _inactivity_task
            if _inactivity_task and not _inactivity_task.done():
                _inactivity_task.cancel()
            _inactivity_task = asyncio.ensure_future(_check_inactivity_progressive())

        @session.on("user_input_transcribed")
        def _on_input_reset_inactivity(ev) -> None:
            if ev.is_final:
                _reset_inactivity_timer()

        @session.on("agent_state_changed")
        def _on_agent_reset_inactivity(ev) -> None:
            if ev.new_state == "speaking":
                _reset_inactivity_timer()

        # Iniciar timer al comenzar la sesión
        _reset_inactivity_timer()

    # ── Registrar transcripción ─────────────────────────────
    @session.on("user_input_transcribed")
    def on_user_input(ev) -> None:
        if ev.is_final:
            handler.add_transcript_entry("user", ev.transcript)
            lifecycle.record_user_speech()
            # Guardrails: detectar prompt injection y escalada de molestia
            if guardrails:
                injection = guardrails.check_user_input(ev.transcript)
                if not injection.passed:
                    logger.warning(
                        "Prompt injection detectado: %s", injection.violations
                    )
                # Detectar molestia real → cierre graceful inmediato
                escalation = guardrails.check_escalation(ev.transcript)
                if not escalation.passed:
                    logger.warning(
                        "Escalada de molestia detectada: %s", escalation.violations
                    )
                    if config.agent.agent_mode != "gemini_live":
                        asyncio.ensure_future(session.generate_reply(
                            instructions=(
                                "CIERRE INMEDIATO: El usuario está molesto y pidió que dejes de llamar. "
                                "Discúlpate brevemente y con respeto. Di que no volverás a llamar. "
                                "NO insistas, NO ofrezcas nada más. Despídete y termina."
                            )
                        ))
                    # Auto-DNC: agregar número a lista de no-llamar
                    _dnc_phone = caller_number if not outbound_mode else handler._callee_number
                    if _dnc_phone and outbound_mode:
                        try:
                            _sb_dnc = get_supabase()
                            _sb_dnc.table("dnc_entries").upsert({
                                "client_id": config.client.id,
                                "phone": _dnc_phone,
                                "reason": f"Escalada detectada: {escalation.violations[0]}",
                                "source": "escalation",
                            }, on_conflict="client_id,phone").execute()
                            logger.info("Auto-DNC: %s agregado a lista", _dnc_phone)
                        except Exception:
                            logger.exception("Error auto-DNC")
                    # Hook: OnGuardrailHit
                    if hook_engine and hook_engine.has_hooks_for("OnGuardrailHit"):
                        task = asyncio.ensure_future(_eval_guardrail_hit_hooks(
                            ev.transcript, injection.violations
                        ))
                        _bg_tasks.add(task)
                        task.add_done_callback(_bg_tasks.discard)
            # Hook: OnUserMessage — evaluar reglas sobre input del usuario
            if hook_engine and hook_engine.has_hooks_for("OnUserMessage"):
                task = asyncio.ensure_future(_eval_user_message_hooks(ev.transcript))
                _bg_tasks.add(task)
                task.add_done_callback(_bg_tasks.discard)
            # Inyectar elapsed time al LLM cada 5 turnos del usuario
            _user_turns = lifecycle._user_turns
            if _user_turns > 0 and _user_turns % 5 == 0 and config.agent.agent_mode != "gemini_live":
                _elapsed = int((datetime.now(timezone.utc) - handler._started_at).total_seconds())
                _elapsed_min = _elapsed // 60
                _elapsed_sec = _elapsed % 60
                _time_ctx = f"\n\n[Contexto: llevas {_elapsed_min}:{_elapsed_sec:02d} minutos en la llamada.]"
                if hasattr(voice_agent, "_instructions"):
                    # Limpiar contexto temporal anterior
                    base = voice_agent.instructions
                    idx = base.find("[Contexto: llevas ")
                    if idx != -1:
                        base = base[:idx].rstrip()
                    voice_agent._instructions = base + _time_ctx

            # Analizar sentimiento, intent y idioma en background
            if sentiment_analyzer or intent_extractor or language_detector:
                task = asyncio.ensure_future(_analyze_user_turn(ev.transcript))
                task.add_done_callback(
                    lambda t: t.exception() and logger.error("_analyze_user_turn failed: %s", t.exception())
                    if not t.cancelled() and t.exception() else None
                )

    async def _eval_user_message_hooks(text: str) -> None:
        """Evalúa hooks OnUserMessage y aplica acciones."""
        if not hook_engine:
            return
        try:
            hctx = HookContext(
                event="OnUserMessage",
                channel="voice",
                agent_id=config.agent.id,
                client_id=config.client.id,
                user_text=text,
                caller_phone=caller_number,
                transcript=list(handler._transcript),
            )
            results = await hook_engine.evaluate("OnUserMessage", hctx)
            # Inyectar contexto adicional al prompt del agente
            extra_ctx = hook_engine.collect_context(results)
            if extra_ctx and hasattr(voice_agent, "_instructions"):
                base = voice_agent.instructions
                # Agregar contexto temporal (se limpia en el siguiente turno)
                voice_agent._instructions = base + f"\n\n## Contexto hooks:\n{extra_ctx}"
                logger.info("Hook OnUserMessage inyectó contexto al prompt")
        except Exception:
            logger.exception("Error en hooks OnUserMessage")

    async def _eval_guardrail_hit_hooks(text: str, violations: list) -> None:
        """Evalúa hooks OnGuardrailHit cuando se detecta una violación."""
        if not hook_engine:
            return
        try:
            hctx = HookContext(
                event="OnGuardrailHit",
                channel="voice",
                agent_id=config.agent.id,
                client_id=config.client.id,
                user_text=text,
                caller_phone=caller_number,
                metadata={"violations": violations},
            )
            results = await hook_engine.evaluate("OnGuardrailHit", hctx)
            extra = hook_engine.collect_context(results)
            if extra and hasattr(voice_agent, "_instructions"):
                voice_agent._instructions = voice_agent.instructions + f"\n\n{extra}"
            notifications = hook_engine.collect_notifications(results)
            for notif in notifications:
                task = asyncio.ensure_future(_send_hook_notification(notif))
                _bg_tasks.add(task)
                task.add_done_callback(_bg_tasks.discard)
        except Exception:
            logger.exception("Error en hooks OnGuardrailHit")

    async def _analyze_user_turn(text: str) -> None:
        """Analiza sentimiento, intent e idioma del turno del usuario."""
        try:
            await _analyze_user_turn_inner(text)
        except Exception:
            logger.exception("Error in _analyze_user_turn")

    async def _analyze_user_turn_inner(text: str) -> None:
        """Lógica interna de análisis — envuelta en try/except por el caller."""
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

        # Language detection: si se decidió un switch, aplicar cambio de idioma
        if "language" in result_map and result_map["language"]:
            detected_lang = result_map["language"]
            previous_lang = voice_agent.current_language if hasattr(voice_agent, "current_language") else None
            logger.info(
                "Switch de idioma detectado: %s → actualizando pipeline",
                detected_lang,
            )
            # Hook: OnLanguageSwitch
            if hook_engine and hook_engine.has_hooks_for("OnLanguageSwitch"):
                try:
                    hctx = HookContext(
                        event="OnLanguageSwitch",
                        channel="voice",
                        agent_id=config.agent.id,
                        client_id=config.client.id,
                        language=detected_lang,
                        previous_language=previous_lang,
                        user_text=text,
                        caller_phone=caller_number,
                    )
                    await hook_engine.evaluate("OnLanguageSwitch", hctx)
                except Exception:
                    logger.exception("Error en hooks OnLanguageSwitch")

            # Aplicar switch de TTS + prompt override via VoiceAgent
            if hasattr(voice_agent, "switch_language"):
                voice_agent.switch_language(detected_lang)
                logger.info("Pipeline actualizado a idioma: %s", detected_lang)
            else:
                # Fallback para OrchestratorAgent u otros tipos
                if language_detector:
                    override = language_detector.get_language_prompt_override()
                    if override and hasattr(voice_agent, "_instructions"):
                        voice_agent._instructions = override
                        logger.info("System prompt actualizado por cambio de idioma")

        # Sentimiento: inyectar directiva si cambió
        sentiment = result_map.get("sentiment")
        if not sentiment_analyzer or sentiment is None:
            return

        # Hook: OnSentimentShift
        if hook_engine and hook_engine.has_hooks_for("OnSentimentShift"):
            try:
                prev = sentiment_analyzer.previous_sentiment if hasattr(sentiment_analyzer, "previous_sentiment") else None
                hctx = HookContext(
                    event="OnSentimentShift",
                    channel="voice",
                    agent_id=config.agent.id,
                    client_id=config.client.id,
                    sentiment=str(sentiment),
                    previous_sentiment=str(prev) if prev else None,
                    sentiment_score=sentiment_analyzer.current_score if hasattr(sentiment_analyzer, "current_score") else None,
                    user_text=text,
                    caller_phone=caller_number,
                )
                sent_results = await hook_engine.evaluate("OnSentimentShift", hctx)
                extra = hook_engine.collect_context(sent_results)
                if extra and hasattr(voice_agent, "_instructions"):
                    voice_agent._instructions = voice_agent.instructions + f"\n\n{extra}"
            except Exception:
                logger.exception("Error en hooks OnSentimentShift")

        directive = sentiment_analyzer.get_empathy_directive()

        # Inyectar directiva emocional al agente si cambió
        if directive and hasattr(voice_agent, "_instructions"):
            # Limpiar directiva anterior si existe
            base = voice_agent.instructions
            for marker in ("## ALERTA:", "## ALERT:", "## ALERTA URGENTE:", "## URGENT ALERT:"):
                idx = base.find(marker)
                if idx != -1:
                    base = base[:idx].rstrip()
            voice_agent._instructions = base + directive
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
                lifecycle.record_agent_speech()
                # Output guardrails: validar respuesta del agente
                if guardrails:
                    check = guardrails.check_agent_response(msg.text_content)
                    if not check.passed:
                        logger.warning(
                            "Output guardrail violations: %s", check.violations
                        )
                        # Inyectar corrección para la siguiente respuesta
                        if hasattr(voice_agent, "_instructions"):
                            correction = (
                                "\n\n## CORRECCIÓN URGENTE\n"
                                "Tu última respuesta violó estas reglas: "
                                + "; ".join(check.violations) + ". "
                                "NO repitas este error. Corrige si el usuario pregunta de nuevo."
                            )
                            base = voice_agent.instructions
                            # Limpiar corrección anterior
                            idx = base.find("## CORRECCIÓN URGENTE")
                            if idx != -1:
                                base = base[:idx].rstrip()
                            voice_agent._instructions = base + correction
                        # Disparar hook OnGuardrailHit
                        if hook_engine and hook_engine.has_hooks_for("OnGuardrailHit"):
                            task = asyncio.ensure_future(
                                _eval_guardrail_hit_hooks(msg.text_content, check.violations)
                            )
                            _bg_tasks.add(task)
                            task.add_done_callback(_bg_tasks.discard)
                # Hook: PostResponse — evaluar reglas sobre respuesta del agente
                if hook_engine and hook_engine.has_hooks_for("PostResponse"):
                    task = asyncio.ensure_future(_eval_post_response_hooks(msg.text_content))
                    _bg_tasks.add(task)
                    task.add_done_callback(_bg_tasks.discard)
        except Exception:
            logger.exception("Error procesando conversation_item_added")

    async def _eval_post_response_hooks(text: str) -> None:
        """Evalúa hooks PostResponse (notificaciones, logging, etc.)."""
        if not hook_engine:
            return
        try:
            hctx = HookContext(
                event="PostResponse",
                channel="voice",
                agent_id=config.agent.id,
                client_id=config.client.id,
                response_text=text,
                caller_phone=caller_number,
                transcript=list(handler._transcript),
            )
            results = await hook_engine.evaluate("PostResponse", hctx)
            # Procesar notificaciones en background
            notifications = hook_engine.collect_notifications(results)
            for notif in notifications:
                task = asyncio.ensure_future(_send_hook_notification(notif))
                _bg_tasks.add(task)
                task.add_done_callback(_bg_tasks.discard)
        except Exception:
            logger.exception("Error en hooks PostResponse")

    async def _send_hook_notification(notif_config: dict) -> None:
        """Envía una notificación generada por un hook (WhatsApp, webhook, email)."""
        try:
            from api.services.hook_notifier import send_hook_notification
            await send_hook_notification(notif_config)
        except ImportError:
            # En contexto de agente sin api module completo — fallback básico
            logger.info(
                "Hook notification [%s] via %s: %s",
                notif_config.get("hook_name"),
                notif_config.get("channel", "webhook"),
                notif_config.get("template"),
            )
        except Exception:
            logger.exception("Error enviando hook notification")

    # Cleanup al terminar
    async def on_shutdown() -> None:
        logger.info(
            "Finalizando sesión para '%s/%s'",
            config.client.slug, config.agent.slug,
        )
        # Esperar checkpoint pendiente para no perder transcript parcial
        if handler._checkpoint_task and not handler._checkpoint_task.done():
            try:
                await asyncio.wait_for(handler._checkpoint_task, timeout=5)
            except (asyncio.TimeoutError, Exception):
                logger.warning("Checkpoint task no completó a tiempo")
        # Esperar a que pending background tasks del handler terminen
        if handler._background_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*handler._background_tasks, return_exceptions=True),
                    timeout=5,
                )
            except (asyncio.TimeoutError, Exception):
                logger.warning("Background tasks del handler no completaron a tiempo")

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

        # Detener grabación de egress si estaba activa
        recording_status: str | None = None
        if recording_egress_id:
            try:
                from livekit.api import LiveKitAPI, StopEgressRequest

                lk_api = LiveKitAPI()
                await lk_api.egress.stop_egress(
                    StopEgressRequest(egress_id=recording_egress_id)
                )
                logger.info("Recording stopped: %s", recording_egress_id)
                await lk_api.aclose()

                # Validar que el archivo se escribió en R2
                if recording_key:
                    await asyncio.sleep(5)  # Dar tiempo a R2 para finalizar escritura
                    from api.services.recording_service import check_exists

                    exists = await asyncio.to_thread(check_exists, recording_key)
                    if exists:
                        recording_status = "completed"
                        logger.info("Recording verified in R2: %s", recording_key)
                    else:
                        recording_status = "failed"
                        logger.warning(
                            "Recording NOT found in R2 after egress stop: %s",
                            recording_key,
                        )
            except Exception:
                logger.exception("Failed to stop recording egress")
                recording_status = "failed"
        elif recording_key:
            # Egress nunca inició correctamente
            recording_status = "failed"

        # Hook: OnConversationEnd — ejecutar antes de finalizar
        if hook_engine and hook_engine.has_hooks_for("OnConversationEnd"):
            try:
                hctx = HookContext(
                    event="OnConversationEnd",
                    channel="voice",
                    agent_id=config.agent.id,
                    client_id=config.client.id,
                    caller_phone=caller_number,
                    transcript=list(handler._transcript),
                )
                results = await hook_engine.evaluate("OnConversationEnd", hctx)
                notifications = hook_engine.collect_notifications(results)
                for notif in notifications:
                    task = asyncio.ensure_future(_send_hook_notification(notif))
                    _bg_tasks.add(task)
                    task.add_done_callback(_bg_tasks.discard)
            except Exception:
                logger.exception("Error en hooks OnConversationEnd")

        await handler.finalize(
            status="completed", recording_status=recording_status,
        )

        # Esperar background tasks del handler (análisis universal, failure detection)
        if handler._background_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*handler._background_tasks, return_exceptions=True),
                    timeout=30,
                )
            except (asyncio.TimeoutError, Exception):
                logger.warning("Background tasks post-finalize no completaron a tiempo")

        # Quality scoring async (no bloquea el shutdown)
        if quality_cfg.enabled and len(handler._transcript) >= 2:
            task = asyncio.create_task(
                _async_quality_score(
                    transcript=list(handler._transcript),
                    business_type=config.client.business_type,
                    room_name=ctx.room.name,
                )
            )
            _bg_tasks.add(task)
            task.add_done_callback(_bg_tasks.discard)

        # Limpiar MCP servers stdio (kill subprocesos huérfanos)
        if mcp_servers:
            for srv in mcp_servers:
                try:
                    if hasattr(srv, "close"):
                        await srv.close()
                    elif hasattr(srv, "shutdown"):
                        await srv.shutdown()
                except Exception:
                    logger.warning("Error closing MCP server: %s", type(srv).__name__)

        # Limpiar registro de llamada activa
        try:
            sb.table("active_calls").delete().eq("room_name", ctx.room.name).execute()
        except Exception:
            logger.exception("Error cleaning up active_calls record")

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

    # Recording disclosure: inyectar en prompt si hay grabación activa
    if recording_key and hasattr(voice_agent, '_instructions') and voice_agent.instructions:
        voice_agent._instructions = voice_agent.instructions + (
            "\n\nIMPORTANTE: Esta llamada está siendo grabada. En tu PRIMER saludo, "
            "menciona brevemente: 'Le informo que esta llamada puede ser grabada "
            "con fines de calidad.' Hazlo de forma natural, no robótica."
        )
        logger.info("Recording disclosure inyectado en system prompt")

    # Callback: inyectar contexto de la conversación anterior al prompt del agente
    if callback_context and hasattr(voice_agent, '_instructions') and voice_agent.instructions:
        voice_agent._instructions = voice_agent.instructions + (
            "\n\n## DEVOLUCIÓN DE LLAMADA\n"
            "ESTA ES UNA DEVOLUCIÓN DE LLAMADA. El usuario pidió que le llamaras.\n"
            "Saluda diciendo que le devuelves la llamada como quedaron.\n"
            f"Contexto de la conversación anterior:\n{callback_context}\n"
            "Usa este contexto para retomar donde quedaron. NO repitas todo desde cero."
        )
        logger.info("Callback context inyectado en system prompt")
    elif outbound_mode and not campaign_script and callback_id:
        # Callback sin contexto
        if hasattr(voice_agent, '_instructions') and voice_agent.instructions:
            voice_agent._instructions = voice_agent.instructions + (
                "\n\n## DEVOLUCIÓN DE LLAMADA\n"
                "ESTA ES UNA DEVOLUCIÓN DE LLAMADA. El usuario pidió que le llamaras.\n"
                "Saluda diciendo que le devuelves la llamada como quedaron y "
                "pregunta en qué puedes ayudarle."
            )

    # Gemini Live: inyectar greeting en system prompt (no soporta generate_reply)
    if config.agent.agent_mode == "gemini_live":
        _gl_greeting = config.agent.greeting or "Hola, en qué puedo ayudarte?"
        if outbound_mode:
            _gl_greeting = config.agent.greeting or "Hola, buenas tardes."
        _gl_instruction = (
            f"\n\nIMPORTANTE: Al iniciar la conversación, saluda al usuario "
            f"diciendo EXACTAMENTE: \"{_gl_greeting}\". Hazlo inmediatamente."
        )
        if hasattr(voice_agent, '_instructions') and voice_agent.instructions:
            voice_agent._instructions = voice_agent.instructions + _gl_instruction
        logger.info("Gemini Live: greeting inyectado en system prompt")

    # Iniciar sesión — envuelto en try/except para garantizar que on_shutdown se ejecute
    try:
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
    except Exception as exc:
        logger.exception(
            "Error crítico en session.start() para '%s/%s'",
            config.client.slug, config.agent.slug,
        )
        lifecycle.record_error(str(exc), category="agent")
        # on_shutdown se ejecutará vía ctx shutdown callback
        return

    lifecycle.add_event("agent_ready")

    # ── OUTBOUND: Esperar a que la persona conteste antes de saludar ──
    # En outbound, el agente se despacha al crear el room, ANTES de que el SIP
    # participant se conecte (la persona contesta). Si saludamos antes de que
    # conteste, el audio se pierde. Esperamos hasta 60s a que conteste.
    if outbound_mode and not _sip_connected.is_set():
        logger.info("Outbound: esperando a que la persona conteste...")
        try:
            await asyncio.wait_for(_sip_connected.wait(), timeout=60)
            logger.info(
                "Outbound: persona contestó — caller=%s, called=%s",
                caller_number, called_number,
            )
            # Registrar en lifecycle
            lifecycle.record_sip_connected(caller_number, called_number)
            # Actualizar números en el handler ahora que los tenemos
            outbound_callee = caller_number  # sip.phoneNumber = a quién llamamos
            outbound_caller = called_number or config.agent.phone_number
            handler._caller_number = outbound_caller
            handler._callee_number = outbound_callee
            # Actualizar identity SIP para transfer
            if hasattr(voice_agent, "_room_name"):
                for p in ctx.room.remote_participants.values():
                    if p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
                        voice_agent._sip_participant_identity = p.identity
                        break
            # Pequeña pausa para que el audio esté estable
            await asyncio.sleep(0.3)
        except asyncio.TimeoutError:
            logger.warning("Outbound: nadie contestó en 60s, cerrando sesión")
            lifecycle.record_no_answer()
            # Actualizar campaign_calls a no_answer
            if campaign_id:
                try:
                    _sb_timeout = get_supabase()
                    # Buscar por campaign_id + status calling (puede haber varias, limitar a 1)
                    _cc = (
                        _sb_timeout.table("campaign_calls")
                        .select("id")
                        .eq("campaign_id", campaign_id)
                        .eq("status", "calling")
                        .limit(1)
                        .execute()
                    )
                    if _cc.data:
                        _sb_timeout.table("campaign_calls").update({
                            "status": "no_answer",
                            "result_summary": "El contacto no contestó la llamada (sin respuesta después de 60s)",
                        }).eq("id", _cc.data[0]["id"]).execute()
                except Exception:
                    logger.exception("Error actualizando campaign_call a no_answer")
            return

    # Hook: OnGreeting — personalizar saludo según contexto (skip en outbound para velocidad)
    greeting_override: str | None = None
    if not outbound_mode and hook_engine and hook_engine.has_hooks_for("OnGreeting"):
        try:
            hctx = HookContext(
                event="OnGreeting",
                channel="voice",
                agent_id=config.agent.id,
                client_id=config.client.id,
                caller_phone=caller_number,
                contact_name=memory.contact.get("name") if memory and memory.contact else None,
                metadata={
                    "direction": "inbound",
                    "is_returning": bool(memory and memory.contact_id and not memory._is_new_contact),
                },
            )
            greeting_results = await hook_engine.evaluate("OnGreeting", hctx)
            for r in greeting_results:
                if r.action == HookAction.SPEAK and r.message:
                    greeting_override = r.message
                    break
            extra = hook_engine.collect_context(greeting_results)
            if extra:
                greeting_override = extra  # Usar contexto como override de greeting
        except Exception:
            logger.exception("Error en hooks OnGreeting")

    # Saludo inicial — Gemini Live ya lo tiene en el system prompt, skip
    if config.agent.agent_mode != "gemini_live":
        if greeting_override:
            await session.generate_reply(instructions=f"Saluda al usuario con: {greeting_override}")
        elif outbound_mode:
            outbound_greeting = config.agent.greeting or "Hola, buenas tardes."
            await session.generate_reply(
                instructions=f"Di EXACTAMENTE esto como saludo: \"{outbound_greeting}\""
            )
        elif hasattr(voice_agent, '_flow_engine') and hasattr(voice_agent, '_flow_state'):
            flow_greeting = voice_agent.flow_engine.get_greeting(voice_agent.flow_state)
            await session.generate_reply(
                instructions=f"Saluda al usuario con: {flow_greeting}"
            )
        elif memory and memory.contact_id and not memory._is_new_contact and memory.contact and (memory.contact.get("name") or "").strip():
            contact_name = memory.contact["name"].strip().split()[0]
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

    # ── VOICEMAIL DETECTION: si outbound y no hay speech del usuario en 8s post-greeting ──
    if outbound_mode:
        _vm_timeout = 8  # segundos sin speech del usuario
        try:
            # Esperar a que lifecycle registre primer speech del usuario
            _vm_start = asyncio.get_event_loop().time()
            while (asyncio.get_event_loop().time() - _vm_start) < _vm_timeout:
                if lifecycle._user_turns > 0:
                    break  # Usuario habló, no es voicemail
                await asyncio.sleep(0.5)
            else:
                # Timeout sin speech → probablemente voicemail
                if lifecycle._user_turns == 0:
                    logger.warning("Voicemail detectado: sin speech del usuario en %ds", _vm_timeout)
                    lifecycle.add_event("voicemail_detected")
                    # Colgar limpiamente
                    return
        except Exception:
            logger.exception("Error en detección de voicemail")


if __name__ == "__main__":
    agents.cli.run_app(server)
