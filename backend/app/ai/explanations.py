"""Decision explanation and transparency system for Nexus AI.

This module provides "I did X because Y" explanations that build user trust
by capturing and explaining AI decision-making processes for both Jarvis
and Ultron agents.

Components:
- DecisionLog: Dataclass for recording decisions with full context
- ExplanationEngine: Core engine for logging and explaining decisions
- ReasoningFormatter: Format explanations for different outputs (speech, display, logs)

Usage:
    from app.ai.explanations import (
        get_explanation_engine,
        log_decision,
        DecisionLog,
        DecisionOutcome,
    )

    # Log a decision
    engine = get_explanation_engine()
    decision_id = await engine.log_decision(
        agent="jarvis",
        action_taken="turn_on_lights",
        reasoning_chain=["User said 'I'm coming home'", "Home arrival usually means lights on", "Ambient light is low"],
        confidence_score=0.85,
        alternatives_considered=["Wait for explicit command", "Turn on only entryway lights"],
        user_context_used={"time_of_day": "evening", "location": "arriving"},
        tools_consulted=["smart_home_control"],
    )

    # Explain what happened
    explanation = await engine.explain_last_action()
    # -> "I turned on the lights because you said you were coming home and it's evening."
"""

from __future__ import annotations

import asyncio
import functools
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Constants
# ============================================================================


class DecisionOutcome(str, Enum):
    """Outcome status of a decision."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEFERRED = "deferred"  # Action postponed for later


class AgentType(str, Enum):
    """Types of agents that can make decisions."""

    JARVIS = "jarvis"
    ULTRON = "ultron"
    SYSTEM = "system"


class ExplanationVerbosity(str, Enum):
    """Verbosity levels for explanations."""

    BRIEF = "brief"  # One-liner
    STANDARD = "standard"  # Few sentences
    DETAILED = "detailed"  # Full reasoning chain


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class DecisionLog:
    """Record of a decision made by an AI agent.

    Captures the full context of why a decision was made, what alternatives
    were considered, and the outcome.

    Attributes:
        decision_id: Unique identifier for this decision
        timestamp: When the decision was made
        agent: Which agent made the decision (jarvis/ultron/system)
        action_taken: What action was performed
        reasoning_chain: Step-by-step logic that led to the decision
        confidence_score: How confident the agent is (0.0 to 1.0)
        alternatives_considered: Other options that were evaluated
        user_context_used: User-specific context that influenced the decision
        tools_consulted: Tools/services used in making or executing the decision
        outcome: Current status of the decision (pending/success/failed)
        user_id: Optional user ID if decision was user-specific
        trigger: What triggered this decision (user request, proactive, scheduled)
        impact_level: Estimated impact (low/medium/high/critical)
        reversible: Whether this action can be undone
        metadata: Additional metadata about the decision
    """

    decision_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    agent: str = "jarvis"
    action_taken: str = ""
    reasoning_chain: List[str] = field(default_factory=list)
    confidence_score: float = 0.0
    alternatives_considered: List[Dict[str, Any]] = field(default_factory=list)
    user_context_used: Dict[str, Any] = field(default_factory=dict)
    tools_consulted: List[str] = field(default_factory=list)
    outcome: DecisionOutcome = DecisionOutcome.PENDING
    user_id: Optional[UUID] = None
    trigger: str = "user_request"  # user_request, proactive, scheduled, delegation
    impact_level: str = "low"  # low, medium, high, critical
    reversible: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Outcome details
    outcome_message: Optional[str] = None
    outcome_timestamp: Optional[datetime] = None
    error_details: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "decision_id": self.decision_id,
            "timestamp": self.timestamp.isoformat(),
            "agent": self.agent,
            "action_taken": self.action_taken,
            "reasoning_chain": self.reasoning_chain,
            "confidence_score": self.confidence_score,
            "alternatives_considered": self.alternatives_considered,
            "user_context_used": self.user_context_used,
            "tools_consulted": self.tools_consulted,
            "outcome": self.outcome.value,
            "user_id": str(self.user_id) if self.user_id else None,
            "trigger": self.trigger,
            "impact_level": self.impact_level,
            "reversible": self.reversible,
            "metadata": self.metadata,
            "outcome_message": self.outcome_message,
            "outcome_timestamp": self.outcome_timestamp.isoformat() if self.outcome_timestamp else None,
            "error_details": self.error_details,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionLog":
        """Create from dictionary."""
        return cls(
            decision_id=data.get("decision_id", str(uuid4())),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.utcnow(),
            agent=data.get("agent", "jarvis"),
            action_taken=data.get("action_taken", ""),
            reasoning_chain=data.get("reasoning_chain", []),
            confidence_score=data.get("confidence_score", 0.0),
            alternatives_considered=data.get("alternatives_considered", []),
            user_context_used=data.get("user_context_used", {}),
            tools_consulted=data.get("tools_consulted", []),
            outcome=DecisionOutcome(data.get("outcome", "pending")),
            user_id=UUID(data["user_id"]) if data.get("user_id") else None,
            trigger=data.get("trigger", "user_request"),
            impact_level=data.get("impact_level", "low"),
            reversible=data.get("reversible", True),
            metadata=data.get("metadata", {}),
            outcome_message=data.get("outcome_message"),
            outcome_timestamp=datetime.fromisoformat(data["outcome_timestamp"]) if data.get("outcome_timestamp") else None,
            error_details=data.get("error_details"),
        )


@dataclass
class AlternativeOption:
    """An alternative option that was considered but not chosen."""

    action: str
    reason_not_chosen: str
    confidence_score: float = 0.0
    potential_outcome: str = ""
    risk_level: str = "low"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "action": self.action,
            "reason_not_chosen": self.reason_not_chosen,
            "confidence_score": self.confidence_score,
            "potential_outcome": self.potential_outcome,
            "risk_level": self.risk_level,
        }


# ============================================================================
# Reasoning Formatter
# ============================================================================


class ReasoningFormatter:
    """Formats decision explanations for different output contexts.

    Provides formatting for:
    - Speech: Concise verbal explanations
    - Display: Detailed UI-friendly explanations with reasoning steps
    - Log: Technical format for debugging and audit trails
    """

    # Agent voice templates for personalized explanations
    VOICE_TEMPLATES = {
        "jarvis": {
            "action_prefix": "I",
            "confirmation": "Very well",
            "uncertainty": "I believe",
            "success": "Successfully",
            "failure": "I'm afraid",
        },
        "ultron": {
            "action_prefix": "I",
            "confirmation": "Done",
            "uncertainty": "Analysis suggests",
            "success": "Completed",
            "failure": "Failed",
        },
    }

    def __init__(self, agent: str = "jarvis"):
        """Initialize formatter for a specific agent.

        Args:
            agent: Which agent's voice to use (jarvis/ultron)
        """
        self.agent = agent.lower()
        self.voice = self.VOICE_TEMPLATES.get(self.agent, self.VOICE_TEMPLATES["jarvis"])

    def format_for_speech(self, decision: DecisionLog) -> str:
        """Format explanation for speech/verbal output.

        Creates concise, natural-sounding explanations suitable for
        voice assistants or brief notifications.

        Args:
            decision: The decision to explain

        Returns:
            Concise verbal explanation

        Example:
            "I turned on the lights because you said you were coming home."
        """
        prefix = self.voice["action_prefix"]
        action = self._humanize_action(decision.action_taken)

        # Get the primary reason (first in chain)
        primary_reason = ""
        if decision.reasoning_chain:
            primary_reason = decision.reasoning_chain[0].lower()
            # Clean up the reason for speech
            if not primary_reason.startswith("because"):
                primary_reason = f"because {primary_reason}"

        # Build the explanation
        if decision.outcome == DecisionOutcome.SUCCESS:
            return f"{prefix} {action} {primary_reason}."
        elif decision.outcome == DecisionOutcome.FAILED:
            error = decision.error_details or "an unexpected issue"
            return f"{self.voice['failure']}, {prefix} couldn't {action} due to {error}."
        elif decision.outcome == DecisionOutcome.PENDING:
            return f"{prefix} am {action} {primary_reason}."
        else:
            return f"{prefix} {action} {primary_reason}."

    def format_for_display(
        self,
        decision: DecisionLog,
        verbosity: ExplanationVerbosity = ExplanationVerbosity.STANDARD,
    ) -> Dict[str, Any]:
        """Format explanation for UI display.

        Creates detailed, structured explanations suitable for
        displaying in a UI with reasoning steps.

        Args:
            decision: The decision to explain
            verbosity: Level of detail to include

        Returns:
            Dictionary with formatted explanation components
        """
        result = {
            "summary": self._generate_summary(decision),
            "action": self._humanize_action(decision.action_taken),
            "confidence": f"{int(decision.confidence_score * 100)}%",
            "outcome": decision.outcome.value,
            "timestamp": decision.timestamp.isoformat(),
            "agent": decision.agent.upper(),
        }

        if verbosity in (ExplanationVerbosity.STANDARD, ExplanationVerbosity.DETAILED):
            result["reasoning_steps"] = self._format_reasoning_steps(decision.reasoning_chain)
            result["context_used"] = self._format_context(decision.user_context_used)

        if verbosity == ExplanationVerbosity.DETAILED:
            result["alternatives"] = self._format_alternatives(decision.alternatives_considered)
            result["tools_used"] = decision.tools_consulted
            result["trigger"] = decision.trigger
            result["impact_level"] = decision.impact_level
            result["reversible"] = decision.reversible

            if decision.error_details:
                result["error"] = decision.error_details

        return result

    def format_for_log(self, decision: DecisionLog) -> str:
        """Format explanation for logging/debugging.

        Creates technical format suitable for log files and
        audit trails.

        Args:
            decision: The decision to explain

        Returns:
            Technical log string
        """
        lines = [
            f"[DECISION] {decision.decision_id}",
            f"  Timestamp: {decision.timestamp.isoformat()}",
            f"  Agent: {decision.agent.upper()}",
            f"  Action: {decision.action_taken}",
            f"  Trigger: {decision.trigger}",
            f"  Confidence: {decision.confidence_score:.2f}",
            f"  Impact: {decision.impact_level}",
            f"  Reversible: {decision.reversible}",
            f"  Outcome: {decision.outcome.value}",
        ]

        if decision.user_id:
            lines.append(f"  User: {decision.user_id}")

        if decision.reasoning_chain:
            lines.append("  Reasoning:")
            for i, step in enumerate(decision.reasoning_chain, 1):
                lines.append(f"    {i}. {step}")

        if decision.alternatives_considered:
            lines.append("  Alternatives:")
            for alt in decision.alternatives_considered:
                if isinstance(alt, dict):
                    action = alt.get("action", "Unknown")
                    reason = alt.get("reason_not_chosen", "N/A")
                    lines.append(f"    - {action}: {reason}")

        if decision.tools_consulted:
            lines.append(f"  Tools: {', '.join(decision.tools_consulted)}")

        if decision.user_context_used:
            lines.append(f"  Context: {decision.user_context_used}")

        if decision.error_details:
            lines.append(f"  Error: {decision.error_details}")

        return "\n".join(lines)

    def _humanize_action(self, action: str) -> str:
        """Convert action name to human-readable form."""
        # Replace underscores and camelCase
        result = action.replace("_", " ")

        # Handle common action patterns
        humanize_map = {
            "turn on": "turned on",
            "turn off": "turned off",
            "set": "set",
            "create": "created",
            "delete": "deleted",
            "update": "updated",
            "send": "sent",
            "schedule": "scheduled",
            "cancel": "cancelled",
            "remind": "set a reminder",
            "log": "logged",
        }

        for pattern, replacement in humanize_map.items():
            if result.lower().startswith(pattern):
                return result.lower().replace(pattern, replacement, 1)

        return result.lower()

    def _generate_summary(self, decision: DecisionLog) -> str:
        """Generate a summary sentence for the decision."""
        action = self._humanize_action(decision.action_taken)
        reason = decision.reasoning_chain[0] if decision.reasoning_chain else "as requested"

        if decision.outcome == DecisionOutcome.SUCCESS:
            return f"{self.voice['success']} {action} - {reason}"
        elif decision.outcome == DecisionOutcome.FAILED:
            return f"{self.voice['failure']} to {action}: {decision.error_details or 'Unknown error'}"
        else:
            return f"{action.capitalize()} - {reason}"

    def _format_reasoning_steps(self, chain: List[str]) -> List[Dict[str, Any]]:
        """Format reasoning chain as numbered steps."""
        return [{"step": i + 1, "reasoning": step} for i, step in enumerate(chain)]

    def _format_context(self, context: Dict[str, Any]) -> List[Dict[str, str]]:
        """Format user context for display."""
        return [{"key": k, "value": str(v)} for k, v in context.items()]

    def _format_alternatives(self, alternatives: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Format alternatives for display."""
        result = []
        for alt in alternatives:
            if isinstance(alt, dict):
                result.append({
                    "option": alt.get("action", "Unknown"),
                    "why_not": alt.get("reason_not_chosen", "Not specified"),
                })
            elif isinstance(alt, str):
                result.append({"option": alt, "why_not": "Lower confidence"})
        return result


# ============================================================================
# Explanation Engine
# ============================================================================


class ExplanationEngine:
    """Core engine for logging and explaining AI decisions.

    Provides methods to:
    - Log decisions with full context
    - Generate human-readable explanations
    - Retrieve reasoning chains
    - Compare alternatives
    - Query decision history
    """

    # Maximum decisions to keep in memory per user
    MAX_DECISIONS_PER_USER = 100

    # Default retention period for decisions
    RETENTION_DAYS = 7

    def __init__(self):
        """Initialize the explanation engine."""
        # In-memory decision store (user_id -> list of decisions)
        # In production, this should be backed by a database
        self._decisions: Dict[str, List[DecisionLog]] = {}

        # Index by decision_id for quick lookup
        self._decision_index: Dict[str, DecisionLog] = {}

        # Last decision per agent per user for quick access
        self._last_decisions: Dict[str, Dict[str, DecisionLog]] = {}

        # Formatters per agent
        self._formatters: Dict[str, ReasoningFormatter] = {}

        logger.info("ExplanationEngine initialized")

    def _get_formatter(self, agent: str) -> ReasoningFormatter:
        """Get or create a formatter for an agent."""
        if agent not in self._formatters:
            self._formatters[agent] = ReasoningFormatter(agent)
        return self._formatters[agent]

    def _get_user_key(self, user_id: Optional[UUID]) -> str:
        """Get storage key for a user."""
        return str(user_id) if user_id else "anonymous"

    async def log_decision(
        self,
        agent: str,
        action_taken: str,
        reasoning_chain: List[str],
        confidence_score: float = 0.5,
        alternatives_considered: Optional[List[Union[Dict[str, Any], str]]] = None,
        user_context_used: Optional[Dict[str, Any]] = None,
        tools_consulted: Optional[List[str]] = None,
        user_id: Optional[UUID] = None,
        trigger: str = "user_request",
        impact_level: str = "low",
        reversible: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a decision with full context.

        Args:
            agent: Which agent made the decision (jarvis/ultron)
            action_taken: What action was performed
            reasoning_chain: Step-by-step logic that led to the decision
            confidence_score: How confident the agent is (0.0 to 1.0)
            alternatives_considered: Other options that were evaluated
            user_context_used: User-specific context that influenced the decision
            tools_consulted: Tools/services used
            user_id: Optional user ID
            trigger: What triggered this decision
            impact_level: Estimated impact level
            reversible: Whether this action can be undone
            metadata: Additional metadata

        Returns:
            The decision_id of the logged decision
        """
        # Normalize alternatives to dict format
        normalized_alternatives = []
        for alt in (alternatives_considered or []):
            if isinstance(alt, str):
                normalized_alternatives.append({"action": alt, "reason_not_chosen": "Lower confidence"})
            elif isinstance(alt, dict):
                normalized_alternatives.append(alt)
            elif isinstance(alt, AlternativeOption):
                normalized_alternatives.append(alt.to_dict())

        decision = DecisionLog(
            agent=agent.lower(),
            action_taken=action_taken,
            reasoning_chain=reasoning_chain,
            confidence_score=max(0.0, min(1.0, confidence_score)),  # Clamp to [0, 1]
            alternatives_considered=normalized_alternatives,
            user_context_used=user_context_used or {},
            tools_consulted=tools_consulted or [],
            user_id=user_id,
            trigger=trigger,
            impact_level=impact_level,
            reversible=reversible,
            metadata=metadata or {},
        )

        # Store the decision
        user_key = self._get_user_key(user_id)

        if user_key not in self._decisions:
            self._decisions[user_key] = []

        self._decisions[user_key].append(decision)
        self._decision_index[decision.decision_id] = decision

        # Track last decision per agent
        if user_key not in self._last_decisions:
            self._last_decisions[user_key] = {}
        self._last_decisions[user_key][agent.lower()] = decision

        # Prune old decisions if needed
        await self._prune_old_decisions(user_key)

        logger.debug(f"Logged decision {decision.decision_id} for {agent}: {action_taken}")

        return decision.decision_id

    async def update_decision_outcome(
        self,
        decision_id: str,
        outcome: DecisionOutcome,
        outcome_message: Optional[str] = None,
        error_details: Optional[str] = None,
    ) -> bool:
        """Update the outcome of a decision.

        Args:
            decision_id: ID of the decision to update
            outcome: New outcome status
            outcome_message: Optional message about the outcome
            error_details: Error details if failed

        Returns:
            True if decision was found and updated
        """
        decision = self._decision_index.get(decision_id)
        if not decision:
            logger.warning(f"Decision {decision_id} not found for outcome update")
            return False

        decision.outcome = outcome
        decision.outcome_message = outcome_message
        decision.outcome_timestamp = datetime.utcnow()
        if error_details:
            decision.error_details = error_details

        logger.debug(f"Updated decision {decision_id} outcome to {outcome.value}")
        return True

    async def explain_last_action(
        self,
        user_id: Optional[UUID] = None,
        agent: Optional[str] = None,
        format_type: str = "speech",
    ) -> Optional[Union[str, Dict[str, Any]]]:
        """Generate human-readable explanation of the last action.

        Args:
            user_id: User to get last action for
            agent: Specific agent to get last action for (or None for any)
            format_type: Output format (speech/display/log)

        Returns:
            Formatted explanation or None if no decisions found
        """
        user_key = self._get_user_key(user_id)
        user_decisions = self._last_decisions.get(user_key, {})

        # Find the most recent decision
        decision = None
        if agent:
            decision = user_decisions.get(agent.lower())
        else:
            # Get most recent across all agents
            most_recent = None
            for d in user_decisions.values():
                if most_recent is None or d.timestamp > most_recent.timestamp:
                    most_recent = d
            decision = most_recent

        if not decision:
            return None

        formatter = self._get_formatter(decision.agent)

        if format_type == "speech":
            return formatter.format_for_speech(decision)
        elif format_type == "display":
            return formatter.format_for_display(decision)
        elif format_type == "log":
            return formatter.format_for_log(decision)
        else:
            return formatter.format_for_speech(decision)

    async def get_reasoning_chain(
        self,
        decision_id: Optional[str] = None,
        user_id: Optional[UUID] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """Return step-by-step logic for a decision.

        Args:
            decision_id: Specific decision ID (or None for last decision)
            user_id: User ID (required if decision_id not provided)

        Returns:
            List of reasoning steps with metadata
        """
        decision = None

        if decision_id:
            decision = self._decision_index.get(decision_id)
        elif user_id:
            user_key = self._get_user_key(user_id)
            decisions = self._decisions.get(user_key, [])
            if decisions:
                decision = decisions[-1]

        if not decision:
            return None

        return [
            {
                "step": i + 1,
                "reasoning": step,
                "agent": decision.agent,
                "action": decision.action_taken,
            }
            for i, step in enumerate(decision.reasoning_chain)
        ]

    async def compare_alternatives(
        self,
        decision_id: Optional[str] = None,
        user_id: Optional[UUID] = None,
    ) -> Optional[Dict[str, Any]]:
        """Show why other options weren't chosen.

        Args:
            decision_id: Specific decision ID (or None for last decision)
            user_id: User ID (required if decision_id not provided)

        Returns:
            Comparison of chosen action vs alternatives
        """
        decision = None

        if decision_id:
            decision = self._decision_index.get(decision_id)
        elif user_id:
            user_key = self._get_user_key(user_id)
            decisions = self._decisions.get(user_key, [])
            if decisions:
                decision = decisions[-1]

        if not decision:
            return None

        return {
            "decision_id": decision.decision_id,
            "chosen_action": {
                "action": decision.action_taken,
                "confidence": decision.confidence_score,
                "reasoning": decision.reasoning_chain,
            },
            "alternatives": [
                {
                    "action": alt.get("action", "Unknown"),
                    "why_not_chosen": alt.get("reason_not_chosen", "Lower confidence"),
                    "potential_confidence": alt.get("confidence_score", 0.0),
                }
                for alt in decision.alternatives_considered
            ],
            "context_that_influenced": decision.user_context_used,
        }

    async def get_decision_history(
        self,
        user_id: Optional[UUID] = None,
        agent: Optional[str] = None,
        limit: int = 10,
        outcome: Optional[DecisionOutcome] = None,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """List recent decisions by agent.

        Args:
            user_id: Filter by user
            agent: Filter by agent (jarvis/ultron)
            limit: Maximum number of decisions to return
            outcome: Filter by outcome
            since: Only include decisions after this time

        Returns:
            List of decision summaries
        """
        user_key = self._get_user_key(user_id)
        decisions = self._decisions.get(user_key, [])

        # Apply filters
        filtered = []
        for d in decisions:
            if agent and d.agent != agent.lower():
                continue
            if outcome and d.outcome != outcome:
                continue
            if since and d.timestamp < since:
                continue
            filtered.append(d)

        # Sort by timestamp descending and limit
        filtered.sort(key=lambda x: x.timestamp, reverse=True)
        filtered = filtered[:limit]

        # Format for output
        formatter = self._get_formatter(agent or "jarvis")
        return [
            {
                "decision_id": d.decision_id,
                "timestamp": d.timestamp.isoformat(),
                "agent": d.agent.upper(),
                "action": formatter._humanize_action(d.action_taken),
                "outcome": d.outcome.value,
                "confidence": f"{int(d.confidence_score * 100)}%",
                "trigger": d.trigger,
                "summary": formatter._generate_summary(d),
            }
            for d in filtered
        ]

    async def get_decision(self, decision_id: str) -> Optional[DecisionLog]:
        """Get a specific decision by ID.

        Args:
            decision_id: The decision ID to look up

        Returns:
            The DecisionLog or None if not found
        """
        return self._decision_index.get(decision_id)

    async def _prune_old_decisions(self, user_key: str) -> None:
        """Remove old decisions to manage memory."""
        decisions = self._decisions.get(user_key, [])

        # Remove decisions older than retention period
        cutoff = datetime.utcnow() - timedelta(days=self.RETENTION_DAYS)
        original_count = len(decisions)

        # Keep decisions newer than cutoff or within max limit
        kept = [d for d in decisions if d.timestamp > cutoff]

        # If still too many, keep only the most recent
        if len(kept) > self.MAX_DECISIONS_PER_USER:
            kept.sort(key=lambda x: x.timestamp, reverse=True)
            removed = kept[self.MAX_DECISIONS_PER_USER:]
            kept = kept[:self.MAX_DECISIONS_PER_USER]

            # Remove from index
            for d in removed:
                self._decision_index.pop(d.decision_id, None)

        self._decisions[user_key] = kept

        removed_count = original_count - len(kept)
        if removed_count > 0:
            logger.debug(f"Pruned {removed_count} old decisions for user {user_key}")


# ============================================================================
# Singleton and Decorator
# ============================================================================


_explanation_engine: Optional[ExplanationEngine] = None


def get_explanation_engine() -> ExplanationEngine:
    """Get the singleton explanation engine instance.

    Returns:
        The global ExplanationEngine instance
    """
    global _explanation_engine
    if _explanation_engine is None:
        _explanation_engine = ExplanationEngine()
    return _explanation_engine


F = TypeVar("F", bound=Callable[..., Any])


def log_decision(
    action_name: Optional[str] = None,
    agent: str = "jarvis",
    impact_level: str = "low",
    reversible: bool = True,
) -> Callable[[F], F]:
    """Decorator for tool executors to automatically log decisions.

    Use this decorator on tool execution methods to capture
    decision context automatically.

    Args:
        action_name: Name of the action (defaults to function name)
        agent: Which agent is executing (jarvis/ultron)
        impact_level: Impact level of the action
        reversible: Whether action can be undone

    Usage:
        @log_decision(action_name="turn_on_lights", agent="jarvis")
        async def execute_light_control(self, room: str, state: bool):
            # ... implementation

    Example with context:
        @log_decision(agent="ultron", impact_level="high")
        async def cleanup_files(self, path: str):
            # Tool automatically logs the decision
            pass
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            engine = get_explanation_engine()
            func_name = action_name or func.__name__

            # Extract user_id if available in args/kwargs
            user_id = kwargs.get("user_id")
            if user_id is None and len(args) > 0:
                # Check if first arg (self) has user_id attribute
                self_obj = args[0]
                if hasattr(self_obj, "user_id"):
                    user_id = self_obj.user_id

            # Build reasoning from function docstring and params
            reasoning = []
            if func.__doc__:
                reasoning.append(func.__doc__.split("\n")[0].strip())

            # Add parameter context
            param_context = {k: v for k, v in kwargs.items() if not k.startswith("_")}

            # Log the decision
            decision_id = await engine.log_decision(
                agent=agent,
                action_taken=func_name,
                reasoning_chain=reasoning or [f"Executing {func_name}"],
                confidence_score=0.9,  # High confidence for direct tool calls
                user_context_used=param_context,
                tools_consulted=[func_name],
                user_id=user_id,
                trigger="user_request",
                impact_level=impact_level,
                reversible=reversible,
            )

            try:
                result = await func(*args, **kwargs)
                await engine.update_decision_outcome(
                    decision_id,
                    DecisionOutcome.SUCCESS,
                    outcome_message="Completed successfully",
                )
                return result
            except Exception as e:
                await engine.update_decision_outcome(
                    decision_id,
                    DecisionOutcome.FAILED,
                    error_details=str(e),
                )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, just call them (no logging for sync)
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator


# ============================================================================
# AI Tools for Explanations
# ============================================================================


EXPLANATION_TOOLS = [
    {
        "name": "explain_action",
        "description": "Explain why the AI took a specific action. Use when the user asks 'Why did you do that?' or wants to understand the reasoning behind an action.",
        "input_schema": {
            "type": "object",
            "properties": {
                "decision_id": {
                    "type": "string",
                    "description": "Specific decision ID to explain (optional, defaults to last action)"
                },
                "format": {
                    "type": "string",
                    "enum": ["brief", "detailed"],
                    "description": "How much detail to include in the explanation"
                }
            },
            "required": []
        }
    },
    {
        "name": "show_reasoning",
        "description": "Walk through the step-by-step reasoning process for a decision. Use when the user asks 'Walk me through your thinking' or wants to see the logic chain.",
        "input_schema": {
            "type": "object",
            "properties": {
                "decision_id": {
                    "type": "string",
                    "description": "Specific decision ID (optional, defaults to last decision)"
                },
                "include_alternatives": {
                    "type": "boolean",
                    "description": "Whether to show alternatives that were considered"
                }
            },
            "required": []
        }
    },
    {
        "name": "list_recent_decisions",
        "description": "List recent decisions made by AI agents. Use when the user asks 'What have you done today?' or 'Show me recent actions'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent": {
                    "type": "string",
                    "enum": ["jarvis", "ultron", "all"],
                    "description": "Which agent's decisions to show (default: all)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of decisions to return (default: 10)"
                },
                "outcome": {
                    "type": "string",
                    "enum": ["success", "failed", "pending", "all"],
                    "description": "Filter by outcome (default: all)"
                }
            },
            "required": []
        }
    },
    {
        "name": "compare_decision_alternatives",
        "description": "Show why the AI chose one action over other possibilities. Use when the user asks 'Why didn't you do X instead?' or wants to understand the decision process.",
        "input_schema": {
            "type": "object",
            "properties": {
                "decision_id": {
                    "type": "string",
                    "description": "Specific decision ID (optional, defaults to last decision)"
                }
            },
            "required": []
        }
    },
]


async def execute_explanation_tool(
    tool_name: str,
    tool_input: Dict[str, Any],
    user_id: Optional[UUID] = None,
) -> Dict[str, Any]:
    """Execute an explanation tool.

    Args:
        tool_name: Name of the tool to execute
        tool_input: Tool input parameters
        user_id: User ID for context

    Returns:
        Tool result dictionary
    """
    engine = get_explanation_engine()

    if tool_name == "explain_action":
        decision_id = tool_input.get("decision_id")
        format_type = tool_input.get("format", "brief")

        if format_type == "brief":
            explanation = await engine.explain_last_action(
                user_id=user_id,
                format_type="speech",
            )
        else:
            explanation = await engine.explain_last_action(
                user_id=user_id,
                format_type="display",
            )

        if explanation:
            return {"success": True, "explanation": explanation}
        else:
            return {"success": False, "error": "No recent decisions found"}

    elif tool_name == "show_reasoning":
        decision_id = tool_input.get("decision_id")
        include_alts = tool_input.get("include_alternatives", False)

        reasoning = await engine.get_reasoning_chain(
            decision_id=decision_id,
            user_id=user_id,
        )

        if not reasoning:
            return {"success": False, "error": "No decision found"}

        result = {"success": True, "reasoning_steps": reasoning}

        if include_alts:
            alternatives = await engine.compare_alternatives(
                decision_id=decision_id,
                user_id=user_id,
            )
            if alternatives:
                result["alternatives"] = alternatives.get("alternatives", [])

        return result

    elif tool_name == "list_recent_decisions":
        agent = tool_input.get("agent", "all")
        limit = tool_input.get("limit", 10)
        outcome_filter = tool_input.get("outcome", "all")

        outcome = None
        if outcome_filter != "all":
            outcome = DecisionOutcome(outcome_filter)

        decisions = await engine.get_decision_history(
            user_id=user_id,
            agent=agent if agent != "all" else None,
            limit=limit,
            outcome=outcome,
        )

        return {
            "success": True,
            "count": len(decisions),
            "decisions": decisions,
        }

    elif tool_name == "compare_decision_alternatives":
        decision_id = tool_input.get("decision_id")

        comparison = await engine.compare_alternatives(
            decision_id=decision_id,
            user_id=user_id,
        )

        if comparison:
            return {"success": True, "comparison": comparison}
        else:
            return {"success": False, "error": "No decision found"}

    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}


def is_explanation_tool(tool_name: str) -> bool:
    """Check if a tool name is an explanation tool.

    Args:
        tool_name: Name of the tool to check

    Returns:
        True if it's an explanation tool
    """
    explanation_tool_names = {tool["name"] for tool in EXPLANATION_TOOLS}
    return tool_name in explanation_tool_names


# ============================================================================
# Integration Middleware
# ============================================================================


class DecisionCaptureMixin:
    """Mixin for AI engines to capture reasoning during tool execution.

    Add this mixin to your AI engine class to automatically capture
    decision context when tools are executed.

    Usage:
        class MyAIEngine(DecisionCaptureMixin, BaseAIEngine):
            pass
    """

    _current_decision_context: Optional[Dict[str, Any]] = None

    def start_decision_capture(
        self,
        agent: str,
        user_id: Optional[UUID] = None,
        trigger: str = "user_request",
    ) -> None:
        """Start capturing context for a decision.

        Call this at the beginning of processing a user message.

        Args:
            agent: Which agent is processing
            user_id: User ID
            trigger: What triggered this processing
        """
        self._current_decision_context = {
            "agent": agent,
            "user_id": user_id,
            "trigger": trigger,
            "reasoning_chain": [],
            "tools_consulted": [],
            "user_context_used": {},
            "start_time": datetime.utcnow(),
        }

    def add_reasoning_step(self, step: str) -> None:
        """Add a reasoning step to the current decision context.

        Args:
            step: The reasoning step to add
        """
        if self._current_decision_context:
            self._current_decision_context["reasoning_chain"].append(step)

    def add_tool_consulted(self, tool_name: str) -> None:
        """Record that a tool was consulted.

        Args:
            tool_name: Name of the tool used
        """
        if self._current_decision_context:
            if tool_name not in self._current_decision_context["tools_consulted"]:
                self._current_decision_context["tools_consulted"].append(tool_name)

    def add_user_context(self, key: str, value: Any) -> None:
        """Add user context that influenced the decision.

        Args:
            key: Context key
            value: Context value
        """
        if self._current_decision_context:
            self._current_decision_context["user_context_used"][key] = value

    async def finalize_decision(
        self,
        action_taken: str,
        confidence_score: float = 0.5,
        alternatives_considered: Optional[List[Dict[str, Any]]] = None,
        impact_level: str = "low",
        reversible: bool = True,
    ) -> Optional[str]:
        """Finalize and log the captured decision.

        Call this after completing tool execution.

        Args:
            action_taken: What action was ultimately taken
            confidence_score: Confidence in the decision
            alternatives_considered: Other options evaluated
            impact_level: Impact level of the action
            reversible: Whether action can be undone

        Returns:
            The decision ID if logged, None if no context was captured
        """
        if not self._current_decision_context:
            return None

        engine = get_explanation_engine()
        ctx = self._current_decision_context

        decision_id = await engine.log_decision(
            agent=ctx["agent"],
            action_taken=action_taken,
            reasoning_chain=ctx["reasoning_chain"],
            confidence_score=confidence_score,
            alternatives_considered=alternatives_considered or [],
            user_context_used=ctx["user_context_used"],
            tools_consulted=ctx["tools_consulted"],
            user_id=ctx["user_id"],
            trigger=ctx["trigger"],
            impact_level=impact_level,
            reversible=reversible,
        )

        self._current_decision_context = None
        return decision_id

    def clear_decision_context(self) -> None:
        """Clear the current decision context without logging."""
        self._current_decision_context = None


# ============================================================================
# Exports
# ============================================================================


__all__ = [
    # Data classes
    "DecisionLog",
    "DecisionOutcome",
    "AlternativeOption",
    "AgentType",
    "ExplanationVerbosity",
    # Core classes
    "ExplanationEngine",
    "ReasoningFormatter",
    # Singleton
    "get_explanation_engine",
    # Decorator
    "log_decision",
    # Tools
    "EXPLANATION_TOOLS",
    "execute_explanation_tool",
    "is_explanation_tool",
    # Mixin
    "DecisionCaptureMixin",
]
