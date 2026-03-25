"""Learning System - How the AI gets smarter over time.

This module enables continuous learning from:
- User corrections and feedback
- Successful vs failed actions
- Interaction patterns
- Preference signals (what user accepts/rejects)

The goal: Every interaction makes the AI better at serving you.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
import hashlib

logger = logging.getLogger(__name__)


class FeedbackType(str, Enum):
    """Types of learning feedback."""
    CORRECTION = "correction"           # User corrected AI's output
    ACCEPTANCE = "acceptance"           # User accepted suggestion
    REJECTION = "rejection"             # User rejected suggestion
    PREFERENCE = "preference"           # User expressed preference
    SUCCESS = "success"                 # Action completed successfully
    FAILURE = "failure"                 # Action failed
    EXPLICIT = "explicit"               # User explicitly taught something


class LearningCategory(str, Enum):
    """Categories of learned knowledge."""
    COMMUNICATION_STYLE = "communication_style"
    TASK_PREFERENCES = "task_preferences"
    SCHEDULE_PATTERNS = "schedule_patterns"
    JOB_PREFERENCES = "job_preferences"
    TOOL_USAGE = "tool_usage"
    RESPONSE_FORMAT = "response_format"
    DOMAIN_KNOWLEDGE = "domain_knowledge"
    CORRECTIONS = "corrections"


@dataclass
class LearningEntry:
    """A single piece of learned knowledge."""
    id: str = ""
    category: LearningCategory = LearningCategory.DOMAIN_KNOWLEDGE
    feedback_type: FeedbackType = FeedbackType.EXPLICIT

    # What was learned
    key: str = ""                       # What this learning is about
    value: Any = None                   # The learned value/preference
    context: str = ""                   # Context in which this was learned

    # Confidence and usage
    confidence: float = 0.5             # How confident (0-1)
    usage_count: int = 0                # How many times this was used
    success_count: int = 0              # How many times it led to success

    # Timestamps
    learned_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_used: Optional[str] = None

    # Source
    source_conversation_id: Optional[str] = None
    source_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LearningEntry":
        if "category" in data and isinstance(data["category"], str):
            data["category"] = LearningCategory(data["category"])
        if "feedback_type" in data and isinstance(data["feedback_type"], str):
            data["feedback_type"] = FeedbackType(data["feedback_type"])
        return cls(**data)


class LearningEngine:
    """The AI's learning and memory system.

    Stores and retrieves learned knowledge to improve over time.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path.home() / ".nexus" / "learning.json"
        self.entries: Dict[str, LearningEntry] = {}
        self.category_index: Dict[LearningCategory, List[str]] = defaultdict(list)
        self._load()

    def _generate_id(self, category: LearningCategory, key: str) -> str:
        """Generate a unique ID for a learning entry."""
        content = f"{category.value}:{key}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def _load(self):
        """Load learned knowledge from disk."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r") as f:
                    data = json.load(f)

                for entry_data in data.get("entries", []):
                    entry = LearningEntry.from_dict(entry_data)
                    self.entries[entry.id] = entry
                    self.category_index[entry.category].append(entry.id)

                logger.info(f"Loaded {len(self.entries)} learning entries")
            except Exception as e:
                logger.warning(f"Failed to load learning data: {e}")

    def _save(self):
        """Save learned knowledge to disk."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "updated_at": datetime.utcnow().isoformat(),
            "entries": [e.to_dict() for e in self.entries.values()],
        }

        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2)

    def learn(
        self,
        category: LearningCategory,
        key: str,
        value: Any,
        feedback_type: FeedbackType = FeedbackType.EXPLICIT,
        context: str = "",
        confidence: float = 0.7,
        conversation_id: Optional[str] = None,
        source_message: Optional[str] = None,
    ) -> LearningEntry:
        """Learn something new or update existing knowledge."""
        entry_id = self._generate_id(category, key)

        if entry_id in self.entries:
            # Update existing entry
            entry = self.entries[entry_id]

            # Adjust confidence based on repetition
            if entry.value == value:
                # Same value reinforced - increase confidence
                entry.confidence = min(1.0, entry.confidence + 0.1)
            else:
                # Different value - this is a correction
                entry.value = value
                entry.confidence = confidence
                entry.feedback_type = FeedbackType.CORRECTION

            entry.usage_count += 1
            entry.last_used = datetime.utcnow().isoformat()

        else:
            # New entry
            entry = LearningEntry(
                id=entry_id,
                category=category,
                feedback_type=feedback_type,
                key=key,
                value=value,
                context=context,
                confidence=confidence,
                source_conversation_id=conversation_id,
                source_message=source_message,
            )
            self.entries[entry_id] = entry
            self.category_index[category].append(entry_id)

        self._save()
        logger.info(f"Learned: [{category.value}] {key} = {value} (confidence: {entry.confidence:.2f})")

        return entry

    def recall(
        self,
        category: Optional[LearningCategory] = None,
        key: Optional[str] = None,
        min_confidence: float = 0.3,
    ) -> List[LearningEntry]:
        """Recall learned knowledge."""
        results = []

        if category and key:
            entry_id = self._generate_id(category, key)
            if entry_id in self.entries:
                entry = self.entries[entry_id]
                if entry.confidence >= min_confidence:
                    results.append(entry)

        elif category:
            for entry_id in self.category_index.get(category, []):
                entry = self.entries[entry_id]
                if entry.confidence >= min_confidence:
                    results.append(entry)

        else:
            for entry in self.entries.values():
                if entry.confidence >= min_confidence:
                    results.append(entry)

        # Sort by confidence and usage
        results.sort(key=lambda e: (e.confidence, e.usage_count), reverse=True)
        return results

    def get_value(
        self,
        category: LearningCategory,
        key: str,
        default: Any = None,
    ) -> Any:
        """Get a specific learned value."""
        entry_id = self._generate_id(category, key)
        if entry_id in self.entries:
            entry = self.entries[entry_id]
            entry.usage_count += 1
            entry.last_used = datetime.utcnow().isoformat()
            self._save()
            return entry.value
        return default

    def record_outcome(
        self,
        category: LearningCategory,
        key: str,
        success: bool,
    ):
        """Record whether using a piece of knowledge led to success."""
        entry_id = self._generate_id(category, key)
        if entry_id in self.entries:
            entry = self.entries[entry_id]
            if success:
                entry.success_count += 1
                entry.confidence = min(1.0, entry.confidence + 0.05)
            else:
                entry.confidence = max(0.1, entry.confidence - 0.1)
            self._save()

    def learn_from_correction(
        self,
        original: str,
        corrected: str,
        context: str = "",
        conversation_id: Optional[str] = None,
    ):
        """Learn from a user correction."""
        self.learn(
            category=LearningCategory.CORRECTIONS,
            key=original[:100],  # Truncate long strings
            value=corrected,
            feedback_type=FeedbackType.CORRECTION,
            context=context,
            confidence=0.9,  # High confidence for explicit corrections
            conversation_id=conversation_id,
        )

    def learn_preference(
        self,
        preference_key: str,
        preference_value: Any,
        category: LearningCategory = LearningCategory.TASK_PREFERENCES,
        context: str = "",
    ):
        """Learn a user preference."""
        self.learn(
            category=category,
            key=preference_key,
            value=preference_value,
            feedback_type=FeedbackType.PREFERENCE,
            context=context,
            confidence=0.8,
        )

    def learn_from_acceptance(
        self,
        suggestion_type: str,
        suggestion: Any,
        context: str = "",
    ):
        """Learn from user accepting a suggestion."""
        self.learn(
            category=LearningCategory.TASK_PREFERENCES,
            key=f"accepted:{suggestion_type}",
            value=suggestion,
            feedback_type=FeedbackType.ACCEPTANCE,
            context=context,
            confidence=0.7,
        )

    def learn_from_rejection(
        self,
        suggestion_type: str,
        suggestion: Any,
        context: str = "",
    ):
        """Learn from user rejecting a suggestion."""
        self.learn(
            category=LearningCategory.TASK_PREFERENCES,
            key=f"rejected:{suggestion_type}",
            value=suggestion,
            feedback_type=FeedbackType.REJECTION,
            context=context,
            confidence=0.7,
        )

    def get_context_for_prompt(self) -> str:
        """Generate context string with learned knowledge for AI prompts."""
        lines = ["## Learned Preferences and Patterns\n"]

        # Communication style
        comm_entries = self.recall(LearningCategory.COMMUNICATION_STYLE, min_confidence=0.5)
        if comm_entries:
            lines.append("### Communication Style")
            for entry in comm_entries[:5]:
                lines.append(f"- {entry.key}: {entry.value}")

        # Task preferences
        task_entries = self.recall(LearningCategory.TASK_PREFERENCES, min_confidence=0.5)
        if task_entries:
            lines.append("\n### Task Preferences")
            for entry in task_entries[:10]:
                lines.append(f"- {entry.key}: {entry.value}")

        # Job preferences (learned, not from profile)
        job_entries = self.recall(LearningCategory.JOB_PREFERENCES, min_confidence=0.5)
        if job_entries:
            lines.append("\n### Job Search Insights")
            for entry in job_entries[:5]:
                lines.append(f"- {entry.key}: {entry.value}")

        # Recent corrections
        corrections = self.recall(LearningCategory.CORRECTIONS, min_confidence=0.7)
        if corrections:
            lines.append("\n### Remember (from past corrections)")
            for entry in corrections[:5]:
                lines.append(f"- When I said \"{entry.key[:50]}...\", user wanted: {entry.value[:100]}")

        return "\n".join(lines) if len(lines) > 1 else ""

    def get_statistics(self) -> Dict[str, Any]:
        """Get learning statistics."""
        stats = {
            "total_entries": len(self.entries),
            "by_category": {},
            "by_feedback_type": {},
            "avg_confidence": 0.0,
            "high_confidence_count": 0,
        }

        total_confidence = 0
        for entry in self.entries.values():
            cat = entry.category.value
            fb = entry.feedback_type.value

            stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1
            stats["by_feedback_type"][fb] = stats["by_feedback_type"].get(fb, 0) + 1

            total_confidence += entry.confidence
            if entry.confidence >= 0.8:
                stats["high_confidence_count"] += 1

        if self.entries:
            stats["avg_confidence"] = total_confidence / len(self.entries)

        return stats


# Global learning engine instance
_learning_engine: Optional[LearningEngine] = None


def get_learning_engine() -> LearningEngine:
    """Get the global learning engine instance."""
    global _learning_engine
    if _learning_engine is None:
        _learning_engine = LearningEngine()
    return _learning_engine


# Convenience functions
def learn(category: LearningCategory, key: str, value: Any, **kwargs) -> LearningEntry:
    """Learn something new."""
    return get_learning_engine().learn(category, key, value, **kwargs)


def recall(category: Optional[LearningCategory] = None, **kwargs) -> List[LearningEntry]:
    """Recall learned knowledge."""
    return get_learning_engine().recall(category, **kwargs)


def get_learned_context() -> str:
    """Get context string for prompts."""
    return get_learning_engine().get_context_for_prompt()
