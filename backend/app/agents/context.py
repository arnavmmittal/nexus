"""Shared context system for multi-agent collaboration.

This module provides a thread-safe shared context store that agents
can use to share memories, facts, and conversation context.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class ContextEntry:
    """An entry in the shared context.

    Attributes:
        key: Unique identifier for this entry
        value: The stored value
        created_at: When the entry was created
        updated_at: When the entry was last updated
        expires_at: Optional expiration time
        created_by: ID of the agent that created this entry
        tags: Optional tags for categorization
    """

    key: str
    value: Any
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    created_by: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary representation."""
        return {
            "key": self.key,
            "value": self.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_by": self.created_by,
            "tags": self.tags,
        }


@dataclass
class ConversationEntry:
    """An entry in a conversation context.

    Attributes:
        id: Unique identifier for this entry
        role: The role of the speaker (user, assistant, agent)
        content: The message content
        agent_id: ID of the agent if applicable
        timestamp: When this entry was added
        metadata: Additional metadata
    """

    role: str
    content: str
    id: str = field(default_factory=lambda: str(uuid4()))
    agent_id: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary representation."""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class SharedContext:
    """Thread-safe shared context store for agents.

    Provides key-value storage with optional TTL (time-to-live) for
    sharing information between agents. Also manages conversation
    context per conversation ID.

    Usage:
        context = SharedContext()
        await context.set("weather", {"temp": 72}, ttl=3600)
        weather = await context.get("weather")
    """

    def __init__(self, cleanup_interval: float = 60.0):
        """Initialize the shared context.

        Args:
            cleanup_interval: Seconds between cleanup of expired entries
        """
        # General key-value store
        self._store: Dict[str, ContextEntry] = {}

        # Conversation-specific context
        self._conversations: Dict[str, List[ConversationEntry]] = {}

        # Locks for thread-safe access
        self._store_lock = asyncio.Lock()
        self._conversation_locks: Dict[str, asyncio.Lock] = {}
        self._locks_lock = asyncio.Lock()

        # Cleanup task
        self._cleanup_interval = cleanup_interval
        self._cleanup_task: Optional[asyncio.Task] = None

        logger.info("SharedContext initialized")

    async def start_cleanup(self) -> None:
        """Start the background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Started SharedContext cleanup task")

    async def _cleanup_loop(self) -> None:
        """Background loop to clean up expired entries."""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def _cleanup_expired(self) -> None:
        """Remove expired entries from the store."""
        async with self._store_lock:
            expired_keys = [
                key for key, entry in self._store.items()
                if entry.is_expired()
            ]

            for key in expired_keys:
                del self._store[key]

            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired entries")

    async def _get_conversation_lock(self, conversation_id: str) -> asyncio.Lock:
        """Get or create a lock for a specific conversation."""
        async with self._locks_lock:
            if conversation_id not in self._conversation_locks:
                self._conversation_locks[conversation_id] = asyncio.Lock()
            return self._conversation_locks[conversation_id]

    async def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the shared context.

        Args:
            key: The key to retrieve
            default: Value to return if key not found or expired

        Returns:
            The stored value, or default if not found/expired
        """
        async with self._store_lock:
            entry = self._store.get(key)

            if entry is None:
                return default

            if entry.is_expired():
                del self._store[key]
                return default

            return entry.value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        created_by: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> None:
        """Set a value in the shared context.

        Args:
            key: The key to store under
            value: The value to store
            ttl: Optional time-to-live in seconds
            created_by: Optional agent ID that created this entry
            tags: Optional tags for categorization
        """
        expires_at = None
        if ttl is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)

        async with self._store_lock:
            now = datetime.now(timezone.utc)

            # Update existing entry or create new one
            if key in self._store:
                entry = self._store[key]
                entry.value = value
                entry.updated_at = now
                entry.expires_at = expires_at
                if created_by:
                    entry.created_by = created_by
                if tags:
                    entry.tags = tags
            else:
                self._store[key] = ContextEntry(
                    key=key,
                    value=value,
                    created_at=now,
                    updated_at=now,
                    expires_at=expires_at,
                    created_by=created_by,
                    tags=tags or [],
                )

            logger.debug(f"Set context key '{key}' (ttl={ttl}s, by={created_by})")

    async def delete(self, key: str) -> bool:
        """Delete a key from the shared context.

        Args:
            key: The key to delete

        Returns:
            True if key was deleted, False if not found
        """
        async with self._store_lock:
            if key in self._store:
                del self._store[key]
                logger.debug(f"Deleted context key '{key}'")
                return True
            return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists and is not expired.

        Args:
            key: The key to check

        Returns:
            True if key exists and is not expired
        """
        async with self._store_lock:
            entry = self._store.get(key)
            if entry is None:
                return False
            if entry.is_expired():
                del self._store[key]
                return False
            return True

    async def get_by_tag(self, tag: str) -> Dict[str, Any]:
        """Get all entries with a specific tag.

        Args:
            tag: The tag to filter by

        Returns:
            Dictionary of key -> value for matching entries
        """
        async with self._store_lock:
            result = {}
            for key, entry in self._store.items():
                if not entry.is_expired() and tag in entry.tags:
                    result[key] = entry.value
            return result

    async def get_by_agent(self, agent_id: str) -> Dict[str, Any]:
        """Get all entries created by a specific agent.

        Args:
            agent_id: The agent ID to filter by

        Returns:
            Dictionary of key -> value for matching entries
        """
        async with self._store_lock:
            result = {}
            for key, entry in self._store.items():
                if not entry.is_expired() and entry.created_by == agent_id:
                    result[key] = entry.value
            return result

    async def get_conversation_context(
        self,
        conversation_id: str,
        limit: Optional[int] = None
    ) -> List[ConversationEntry]:
        """Get the context for a specific conversation.

        Args:
            conversation_id: The conversation ID
            limit: Optional limit on number of entries (most recent)

        Returns:
            List of conversation entries
        """
        lock = await self._get_conversation_lock(conversation_id)
        async with lock:
            entries = self._conversations.get(conversation_id, [])
            if limit is not None:
                return entries[-limit:]
            return entries.copy()

    async def add_to_context(
        self,
        conversation_id: str,
        entry: ConversationEntry
    ) -> None:
        """Add an entry to a conversation's context.

        Args:
            conversation_id: The conversation ID
            entry: The conversation entry to add
        """
        lock = await self._get_conversation_lock(conversation_id)
        async with lock:
            if conversation_id not in self._conversations:
                self._conversations[conversation_id] = []

            self._conversations[conversation_id].append(entry)
            logger.debug(
                f"Added entry to conversation {conversation_id}: "
                f"role={entry.role}, agent={entry.agent_id}"
            )

    async def clear_conversation(self, conversation_id: str) -> int:
        """Clear all context for a conversation.

        Args:
            conversation_id: The conversation ID to clear

        Returns:
            Number of entries cleared
        """
        lock = await self._get_conversation_lock(conversation_id)
        async with lock:
            count = len(self._conversations.get(conversation_id, []))
            self._conversations.pop(conversation_id, None)
            logger.info(f"Cleared {count} entries from conversation {conversation_id}")
            return count

    async def get_conversation_summary(
        self,
        conversation_id: str
    ) -> Dict[str, Any]:
        """Get a summary of a conversation's context.

        Args:
            conversation_id: The conversation ID

        Returns:
            Summary dictionary with entry count and participants
        """
        entries = await self.get_conversation_context(conversation_id)

        agents = set()
        roles = set()

        for entry in entries:
            roles.add(entry.role)
            if entry.agent_id:
                agents.add(entry.agent_id)

        return {
            "conversation_id": conversation_id,
            "entry_count": len(entries),
            "agents": list(agents),
            "roles": list(roles),
            "first_entry": entries[0].timestamp.isoformat() if entries else None,
            "last_entry": entries[-1].timestamp.isoformat() if entries else None,
        }

    async def shutdown(self) -> None:
        """Shutdown the context and cleanup resources."""
        logger.info("Shutting down SharedContext")

        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        async with self._store_lock:
            self._store.clear()

        for conversation_id in list(self._conversations.keys()):
            await self.clear_conversation(conversation_id)

        logger.info("SharedContext shutdown complete")

    def __repr__(self) -> str:
        """String representation of the context."""
        return (
            f"SharedContext(entries={len(self._store)}, "
            f"conversations={len(self._conversations)})"
        )


# Global shared context instance
_shared_context: Optional[SharedContext] = None


def get_shared_context() -> SharedContext:
    """Get the global shared context instance.

    Returns:
        The singleton SharedContext instance
    """
    global _shared_context
    if _shared_context is None:
        _shared_context = SharedContext()
    return _shared_context
