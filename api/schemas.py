"""Pydantic v2 request/response models para la API."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# ── Auth ──────────────────────────────────────────────

class UserOut(BaseModel):
    id: str
    email: str
    role: str
    client_id: str | None = None
    display_name: str | None = None
    is_active: bool = True


class RegisterUserRequest(BaseModel):
    email: str
    password: str
    role: str = "client"
    client_id: str | None = None
    display_name: str | None = None


# ── Voices ────────────────────────────────────────────

class VoiceOut(BaseModel):
    key: str
    id: str
    name: str
    language: str
    gender: str
    description: str


# ── Agents ───────────────────────────────────────────

class AgentOut(BaseModel):
    id: str
    client_id: str
    name: str
    slug: str
    phone_number: str | None = None
    system_prompt: str = ""
    greeting: str = ""
    examples: str | None = None
    voice_config: dict = Field(default_factory=dict)
    llm_config: dict = Field(default_factory=dict)
    stt_config: dict = Field(default_factory=dict)
    agent_mode: str = "pipeline"
    agent_type: str = "inbound"
    transfer_number: str | None = None
    after_hours_message: str | None = None
    max_call_duration_seconds: int = 300
    is_active: bool = True
    # Orchestration
    role_description: str | None = None
    orchestrator_enabled: bool = True
    orchestrator_priority: int = 0
    # Flow builder
    conversation_mode: str = "prompt"
    conversation_flow: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AgentCreateRequest(BaseModel):
    name: str
    slug: str | None = None
    system_prompt: str | None = None
    greeting: str | None = None
    examples: str | None = None
    agent_mode: str = "pipeline"
    agent_type: str = "inbound"
    transfer_number: str | None = None
    after_hours_message: str | None = None
    max_call_duration_seconds: int = 300
    voice_key: str = "es_female_warm"
    stt_provider: str = "deepgram"
    llm_provider: str = "google"
    tts_provider: str = "cartesia"
    stt_api_key: str | None = None
    llm_api_key: str | None = None
    tts_api_key: str | None = None
    realtime_api_key: str | None = None
    realtime_voice: str = "alloy"
    realtime_model: str = "gpt-4o-realtime-preview"
    # Orchestration
    role_description: str | None = None
    orchestrator_enabled: bool = True
    orchestrator_priority: int = 0
    # Flow builder
    conversation_mode: str = "prompt"
    conversation_flow: dict | None = None


class AgentUpdateRequest(BaseModel):
    name: str | None = None
    system_prompt: str | None = None
    greeting: str | None = None
    examples: str | None = None
    agent_mode: str | None = None
    agent_type: str | None = None
    transfer_number: str | None = None
    after_hours_message: str | None = None
    max_call_duration_seconds: int | None = None
    is_active: bool | None = None
    voice_id: str | None = None
    stt_provider: str | None = None
    llm_provider: str | None = None
    tts_provider: str | None = None
    stt_api_key: str | None = None
    llm_api_key: str | None = None
    tts_api_key: str | None = None
    realtime_api_key: str | None = None
    realtime_voice: str | None = None
    realtime_model: str | None = None
    # Orchestration
    role_description: str | None = None
    orchestrator_enabled: bool | None = None
    orchestrator_priority: int | None = None
    # Flow builder
    conversation_mode: str | None = None
    conversation_flow: dict | None = None


# ── Clients ───────────────────────────────────────────

class ClientOut(BaseModel):
    id: str
    name: str
    slug: str
    business_type: str
    agent_name: str
    language: str
    voice_id: str
    greeting: str
    system_prompt: str
    file_search_store_id: str | None = None
    file_search_store_name: str | None = None
    phone_number: str | None = None
    max_call_duration_seconds: int = 300
    tools_enabled: list[str] = Field(default_factory=lambda: ["search_knowledge"])
    transfer_number: str | None = None
    business_hours: dict | None = None
    after_hours_message: str | None = None
    conversation_examples: str | None = None
    is_active: bool = True
    owner_email: str | None = None
    monthly_minutes_limit: int = 500
    google_calendar_id: str | None = None
    whatsapp_instance_id: str | None = None
    whatsapp_api_url: str | None = None
    enabled_tools: list[str] = Field(default_factory=lambda: ["search_knowledge"])
    # BYOK voice pipeline
    voice_mode: str = "pipeline"
    stt_provider: str = "deepgram"
    llm_provider: str = "google"
    tts_provider: str = "cartesia"
    has_stt_api_key: bool = False
    has_llm_api_key: bool = False
    has_tts_api_key: bool = False
    has_realtime_api_key: bool = False
    realtime_voice: str = "alloy"
    realtime_model: str = "gpt-4o-realtime-preview"
    # Orchestration
    orchestration_mode: str = "simple"
    orchestrator_model: str = "gemini-2.0-flash"
    orchestrator_prompt: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ClientCreateRequest(BaseModel):
    name: str
    slug: str
    business_type: str = "generic"
    agent_name: str = "María"
    voice_key: str = "es_female_warm"
    language: str = "es"
    greeting: str | None = None
    system_prompt: str | None = None
    owner_email: str | None = None
    skip_store: bool = False


class ClientUpdateRequest(BaseModel):
    name: str | None = None
    business_type: str | None = None
    owner_email: str | None = None
    agent_name: str | None = None
    language: str | None = None
    voice_id: str | None = None
    greeting: str | None = None
    system_prompt: str | None = None
    conversation_examples: str | None = None
    max_call_duration_seconds: int | None = None
    transfer_number: str | None = None
    business_hours: dict | None = None
    after_hours_message: str | None = None
    is_active: bool | None = None
    monthly_minutes_limit: int | None = None
    # Integraciones
    google_calendar_id: str | None = None
    whatsapp_instance_id: str | None = None
    whatsapp_api_url: str | None = None
    whatsapp_api_key: str | None = None
    enabled_tools: list[str] | None = None
    # BYOK voice pipeline
    voice_mode: str | None = None
    stt_provider: str | None = None
    llm_provider: str | None = None
    tts_provider: str | None = None
    stt_api_key: str | None = None
    llm_api_key: str | None = None
    tts_api_key: str | None = None
    realtime_api_key: str | None = None
    realtime_voice: str | None = None
    realtime_model: str | None = None
    # Orchestration
    orchestration_mode: str | None = None
    orchestrator_model: str | None = None
    orchestrator_prompt: str | None = None


class AssignPhoneRequest(BaseModel):
    phone_number: str
    skip_livekit: bool = False


class AvailableNumberOut(BaseModel):
    phone_number: str
    friendly_name: str
    locality: str | None = None
    region: str | None = None


class PurchaseNumberRequest(BaseModel):
    phone_number: str


class PromptTemplateOut(BaseModel):
    key: str
    name: str
    content: str


# ── Calls ─────────────────────────────────────────────

class CallOut(BaseModel):
    id: str
    client_id: str
    agent_id: str | None = None
    agent_name: str | None = None
    direction: str
    caller_number: str | None = None
    callee_number: str | None = None
    duration_seconds: int = 0
    cost_total: Decimal = Decimal("0")
    status: str = "completed"
    summary: str | None = None
    sentimiento: str | None = None
    resumen_ia: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None


class CallDetailOut(CallOut):
    livekit_room_id: str | None = None
    livekit_room_name: str | None = None
    cost_livekit: Decimal = Decimal("0")
    cost_stt: Decimal = Decimal("0")
    cost_llm: Decimal = Decimal("0")
    cost_tts: Decimal = Decimal("0")
    cost_telephony: Decimal = Decimal("0")
    transcript: list[dict] | None = None
    agent_turns: list[dict] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    intencion: str | None = None
    lead_score: int | None = None
    siguiente_accion: str | None = None
    preguntas_sin_respuesta: list[str] | None = None
    cost_breakdown: CostBreakdown | None = None


class CallStatsOut(BaseModel):
    total_calls: int = 0
    total_minutes: float = 0
    total_cost: float = 0
    avg_duration_seconds: float = 0
    calls_today: int = 0
    minutes_today: float = 0


# ── Documents ─────────────────────────────────────────

class DocumentOut(BaseModel):
    id: str
    client_id: str
    filename: str
    file_type: str | None = None
    file_size_bytes: int | None = None
    indexing_status: str = "pending"
    description: str | None = None
    uploaded_at: datetime | None = None


# ── Costs ─────────────────────────────────────────────

class CostLineItem(BaseModel):
    service: str
    label: str
    amount: float
    classification: str  # "platform" | "external"
    provider: str
    is_estimate: bool = False


class CostBreakdown(BaseModel):
    platform_cost: float = 0
    external_cost_estimate: float = 0
    total: float = 0
    lines: list[CostLineItem] = Field(default_factory=list)


class CostEstimateRequest(BaseModel):
    stt_provider: str = "deepgram"
    llm_provider: str = "google"
    tts_provider: str = "cartesia"
    minutes: float = 1.0


class CostEstimateResponse(BaseModel):
    minutes: float
    platform_cost: float
    external_cost_estimate: float
    total_estimate: float
    lines: list[CostLineItem] = Field(default_factory=list)
    note: str = ""


# ── Dashboard ─────────────────────────────────────────

class DashboardOverview(BaseModel):
    total_calls: int = 0
    total_minutes: float = 0
    total_cost: float = 0
    calls_today: int = 0
    minutes_today: float = 0
    cost_today: float = 0
    active_documents: int = 0
    client_name: str | None = None
    platform_cost_today: float = 0
    external_cost_today: float = 0
    platform_cost_total: float = 0
    external_cost_total: float = 0


class UsageDataPoint(BaseModel):
    date: date
    calls: int = 0
    minutes: float = 0
    cost: float = 0


class DashboardUsage(BaseModel):
    data: list[UsageDataPoint] = Field(default_factory=list)
    period_days: int = 30


# ── Contacts ─────────────────────────────────────────

class ContactOut(BaseModel):
    id: str
    client_id: str
    name: str | None = None
    phone: str
    email: str | None = None
    source: str = "inbound_call"
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    call_count: int = 0
    last_call_at: datetime | None = None
    lead_score: int = 0
    # Campos de memoria
    summary: str | None = None
    preferences: dict = Field(default_factory=dict)
    key_facts: list = Field(default_factory=list)
    last_interaction_channel: str | None = None
    average_sentiment: str | None = None
    first_interaction_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ContactCreateRequest(BaseModel):
    name: str | None = None
    phone: str
    email: str | None = None
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)


class ContactUpdateRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    notes: str | None = None
    tags: list[str] | None = None


# ── Memories ─────────────────────────────────────────

class MemoryOut(BaseModel):
    id: str
    summary: str
    channel: str = "call"
    agent_name: str | None = None
    duration_seconds: int | None = None
    sentiment: str | None = None
    topics: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    extracted_data: dict = Field(default_factory=dict)
    created_at: datetime | None = None


class IdentifierOut(BaseModel):
    id: str
    identifier_type: str
    identifier_value: str
    is_primary: bool = False
    is_verified: bool = False
    created_at: datetime | None = None


class IdentifierCreateRequest(BaseModel):
    identifier_type: str
    identifier_value: str


# ── Appointments ─────────────────────────────────────

class AppointmentOut(BaseModel):
    id: str
    client_id: str
    contact_id: str | None = None
    call_id: str | None = None
    title: str
    description: str | None = None
    start_time: datetime
    end_time: datetime
    status: str = "confirmed"
    google_event_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AppointmentCreateRequest(BaseModel):
    contact_id: str | None = None
    title: str
    description: str | None = None
    start_time: datetime
    end_time: datetime


class AppointmentUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    status: str | None = None


# ── AI Prompt Assistant ──────────────────────────────

class GeneratePromptRequest(BaseModel):
    type: str = "agent"  # "agent" | "campaign"
    business_name: str | None = None
    business_type: str | None = None
    agent_name: str | None = None
    tone: str | None = None
    main_function: str | None = None
    # Campaign-specific
    objective: str | None = None
    product: str | None = None
    hook: str | None = None
    data_to_capture: str | None = None
    objection_handling: str | None = None


class ImprovePromptRequest(BaseModel):
    prompt: str
    type: str = "agent"


class PromptAIResponse(BaseModel):
    prompt: str


# ── MCP Servers ──────────────────────────────────────

class McpServerOut(BaseModel):
    id: str
    client_id: str
    name: str
    description: str | None = None
    connection_type: str = "http"
    url: str | None = None
    transport_type: str = "sse"
    has_headers: bool = False
    command: str | None = None
    command_args: list[str] = Field(default_factory=list)
    has_env_vars: bool = False
    allowed_tools: list[str] | None = None
    agent_ids: list[str] | None = None
    is_active: bool = True
    tools_cache: list[dict] | None = None
    last_connected_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class McpServerCreateRequest(BaseModel):
    name: str
    description: str | None = None
    connection_type: str = "http"
    url: str | None = None
    transport_type: str = "sse"
    headers: dict[str, str] = Field(default_factory=dict)
    command: str | None = None
    command_args: list[str] = Field(default_factory=list)
    env_vars: dict[str, str] = Field(default_factory=dict)
    allowed_tools: list[str] | None = None
    agent_ids: list[str] | None = None
    template_id: str | None = None


class McpServerUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    url: str | None = None
    transport_type: str | None = None
    headers: dict[str, str] | None = None
    command: str | None = None
    command_args: list[str] | None = None
    env_vars: dict[str, str] | None = None
    allowed_tools: list[str] | None = None
    agent_ids: list[str] | None = None
    is_active: bool | None = None


class McpTestResult(BaseModel):
    success: bool
    tools: list[dict] = Field(default_factory=list)
    error: str | None = None


class McpServerTemplateOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    icon: str | None = None
    category: str = "general"
    connection_type: str = "http"
    default_url: str | None = None
    default_transport_type: str = "sse"
    default_command: str | None = None
    default_command_args: list[str] = Field(default_factory=list)
    required_env_vars: list[str] = Field(default_factory=list)
    documentation_url: str | None = None


# ── Billing ──────────────────────────────────────────

class CreditBalanceOut(BaseModel):
    balance: float = 0
    total_purchased: float = 0
    total_consumed: float = 0
    total_gifted: float = 0


class CreditPackageOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    credits: int
    volume_discount: float = 0
    price_usd: float | None = None
    price_mxn: float | None = None
    price_per_credit_usd: float | None = None
    sort_order: int = 0
    is_popular: bool = False
    is_active: bool = True


class PurchaseRequest(BaseModel):
    client_id: str
    package_id: str
    payment_method: str  # 'stripe' o 'mercadopago'


class CreditTransactionOut(BaseModel):
    id: str
    client_id: str
    type: str
    credits: float
    balance_after: float
    payment_provider: str | None = None
    payment_id: str | None = None
    payment_status: str | None = None
    amount_paid: float | None = None
    currency: str | None = None
    package_id: str | None = None
    call_id: str | None = None
    agent_id: str | None = None
    duration_seconds: int | None = None
    reason: str | None = None
    admin_email: str | None = None
    created_at: datetime | None = None


class PricingConfigOut(BaseModel):
    id: str
    cost_twilio_per_min: float = 0.013
    cost_stt_per_min: float = 0.006
    cost_llm_per_min: float = 0.003
    cost_tts_per_min: float = 0.008
    cost_livekit_per_min: float = 0.002
    cost_mcp_per_min: float = 0.003
    profit_margin: float = 0.75
    free_credits_new_account: int = 10
    alert_threshold_warning: float = 0.20
    alert_threshold_critical: float = 0.05
    base_currency: str = "USD"
    usd_to_mxn_rate: float = 20.0
    stripe_enabled: bool = True
    mercadopago_enabled: bool = True
    _calculated: dict | None = None


class PricingUpdate(BaseModel):
    cost_twilio_per_min: float | None = None
    cost_stt_per_min: float | None = None
    cost_llm_per_min: float | None = None
    cost_tts_per_min: float | None = None
    cost_livekit_per_min: float | None = None
    cost_mcp_per_min: float | None = None
    profit_margin: float | None = None
    free_credits_new_account: int | None = None
    usd_to_mxn_rate: float | None = None


class GiftCreditsRequest(BaseModel):
    client_id: str
    credits: float
    reason: str
    admin_email: str


# ── Generic ───────────────────────────────────────────

# ── API Integrations ────────────────────────────────

class ApiIntegrationOut(BaseModel):
    id: str
    client_id: str
    name: str
    description: str = ""
    url: str
    method: str = "POST"
    has_headers: bool = False
    has_auth_config: bool = False
    auth_type: str = "none"
    response_type: str = "json"
    response_path: str = ""
    query_params: dict = Field(default_factory=dict)
    body_template: dict | None = None
    agent_ids: list[str] | None = None
    is_active: bool = True
    input_schema: dict = Field(default_factory=lambda: {"parameters": []})
    last_tested_at: datetime | None = None
    last_test_status: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ApiIntegrationCreateRequest(BaseModel):
    name: str
    description: str = ""
    url: str
    method: str = "POST"
    headers: dict[str, str] = Field(default_factory=dict)
    body_template: dict | None = None
    query_params: dict[str, str] = Field(default_factory=dict)
    auth_type: str = "none"
    auth_config: dict = Field(default_factory=dict)
    response_type: str = "json"
    response_path: str = ""
    agent_ids: list[str] | None = None
    input_schema: dict = Field(default_factory=lambda: {"parameters": []})


class ApiIntegrationUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    url: str | None = None
    method: str | None = None
    headers: dict[str, str] | None = None
    body_template: dict | None = None
    query_params: dict[str, str] | None = None
    auth_type: str | None = None
    auth_config: dict | None = None
    response_type: str | None = None
    response_path: str | None = None
    agent_ids: list[str] | None = None
    is_active: bool | None = None
    input_schema: dict | None = None


class ApiIntegrationTestResult(BaseModel):
    success: bool
    status_code: int | None = None
    response_preview: str | None = None
    error: str | None = None


class FlowValidationResult(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0


class ChatMessageRequest(BaseModel):
    conversation_id: str | None = None
    message: str = ""
    contact_name: str | None = None  # outbound: nombre del contacto
    campaign_script: str | None = None  # script de campaña que reemplaza el prompt
    flow_override: dict | None = None  # flujo temporal desde el editor (no guardado aún)


class ChatMessageResponse(BaseModel):
    conversation_id: str
    role: str = "agent"
    text: str
    tool_calls: list[dict] = Field(default_factory=list)


class ChatResetResponse(BaseModel):
    message: str


class MessageResponse(BaseModel):
    message: str


class PaginatedResponse(BaseModel):
    data: list = Field(default_factory=list)
    total: int = 0
    page: int = 1
    per_page: int = 20


# ── Helpers ──────────────────────────────────────────

def client_out_from_row(row: dict) -> ClientOut:
    """Convierte un row de DB a ClientOut, reemplazando API keys con booleans has_*."""
    data = dict(row)
    # Convertir presencia de keys a booleans y eliminar las keys reales
    data["has_stt_api_key"] = bool(data.pop("stt_api_key", None))
    data["has_llm_api_key"] = bool(data.pop("llm_api_key", None))
    data["has_tts_api_key"] = bool(data.pop("tts_api_key", None))
    data["has_realtime_api_key"] = bool(data.pop("realtime_api_key", None))
    # Eliminar google_service_account_key del output (es un JSON grande)
    data.pop("google_service_account_key", None)
    return ClientOut(**data)


def mcp_server_out_from_row(row: dict) -> McpServerOut:
    """Convierte un row de DB mcp_servers a McpServerOut, ocultando secrets."""
    data = dict(row)
    # Convertir presencia de secrets a booleans
    data["has_headers"] = bool(data.pop("headers", None))
    data["has_env_vars"] = bool(data.pop("env_vars", None))
    return McpServerOut(**data)


def agent_out_from_row(row: dict) -> AgentOut:
    """Convierte un row de DB agents a AgentOut, strip API keys."""
    data = dict(row)
    # Strip API keys de voice_config, llm_config, stt_config
    for config_key in ("voice_config", "llm_config", "stt_config"):
        cfg = data.get(config_key) or {}
        if isinstance(cfg, dict):
            stripped = dict(cfg)
            has_key = bool(stripped.pop("api_key", None))
            has_realtime = bool(stripped.pop("realtime_api_key", None))
            stripped["has_api_key"] = has_key
            if config_key == "voice_config":
                stripped["has_realtime_api_key"] = has_realtime
            data[config_key] = stripped
    # Eliminar columna clients si viene del join
    data.pop("clients", None)
    return AgentOut(**data)


def api_integration_out_from_row(row: dict) -> ApiIntegrationOut:
    """Convierte un row de DB api_integrations a ApiIntegrationOut, ocultando secrets."""
    data = dict(row)
    data["has_headers"] = bool(data.pop("headers", None))
    data["has_auth_config"] = bool(data.pop("auth_config", None))
    return ApiIntegrationOut(**data)
