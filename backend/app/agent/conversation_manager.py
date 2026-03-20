"""
Conversation Manager - Handles conversation persistence and retrieval.

Provides functionality for:
- Starting and ending conversations
- Adding messages to conversations
- Generating conversation summaries
- Searching conversation history
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db_session
from app.memory.vector_store import get_vector_store
from app.models.conversation import AgentConversation, ConversationMessage

logger = logging.getLogger(__name__)


class ConversationManager:
    """
    Manager for conversation persistence and retrieval.

    Handles the full lifecycle of conversations including:
    - Creation and ending of conversation sessions
    - Message storage and retrieval
    - AI-generated summaries
    - Vector search for conversation history
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the conversation manager.

        Args:
            db: AsyncSession for database operations
        """
        self.db = db
        self._vector_store = None

    @property
    def vector_store(self):
        """Lazy-load vector store."""
        if self._vector_store is None:
            self._vector_store = get_vector_store()
        return self._vector_store

    async def start_conversation(
        self,
        user_id: UUID,
        title: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> AgentConversation:
        """
        Start a new conversation session.

        Args:
            user_id: User ID for the conversation
            title: Optional title for the conversation
            extra_data: Optional extra data dict

        Returns:
            Created AgentConversation instance
        """
        conversation = AgentConversation(
            user_id=user_id,
            title=title,
            started_at=datetime.utcnow(),
            extra_data=extra_data or {},
        )

        self.db.add(conversation)
        await self.db.flush()

        logger.info(f"Started conversation {conversation.id} for user {user_id}")
        return conversation

    async def add_message(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        tool_calls: Optional[Dict[str, Any]] = None,
        tokens_used: Optional[int] = None,
    ) -> ConversationMessage:
        """
        Add a message to an existing conversation.

        Args:
            conversation_id: ID of the conversation
            role: Message role ('user', 'assistant', 'system')
            content: Message content
            tool_calls: Optional tool calls made by assistant
            tokens_used: Optional token count for this message

        Returns:
            Created ConversationMessage instance
        """
        message = ConversationMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            timestamp=datetime.utcnow(),
            tool_calls=tool_calls,
            tokens_used=tokens_used,
        )

        self.db.add(message)
        await self.db.flush()

        logger.debug(f"Added {role} message to conversation {conversation_id}")
        return message

    async def end_conversation(
        self,
        conversation_id: UUID,
        generate_summary: bool = True,
        summary: Optional[str] = None,
    ) -> AgentConversation:
        """
        End a conversation session.

        Marks the conversation as ended and optionally generates a summary.

        Args:
            conversation_id: ID of the conversation to end
            generate_summary: Whether to auto-generate a summary
            summary: Optional pre-generated summary to use

        Returns:
            Updated AgentConversation instance
        """
        # Get conversation with messages
        stmt = (
            select(AgentConversation)
            .options(selectinload(AgentConversation.messages))
            .where(AgentConversation.id == conversation_id)
        )
        result = await self.db.execute(stmt)
        conversation = result.scalar_one_or_none()

        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found")

        conversation.ended_at = datetime.utcnow()

        # Generate or use provided summary
        if summary:
            conversation.summary = summary
        elif generate_summary and conversation.messages:
            conversation.summary = await self._generate_summary(conversation)

        # Index conversation for vector search
        await self._index_conversation(conversation)

        await self.db.flush()
        logger.info(f"Ended conversation {conversation_id}")

        return conversation

    async def get_conversation(
        self,
        conversation_id: UUID,
        include_messages: bool = True,
    ) -> Optional[AgentConversation]:
        """
        Get a conversation by ID.

        Args:
            conversation_id: ID of the conversation
            include_messages: Whether to include messages

        Returns:
            AgentConversation or None
        """
        stmt = select(AgentConversation).where(
            AgentConversation.id == conversation_id
        )

        if include_messages:
            stmt = stmt.options(selectinload(AgentConversation.messages))

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_conversation(
        self,
        user_id: UUID,
    ) -> Optional[AgentConversation]:
        """
        Get the active (not ended) conversation for a user.

        Args:
            user_id: User ID

        Returns:
            Active AgentConversation or None
        """
        stmt = (
            select(AgentConversation)
            .options(selectinload(AgentConversation.messages))
            .where(
                AgentConversation.user_id == user_id,
                AgentConversation.ended_at.is_(None),
            )
            .order_by(desc(AgentConversation.started_at))
            .limit(1)
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_recent_conversations(
        self,
        user_id: UUID,
        limit: int = 10,
        offset: int = 0,
        include_active: bool = True,
    ) -> List[AgentConversation]:
        """
        Get recent conversations for a user.

        Args:
            user_id: User ID
            limit: Maximum number of conversations to return
            offset: Number of conversations to skip
            include_active: Whether to include active (not ended) conversations

        Returns:
            List of AgentConversation instances
        """
        stmt = (
            select(AgentConversation)
            .where(AgentConversation.user_id == user_id)
            .order_by(desc(AgentConversation.started_at))
            .offset(offset)
            .limit(limit)
        )

        if not include_active:
            stmt = stmt.where(AgentConversation.ended_at.isnot(None))

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def search_conversations(
        self,
        user_id: UUID,
        query: str,
        limit: int = 5,
        min_score: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """
        Search conversations using vector similarity.

        Args:
            user_id: User ID
            query: Search query
            limit: Maximum number of results
            min_score: Minimum similarity score (0-1)

        Returns:
            List of matching conversations with scores
        """
        # Search vector store for relevant conversations
        results = await self.vector_store.search(
            query=query,
            user_id=str(user_id),
            limit=limit * 2,  # Get more to filter
            min_score=min_score,
        )

        # Filter for conversation documents and get conversation IDs
        conversation_ids = set()
        for doc in results:
            metadata = doc.get("metadata", {})
            if metadata.get("type") == "conversation":
                conv_id = metadata.get("conversation_id")
                if conv_id:
                    conversation_ids.add(conv_id)

        if not conversation_ids:
            # Fall back to text search
            return await self._text_search_conversations(user_id, query, limit)

        # Fetch conversations
        stmt = (
            select(AgentConversation)
            .where(
                AgentConversation.user_id == user_id,
                AgentConversation.id.in_([UUID(cid) for cid in conversation_ids]),
            )
            .order_by(desc(AgentConversation.started_at))
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        conversations = result.scalars().all()

        # Build results with scores
        search_results = []
        for conv in conversations:
            # Find score from vector results
            score = 0.0
            for doc in results:
                if doc.get("metadata", {}).get("conversation_id") == str(conv.id):
                    score = max(score, doc.get("score", 0))

            search_results.append({
                "conversation": conv,
                "score": score,
            })

        return sorted(search_results, key=lambda x: x["score"], reverse=True)

    async def _text_search_conversations(
        self,
        user_id: UUID,
        query: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """
        Fall back to basic text search when vector search yields no results.

        Args:
            user_id: User ID
            query: Search query
            limit: Maximum number of results

        Returns:
            List of matching conversations
        """
        # Search in summaries and titles
        search_term = f"%{query.lower()}%"
        stmt = (
            select(AgentConversation)
            .where(
                AgentConversation.user_id == user_id,
                or_(
                    AgentConversation.summary.ilike(search_term),
                    AgentConversation.title.ilike(search_term),
                ),
            )
            .order_by(desc(AgentConversation.started_at))
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        conversations = result.scalars().all()

        return [{"conversation": conv, "score": 0.5} for conv in conversations]

    async def _generate_summary(
        self,
        conversation: AgentConversation,
    ) -> str:
        """
        Generate a summary for a conversation using AI.

        Args:
            conversation: The conversation to summarize

        Returns:
            Generated summary string
        """
        # Build conversation text for summarization
        messages_text = []
        for msg in conversation.messages[:20]:  # Limit to first 20 messages
            role_label = "User" if msg.role == "user" else "Assistant"
            messages_text.append(f"{role_label}: {msg.content[:500]}")

        if not messages_text:
            return "Empty conversation"

        conversation_text = "\n".join(messages_text)

        # Try to use AI for summarization
        try:
            from anthropic import Anthropic

            client = Anthropic()
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=150,
                messages=[
                    {
                        "role": "user",
                        "content": f"Summarize this conversation in 1-2 sentences. Focus on the main topics and outcomes:\n\n{conversation_text}",
                    }
                ],
            )
            return response.content[0].text.strip()
        except Exception as e:
            logger.warning(f"Failed to generate AI summary: {e}")
            # Fall back to simple summary
            return self._simple_summary(conversation)

    def _simple_summary(self, conversation: AgentConversation) -> str:
        """
        Generate a simple summary without AI.

        Args:
            conversation: The conversation to summarize

        Returns:
            Simple summary string
        """
        message_count = len(conversation.messages)
        user_messages = [m for m in conversation.messages if m.role == "user"]

        if not user_messages:
            return f"Conversation with {message_count} messages"

        # Use first user message as summary base
        first_msg = user_messages[0].content[:100]
        if len(user_messages[0].content) > 100:
            first_msg += "..."

        return f"{first_msg} ({message_count} messages)"

    async def _index_conversation(self, conversation: AgentConversation) -> None:
        """
        Index conversation in vector store for search.

        Args:
            conversation: The conversation to index
        """
        # Build searchable content
        content_parts = []

        if conversation.title:
            content_parts.append(f"Title: {conversation.title}")

        if conversation.summary:
            content_parts.append(f"Summary: {conversation.summary}")

        # Include key message content
        for msg in conversation.messages[:10]:
            content_parts.append(f"{msg.role}: {msg.content[:200]}")

        if not content_parts:
            return

        content = "\n".join(content_parts)

        # Add to vector store
        try:
            await self.vector_store.add_document(
                content=content,
                user_id=str(conversation.user_id),
                metadata={
                    "type": "conversation",
                    "conversation_id": str(conversation.id),
                    "started_at": conversation.started_at.isoformat(),
                    "ended_at": conversation.ended_at.isoformat() if conversation.ended_at else None,
                },
                document_id=f"conversation:{conversation.id}",
            )
            logger.debug(f"Indexed conversation {conversation.id} in vector store")
        except Exception as e:
            logger.warning(f"Failed to index conversation {conversation.id}: {e}")

    async def delete_conversation(self, conversation_id: UUID) -> bool:
        """
        Delete a conversation and its messages.

        Args:
            conversation_id: ID of the conversation to delete

        Returns:
            True if deleted, False if not found
        """
        conversation = await self.get_conversation(
            conversation_id, include_messages=False
        )

        if conversation is None:
            return False

        # Delete from vector store
        try:
            await self.vector_store.delete_document(f"conversation:{conversation_id}")
        except Exception as e:
            logger.warning(f"Failed to delete conversation from vector store: {e}")

        # Delete from database (cascade will delete messages)
        await self.db.delete(conversation)
        await self.db.flush()

        logger.info(f"Deleted conversation {conversation_id}")
        return True

    async def get_conversation_messages(
        self,
        conversation_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ConversationMessage]:
        """
        Get messages for a conversation with pagination.

        Args:
            conversation_id: ID of the conversation
            limit: Maximum number of messages
            offset: Number of messages to skip

        Returns:
            List of ConversationMessage instances
        """
        stmt = (
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.timestamp)
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())


# Helper function for getting a conversation manager
async def get_conversation_manager() -> ConversationManager:
    """
    Get a conversation manager with a database session.

    Returns:
        ConversationManager instance with active database session
    """
    async with get_db_session() as db:
        yield ConversationManager(db)
