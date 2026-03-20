"""Conversation models - Full conversation history with messages."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.db_types import GUID, JSONType, generate_uuid

if TYPE_CHECKING:
    from app.models.user import User


class AgentConversation(Base):
    """
    Agent conversation session.

    Tracks individual conversation sessions with the AI agent,
    including metadata like timing and AI-generated summaries.
    """

    __tablename__ = "agent_conversations"

    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=generate_uuid,
    )
    user_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    extra_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONType(),
        nullable=True,
        default=dict,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="agent_conversations")
    messages: Mapped[List["ConversationMessage"]] = relationship(
        "ConversationMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.timestamp",
    )

    @property
    def is_active(self) -> bool:
        """Check if conversation is still active (not ended)."""
        return self.ended_at is None

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get conversation duration in seconds."""
        if self.started_at is None:
            return None
        end = self.ended_at or datetime.utcnow()
        return (end - self.started_at).total_seconds()

    @property
    def message_count(self) -> int:
        """Get number of messages in conversation."""
        return len(self.messages)


class ConversationMessage(Base):
    """
    Individual message within a conversation.

    Stores the content, role (user/assistant), and any tool calls
    made by the assistant.
    """

    __tablename__ = "conversation_messages"

    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=generate_uuid,
    )
    conversation_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("agent_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )  # 'user', 'assistant', 'system'
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    tool_calls: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONType(),
        nullable=True,
    )
    tokens_used: Mapped[Optional[int]] = mapped_column(
        nullable=True,
    )

    # Relationships
    conversation: Mapped["AgentConversation"] = relationship(
        "AgentConversation",
        back_populates="messages",
    )

    @property
    def is_user_message(self) -> bool:
        """Check if this is a user message."""
        return self.role == "user"

    @property
    def is_assistant_message(self) -> bool:
        """Check if this is an assistant message."""
        return self.role == "assistant"

    @property
    def has_tool_calls(self) -> bool:
        """Check if message contains tool calls."""
        return self.tool_calls is not None and len(self.tool_calls) > 0
