"""Entrypoint del agente de voz LiveKit.

Un solo worker que se adapta dinámicamente por llamada,
cargando la configuración del cliente desde Supabase.
"""

from __future__ import annotations

import logging

from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import AgentSession, AgentServer, room_io
from livekit.plugins import silero, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from agent.agent_factory import build_agent
from agent.config_loader import load_client_config_by_id, load_client_config_by_phone
from agent.pipeline_builder import build_llm, build_realtime_model, build_stt, build_tts
from agent.session_handler import SessionHandler

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("voice-ai")

server = AgentServer()


@server.rtc_session(agent_name="voice-ai-platform")
async def entrypoint(ctx: agents.JobContext) -> None:
    """Punto de entrada para cada llamada."""
    await ctx.connect(auto_subscribe=agents.AutoSubscribe.AUDIO_ONLY)

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
        import asyncio
        await asyncio.sleep(2)
        for p in ctx.room.remote_participants.values():
            if p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
                caller_number = p.attributes.get("sip.phoneNumber")
                called_number = p.attributes.get("sip.trunkPhoneNumber")
                break

    # Detectar modo outbound desde metadata del room
    import json
    outbound_mode = False
    campaign_script: str | None = None
    outbound_client_id: str | None = None
    campaign_id: str | None = None
    room_metadata = ctx.room.metadata or ""
    if room_metadata:
        try:
            meta = json.loads(room_metadata)
            if meta.get("type") == "outbound":
                outbound_mode = True
                campaign_script = meta.get("script")
                outbound_client_id = meta.get("client_id")
                campaign_id = meta.get("campaign_id")
                logger.info("Modo outbound detectado, campaign_id: %s", campaign_id)
        except (json.JSONDecodeError, AttributeError):
            pass

    # Cargar config del cliente
    config = None
    if outbound_mode and outbound_client_id:
        config = await load_client_config_by_id(outbound_client_id)
    elif called_number:
        config = await load_client_config_by_phone(called_number)

    if not config:
        logger.warning(
            "No se encontró cliente para número '%s'. Usando config por defecto.",
            called_number,
        )
        # Config por defecto para testing
        from agent.config_loader import ClientConfig
        config = ClientConfig(
            id="00000000-0000-0000-0000-000000000000",
            name="Test",
            slug="test",
            business_type="generic",
            agent_name="Asistente",
            language="es",
            voice_id="default",
            greeting="Hola, soy un asistente virtual de prueba. ¿En qué puedo ayudarle?",
            system_prompt="Eres un asistente virtual de prueba. Responde en español de forma amable y concisa.",
            file_search_store_id=None,
            tools_enabled=["search_knowledge"],
            max_call_duration_seconds=300,
            transfer_number=None,
            business_hours=None,
            after_hours_message=None,
        )

    # Override del system prompt para outbound con script de campaña
    if outbound_mode and campaign_script:
        from dataclasses import replace
        config = replace(config, system_prompt=campaign_script)

    # Construir agente dinámico
    voice_agent = build_agent(config)

    # Configurar pipeline de voz (BYOK)
    stt_language = "es" if config.language in ("es", "es-en") else "en"

    vad = silero.VAD.load(
        activation_threshold=0.6,
        min_speech_duration=0.15,
        min_silence_duration=0.8,
        sample_rate=8000,
    )

    if config.voice_mode == "realtime":
        logger.info("Modo realtime: model=%s, voice=%s", config.realtime_model, config.realtime_voice)
        session = AgentSession(
            llm=build_realtime_model(config),
            vad=vad,
            turn_detection=MultilingualModel(),
            min_endpointing_delay=0.8,
            max_endpointing_delay=6.0,
            min_interruption_duration=0.7,
            min_interruption_words=1,
        )
    else:
        logger.info(
            "Modo pipeline: stt=%s, llm=%s, tts=%s",
            config.stt_provider, config.llm_provider, config.tts_provider,
        )
        session = AgentSession(
            stt=build_stt(config, stt_language),
            llm=build_llm(config),
            tts=build_tts(config, stt_language),
            vad=vad,
            turn_detection=MultilingualModel(),
            min_endpointing_delay=0.8,
            max_endpointing_delay=6.0,
            min_interruption_duration=0.7,
            min_interruption_words=1,
        )

    # Para outbound, los números van al revés:
    # - caller_number = nuestro número (el que llama)
    # - callee_number = el número destino (sip.phoneNumber del participante SIP)
    if outbound_mode:
        outbound_callee = caller_number  # sip.phoneNumber = a quién llamamos
        outbound_caller = called_number or config.phone_number if hasattr(config, 'phone_number') else None
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
    )

    # Registrar transcripción
    @session.on("user_input_transcribed")
    def on_user_input(ev) -> None:
        if ev.is_final:
            handler.add_transcript_entry("user", ev.transcript)

    @session.on("conversation_item_added")
    def on_conversation_item(ev) -> None:
        try:
            msg = ev.item
            if msg.role == "assistant" and msg.text_content:
                handler.add_transcript_entry("assistant", msg.text_content)
        except Exception:
            logger.exception("Error procesando conversation_item_added")

    # Cleanup al terminar
    async def on_shutdown() -> None:
        logger.info("Finalizando sesión para '%s'", config.slug)
        await handler.finalize(status="completed")

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
    else:
        await session.generate_reply(instructions=f"Saluda al usuario con: {config.greeting}")


if __name__ == "__main__":
    agents.cli.run_app(server)
