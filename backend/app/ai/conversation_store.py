"""Conversation persistence layer.

Stores and retrieves conversation history from the database.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import AgentConversation, ConversationMessage

logger = logging.getLogger(__name__)


class ConversationStore:
    """Manages conversation persistence to database."""

    def __init__(self, db: AsyncSession, user_id: Optional[UUID] = None):
        self.db = db
        self.user_id = user_id or UUID("00000000-0000-0000-0000-000000000001")

    async def get_or_create_conversation(
        self, conversation_id: str
    ) -> AgentConversation:
        """Get existing conversation or create a new one."""
        try:
            conv_uuid = UUID(conversation_id)
        except (ValueError, TypeError):
            # Generate a deterministic UUID from string ID
            import hashlib
            hash_bytes = hashlib.md5(conversation_id.encode()).digest()
            conv_uuid = UUID(bytes=hash_bytes)

        # Try to find existing
        result = await self.db.execute(
            select(AgentConversation).where(AgentConversation.id == conv_uuid)
        )
        conversation = result.scalar_one_or_none()

        if conversation is None:
            conversation = AgentConversation(
                id=conv_uuid,
                user_id=self.user_id,
                started_at=datetime.utcnow(),
            )
            self.db.add(conversation)
            await self.db.commit()
            await self.db.refresh(conversation)
            logger.debug(f"Created new conversation: {conv_uuid}")

        return conversation

    async def load_messages(
        self, conversation_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Load conversation messages from database."""
        conversation = await self.get_or_create_conversation(conversation_id)

        result = await self.db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation.id)
            .order_by(ConversationMessage.timestamp.desc())
            .limit(limit)
        )
        messages = result.scalars().all()

        # Convert to Claude message format (reverse to chronological order)
        claude_messages = []
        for msg in reversed(messages):
            claude_messages.append({
                "role": msg.role,
                "content": msg.content,
            })

        logger.debug(f"Loaded {len(claude_messages)} messages for {conversation_id}")
        return claude_messages

    async def save_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        tool_calls: Optional[Dict[str, Any]] = None,
        tokens_used: Optional[int] = None,
    ) -> ConversationMessage:
        """Save a message to the database."""
        conversation = await self.get_or_create_conversation(conversation_id)

        message = ConversationMessage(
            conversation_id=conversation.id,
            role=role,
            content=content,
            timestamp=datetime.utcnow(),
            tool_calls=tool_calls,
            tokens_used=tokens_used,
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)

        logger.debug(f"Saved {role} message to {conversation_id}")
        return message

    async def save_user_message(self, conversation_id: str, content: str):
        """Save a user message."""
        return await self.save_message(conversation_id, "user", content)

    async def save_assistant_message(
        self,
        conversation_id: str,
        content: str,
        tool_calls: Optional[Dict[str, Any]] = None,
        tokens_used: Optional[int] = None,
    ):
        """Save an assistant message."""
        return await self.save_message(
            conversation_id, "assistant", content, tool_calls, tokens_used
        )

    async def get_conversation_summary(self, conversation_id: str) -> Optional[str]:
        """Get conversation summary if exists."""
        conversation = await self.get_or_create_conversation(conversation_id)
        return conversation.summary

    async def set_conversation_summary(self, conversation_id: str, summary: str):
        """Set conversation summary."""
        conversation = await self.get_or_create_conversation(conversation_id)
        conversation.summary = summary
        await self.db.commit()

    async def clear_conversation(self, conversation_id: str):
        """Clear all messages from a conversation."""
        conversation = await self.get_or_create_conversation(conversation_id)

        # Delete all messages
        await self.db.execute(
            ConversationMessage.__table__.delete().where(
                ConversationMessage.conversation_id == conversation.id
            )
        )
        await self.db.commit()
        logger.info(f"Cleared conversation: {conversation_id}")
