"""Pydantic schemas para el Asistente Personal."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# ── Authorized Callers ───────────────────────────────────


class PaCallerOut(BaseModel):
    id: str
    agent_id: str
    phone_number: str
    label: str | None = None
    is_owner: bool = False
    reminder_delivery: str = "both"
    created_at: datetime | None = None


class PaCallerCreateRequest(BaseModel):
    phone_number: str
    label: str | None = None
    is_owner: bool = False
    reminder_delivery: str = "both"

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        import re
        v = v.strip()
        if not re.match(r"^\+?[0-9\s\-()]{7,20}$", v):
            raise ValueError("Formato de teléfono inválido.")
        return v

    @field_validator("reminder_delivery")
    @classmethod
    def validate_delivery(cls, v: str) -> str:
        if v not in ("call", "whatsapp", "both"):
            raise ValueError("Delivery debe ser 'call', 'whatsapp' o 'both'.")
        return v


# ── Memory Items ─────────────────────────────────────────


class PaMemoryItemOut(BaseModel):
    id: str
    agent_id: str
    item_type: str
    content: str
    metadata: dict = Field(default_factory=dict)
    is_completed: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PaTaskUpdateRequest(BaseModel):
    is_completed: bool | None = None
    content: str | None = None
    metadata: dict | None = None


# ── Email Config ─────────────────────────────────────────


class PaEmailConfigOut(BaseModel):
    id: str
    agent_id: str
    from_name: str
    from_email: str
    reply_to: str | None = None
    signature: str | None = None
    created_at: datetime | None = None


class PaEmailConfigRequest(BaseModel):
    from_name: str = Field(..., min_length=1, max_length=200)
    from_email: str
    reply_to: str | None = None
    signature: str | None = None

    @field_validator("from_email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        import re
        v = v.strip().lower()
        if not re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("Formato de email inválido.")
        return v
