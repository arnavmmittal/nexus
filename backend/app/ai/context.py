"""Context assembly for AI conversations."""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import Fact, Pattern
from app.models.skill import Skill
from app.models.goal import Goal, Streak
from app.models.user import User


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
        self, query: str, user_id: UUID, max_tokens: int = 2000
    ) -> str:
        """
        Assemble relevant context for a query.

        Args:
            query: The user's query
            user_id: User ID for context
            max_tokens: Maximum tokens for context

        Returns:
            Assembled context string
        """
        context_parts = []

        # 1. Load user identity
        identity = await self._get_user_identity(user_id)
        if identity:
            context_parts.append(f"## About {identity.get('name', 'User')}\n{identity.get('description', '')}")

        # 2. Load relevant facts
        facts = await self._get_relevant_facts(user_id, limit=10)
        if facts:
            facts_str = "\n".join([f"- {f.key}: {f.value}" for f in facts])
            context_parts.append(f"## Known Facts\n{facts_str}")

        # 3. Load active goals
        goals = await self._get_active_goals(user_id)
        if goals:
            goals_str = "\n".join(
                [f"- {g.title}: {g.progress_percentage:.0f}% complete" for g in goals]
            )
            context_parts.append(f"## Active Goals\n{goals_str}")

        # 4. Load recent skills
        skills = await self._get_recent_skills(user_id, days=30)
        if skills:
            skills_str = "\n".join(
                [f"- {s.name} (Level {s.current_level})" for s in skills]
            )
            context_parts.append(f"## Recent Skills\n{skills_str}")

        # 5. Load patterns
        patterns = await self._get_patterns(user_id, limit=5)
        if patterns:
            patterns_str = "\n".join([f"- {p.description}" for p in patterns])
            context_parts.append(f"## Observed Patterns\n{patterns_str}")

        # 6. Semantic search (if vector store available)
        if self.vector_store:
            relevant_memories = await self._search_memories(query, user_id)
            if relevant_memories:
                context_parts.append(f"## Relevant Memories\n{relevant_memories}")

        return "\n\n".join(context_parts)

    async def get_current_state(self, user_id: UUID) -> str:
        """
        Get current state summary for the user.

        Args:
            user_id: User ID

        Returns:
            Current state summary string
        """
        state_parts = []

        # Today's date
        today = datetime.now()
        state_parts.append(f"Current date: {today.strftime('%A, %B %d, %Y')}")

        # Active streaks
        streaks = await self._get_active_streaks(user_id)
        if streaks:
            streaks_str = ", ".join(
                [f"{s.activity}: {s.current_count} days" for s in streaks]
            )
            state_parts.append(f"Active streaks: {streaks_str}")

        # Goals close to deadline
        upcoming_goals = await self._get_upcoming_deadline_goals(user_id, days=7)
        if upcoming_goals:
            goals_str = ", ".join([g.title for g in upcoming_goals])
            state_parts.append(f"Goals due soon: {goals_str}")

        return "\n".join(state_parts)

    async def _get_user_identity(self, user_id: UUID) -> dict | None:
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
