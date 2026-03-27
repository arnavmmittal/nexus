"""Long-Term Memory System for Jarvis/Ultron.

This module provides persistent memory across conversation sessions:
- Store conversation summaries
- Extract and remember key facts
- Semantic search over past conversations
- "Remember when we discussed X?" capability

The memory system makes the AI feel truly intelligent by maintaining
context across sessions and learning from every interaction.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from anthropic import AsyncAnthropic
from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

logger = logging.getLogger(__name__)


class MemoryType(str, Enum):
    """Types of memory entries."""
    CONVERSATION_SUMMARY = "conversation_summary"
    KEY_FACT = "key_fact"
    USER_PREFERENCE = "user_preference"
    DECISION = "decision"
    TASK_OUTCOME = "task_outcome"
    IMPORTANT_EVENT = "important_event"


class FactCategory(str, Enum):
    """Categories for extracted facts."""
    PERSONAL = "personal"           # Personal info (name, relationships)
    PREFERENCE = "preference"       # User preferences
    WORK = "work"                   # Work/career related
    PROJECT = "project"             # Specific projects discussed
    GOAL = "goal"                   # Goals and aspirations
    SCHEDULE = "schedule"           # Schedule/timing preferences
    TECHNICAL = "technical"         # Technical knowledge/preferences
    DECISION = "decision"           # Decisions made
    CONTEXT = "context"             # General context
    OTHER = "other"


@dataclass
class MemoryEntry:
    """A single memory entry."""
    id: str = ""
    user_id: str = ""
    memory_type: MemoryType = MemoryType.CONVERSATION_SUMMARY

    # Content
    content: str = ""
    summary: str = ""
    key_facts: List[Dict[str, Any]] = field(default_factory=list)

    # Source tracking
    conversation_id: Optional[str] = None
    source: str = "nexus"  # nexus, claude_code, etc.

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_accessed: Optional[str] = None

    # Relevance tracking
    access_count: int = 0
    importance_score: float = 0.5  # 0-1, how important this memory is

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["memory_type"] = self.memory_type.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        if "memory_type" in data and isinstance(data["memory_type"], str):
            data["memory_type"] = MemoryType(data["memory_type"])
        return cls(**data)


@dataclass
class ExtractedFact:
    """A fact extracted from a conversation."""
    id: str = ""
    user_id: str = ""

    # Content
    fact: str = ""
    category: FactCategory = FactCategory.OTHER
    confidence: float = 0.8

    # Source
    conversation_id: Optional[str] = None
    source_message: Optional[str] = None

    # Timestamps
    extracted_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_verified: Optional[str] = None

    # Usage
    times_referenced: int = 0

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["category"] = self.category.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtractedFact":
        if "category" in data and isinstance(data["category"], str):
            data["category"] = FactCategory(data["category"])
        return cls(**data)


class LongTermMemory:
    """Long-term memory system for AI conversations.

    Provides:
    - Persistent conversation summaries
    - Key fact extraction and storage
    - Semantic search over past conversations
    - "Remember when we discussed X?" capability
    """

    # Prompts for memory operations
    SUMMARY_PROMPT = """Summarize this conversation concisely. Focus on:
1. Main topics discussed
2. Key decisions or conclusions reached
3. Action items or commitments made
4. Important information shared by the user
5. Any problems solved or questions answered

Keep the summary under 300 words but capture all essential information.

CONVERSATION:
{conversation}

SUMMARY:"""

    FACT_EXTRACTION_PROMPT = """Extract key facts from this conversation that should be remembered.

For each fact, provide:
- fact: The specific piece of information
- category: One of: personal, preference, work, project, goal, schedule, technical, decision, context, other
- confidence: How confident you are this is accurate (0.0-1.0)
- importance: How important this is to remember (0.0-1.0)

Focus on:
- Personal information the user shared
- Preferences and habits
- Important dates or events mentioned
- Decisions made
- Goals or aspirations expressed
- Technical preferences or skills
- Relationships mentioned
- Project details

Return as JSON array. Only extract facts that would be useful to remember for future conversations.
If no important facts are found, return an empty array.

CONVERSATION:
{conversation}

FACTS (JSON array):"""

    def __init__(
        self,
        db: Optional[AsyncSession] = None,
        vector_store: Optional[Any] = None,
        user_id: Optional[UUID] = None,
    ):
        """Initialize long-term memory.

        Args:
            db: Database session for persistence
            vector_store: Vector store for semantic search
            user_id: User ID for filtering
        """
        self.db = db
        self.vector_store = vector_store
        self.user_id = user_id
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)

        # In-memory cache for fast access
        self._memory_cache: Dict[str, MemoryEntry] = {}
        self._fact_cache: Dict[str, ExtractedFact] = {}
        self._cache_loaded = False

    async def _ensure_cache_loaded(self):
        """Load memory from database into cache if not already loaded."""
        if self._cache_loaded or not self.db:
            return

        try:
            # Load recent memories from database
            from app.models.memory import Conversation, Fact

            if self.user_id:
                # Load conversation summaries
                result = await self.db.execute(
                    select(Conversation)
                    .where(Conversation.user_id == self.user_id)
                    .order_by(desc(Conversation.ended_at))
                    .limit(100)
                )
                conversations = result.scalars().all()

                for conv in conversations:
                    if conv.summary:
                        entry = MemoryEntry(
                            id=str(conv.id),
                            user_id=str(conv.user_id),
                            memory_type=MemoryType.CONVERSATION_SUMMARY,
                            content=conv.summary,
                            summary=conv.summary,
                            key_facts=conv.extracted_facts or [],
                            conversation_id=str(conv.id),
                            source=conv.source,
                            created_at=conv.started_at.isoformat() if conv.started_at else datetime.utcnow().isoformat(),
                        )
                        self._memory_cache[entry.id] = entry

                # Load facts
                result = await self.db.execute(
                    select(Fact)
                    .where(Fact.user_id == self.user_id)
                    .order_by(desc(Fact.created_at))
                    .limit(500)
                )
                facts = result.scalars().all()

                for fact in facts:
                    extracted = ExtractedFact(
                        id=str(fact.id),
                        user_id=str(fact.user_id),
                        fact=fact.value,
                        category=self._map_category(fact.category),
                        confidence=fact.confidence,
                        extracted_at=fact.created_at.isoformat(),
                    )
                    self._fact_cache[extracted.id] = extracted

                logger.info(
                    f"Loaded {len(self._memory_cache)} memories and "
                    f"{len(self._fact_cache)} facts from database"
                )

            self._cache_loaded = True

        except Exception as e:
            logger.warning(f"Failed to load memory cache: {e}")
            self._cache_loaded = True  # Don't retry on failure

    def _map_category(self, category: str) -> FactCategory:
        """Map database category string to FactCategory enum."""
        category_map = {
            "goal": FactCategory.GOAL,
            "preference": FactCategory.PREFERENCE,
            "value": FactCategory.PERSONAL,
            "identity": FactCategory.PERSONAL,
        }
        return category_map.get(category, FactCategory.OTHER)

    async def store_conversation_summary(
        self,
        conversation_id: str,
        summary: str,
        key_facts: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryEntry:
        """Store a conversation summary in long-term memory.

        Args:
            conversation_id: Unique conversation identifier
            summary: AI-generated summary of the conversation
            key_facts: List of key facts extracted
            metadata: Additional metadata

        Returns:
            Created MemoryEntry
        """
        await self._ensure_cache_loaded()

        entry = MemoryEntry(
            id=conversation_id,
            user_id=str(self.user_id) if self.user_id else "",
            memory_type=MemoryType.CONVERSATION_SUMMARY,
            content=summary,
            summary=summary,
            key_facts=key_facts or [],
            conversation_id=conversation_id,
            metadata=metadata or {},
        )

        # Store in cache
        self._memory_cache[entry.id] = entry

        # Persist to database
        if self.db and self.user_id:
            try:
                from app.models.memory import Conversation

                # Update or create conversation record
                result = await self.db.execute(
                    select(Conversation).where(Conversation.id == UUID(conversation_id))
                )
                existing = result.scalar_one_or_none()

                if existing:
                    existing.summary = summary
                    existing.extracted_facts = key_facts
                    existing.ended_at = datetime.utcnow()
                else:
                    conv = Conversation(
                        id=UUID(conversation_id),
                        user_id=self.user_id,
                        source="nexus",
                        started_at=datetime.utcnow(),
                        ended_at=datetime.utcnow(),
                        summary=summary,
                        extracted_facts=key_facts,
                    )
                    self.db.add(conv)

                await self.db.commit()
                logger.info(f"Stored conversation summary: {conversation_id}")

            except Exception as e:
                logger.error(f"Failed to persist conversation summary: {e}")

        # Store in vector store for semantic search
        if self.vector_store and self.user_id:
            try:
                await self.vector_store.add_document(
                    content=summary,
                    user_id=str(self.user_id),
                    metadata={
                        "type": "conversation_summary",
                        "conversation_id": conversation_id,
                        "created_at": entry.created_at,
                    },
                    document_id=f"conv_summary_{conversation_id}",
                )
                logger.debug(f"Added conversation summary to vector store")
            except Exception as e:
                logger.warning(f"Failed to add to vector store: {e}")

        return entry

    async def store_fact(
        self,
        fact: str,
        category: FactCategory = FactCategory.OTHER,
        confidence: float = 0.8,
        conversation_id: Optional[str] = None,
        source_message: Optional[str] = None,
    ) -> ExtractedFact:
        """Store a single fact in long-term memory.

        Args:
            fact: The fact to store
            category: Category of the fact
            confidence: Confidence score (0-1)
            conversation_id: Source conversation
            source_message: Original message the fact came from

        Returns:
            Created ExtractedFact
        """
        await self._ensure_cache_loaded()

        fact_id = hashlib.md5(f"{fact}:{category.value}".encode()).hexdigest()[:16]

        extracted = ExtractedFact(
            id=fact_id,
            user_id=str(self.user_id) if self.user_id else "",
            fact=fact,
            category=category,
            confidence=confidence,
            conversation_id=conversation_id,
            source_message=source_message,
        )

        # Check if similar fact exists (update instead of duplicate)
        existing = self._fact_cache.get(fact_id)
        if existing:
            # Update confidence if repeated
            existing.confidence = min(1.0, existing.confidence + 0.1)
            existing.times_referenced += 1
            existing.last_verified = datetime.utcnow().isoformat()
            extracted = existing
        else:
            self._fact_cache[fact_id] = extracted

        # Persist to database
        if self.db and self.user_id:
            try:
                from app.models.memory import Fact

                # Map FactCategory to database category
                db_category = self._category_to_db(category)

                result = await self.db.execute(
                    select(Fact).where(
                        and_(
                            Fact.user_id == self.user_id,
                            Fact.key == fact[:255],
                        )
                    )
                )
                existing_db = result.scalar_one_or_none()

                if existing_db:
                    existing_db.confidence = min(1.0, existing_db.confidence + 0.1)
                else:
                    db_fact = Fact(
                        user_id=self.user_id,
                        category=db_category,
                        key=fact[:255],
                        value=fact,
                        confidence=confidence,
                        source=f"conversation:{conversation_id}" if conversation_id else "extraction",
                    )
                    self.db.add(db_fact)

                await self.db.commit()

            except Exception as e:
                logger.error(f"Failed to persist fact: {e}")

        # Store in vector store
        if self.vector_store and self.user_id:
            try:
                await self.vector_store.add_document(
                    content=fact,
                    user_id=str(self.user_id),
                    metadata={
                        "type": "extracted_fact",
                        "category": category.value,
                        "confidence": confidence,
                        "conversation_id": conversation_id,
                    },
                    document_id=f"fact_{fact_id}",
                )
            except Exception as e:
                logger.warning(f"Failed to add fact to vector store: {e}")

        return extracted

    def _category_to_db(self, category: FactCategory) -> str:
        """Map FactCategory to database category string."""
        category_map = {
            FactCategory.PERSONAL: "identity",
            FactCategory.PREFERENCE: "preference",
            FactCategory.GOAL: "goal",
            FactCategory.WORK: "identity",
            FactCategory.PROJECT: "identity",
            FactCategory.SCHEDULE: "preference",
            FactCategory.TECHNICAL: "preference",
            FactCategory.DECISION: "value",
            FactCategory.CONTEXT: "identity",
            FactCategory.OTHER: "identity",
        }
        return category_map.get(category, "identity")

    async def recall_relevant(
        self,
        query: str,
        limit: int = 5,
        min_score: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """Find relevant past discussions for a query.

        This enables "remember when we discussed X?" functionality.

        Args:
            query: The query to search for
            limit: Maximum results to return
            min_score: Minimum relevance score

        Returns:
            List of relevant memories with scores
        """
        await self._ensure_cache_loaded()

        results = []

        # Search vector store first (semantic search)
        if self.vector_store and self.user_id:
            try:
                vector_results = await self.vector_store.search(
                    query=query,
                    user_id=str(self.user_id),
                    limit=limit * 2,  # Get more for filtering
                    min_score=min_score,
                )

                for result in vector_results:
                    results.append({
                        "content": result["content"],
                        "score": result["score"],
                        "type": result["metadata"].get("type", "unknown"),
                        "conversation_id": result["metadata"].get("conversation_id"),
                        "created_at": result["metadata"].get("created_at"),
                        "source": "vector_search",
                    })

            except Exception as e:
                logger.warning(f"Vector search failed: {e}")

        # Also search cache with keyword matching
        query_lower = query.lower()
        query_words = set(query_lower.split())

        for entry in self._memory_cache.values():
            content_lower = entry.content.lower()

            # Simple keyword matching score
            matching_words = sum(1 for word in query_words if word in content_lower)
            if matching_words > 0:
                score = matching_words / len(query_words) * 0.5  # Max 0.5 for keyword match

                results.append({
                    "content": entry.content,
                    "score": score,
                    "type": entry.memory_type.value,
                    "conversation_id": entry.conversation_id,
                    "created_at": entry.created_at,
                    "source": "cache_search",
                })

        # Also search facts
        for fact in self._fact_cache.values():
            fact_lower = fact.fact.lower()

            matching_words = sum(1 for word in query_words if word in fact_lower)
            if matching_words > 0:
                score = matching_words / len(query_words) * 0.6 * fact.confidence

                results.append({
                    "content": fact.fact,
                    "score": score,
                    "type": "fact",
                    "category": fact.category.value,
                    "conversation_id": fact.conversation_id,
                    "created_at": fact.extracted_at,
                    "source": "fact_search",
                })

        # Deduplicate and sort by score
        seen_content = set()
        unique_results = []
        for result in sorted(results, key=lambda x: x["score"], reverse=True):
            content_hash = hashlib.md5(result["content"].encode()).hexdigest()
            if content_hash not in seen_content:
                seen_content.add(content_hash)
                unique_results.append(result)

        return unique_results[:limit]

    async def get_conversation_history(
        self,
        days: int = 30,
        limit: int = 50,
    ) -> List[MemoryEntry]:
        """Get recent conversation summaries.

        Args:
            days: Number of days to look back
            limit: Maximum results

        Returns:
            List of recent conversation memories
        """
        await self._ensure_cache_loaded()

        cutoff = datetime.utcnow() - timedelta(days=days)
        cutoff_str = cutoff.isoformat()

        # Filter cache by date
        recent = [
            entry for entry in self._memory_cache.values()
            if entry.memory_type == MemoryType.CONVERSATION_SUMMARY
            and entry.created_at >= cutoff_str
        ]

        # Sort by date descending
        recent.sort(key=lambda x: x.created_at, reverse=True)

        return recent[:limit]

    async def extract_key_facts(
        self,
        conversation: List[Dict[str, Any]],
        conversation_id: Optional[str] = None,
    ) -> List[ExtractedFact]:
        """Use Claude to extract important facts from a conversation.

        Args:
            conversation: List of conversation messages
            conversation_id: Optional conversation ID for tracking

        Returns:
            List of extracted facts
        """
        # Format conversation for the prompt
        formatted = self._format_conversation(conversation)

        if not formatted.strip():
            return []

        prompt = self.FACT_EXTRACTION_PROMPT.format(conversation=formatted)

        try:
            response = await self.client.messages.create(
                model="claude-haiku-4-5-20251001",  # Use fast/cheap model
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = response.content[0].text if response.content else "[]"

            # Parse JSON response
            try:
                # Find JSON array in response
                start = response_text.find("[")
                end = response_text.rfind("]") + 1
                if start >= 0 and end > start:
                    facts_json = json.loads(response_text[start:end])
                else:
                    facts_json = []
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse fact extraction response")
                facts_json = []

            # Convert to ExtractedFact objects and store
            extracted_facts = []
            for fact_data in facts_json:
                if not isinstance(fact_data, dict) or "fact" not in fact_data:
                    continue

                category_str = fact_data.get("category", "other").lower()
                try:
                    category = FactCategory(category_str)
                except ValueError:
                    category = FactCategory.OTHER

                confidence = float(fact_data.get("confidence", 0.8))

                fact = await self.store_fact(
                    fact=fact_data["fact"],
                    category=category,
                    confidence=confidence,
                    conversation_id=conversation_id,
                )
                extracted_facts.append(fact)

            logger.info(f"Extracted {len(extracted_facts)} facts from conversation")
            return extracted_facts

        except Exception as e:
            logger.error(f"Fact extraction failed: {e}")
            return []

    async def search_memory(
        self,
        query: str,
        memory_types: Optional[List[MemoryType]] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Semantic search over all memory.

        Args:
            query: Search query
            memory_types: Filter by memory types (None = all)
            limit: Maximum results

        Returns:
            List of matching memories
        """
        # Use recall_relevant as the main search
        results = await self.recall_relevant(query, limit=limit * 2)

        # Filter by memory type if specified
        if memory_types:
            type_values = [t.value for t in memory_types]
            results = [
                r for r in results
                if r.get("type") in type_values or r.get("type") == "fact"
            ]

        return results[:limit]

    async def generate_conversation_summary(
        self,
        conversation: List[Dict[str, Any]],
    ) -> str:
        """Generate a summary of a conversation using Claude.

        Args:
            conversation: List of conversation messages

        Returns:
            Summary string
        """
        formatted = self._format_conversation(conversation)

        if not formatted.strip():
            return ""

        prompt = self.SUMMARY_PROMPT.format(conversation=formatted)

        try:
            response = await self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )

            summary = response.content[0].text if response.content else ""
            logger.info(f"Generated conversation summary ({len(summary)} chars)")
            return summary

        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return self._fallback_summary(conversation)

    def _format_conversation(self, conversation: List[Dict[str, Any]]) -> str:
        """Format conversation messages for prompts.

        Args:
            conversation: List of message dicts

        Returns:
            Formatted string
        """
        lines = []
        for msg in conversation:
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
                            lines.append(f"{role}: [Used tool: {item.get('name', 'unknown')}]")
                        elif item.get("type") == "tool_result":
                            result = str(item.get("content", ""))[:100]
                            lines.append(f"{role}: [Tool result: {result}...]")

        return "\n".join(lines)

    def _fallback_summary(self, conversation: List[Dict[str, Any]]) -> str:
        """Generate a basic summary without API call.

        Args:
            conversation: List of messages

        Returns:
            Basic summary string
        """
        message_count = len(conversation)
        user_messages = sum(1 for m in conversation if m.get("role") == "user")

        # Extract any tool names used
        tools_used = set()
        for msg in conversation:
            content = msg.get("content", [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_use":
                        tools_used.add(item.get("name", "unknown"))

        summary_parts = [f"Conversation with {message_count} messages ({user_messages} from user)"]
        if tools_used:
            summary_parts.append(f"Tools used: {', '.join(list(tools_used)[:5])}")

        return ". ".join(summary_parts)

    async def get_all_facts(
        self,
        category: Optional[FactCategory] = None,
        min_confidence: float = 0.5,
    ) -> List[ExtractedFact]:
        """Get all stored facts, optionally filtered.

        Args:
            category: Filter by category
            min_confidence: Minimum confidence threshold

        Returns:
            List of facts
        """
        await self._ensure_cache_loaded()

        facts = list(self._fact_cache.values())

        if category:
            facts = [f for f in facts if f.category == category]

        facts = [f for f in facts if f.confidence >= min_confidence]

        # Sort by confidence and recency
        facts.sort(key=lambda f: (f.confidence, f.extracted_at), reverse=True)

        return facts

    def get_context_for_prompt(self, max_facts: int = 10) -> str:
        """Generate context string with relevant memories for AI prompts.

        Args:
            max_facts: Maximum number of facts to include

        Returns:
            Formatted context string
        """
        lines = ["## Long-Term Memory\n"]

        # Add recent facts
        facts = sorted(
            self._fact_cache.values(),
            key=lambda f: (f.confidence, f.extracted_at),
            reverse=True
        )[:max_facts]

        if facts:
            lines.append("### Key Facts I Remember")
            for fact in facts:
                lines.append(f"- {fact.fact} (confidence: {fact.confidence:.1f})")

        # Add recent conversation topics
        recent_memories = sorted(
            [m for m in self._memory_cache.values()
             if m.memory_type == MemoryType.CONVERSATION_SUMMARY],
            key=lambda m: m.created_at,
            reverse=True
        )[:3]

        if recent_memories:
            lines.append("\n### Recent Conversation Topics")
            for memory in recent_memories:
                # Extract first sentence or first 100 chars
                preview = memory.summary.split(".")[0][:100]
                lines.append(f"- {preview}...")

        return "\n".join(lines) if len(lines) > 1 else ""

    async def end_conversation(
        self,
        conversation_id: str,
        messages: List[Dict[str, Any]],
    ) -> Tuple[str, List[ExtractedFact]]:
        """Process and store conversation when it ends.

        This should be called when a conversation session ends.
        It generates a summary, extracts facts, and stores everything.

        Args:
            conversation_id: The conversation ID
            messages: All messages in the conversation

        Returns:
            Tuple of (summary, extracted_facts)
        """
        if not messages:
            return "", []

        # Generate summary and extract facts in parallel
        import asyncio

        summary_task = self.generate_conversation_summary(messages)
        facts_task = self.extract_key_facts(messages, conversation_id)

        summary, facts = await asyncio.gather(summary_task, facts_task)

        # Store the summary
        if summary:
            key_facts_dicts = [f.to_dict() for f in facts]
            await self.store_conversation_summary(
                conversation_id=conversation_id,
                summary=summary,
                key_facts=key_facts_dicts,
            )

        logger.info(
            f"Ended conversation {conversation_id}: "
            f"summary={len(summary)} chars, facts={len(facts)}"
        )

        return summary, facts


# Global instance (lazy initialization)
_long_term_memory: Optional[LongTermMemory] = None


def get_long_term_memory(
    db: Optional[AsyncSession] = None,
    vector_store: Optional[Any] = None,
    user_id: Optional[UUID] = None,
) -> LongTermMemory:
    """Get or create the global long-term memory instance.

    Args:
        db: Database session
        vector_store: Vector store for semantic search
        user_id: User ID

    Returns:
        LongTermMemory instance
    """
    global _long_term_memory

    # Create new instance if parameters changed or not initialized
    if (_long_term_memory is None or
        (user_id and _long_term_memory.user_id != user_id)):
        _long_term_memory = LongTermMemory(
            db=db,
            vector_store=vector_store,
            user_id=user_id,
        )

    # Update db/vector_store if provided
    if db:
        _long_term_memory.db = db
    if vector_store:
        _long_term_memory.vector_store = vector_store

    return _long_term_memory
