"""app/models/chat.py — ORM tables historique BO6 (schéma bo6_tracking Supabase)."""
import uuid
from datetime import datetime
from sqlalchemy import JSON, Boolean, DateTime, Double, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.engine import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    __table_args__ = {"schema": "bo6_tracking"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str | None] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    interactions: Mapped[list["ChatInteraction"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    reports: Mapped[list["ReportRecord"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class ChatInteraction(Base):
    __tablename__ = "chat_interactions"
    __table_args__ = {"schema": "bo6_tracking"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bo6_tracking.chat_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    sequence_number: Mapped[int] = mapped_column(Integer, default=1)
    original_query: Mapped[str] = mapped_column(Text, nullable=False)
    detected_language: Mapped[str] = mapped_column(String(10), default="unknown")
    translated_query: Mapped[str | None] = mapped_column(Text)
    detected_intent: Mapped[str | None] = mapped_column(String(64), index=True)
    intent_confidence: Mapped[float | None] = mapped_column(Double)
    intent_probabilities: Mapped[dict | None] = mapped_column(JSON)
    routed_to_agent: Mapped[str | None] = mapped_column(String(64))
    agent_url: Mapped[str | None] = mapped_column(String(256))
    agent_raw_response: Mapped[dict | None] = mapped_column(JSON)
    response_text: Mapped[str | None] = mapped_column(Text)
    explanation_json: Mapped[dict | None] = mapped_column(JSON)
    pipeline_steps_json: Mapped[dict | None] = mapped_column(JSON)
    confidence_score: Mapped[float | None] = mapped_column(Double)
    report_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    report_path: Mapped[str | None] = mapped_column(String(512))
    processing_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    is_darija: Mapped[bool] = mapped_column(Boolean, default=False)
    darija_terms: Mapped[dict | None] = mapped_column(JSON)
    top_ngrams: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    session: Mapped["ChatSession"] = relationship(back_populates="interactions")


class ReportRecord(Base):
    __tablename__ = "report_records"
    __table_args__ = {"schema": "bo6_tracking"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bo6_tracking.chat_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    report_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    parameters: Mapped[dict | None] = mapped_column(JSON)
    summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    session: Mapped["ChatSession"] = relationship(back_populates="reports")
