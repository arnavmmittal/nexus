"""Event Bus - Pub/Sub pattern for event-driven architecture.

This module provides the core event bus that enables decoupled communication
across the Nexus system. Events can trigger automated workflows, agent actions,
and system integrations.

Events flow through the system like this:
1. Component publishes event (e.g., WebSocket receives message)
2. Event bus routes to matching subscribers
3. Handlers process event (logging, metrics, workflows)
4. Workflows may trigger agent actions or further events

"The house is alive" - events make the AI feel connected and responsive.
"""

from __future__ import annotations

import asyncio
import fnmatch
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Pattern,
    Set,
    Union,
)
from uuid import uuid4

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Standard event types for the Nexus system."""

    # User interaction events
    USER_MESSAGE = "user_message"
    VOICE_COMMAND = "voice_command"

    # Agent events
    AGENT_RESPONSE = "agent_response"
    AGENT_THINKING = "agent_thinking"
    AGENT_ERROR = "agent_error"

    # Tool events
    TOOL_EXECUTED = "tool_executed"
    TOOL_FAILED = "tool_failed"

    # Memory events
    MEMORY_UPDATED = "memory_updated"
    MEMORY_RECALLED = "memory_recalled"

    # Proactive events
    PROACTIVE_SUGGESTION = "proactive_suggestion"
    PROACTIVE_ACTION = "proactive_action"

    # Scheduler events
    SCHEDULE_TRIGGERED = "schedule_triggered"
    SCHEDULE_CREATED = "schedule_created"

    # Smart home / environment events
    SMART_HOME_CHANGED = "smart_home_changed"
    LOCATION_CHANGED = "location_changed"
    PRESENCE_DETECTED = "presence_detected"

    # System events
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    ERROR_OCCURRED = "error_occurred"

    # Integration events
    EMAIL_RECEIVED = "email_received"
    CALENDAR_EVENT = "calendar_event"
    NOTIFICATION_SENT = "notification_sent"

    # Workflow events
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_STEP_COMPLETED = "workflow_step_completed"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"

    # Custom/wildcard
    CUSTOM = "custom"


class EventPriority(int, Enum):
    """Priority levels for events."""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Event:
    """An event in the system.

    Events are the fundamental unit of communication in the event-driven
    architecture. They carry information about what happened and any
    associated data.
    """

    type: Union[EventType, str]
    data: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4())[:12])
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "system"  # Which component generated this event
    priority: EventPriority = EventPriority.NORMAL
    correlation_id: Optional[str] = None  # Links related events
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def type_str(self) -> str:
        """Get event type as string."""
        if isinstance(self.type, EventType):
            return self.type.value
        return str(self.type)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.type_str,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "priority": self.priority.value,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """Create from dictionary."""
        event_type = data["type"]
        try:
            event_type = EventType(event_type)
        except ValueError:
            pass  # Keep as string for custom types

        return cls(
            id=data.get("id", str(uuid4())[:12]),
            type=event_type,
            data=data.get("data", {}),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else datetime.now(timezone.utc),
            source=data.get("source", "system"),
            priority=EventPriority(data.get("priority", 1)),
            correlation_id=data.get("correlation_id"),
            metadata=data.get("metadata", {}),
        )

    def derive(
        self,
        new_type: Union[EventType, str],
        new_data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> "Event":
        """Create a derived event from this one.

        Useful for chaining events (e.g., tool_executed -> memory_updated).
        """
        return Event(
            type=new_type,
            data=new_data if new_data is not None else self.data.copy(),
            source=kwargs.get("source", self.source),
            priority=kwargs.get("priority", self.priority),
            correlation_id=self.correlation_id or self.id,
            metadata={**self.metadata, "derived_from": self.id},
        )


# Type alias for event handlers
EventHandler = Callable[[Event], Awaitable[None]]


@dataclass
class Subscription:
    """A subscription to events."""

    handler: EventHandler
    pattern: str  # Event type pattern (supports wildcards)
    filter_fn: Optional[Callable[[Event], bool]] = None
    priority: int = 0  # Handler priority (higher = called first)
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    name: str = ""
    _compiled_pattern: Optional[Pattern] = field(default=None, repr=False)

    def matches(self, event_type: str) -> bool:
        """Check if this subscription matches the event type."""
        # Direct match
        if self.pattern == event_type or self.pattern == "*":
            return True

        # Wildcard match using fnmatch
        if fnmatch.fnmatch(event_type, self.pattern):
            return True

        # Regex match (if pattern starts with ^)
        if self.pattern.startswith("^"):
            if self._compiled_pattern is None:
                try:
                    self._compiled_pattern = re.compile(self.pattern)
                except re.error:
                    return False
            return bool(self._compiled_pattern.match(event_type))

        return False


class EventBus:
    """Central event bus for the Nexus system.

    Provides publish/subscribe functionality for events. Supports:
    - Direct event type subscriptions
    - Pattern matching (wildcards: user_*, tool_*, etc.)
    - Regex patterns (^agent_.*)
    - Conditional filters on event data
    - Priority-based handler ordering
    - Event history for debugging
    """

    def __init__(self, max_history: int = 1000):
        """Initialize the event bus.

        Args:
            max_history: Maximum number of events to keep in history
        """
        self._subscriptions: List[Subscription] = []
        self._event_history: List[Event] = []
        self._max_history = max_history
        self._lock = asyncio.Lock()
        self._running = True
        self._event_counts: Dict[str, int] = defaultdict(int)

        logger.info("EventBus initialized")

    async def publish(self, event: Event) -> None:
        """Publish an event to all matching subscribers.

        Args:
            event: The event to publish
        """
        if not self._running:
            logger.warning("EventBus is not running, dropping event")
            return

        async with self._lock:
            # Store in history
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history = self._event_history[-self._max_history :]

            # Update counts
            self._event_counts[event.type_str] += 1

        logger.debug(f"Publishing event: {event.type_str} from {event.source}")

        # Find matching subscriptions
        matching = self._get_matching_subscriptions(event)

        # Sort by priority (higher first)
        matching.sort(key=lambda s: -s.priority)

        # Call handlers (in parallel for same priority)
        for subscription in matching:
            try:
                await subscription.handler(event)
            except Exception as e:
                logger.error(
                    f"Error in event handler {subscription.name or subscription.id}: {e}",
                    exc_info=True,
                )

    async def publish_many(self, events: List[Event]) -> None:
        """Publish multiple events.

        Args:
            events: List of events to publish
        """
        for event in events:
            await self.publish(event)

    def _get_matching_subscriptions(self, event: Event) -> List[Subscription]:
        """Get all subscriptions matching an event."""
        matching = []
        event_type = event.type_str

        for sub in self._subscriptions:
            if sub.matches(event_type):
                # Apply optional filter
                if sub.filter_fn is None or sub.filter_fn(event):
                    matching.append(sub)

        return matching

    def subscribe(
        self,
        pattern: str,
        handler: EventHandler,
        name: str = "",
        priority: int = 0,
        filter_fn: Optional[Callable[[Event], bool]] = None,
    ) -> str:
        """Subscribe to events matching a pattern.

        Args:
            pattern: Event type pattern (supports wildcards like user_*, ^regex.*)
            handler: Async function to call when event matches
            name: Optional name for the subscription
            priority: Handler priority (higher = called first)
            filter_fn: Optional function to filter events

        Returns:
            Subscription ID for unsubscribing

        Examples:
            # Subscribe to all user messages
            bus.subscribe("user_message", handle_message)

            # Subscribe to all agent events
            bus.subscribe("agent_*", handle_agent_event)

            # Subscribe with filter
            bus.subscribe(
                "tool_executed",
                handle_tool,
                filter_fn=lambda e: e.data.get("tool") == "calendar"
            )
        """
        subscription = Subscription(
            handler=handler,
            pattern=pattern,
            filter_fn=filter_fn,
            priority=priority,
            name=name,
        )

        self._subscriptions.append(subscription)
        logger.debug(
            f"Subscribed {name or subscription.id} to pattern '{pattern}'"
        )

        return subscription.id

    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events.

        Args:
            subscription_id: The subscription ID returned from subscribe()

        Returns:
            True if unsubscribed, False if not found
        """
        for i, sub in enumerate(self._subscriptions):
            if sub.id == subscription_id:
                self._subscriptions.pop(i)
                logger.debug(f"Unsubscribed {subscription_id}")
                return True

        return False

    def get_history(
        self,
        limit: int = 100,
        type_filter: Optional[str] = None,
        source_filter: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> List[Event]:
        """Get recent event history.

        Args:
            limit: Maximum number of events to return
            type_filter: Optional event type to filter by
            source_filter: Optional source to filter by
            since: Optional timestamp to filter events after

        Returns:
            List of matching events
        """
        events = self._event_history.copy()

        if type_filter:
            events = [e for e in events if e.type_str == type_filter]

        if source_filter:
            events = [e for e in events if e.source == source_filter]

        if since:
            events = [e for e in events if e.timestamp > since]

        return events[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        return {
            "total_events": sum(self._event_counts.values()),
            "event_counts": dict(self._event_counts),
            "subscription_count": len(self._subscriptions),
            "history_size": len(self._event_history),
        }

    async def shutdown(self) -> None:
        """Shutdown the event bus."""
        self._running = False
        self._subscriptions.clear()
        logger.info("EventBus shutdown complete")


# Global event bus instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


async def publish(event: Event) -> None:
    """Convenience function to publish an event to the global bus."""
    bus = get_event_bus()
    await bus.publish(event)


async def emit(
    event_type: Union[EventType, str],
    data: Optional[Dict[str, Any]] = None,
    source: str = "system",
    priority: EventPriority = EventPriority.NORMAL,
    correlation_id: Optional[str] = None,
) -> Event:
    """Convenience function to create and publish an event.

    Args:
        event_type: The type of event
        data: Event data
        source: Source component
        priority: Event priority
        correlation_id: ID linking related events

    Returns:
        The created event
    """
    event = Event(
        type=event_type,
        data=data or {},
        source=source,
        priority=priority,
        correlation_id=correlation_id,
    )
    await publish(event)
    return event


def subscribe(
    pattern: str,
    handler: EventHandler,
    name: str = "",
    priority: int = 0,
    filter_fn: Optional[Callable[[Event], bool]] = None,
) -> str:
    """Convenience function to subscribe to events on the global bus."""
    bus = get_event_bus()
    return bus.subscribe(pattern, handler, name, priority, filter_fn)


def unsubscribe(subscription_id: str) -> bool:
    """Convenience function to unsubscribe from the global bus."""
    bus = get_event_bus()
    return bus.unsubscribe(subscription_id)
