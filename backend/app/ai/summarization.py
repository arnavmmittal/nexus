"""Conversation summarization for token efficiency.

This module provides intelligent conversation summarization to compress
long context windows while preserving important information.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from anthropic import AsyncAnthropic

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SummarizationConfig:
    """Configuration for conversation summarization."""

    # Token thresholds
    max_context_tokens: int = 8000  # Start summarizing above this
    target_context_tokens: int = 4000  # Target after summarization
    min_recent_messages: int = 4  # Always keep this many recent messages

    # Summarization behavior
    summarize_batch_size: int = 10  # Summarize this many messages at once
    preserve_tool_results: bool = True  # Keep tool call/result pairs intact

    # Model for summarization (use cheapest model)
    summarization_model: str = "claude-3-haiku-20240307"
    summarization_max_tokens: int = 500


# Approximate tokens per character (conservative estimate)
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Estimate token count from text length.

    Args:
        text: Text to estimate

    Returns:
        Estimated token count
    """
    return len(text) // CHARS_PER_TOKEN


def estimate_message_tokens(message: Dict[str, Any]) -> int:
    """Estimate tokens in a message.

    Args:
        message: Message dict with role and content

    Returns:
        Estimated token count
    """
    content = message.get("content", "")
    if isinstance(content, str):
        return estimate_tokens(content) + 10  # Overhead for role, etc.
    elif isinstance(content, list):
        total = 10
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    total += estimate_tokens(item.get("text", ""))
                elif item.get("type") == "tool_use":
                    total += estimate_tokens(str(item.get("input", {}))) + 20
                elif item.get("type") == "tool_result":
                    total += estimate_tokens(str(item.get("content", ""))) + 20
        return total
    return 50  # Default estimate


def estimate_conversation_tokens(messages: List[Dict[str, Any]]) -> int:
    """Estimate total tokens in a conversation.

    Args:
        messages: List of conversation messages

    Returns:
        Estimated total token count
    """
    return sum(estimate_message_tokens(msg) for msg in messages)


class ConversationSummarizer:
    """Summarizes conversation history to reduce token usage.

    Strategy:
    1. Keep the most recent N messages intact (for context continuity)
    2. Summarize older messages into a condensed summary
    3. Preserve key information: decisions, tool results, user preferences
    """

    SUMMARY_PROMPT = """Summarize the following conversation segment concisely.
Focus on:
- Key decisions and conclusions
- Important facts and data mentioned
- User preferences and requests
- Tool actions taken and their results
- Any errors or issues encountered

Keep the summary under 300 words. Use bullet points for clarity.

CONVERSATION:
{conversation}

SUMMARY:"""

    def __init__(self, config: Optional[SummarizationConfig] = None):
        """Initialize summarizer.

        Args:
            config: Summarization configuration
        """
        self.config = config or SummarizationConfig()
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._summary_cache: Dict[str, str] = {}

    def needs_summarization(self, messages: List[Dict[str, Any]]) -> bool:
        """Check if conversation needs summarization.

        Args:
            messages: Conversation messages

        Returns:
            True if summarization is needed
        """
        if len(messages) <= self.config.min_recent_messages:
            return False

        token_count = estimate_conversation_tokens(messages)
        return token_count > self.config.max_context_tokens

    def _split_messages(
        self,
        messages: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Split messages into old (to summarize) and recent (to keep).

        Args:
            messages: All conversation messages

        Returns:
            Tuple of (old_messages, recent_messages)
        """
        # Always keep min_recent_messages
        if len(messages) <= self.config.min_recent_messages:
            return [], messages

        # Find split point ensuring we keep complete tool call/result pairs
        split_idx = len(messages) - self.config.min_recent_messages

        # Ensure we don't split in the middle of a tool use sequence
        recent = messages[split_idx:]
        old = messages[:split_idx]

        # If first recent message is a tool_result, include its tool_use from old
        if recent and self._is_tool_result(recent[0]):
            # Find matching tool_use in old messages
            for i in range(len(old) - 1, -1, -1):
                if self._is_tool_use(old[i]):
                    # Move the tool_use to recent
                    recent = old[i:] + recent[len(old) - i:]
                    old = old[:i]
                    break

        return old, recent

    def _is_tool_use(self, message: Dict[str, Any]) -> bool:
        """Check if message contains tool use."""
        content = message.get("content", [])
        if isinstance(content, list):
            return any(
                isinstance(item, dict) and item.get("type") == "tool_use"
                for item in content
            )
        return False

    def _is_tool_result(self, message: Dict[str, Any]) -> bool:
        """Check if message contains tool result."""
        content = message.get("content", [])
        if isinstance(content, list):
            return any(
                isinstance(item, dict) and item.get("type") == "tool_result"
                for item in content
            )
        return False

    def _format_messages_for_summary(
        self,
        messages: List[Dict[str, Any]],
    ) -> str:
        """Format messages into text for summarization.

        Args:
            messages: Messages to format

        Returns:
            Formatted conversation text
        """
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")

            if isinstance(content, str):
                lines.append(f"{role}: {content}")
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            lines.append(f"{role}: {item.get('text', '')}")
                        elif item.get("type") == "tool_use":
                            tool_name = item.get("name", "unknown")
                            lines.append(f"{role}: [Used tool: {tool_name}]")
                        elif item.get("type") == "tool_result":
                            result = str(item.get("content", ""))[:200]
                            lines.append(f"{role}: [Tool result: {result}...]")

        return "\n".join(lines)

    async def _generate_summary(
        self,
        messages: List[Dict[str, Any]],
    ) -> str:
        """Generate a summary of messages using Claude.

        Args:
            messages: Messages to summarize

        Returns:
            Summary text
        """
        conversation_text = self._format_messages_for_summary(messages)

        # Check cache
        cache_key = hash(conversation_text)
        if cache_key in self._summary_cache:
            return self._summary_cache[cache_key]

        prompt = self.SUMMARY_PROMPT.format(conversation=conversation_text)

        try:
            response = await self.client.messages.create(
                model=self.config.summarization_model,
                max_tokens=self.config.summarization_max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )

            summary = response.content[0].text if response.content else ""

            # Cache the summary
            self._summary_cache[cache_key] = summary

            logger.info(
                f"Summarized {len(messages)} messages "
                f"({estimate_conversation_tokens(messages)} tokens) "
                f"into {estimate_tokens(summary)} tokens"
            )

            return summary

        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            # Fallback: just truncate
            return self._fallback_summary(messages)

    def _fallback_summary(self, messages: List[Dict[str, Any]]) -> str:
        """Generate a simple fallback summary without API call.

        Args:
            messages: Messages to summarize

        Returns:
            Basic summary
        """
        summary_parts = [f"[Previous conversation summary - {len(messages)} messages]"]

        # Extract key information
        tool_names = set()
        topics = []

        for msg in messages:
            content = msg.get("content", [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_use":
                        tool_names.add(item.get("name", "unknown"))

        if tool_names:
            summary_parts.append(f"Tools used: {', '.join(list(tool_names)[:5])}")

        return "\n".join(summary_parts)

    async def summarize_conversation(
        self,
        messages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Summarize a conversation to reduce token count.

        Args:
            messages: Full conversation messages

        Returns:
            Compressed messages list with summary
        """
        if not self.needs_summarization(messages):
            return messages

        old_messages, recent_messages = self._split_messages(messages)

        if not old_messages:
            return messages

        # Generate summary of old messages
        summary = await self._generate_summary(old_messages)

        # Create summary message
        summary_message = {
            "role": "user",
            "content": f"[CONVERSATION SUMMARY]\n{summary}\n[END SUMMARY - Recent messages follow]",
        }

        # Combine summary with recent messages
        result = [summary_message] + recent_messages

        original_tokens = estimate_conversation_tokens(messages)
        new_tokens = estimate_conversation_tokens(result)
        savings = original_tokens - new_tokens

        logger.info(
            f"Conversation compressed: {original_tokens} -> {new_tokens} tokens "
            f"(saved {savings} tokens, {savings * 100 // original_tokens}%)"
        )

        return result


# Global summarizer instance
_summarizer: Optional[ConversationSummarizer] = None


def get_summarizer() -> ConversationSummarizer:
    """Get the global conversation summarizer."""
    global _summarizer
    if _summarizer is None:
        _summarizer = ConversationSummarizer()
    return _summarizer


async def maybe_summarize(
    messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Summarize conversation if needed.

    Convenience function that checks if summarization is needed
    and applies it if so.

    Args:
        messages: Conversation messages

    Returns:
        Original or summarized messages
    """
    summarizer = get_summarizer()
    if summarizer.needs_summarization(messages):
        return await summarizer.summarize_conversation(messages)
    return messages
