"""Pydantic schemas for chat."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Schema for a chat message."""

    role: Literal["user", "assistant"] = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    """Schema for chat request."""

    message: str = Field(..., min_length=1, description="User message")
    conversation_id: str | None = Field(
        default=None, description="Conversation ID for context"
    )


class ChatResponse(BaseModel):
    """Schema for chat response."""

    message: str = Field(..., description="Assistant response")
    conversation_id: str = Field(..., description="Conversation ID")


class ChatStreamEvent(BaseModel):
    """Schema for streaming chat events."""

    type: Literal["content", "done", "error"] = Field(..., description="Event type")
    content: str | None = Field(default=None, description="Content chunk")
    conversation_id: str | None = Field(default=None, description="Conversation ID")
    error: str | None = Field(default=None, description="Error message if any")


class WidgetSubscription(BaseModel):
    """Schema for widget subscription."""

    widget: str = Field(..., description="Widget name to subscribe to")


class WebSocketMessage(BaseModel):
    """Schema for WebSocket messages."""

    type: Literal[
        "chat_message",
        "subscribe_widget",
        "unsubscribe_widget",
        "ping",
    ] = Field(..., description="Message type")
    content: str | None = Field(default=None, description="Message content")
    widget: str | None = Field(default=None, description="Widget name")
