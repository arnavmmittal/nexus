"""Scheduled action types and data models.

This module defines the core data structures for scheduled actions,
supporting deferred execution of AI assistant tasks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID, uuid4


class ActionType(str, Enum):
    """Types of actions that can be scheduled."""

    SEND_MESSAGE = "send_message"        # Send a message/notification to user
    EXECUTE_TOOL = "execute_tool"        # Execute an integration tool
    RUN_WORKFLOW = "run_workflow"        # Run a multi-step workflow
    REMINDER = "reminder"                 # Simple reminder notification
    CHECK_CONDITION = "check_condition"  # Check a condition and act on result


class ActionStatus(str, Enum):
    """Status of a scheduled action."""

    PENDING = "pending"          # Waiting for scheduled time
    RUNNING = "running"          # Currently executing
    COMPLETED = "completed"      # Successfully completed
    FAILED = "failed"            # Failed after retries exhausted
    CANCELLED = "cancelled"      # Cancelled by user or system
    RETRYING = "retrying"        # Failed but will retry


class CreatedBy(str, Enum):
    """Agent or system that created the action."""

    JARVIS = "jarvis"    # JARVIS AI assistant
    ULTRON = "ultron"    # Ultron autonomous agent
    USER = "user"        # Direct user request
    SYSTEM = "system"    # System-generated


@dataclass
class ScheduledAction:
    """A scheduled action to be executed at a future time.

    Attributes:
        id: Unique identifier for the action
        action_type: Type of action to execute
        payload: Action-specific data (tool name, message, etc.)
        scheduled_time: When to execute (UTC)
        recurring: Optional cron pattern for recurring actions
        created_by: Agent/system that created this action
        user_id: User this action belongs to
        status: Current status of the action
        description: Human-readable description of the action
        created_at: When the action was created
        updated_at: When the action was last updated
        executed_at: When the action was executed
        retry_count: Number of retry attempts
        max_retries: Maximum retry attempts allowed
        last_error: Error message from last failure
        result: Result from successful execution
        metadata: Additional action metadata
    """

    action_type: ActionType
    payload: Dict[str, Any]
    scheduled_time: datetime
    user_id: UUID
    id: str = field(default_factory=lambda: str(uuid4()))
    recurring: Optional[str] = None  # Cron pattern like "0 9 * * *"
    created_by: CreatedBy = CreatedBy.JARVIS
    status: ActionStatus = ActionStatus.PENDING
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    executed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    last_error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate and normalize fields after initialization."""
        # Ensure scheduled_time is UTC
        if self.scheduled_time.tzinfo is None:
            self.scheduled_time = self.scheduled_time.replace(tzinfo=timezone.utc)

        # Auto-generate description if not provided
        if not self.description:
            self.description = self._generate_description()

    def _generate_description(self) -> str:
        """Generate a human-readable description from the action."""
        action_descriptions = {
            ActionType.SEND_MESSAGE: lambda p: f"Send message: {p.get('message', '')[:50]}...",
            ActionType.EXECUTE_TOOL: lambda p: f"Execute tool: {p.get('tool_name', 'unknown')}",
            ActionType.RUN_WORKFLOW: lambda p: f"Run workflow: {p.get('workflow_name', 'unnamed')}",
            ActionType.REMINDER: lambda p: f"Reminder: {p.get('message', '')}",
            ActionType.CHECK_CONDITION: lambda p: f"Check condition: {p.get('condition', '')}",
        }

        generator = action_descriptions.get(
            self.action_type,
            lambda p: f"Action: {self.action_type.value}"
        )
        return generator(self.payload)

    def is_due(self) -> bool:
        """Check if this action is due for execution."""
        if self.status != ActionStatus.PENDING:
            return False
        return datetime.now(timezone.utc) >= self.scheduled_time

    def can_retry(self) -> bool:
        """Check if this action can be retried."""
        return self.retry_count < self.max_retries

    def mark_running(self) -> None:
        """Mark the action as currently running."""
        self.status = ActionStatus.RUNNING
        self.updated_at = datetime.now(timezone.utc)

    def mark_completed(self, result: Optional[Dict[str, Any]] = None) -> None:
        """Mark the action as successfully completed."""
        self.status = ActionStatus.COMPLETED
        self.executed_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        self.result = result

    def mark_failed(self, error: str) -> None:
        """Mark the action as failed."""
        self.retry_count += 1
        self.last_error = error
        self.updated_at = datetime.now(timezone.utc)

        if self.can_retry():
            self.status = ActionStatus.RETRYING
        else:
            self.status = ActionStatus.FAILED

    def mark_cancelled(self) -> None:
        """Mark the action as cancelled."""
        self.status = ActionStatus.CANCELLED
        self.updated_at = datetime.now(timezone.utc)

    def reset_for_retry(self) -> None:
        """Reset status to pending for retry."""
        if self.status == ActionStatus.RETRYING:
            self.status = ActionStatus.PENDING
            self.updated_at = datetime.now(timezone.utc)

    def schedule_next_occurrence(self) -> Optional["ScheduledAction"]:
        """Create the next occurrence for a recurring action.

        Returns:
            New ScheduledAction for the next occurrence, or None if not recurring
        """
        if not self.recurring:
            return None

        from croniter import croniter

        cron = croniter(self.recurring, self.scheduled_time)
        next_time = cron.get_next(datetime)

        # Ensure timezone is preserved
        if next_time.tzinfo is None:
            next_time = next_time.replace(tzinfo=timezone.utc)

        return ScheduledAction(
            action_type=self.action_type,
            payload=self.payload.copy(),
            scheduled_time=next_time,
            user_id=self.user_id,
            recurring=self.recurring,
            created_by=self.created_by,
            description=self.description,
            max_retries=self.max_retries,
            metadata=self.metadata.copy(),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "action_type": self.action_type.value,
            "payload": self.payload,
            "scheduled_time": self.scheduled_time.isoformat(),
            "recurring": self.recurring,
            "created_by": self.created_by.value,
            "user_id": str(self.user_id),
            "status": self.status.value,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "last_error": self.last_error,
            "result": self.result,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScheduledAction":
        """Create a ScheduledAction from a dictionary."""
        return cls(
            id=data["id"],
            action_type=ActionType(data["action_type"]),
            payload=data["payload"],
            scheduled_time=datetime.fromisoformat(data["scheduled_time"]),
            recurring=data.get("recurring"),
            created_by=CreatedBy(data.get("created_by", "jarvis")),
            user_id=UUID(data["user_id"]),
            status=ActionStatus(data.get("status", "pending")),
            description=data.get("description", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(timezone.utc),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(timezone.utc),
            executed_at=datetime.fromisoformat(data["executed_at"]) if data.get("executed_at") else None,
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            last_error=data.get("last_error"),
            result=data.get("result"),
            metadata=data.get("metadata", {}),
        )


# Common cron patterns for convenience
class CronPatterns:
    """Common cron patterns for scheduling."""

    EVERY_MINUTE = "* * * * *"
    EVERY_HOUR = "0 * * * *"
    EVERY_DAY_9AM = "0 9 * * *"
    EVERY_DAY_MIDNIGHT = "0 0 * * *"
    EVERY_WEEKDAY_9AM = "0 9 * * 1-5"
    EVERY_MONDAY_9AM = "0 9 * * 1"
    EVERY_MONTH_FIRST = "0 9 1 * *"

    @staticmethod
    def daily_at(hour: int, minute: int = 0) -> str:
        """Create a cron pattern for daily at specified time."""
        return f"{minute} {hour} * * *"

    @staticmethod
    def weekdays_at(hour: int, minute: int = 0) -> str:
        """Create a cron pattern for weekdays at specified time."""
        return f"{minute} {hour} * * 1-5"

    @staticmethod
    def weekly_on(day: int, hour: int = 9, minute: int = 0) -> str:
        """Create a cron pattern for weekly on specified day (0=Sunday, 6=Saturday)."""
        return f"{minute} {hour} * * {day}"
