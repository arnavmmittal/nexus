"""Memory models - Facts, Patterns, Conversations."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.db_types import GUID, JSONType, generate_uuid

if TYPE_CHECKING:
    from app.models.user import User


class Fact(Base):
    """Explicit knowledge about the user."""

    __tablename__ = "facts"

    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=generate_uuid,
    )
    user_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id"),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'goal', 'preference', 'value', 'identity'
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="facts")


class Pattern(Base):
    """Learned behavioral patterns."""

    __tablename__ = "patterns"

    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=generate_uuid,
    )
    user_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id"),
        nullable=False,
    )
    domain: Mapped[str] = mapped_column(String(50), nullable=False)
    pattern_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONType(), default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    discovered_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="patterns")


class Conversation(Base):
    """Conversation records for memory.

    Stores conversation summaries and extracted information for
    long-term memory across sessions.
    """

    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=generate_uuid,
    )
    user_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id"),
        nullable=False,
        index=True,  # Index for faster user-based queries
    )
    source: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'nexus', 'claude_code', 'claude_web'
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extracted_facts: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONType(), nullable=True
    )
    extracted_skills: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONType(), nullable=True
    )

    # Additional fields for long-term memory
    title: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # Auto-generated title for the conversation
    topics: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONType(), nullable=True
    )  # Main topics discussed
    message_count: Mapped[Optional[int]] = mapped_column(
        nullable=True
    )  # Number of messages in conversation
    importance_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # How important this conversation is (0-1)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="conversations")

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get conversation duration in seconds."""
        if self.started_at is None or self.ended_at is None:
            return None
        return (self.ended_at - self.started_at).total_seconds()

    @property
    def has_summary(self) -> bool:
        """Check if conversation has a summary."""
        return self.summary is not None and len(self.summary) > 0

    @property
    def fact_count(self) -> int:
        """Get number of extracted facts."""
        if self.extracted_facts is None:
            return 0
        if isinstance(self.extracted_facts, list):
            return len(self.extracted_facts)
        return 0
