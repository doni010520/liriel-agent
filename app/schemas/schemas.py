from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


# ============================================================
# Uazapi Webhook Schemas
# These will be adjusted once we have the exact v2 docs
# ============================================================

class UazapiWebhookData(BaseModel):
    """Incoming message data from Uazapi webhook."""
    id: str | None = None
    phone: str | None = None  # remoteJid / from
    body: str | None = None  # message text
    type: str | None = None  # text, image, audio, etc.
    timestamp: int | None = None
    push_name: str | None = None
    is_group: bool = False

    class Config:
        extra = "allow"  # accept unknown fields from Uazapi


class UazapiWebhookPayload(BaseModel):
    """Top-level webhook payload from Uazapi.
    Structure will be confirmed with actual v2 docs.
    """
    instance: str | None = None
    event: str | None = None
    data: dict | None = None  # raw dict, parsed manually

    class Config:
        extra = "allow"


# ============================================================
# API Response Schemas
# ============================================================

class ContactResponse(BaseModel):
    id: UUID
    phone: str
    name: str | None
    push_name: str | None
    is_blocked: bool
    created_at: datetime


class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    message_type: str
    created_at: datetime


class ConversationResponse(BaseModel):
    id: UUID
    contact: ContactResponse
    is_active: bool
    is_ai_enabled: bool
    messages: list[MessageResponse] = []
    created_at: datetime


class HealthResponse(BaseModel):
    status: str
    database: str
    redis: str
    version: str = "1.0.0"
