"""AI Engine - Claude integration for Nexus."""

import asyncio
from typing import AsyncGenerator
from uuid import UUID

from anthropic import Anthropic, AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.context import ContextAssembler
from app.ai.prompts import get_system_prompt
from app.core.config import settings


class AIEngine:
    """AI Engine for processing chat messages with Claude."""

    MODEL = "claude-sonnet-4-20250514"
    MAX_TOKENS = 4096

    def __init__(self, db: AsyncSession, vector_store=None):
        """
        Initialize AI Engine.

        Args:
            db: Database session
            vector_store: Optional vector store for memory search
        """
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.context_assembler = ContextAssembler(db, vector_store)
        self.conversation_history: dict[str, list[dict]] = {}

    async def chat(
        self,
        message: str,
        user_id: UUID,
        conversation_id: str | None = None,
        user_name: str = "User",
    ) -> str:
        """
        Send a message and get a response.

        Args:
            message: User message
            user_id: User ID for context
            conversation_id: Optional conversation ID for continuity
            user_name: User's name

        Returns:
            Assistant response string
        """
        # Generate conversation ID if not provided
        if not conversation_id:
            import uuid
            conversation_id = str(uuid.uuid4())

        # Assemble context
        context = await self.context_assembler.assemble_context(message, user_id)
        current_state = await self.context_assembler.get_current_state(user_id)

        # Build system prompt
        system_prompt = get_system_prompt(
            user_name=user_name,
            assembled_context=context,
            current_state=current_state,
        )

        # Get or create conversation history
        if conversation_id not in self.conversation_history:
            self.conversation_history[conversation_id] = []

        # Add user message to history
        self.conversation_history[conversation_id].append(
            {"role": "user", "content": message}
        )

        # Keep conversation history manageable (last 20 messages)
        messages = self.conversation_history[conversation_id][-20:]

        # Call Claude API
        response = await self.client.messages.create(
            model=self.MODEL,
            max_tokens=self.MAX_TOKENS,
            system=system_prompt,
            messages=messages,
        )

        # Extract response content
        assistant_message = response.content[0].text

        # Add assistant response to history
        self.conversation_history[conversation_id].append(
            {"role": "assistant", "content": assistant_message}
        )

        return assistant_message

    async def stream_chat(
        self,
        message: str,
        user_id: UUID,
        conversation_id: str | None = None,
        user_name: str = "User",
    ) -> AsyncGenerator[str, None]:
        """
        Stream a chat response.

        Args:
            message: User message
            user_id: User ID for context
            conversation_id: Optional conversation ID
            user_name: User's name

        Yields:
            Response content chunks
        """
        # Generate conversation ID if not provided
        if not conversation_id:
            import uuid
            conversation_id = str(uuid.uuid4())

        # Assemble context
        context = await self.context_assembler.assemble_context(message, user_id)
        current_state = await self.context_assembler.get_current_state(user_id)

        # Build system prompt
        system_prompt = get_system_prompt(
            user_name=user_name,
            assembled_context=context,
            current_state=current_state,
        )

        # Get or create conversation history
        if conversation_id not in self.conversation_history:
            self.conversation_history[conversation_id] = []

        # Add user message to history
        self.conversation_history[conversation_id].append(
            {"role": "user", "content": message}
        )

        # Keep conversation history manageable
        messages = self.conversation_history[conversation_id][-20:]

        # Stream response from Claude
        full_response = ""
        async with self.client.messages.stream(
            model=self.MODEL,
            max_tokens=self.MAX_TOKENS,
            system=system_prompt,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                full_response += text
                yield text

        # Add full response to history
        self.conversation_history[conversation_id].append(
            {"role": "assistant", "content": full_response}
        )

    def clear_conversation(self, conversation_id: str) -> None:
        """Clear conversation history."""
        if conversation_id in self.conversation_history:
            del self.conversation_history[conversation_id]

    def get_conversation_history(self, conversation_id: str) -> list[dict]:
        """Get conversation history."""
        return self.conversation_history.get(conversation_id, [])
