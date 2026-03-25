from __future__ import annotations
"""Context assembly for AI conversations.

PERFORMANCE OPTIMIZED:
- Parallel database queries using asyncio.gather()
- Smart query skipping based on query type
- Conversation-level caching
- Batch queries where possible
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import Fact, Pattern
from app.models.skill import Skill
from app.models.goal import Goal, Streak
from app.models.user import User

logger = logging.getLogger(__name__)

# Simple queries that don't need full context
SIMPLE_QUERY_PATTERNS = [
    "what time", "what's the time", "current time",
    "what date", "what's the date", "today's date",
    "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
    "thanks", "thank you", "ok", "okay", "got it",
]

# Context cache (conversation_id -> (timestamp, context))
_context_cache: Dict[str, Tuple[datetime, str]] = {}
_CACHE_TTL_SECONDS = 60  # Cache context for 1 minute within same conversation


def _is_simple_query(query: str) -> bool:
    """Check if query is simple and doesn't need full context."""
    query_lower = query.lower().strip()
    return any(pattern in query_lower for pattern in SIMPLE_QUERY_PATTERNS)


def _get_cache_key(user_id: UUID, conversation_id: Optional[str] = None) -> str:
    """Generate cache key for context."""
    return f"{user_id}:{conversation_id or 'default'}"


class ContextAssembler:
    """Assembles context for AI conversations from various sources."""

    def __init__(self, db: AsyncSession, vector_store=None):
        """
        Initialize context assembler.

        Args:
            db: Database session
            vector_store: Optional vector store for semantic search
        """
        self.db = db
        self.vector_store = vector_store

    async def assemble_context(
        self, query: str, user_id: UUID, max_tokens: int = 2000,
        conversation_id: Optional[str] = None, use_cache: bool = True
    ) -> str:
        """
        Assemble relevant context for a query.

        OPTIMIZED: Uses parallel queries and smart caching.

        Args:
            query: The user's query
            user_id: User ID for context
            max_tokens: Maximum tokens for context
            conversation_id: Optional conversation ID for caching
            use_cache: Whether to use context cache

        Returns:
            Assembled context string
        """
        start_time = datetime.now()

        # Check cache first (for same conversation within TTL)
        if use_cache and conversation_id:
            cache_key = _get_cache_key(user_id, conversation_id)
            if cache_key in _context_cache:
                cached_time, cached_context = _context_cache[cache_key]
                if (datetime.now() - cached_time).total_seconds() < _CACHE_TTL_SECONDS:
                    logger.debug(f"Context cache HIT for {cache_key}")
                    return cached_context

        # For simple queries, skip heavy context loading
        if _is_simple_query(query):
            logger.debug(f"Simple query detected, using minimal context")
            identity = await self._get_user_identity(user_id)
            name = identity.get('name', 'User') if identity else 'User'
            return f"## About {name}\nUser is asking a simple question."

        # PARALLEL QUERY EXECUTION - This is the key optimization!
        # Run all database queries concurrently instead of sequentially
        results = await asyncio.gather(
            self._get_user_identity(user_id),
            self._get_relevant_facts(user_id, limit=10),
            self._get_active_goals(user_id),
            self._get_recent_skills(user_id, days=30),
            self._get_patterns(user_id, limit=5),
            # Only search memories if vector store is available and query is complex
            self._search_memories(query, user_id) if self.vector_store and len(query) > 20 else asyncio.sleep(0),
            return_exceptions=True  # Don't fail if one query fails
        )

        # Unpack results
        identity, facts, goals, skills, patterns, memories = results[:6]

        context_parts = []

        # 1. User identity
        if identity and not isinstance(identity, Exception):
            context_parts.append(f"## About {identity.get('name', 'User')}\n{identity.get('description', '')}")

        # 2. Relevant facts
        if facts and not isinstance(facts, Exception) and len(facts) > 0:
            facts_str = "\n".join([f"- {f.key}: {f.value}" for f in facts])
            context_parts.append(f"## Known Facts\n{facts_str}")

        # 3. Active goals
        if goals and not isinstance(goals, Exception) and len(goals) > 0:
            goals_str = "\n".join(
                [f"- {g.title}: {g.progress_percentage:.0f}% complete" for g in goals]
            )
            context_parts.append(f"## Active Goals\n{goals_str}")

        # 4. Recent skills
        if skills and not isinstance(skills, Exception) and len(skills) > 0:
            skills_str = "\n".join(
                [f"- {s.name} (Level {s.current_level})" for s in skills]
            )
            context_parts.append(f"## Recent Skills\n{skills_str}")

        # 5. Patterns
        if patterns and not isinstance(patterns, Exception) and len(patterns) > 0:
            patterns_str = "\n".join([f"- {p.description}" for p in patterns])
            context_parts.append(f"## Observed Patterns\n{patterns_str}")

        # 6. Semantic memories
        if memories and not isinstance(memories, Exception) and memories:
            context_parts.append(f"## Relevant Memories\n{memories}")

        assembled = "\n\n".join(context_parts)

        # Cache the result
        if use_cache and conversation_id:
            cache_key = _get_cache_key(user_id, conversation_id)
            _context_cache[cache_key] = (datetime.now(), assembled)
            # Cleanup old cache entries
            _cleanup_context_cache()

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.debug(f"Context assembled in {elapsed:.3f}s (parallel queries)")

        return assembled

    async def get_current_state(self, user_id: UUID) -> str:
        """
        Get current state summary for the user.

        OPTIMIZED: Uses parallel queries.

        Args:
            user_id: User ID

        Returns:
            Current state summary string
        """
        state_parts = []

        # Today's date (instant, no DB)
        today = datetime.now()
        state_parts.append(f"Current date: {today.strftime('%A, %B %d, %Y')}")

        # PARALLEL: Fetch streaks and upcoming goals at the same time
        streaks, upcoming_goals = await asyncio.gather(
            self._get_active_streaks(user_id),
            self._get_upcoming_deadline_goals(user_id, days=7),
            return_exceptions=True
        )

        # Active streaks
        if streaks and not isinstance(streaks, Exception) and len(streaks) > 0:
            streaks_str = ", ".join(
                [f"{s.activity}: {s.current_count} days" for s in streaks]
            )
            state_parts.append(f"Active streaks: {streaks_str}")

        # Goals close to deadline
        if upcoming_goals and not isinstance(upcoming_goals, Exception) and len(upcoming_goals) > 0:
            goals_str = ", ".join([g.title for g in upcoming_goals])
            state_parts.append(f"Goals due soon: {goals_str}")

        return "\n".join(state_parts)


def _cleanup_context_cache():
    """Remove expired cache entries."""
    global _context_cache
    now = datetime.now()
    expired_keys = [
        key for key, (timestamp, _) in _context_cache.items()
        if (now - timestamp).total_seconds() > _CACHE_TTL_SECONDS * 2
    ]
    for key in expired_keys:
        del _context_cache[key]
    # Also limit cache size
    if len(_context_cache) > 100:
        # Remove oldest entries
        sorted_keys = sorted(_context_cache.keys(), key=lambda k: _context_cache[k][0])
        for key in sorted_keys[:50]:
            del _context_cache[key]

    async def _get_user_identity(self, user_id: UUID) -> Optional[Dict]:
        """Get user identity information."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if user:
            return {
                "name": user.name or "User",
                "description": user.settings.get("description", ""),
            }
        return None

    async def _get_relevant_facts(self, user_id: UUID, limit: int = 10) -> list[Fact]:
        """Get relevant facts for the user."""
        result = await self.db.execute(
            select(Fact)
            .where(Fact.user_id == user_id)
            .order_by(Fact.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _get_active_goals(self, user_id: UUID) -> list[Goal]:
        """Get active goals for the user."""
        result = await self.db.execute(
            select(Goal)
            .where(Goal.user_id == user_id, Goal.status == "active")
            .order_by(Goal.deadline.asc().nullslast())
        )
        return list(result.scalars().all())

    async def _get_recent_skills(self, user_id: UUID, days: int = 30) -> list[Skill]:
        """Get recently practiced skills."""
        cutoff = datetime.now() - timedelta(days=days)
        result = await self.db.execute(
            select(Skill)
            .where(
                Skill.user_id == user_id,
                Skill.last_practiced >= cutoff,
            )
            .order_by(Skill.last_practiced.desc())
            .limit(10)
        )
        return list(result.scalars().all())

    async def _get_patterns(self, user_id: UUID, limit: int = 5) -> list[Pattern]:
        """Get observed patterns for the user."""
        result = await self.db.execute(
            select(Pattern)
            .where(Pattern.user_id == user_id)
            .order_by(Pattern.confidence.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _get_active_streaks(self, user_id: UUID) -> list[Streak]:
        """Get active streaks for the user."""
        result = await self.db.execute(
            select(Streak)
            .where(Streak.user_id == user_id, Streak.current_count > 0)
            .order_by(Streak.current_count.desc())
        )
        return list(result.scalars().all())

    async def _get_upcoming_deadline_goals(
        self, user_id: UUID, days: int = 7
    ) -> list[Goal]:
        """Get goals with upcoming deadlines."""
        cutoff = datetime.now().date() + timedelta(days=days)
        result = await self.db.execute(
            select(Goal)
            .where(
                Goal.user_id == user_id,
                Goal.status == "active",
                Goal.deadline <= cutoff,
            )
            .order_by(Goal.deadline.asc())
        )
        return list(result.scalars().all())

    async def _search_memories(self, query: str, user_id: UUID) -> str:
        """Search for relevant memories using vector store."""
        if not self.vector_store:
            return ""

        # Placeholder for vector search integration
        # Will be implemented when ChromaDB is fully integrated
        try:
            results = await self.vector_store.search(
                query=query,
                user_id=str(user_id),
                limit=5,
            )
            if results:
                return "\n".join([r.get("content", "") for r in results])
        except Exception:
            pass
        return ""
