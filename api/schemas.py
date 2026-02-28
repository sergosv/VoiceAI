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
    metadata: dict = Field(default_factory=dict)
    intencion: str | None = None
    lead_score: int | None = None
    siguiente_accion: str | None = None
    preguntas_sin_respuesta: list[str] | None = None


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


# ── Generic ───────────────────────────────────────────

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
