"""Carga configuración de clientes y agentes desde Supabase."""

from __future__ import annotations

import asyncio
import logging
import os
import warnings
from dataclasses import dataclass, field

from supabase import Client

# Timeout para queries a Supabase (segundos)
DB_QUERY_TIMEOUT_S = 8.0

logger = logging.getLogger(__name__)


# ── Nuevos dataclasses (multi-agent) ────────────────────


@dataclass(frozen=True)
class AgentConfig:
    """Configuración de un agente individual."""

    id: str
    client_id: str
    name: str
    slug: str
    phone_number: str | None
    phone_sid: str | None
    livekit_sip_trunk_id: str | None
    system_prompt: str
    greeting: str
    examples: str | None
    voice_config: dict = field(default_factory=dict)
    llm_config: dict = field(default_factory=dict)
    stt_config: dict = field(default_factory=dict)
    agent_mode: str = "pipeline"
    agent_type: str = "inbound"
    transfer_number: str | None = None
    after_hours_message: str | None = None
    max_call_duration_seconds: int = 300
    is_active: bool = True
    # Orchestration fields
    role_description: str | None = None
    orchestrator_enabled: bool = True
    orchestrator_priority: int = 0
    # Flow builder
    conversation_mode: str = "prompt"
    conversation_flow: dict | None = None

    # Properties de conveniencia (compatibilidad con pipeline_builder)
    @property
    def tts_provider(self) -> str:
        return self.voice_config.get("provider", "cartesia")

    @property
    def voice_id(self) -> str:
        return self.voice_config.get("voice_id", "default")

    @property
    def tts_api_key(self) -> str | None:
        return self.voice_config.get("api_key")

    @property
    def llm_provider(self) -> str:
        return self.llm_config.get("provider", "google")

    @property
    def llm_api_key(self) -> str | None:
        return self.llm_config.get("api_key")

    @property
    def stt_provider(self) -> str:
        return self.stt_config.get("provider", "deepgram")

    @property
    def stt_api_key(self) -> str | None:
        return self.stt_config.get("api_key")

    @property
    def realtime_voice(self) -> str:
        return self.voice_config.get("realtime_voice", "alloy")

    @property
    def realtime_model(self) -> str:
        return self.voice_config.get("realtime_model", "gpt-4o-realtime-preview")

    @property
    def realtime_api_key(self) -> str | None:
        return self.voice_config.get("realtime_api_key")

    @property
    def voice_mode(self) -> str:
        """Alias de agent_mode para backward compat."""
        return self.agent_mode


@dataclass(frozen=True)
class SlimClientConfig:
    """Configuración del negocio (sin datos de agente)."""

    id: str
    name: str
    slug: str
    business_type: str
    language: str
    file_search_store_id: str | None
    file_search_store_name: str | None = None
    google_calendar_id: str | None = None
    google_service_account_key: dict | None = None
    whatsapp_instance_id: str | None = None
    whatsapp_api_url: str | None = None
    whatsapp_api_key: str | None = None
    enabled_tools: list[str] = field(default_factory=lambda: ["search_knowledge"])
    business_hours: dict | None = None
    is_active: bool = True
    owner_email: str | None = None
    monthly_minutes_limit: int = 500
    # Orchestration fields
    orchestration_mode: str = "simple"
    orchestrator_model: str = "gemini-2.0-flash"
    orchestrator_prompt: str | None = None


@dataclass(frozen=True)
class ResolvedConfig:
    """Configuración combinada de agente + cliente para una llamada."""

    agent: AgentConfig
    client: SlimClientConfig


# ── Legacy dataclass (deprecated, mantener para backward compat) ─────


@dataclass(frozen=True)
class ClientConfig:
    """Configuración completa de un cliente para el agente de voz.

    DEPRECATED: Usar ResolvedConfig con AgentConfig + SlimClientConfig.
    """

    id: str
    name: str
    slug: str
    business_type: str
    agent_name: str
    language: str
    voice_id: str
    greeting: str
    system_prompt: str
    file_search_store_id: str | None
    tools_enabled: list[str]
    max_call_duration_seconds: int
    transfer_number: str | None
    business_hours: dict | None
    after_hours_message: str | None
    # Integraciones Phase 3
    google_calendar_id: str | None = None
    google_service_account_key: dict | None = None
    whatsapp_instance_id: str | None = None
    whatsapp_api_url: str | None = None
    whatsapp_api_key: str | None = None
    enabled_tools: list[str] = field(default_factory=lambda: ["search_knowledge"])
    conversation_examples: str | None = None
    # BYOK — Voice Pipeline
    voice_mode: str = "pipeline"
    stt_provider: str = "deepgram"
    llm_provider: str = "google"
    tts_provider: str = "cartesia"
    stt_api_key: str | None = None
    llm_api_key: str | None = None
    tts_api_key: str | None = None
    realtime_api_key: str | None = None
    realtime_voice: str = "alloy"
    realtime_model: str = "gpt-4o-realtime-preview"


# ── Supabase helper ─────────────────────────────────────


def _get_supabase() -> Client:
    """Retorna cliente Supabase singleton."""
    from agent.db import get_supabase
    return get_supabase()


# ── Nuevas funciones de carga (multi-agent) ─────────────


async def load_config_by_phone(phone_number: str) -> ResolvedConfig | None:
    """Carga config buscando por número de teléfono del agente."""
    sb = _get_supabase()

    try:
        # Buscar en agents por número exacto (con timeout)
        result = await asyncio.wait_for(
            asyncio.to_thread(
                lambda: sb.table("agents")
                .select("*, clients(*)")
                .eq("phone_number", phone_number)
                .eq("is_active", True)
                .limit(1)
                .execute()
            ),
            timeout=DB_QUERY_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.error("Timeout cargando config por teléfono: %s", phone_number)
        return None

    if not result.data:
        # Buscar con variantes de número
        clean = phone_number.lstrip("+")
        try:
            all_agents = await asyncio.wait_for(
                asyncio.to_thread(
                    lambda: sb.table("agents")
                    .select("*, clients(*)")
                    .eq("is_active", True)
                    .execute()
                ),
                timeout=DB_QUERY_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            logger.error("Timeout cargando agentes para búsqueda fuzzy")
            return None

        for row in all_agents.data:
            db_phone = (row.get("phone_number") or "").lstrip("+")
            if db_phone and (
                db_phone == clean
                or clean.endswith(db_phone)
                or db_phone.endswith(clean)
            ):
                return _rows_to_resolved(row)
        return None

    return _rows_to_resolved(result.data[0])


async def load_config_by_agent_id(agent_id: str) -> ResolvedConfig | None:
    """Carga config por UUID del agente."""
    sb = _get_supabase()
    result = (
        sb.table("agents")
        .select("*, clients(*)")
        .eq("id", agent_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return _rows_to_resolved(result.data[0])


async def load_config_by_client_id(client_id: str) -> ResolvedConfig | None:
    """Carga config del primer agente activo del cliente."""
    sb = _get_supabase()
    result = (
        sb.table("agents")
        .select("*, clients(*)")
        .eq("client_id", client_id)
        .eq("is_active", True)
        .order("created_at")
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return _rows_to_resolved(result.data[0])


async def load_mcp_servers(client_id: str, agent_id: str | None = None) -> list[dict]:
    """Carga MCP servers activos para un cliente, filtrados por agent_id si aplica.

    Args:
        client_id: UUID del cliente.
        agent_id: UUID del agente (opcional). Si se da, filtra servers asignados
                  a ese agente o a todos los agentes (agent_ids IS NULL).

    Returns:
        Lista de dicts con la config de cada MCP server.
    """
    sb = _get_supabase()
    result = (
        sb.table("mcp_servers")
        .select("*")
        .eq("client_id", client_id)
        .eq("is_active", True)
        .execute()
    )

    if not result.data:
        return []

    servers = []
    for row in result.data:
        agent_ids = row.get("agent_ids")
        # agent_ids null = disponible para todos los agentes
        if agent_ids is not None and agent_id:
            if agent_id not in agent_ids:
                continue
        servers.append(row)

    return servers


async def load_api_integrations(
    client_id: str, agent_id: str | None = None
) -> list[dict]:
    """Carga API integrations activas para un cliente, filtradas por agent_id.

    Args:
        client_id: UUID del cliente.
        agent_id: UUID del agente (opcional). Si se da, filtra integrations
                  asignadas a ese agente o a todos (agent_ids IS NULL).

    Returns:
        Lista de dicts con la config de cada API integration.
    """
    sb = _get_supabase()
    result = (
        sb.table("api_integrations")
        .select("*")
        .eq("client_id", client_id)
        .eq("is_active", True)
        .execute()
    )

    if not result.data:
        return []

    integrations = []
    for row in result.data:
        agent_ids = row.get("agent_ids")
        if agent_ids is not None and agent_id:
            if agent_id not in agent_ids:
                continue
        integrations.append(row)

    return integrations


async def load_whatsapp_config_by_agent_id(agent_id: str) -> dict | None:
    """Carga whatsapp_config por agent_id."""
    sb = _get_supabase()
    result = (
        sb.table("whatsapp_configs")
        .select("*")
        .eq("agent_id", agent_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


async def load_whatsapp_config_by_ghl_location(location_id: str) -> dict | None:
    """Carga whatsapp_config por ghl_location_id."""
    sb = _get_supabase()
    result = (
        sb.table("whatsapp_configs")
        .select("*")
        .eq("ghl_location_id", location_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


async def load_whatsapp_config_by_evo_instance(instance_id: str) -> dict | None:
    """Carga whatsapp_config por evo_instance_id."""
    sb = _get_supabase()
    result = (
        sb.table("whatsapp_configs")
        .select("*")
        .eq("evo_instance_id", instance_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


async def load_orchestrated_configs(client_id: str) -> list[ResolvedConfig]:
    """Carga todos los agentes habilitados para orquestación de un cliente.

    Retorna lista ordenada por orchestrator_priority DESC.
    """
    sb = _get_supabase()
    result = (
        sb.table("agents")
        .select("*, clients(*)")
        .eq("client_id", client_id)
        .eq("is_active", True)
        .eq("orchestrator_enabled", True)
        .order("orchestrator_priority", desc=True)
        .execute()
    )
    if not result.data:
        return []
    return [_rows_to_resolved(row) for row in result.data]


def _rows_to_resolved(agent_row: dict) -> ResolvedConfig:
    """Convierte un row de agents con join clients a ResolvedConfig."""
    client_row = agent_row.get("clients") or {}

    agent = AgentConfig(
        id=str(agent_row["id"]),
        client_id=str(agent_row["client_id"]),
        name=agent_row["name"],
        slug=agent_row["slug"],
        phone_number=agent_row.get("phone_number"),
        phone_sid=agent_row.get("phone_sid"),
        livekit_sip_trunk_id=agent_row.get("livekit_sip_trunk_id"),
        system_prompt=agent_row.get("system_prompt", ""),
        greeting=agent_row.get("greeting", ""),
        examples=agent_row.get("examples"),
        voice_config=agent_row.get("voice_config") or {},
        llm_config=agent_row.get("llm_config") or {},
        stt_config=agent_row.get("stt_config") or {},
        agent_mode=agent_row.get("agent_mode", "pipeline"),
        agent_type=agent_row.get("agent_type", "inbound"),
        transfer_number=agent_row.get("transfer_number"),
        after_hours_message=agent_row.get("after_hours_message"),
        max_call_duration_seconds=agent_row.get("max_call_duration_seconds", 300),
        is_active=agent_row.get("is_active", True),
        role_description=agent_row.get("role_description"),
        orchestrator_enabled=agent_row.get("orchestrator_enabled", True),
        orchestrator_priority=agent_row.get("orchestrator_priority", 0),
        conversation_mode=agent_row.get("conversation_mode", "prompt"),
        conversation_flow=agent_row.get("conversation_flow"),
    )

    client = SlimClientConfig(
        id=str(client_row.get("id", agent_row["client_id"])),
        name=client_row.get("name", ""),
        slug=client_row.get("slug", ""),
        business_type=client_row.get("business_type", "generic"),
        language=client_row.get("language", "es"),
        file_search_store_id=client_row.get("file_search_store_id"),
        file_search_store_name=client_row.get("file_search_store_name"),
        google_calendar_id=client_row.get("google_calendar_id"),
        google_service_account_key=client_row.get("google_service_account_key"),
        whatsapp_instance_id=client_row.get("whatsapp_instance_id"),
        whatsapp_api_url=client_row.get("whatsapp_api_url"),
        whatsapp_api_key=client_row.get("whatsapp_api_key"),
        enabled_tools=client_row.get("enabled_tools") or ["search_knowledge"],
        business_hours=client_row.get("business_hours"),
        is_active=client_row.get("is_active", True),
        owner_email=client_row.get("owner_email"),
        monthly_minutes_limit=client_row.get("monthly_minutes_limit", 500),
        orchestration_mode=client_row.get("orchestration_mode", "simple"),
        orchestrator_model=client_row.get("orchestrator_model", "gemini-2.0-flash"),
        orchestrator_prompt=client_row.get("orchestrator_prompt"),
    )

    return ResolvedConfig(agent=agent, client=client)


# ── Legacy funciones (deprecated) ───────────────────────


async def load_client_config_by_phone(phone_number: str) -> ClientConfig | None:
    """DEPRECATED: Usar load_config_by_phone(). Mantiene firma para backward compat."""
    warnings.warn(
        "load_client_config_by_phone está deprecated, usar load_config_by_phone",
        DeprecationWarning,
        stacklevel=2,
    )
    sb = _get_supabase()

    result = (
        sb.table("clients")
        .select("*")
        .eq("phone_number", phone_number)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )

    if not result.data:
        clean = phone_number.lstrip("+")
        result = (
            sb.table("clients")
            .select("*")
            .eq("is_active", True)
            .execute()
        )
        for row in result.data:
            db_phone = (row.get("phone_number") or "").lstrip("+")
            if db_phone and (
                db_phone == clean
                or clean.endswith(db_phone)
                or db_phone.endswith(clean)
            ):
                return _row_to_config(row)
        return None

    return _row_to_config(result.data[0])


async def load_client_config_by_slug(slug: str) -> ClientConfig | None:
    """DEPRECATED: Carga config de cliente por slug."""
    warnings.warn(
        "load_client_config_by_slug está deprecated",
        DeprecationWarning,
        stacklevel=2,
    )
    sb = _get_supabase()
    result = (
        sb.table("clients")
        .select("*")
        .eq("slug", slug)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return _row_to_config(result.data[0])


async def load_client_config_by_id(client_id: str) -> ClientConfig | None:
    """DEPRECATED: Usar load_config_by_client_id(). Carga config por UUID."""
    warnings.warn(
        "load_client_config_by_id está deprecated, usar load_config_by_client_id",
        DeprecationWarning,
        stacklevel=2,
    )
    sb = _get_supabase()
    result = (
        sb.table("clients")
        .select("*")
        .eq("id", client_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return _row_to_config(result.data[0])


def _row_to_config(row: dict) -> ClientConfig:
    """Convierte un row de Supabase a ClientConfig (legacy)."""
    return ClientConfig(
        id=str(row["id"]),
        name=row["name"],
        slug=row["slug"],
        business_type=row.get("business_type", "generic"),
        agent_name=row["agent_name"],
        language=row.get("language", "es"),
        voice_id=row["voice_id"],
        greeting=row["greeting"],
        system_prompt=row["system_prompt"],
        file_search_store_id=row.get("file_search_store_id"),
        tools_enabled=row.get("tools_enabled") or ["search_knowledge"],
        max_call_duration_seconds=row.get("max_call_duration_seconds", 300),
        transfer_number=row.get("transfer_number"),
        business_hours=row.get("business_hours"),
        after_hours_message=row.get("after_hours_message"),
        google_calendar_id=row.get("google_calendar_id"),
        google_service_account_key=row.get("google_service_account_key"),
        whatsapp_instance_id=row.get("whatsapp_instance_id"),
        whatsapp_api_url=row.get("whatsapp_api_url"),
        whatsapp_api_key=row.get("whatsapp_api_key"),
        enabled_tools=row.get("enabled_tools") or ["search_knowledge"],
        conversation_examples=row.get("conversation_examples"),
        voice_mode=row.get("voice_mode", "pipeline"),
        stt_provider=row.get("stt_provider", "deepgram"),
        llm_provider=row.get("llm_provider", "google"),
        tts_provider=row.get("tts_provider", "cartesia"),
        stt_api_key=row.get("stt_api_key"),
        llm_api_key=row.get("llm_api_key"),
        tts_api_key=row.get("tts_api_key"),
        realtime_api_key=row.get("realtime_api_key"),
        realtime_voice=row.get("realtime_voice", "alloy"),
        realtime_model=row.get("realtime_model", "gpt-4o-realtime-preview"),
    )
