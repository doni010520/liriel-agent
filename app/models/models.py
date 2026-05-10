import uuid
from datetime import datetime, date

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Contact(Base):
    """WhatsApp contact / church member."""

    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    push_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str | None] = mapped_column(
        String(20)
    )  # membro, congregado, visitante
    birthday: Mapped[date | None] = mapped_column(Date)
    neighborhood: Mapped[str | None] = mapped_column(String(100))
    how_found: Mapped[str | None] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="contact", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_contacts_phone", "phone"),)


class Conversation(Base):
    """A conversation session with a contact."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    summary: Mapped[str | None] = mapped_column(Text)
    summary_message_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    contact: Mapped["Contact"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_conversations_contact_active", "contact_id", "is_active"),
    )


class Message(Base):
    """Individual message in a conversation."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(20), default="text")
    whatsapp_message_id: Mapped[str | None] = mapped_column(String(100))
    token_count: Mapped[int | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    __table_args__ = (
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )


class KnowledgeBase(Base):
    """Church knowledge base for RAG retrieval."""

    __tablename__ = "knowledge_base"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # embedding column (vector(1536)) created via SQL in rag_service.setup_pgvector
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("ix_knowledge_category", "category"),)


class Event(Base):
    """Church events with hybrid search support."""

    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[str | None] = mapped_column(String(20))  # "9h", "19h30"
    end_time: Mapped[str | None] = mapped_column(String(20))  # "17h", "21h"
    location: Mapped[str | None] = mapped_column(String(255))
    # embedding column (vector(1536)) created via SQL in events_service.setup_events_pgvector
    created_by: Mapped[str | None] = mapped_column(String(20))  # phone of admin
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_events_date", "event_date"),
        Index("ix_events_active_date", "is_active", "event_date"),
    )


class MediaAsset(Base):
    """Binary assets (profile pic, banners) hosted in the DB.

    Sync flow: files in /app/assets/ are read at boot, hashed, and upserted
    into this table. Anything that needs the binary (e.g. Uazapi profile
    picture push) reads from here, not from the filesystem.
    """

    __tablename__ = "media_assets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    last_pushed_sha256: Mapped[str | None] = mapped_column(String(64))
    last_pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class NotificationLog(Base):
    """Log of notifications sent to leadership."""

    __tablename__ = "notification_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    team: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[str | None] = mapped_column(Text)
    contact_phone: Mapped[str | None] = mapped_column(String(20))
    contact_name: Mapped[str | None] = mapped_column(String(255))
    notified_phone: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="sent")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
