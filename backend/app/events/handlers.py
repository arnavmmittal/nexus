"""Built-in Event Handlers - Standard handlers for common event processing.

This module provides reusable handlers for logging, metrics, chaining,
and conditional event processing.

These handlers can be composed together to build complex event-driven
behaviors without tight coupling between components.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

from .bus import Event, EventBus, EventPriority, EventType, get_event_bus

logger = logging.getLogger(__name__)


class BaseHandler(ABC):
    """Abstract base class for event handlers.

    Provides a structured way to create handlers with setup/teardown,
    filtering, and automatic subscription management.
    """

    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__
        self._subscriptions: List[str] = []
        self._enabled = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        """Enable the handler."""
        self._enabled = True
        logger.info(f"Handler {self.name} enabled")

    def disable(self) -> None:
        """Disable the handler."""
        self._enabled = False
        logger.info(f"Handler {self.name} disabled")

    @abstractmethod
    async def handle(self, event: Event) -> None:
        """Handle an event. Must be implemented by subclasses."""
        pass

    async def _wrapper(self, event: Event) -> None:
        """Wrapper that checks enabled state before handling."""
        if self._enabled:
            await self.handle(event)

    def register(
        self,
        bus: Optional[EventBus] = None,
        patterns: Optional[List[str]] = None,
    ) -> None:
        """Register this handler with an event bus.

        Args:
            bus: Event bus to register with (uses global if not provided)
            patterns: Event patterns to subscribe to (uses ["*"] if not provided)
        """
        if bus is None:
            bus = get_event_bus()

        if patterns is None:
            patterns = ["*"]

        for pattern in patterns:
            sub_id = bus.subscribe(
                pattern=pattern,
                handler=self._wrapper,
                name=f"{self.name}:{pattern}",
            )
            self._subscriptions.append(sub_id)

        logger.info(f"Handler {self.name} registered for {patterns}")

    def unregister(self, bus: Optional[EventBus] = None) -> None:
        """Unregister this handler from an event bus."""
        if bus is None:
            bus = get_event_bus()

        for sub_id in self._subscriptions:
            bus.unsubscribe(sub_id)

        self._subscriptions.clear()
        logger.info(f"Handler {self.name} unregistered")


class LoggingHandler(BaseHandler):
    """Handler that logs all events.

    Useful for debugging and auditing. Supports different log levels
    based on event priority.
    """

    def __init__(
        self,
        name: str = "LoggingHandler",
        log_level: int = logging.DEBUG,
        include_data: bool = True,
        max_data_length: int = 500,
    ):
        """Initialize the logging handler.

        Args:
            name: Handler name
            log_level: Base log level
            include_data: Whether to include event data in logs
            max_data_length: Maximum length of data to log
        """
        super().__init__(name)
        self.log_level = log_level
        self.include_data = include_data
        self.max_data_length = max_data_length

    async def handle(self, event: Event) -> None:
        """Log the event."""
        # Adjust log level based on priority
        level = self.log_level
        if event.priority == EventPriority.CRITICAL:
            level = logging.ERROR
        elif event.priority == EventPriority.HIGH:
            level = logging.WARNING
        elif event.priority == EventPriority.NORMAL:
            level = logging.INFO

        # Build log message
        msg = f"[EVENT] {event.type_str} from {event.source}"

        if event.correlation_id:
            msg += f" (corr: {event.correlation_id})"

        if self.include_data and event.data:
            data_str = str(event.data)
            if len(data_str) > self.max_data_length:
                data_str = data_str[: self.max_data_length] + "..."
            msg += f" | data: {data_str}"

        logger.log(level, msg)


@dataclass
class MetricPoint:
    """A single metric data point."""

    event_type: str
    timestamp: datetime
    latency_ms: float = 0.0
    success: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class MetricsHandler(BaseHandler):
    """Handler that tracks event counts and latencies.

    Provides statistics that can be used for monitoring, alerting,
    and performance optimization.
    """

    def __init__(
        self,
        name: str = "MetricsHandler",
        window_minutes: int = 60,
    ):
        """Initialize the metrics handler.

        Args:
            name: Handler name
            window_minutes: Time window for rate calculations
        """
        super().__init__(name)
        self.window_minutes = window_minutes
        self._counts: Dict[str, int] = defaultdict(int)
        self._latencies: Dict[str, List[float]] = defaultdict(list)
        self._recent_events: List[MetricPoint] = []
        self._start_time = datetime.now(timezone.utc)
        self._lock = asyncio.Lock()

    async def handle(self, event: Event) -> None:
        """Track event metrics."""
        async with self._lock:
            event_type = event.type_str
            now = datetime.now(timezone.utc)

            # Update counts
            self._counts[event_type] += 1
            self._counts["_total"] += 1

            # Track latency if provided
            latency = event.metadata.get("latency_ms", 0.0)
            if latency > 0:
                self._latencies[event_type].append(latency)
                # Keep only recent latencies
                self._latencies[event_type] = self._latencies[event_type][-1000:]

            # Store metric point
            point = MetricPoint(
                event_type=event_type,
                timestamp=now,
                latency_ms=latency,
                success=event.type != EventType.ERROR_OCCURRED,
            )
            self._recent_events.append(point)

            # Clean up old events
            cutoff = now - timedelta(minutes=self.window_minutes)
            self._recent_events = [
                p for p in self._recent_events if p.timestamp > cutoff
            ]

    def get_counts(self) -> Dict[str, int]:
        """Get event counts."""
        return dict(self._counts)

    def get_rate(self, event_type: str = "_total") -> float:
        """Get events per minute rate."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=self.window_minutes)

        count = sum(
            1
            for p in self._recent_events
            if p.event_type == event_type or event_type == "_total"
            if p.timestamp > cutoff
        )

        return count / self.window_minutes

    def get_latency_stats(
        self, event_type: Optional[str] = None
    ) -> Dict[str, float]:
        """Get latency statistics."""
        if event_type:
            latencies = self._latencies.get(event_type, [])
        else:
            # All latencies
            latencies = [
                lat
                for lats in self._latencies.values()
                for lat in lats
            ]

        if not latencies:
            return {"min": 0, "max": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0}

        sorted_lat = sorted(latencies)
        n = len(sorted_lat)

        return {
            "min": sorted_lat[0],
            "max": sorted_lat[-1],
            "avg": sum(sorted_lat) / n,
            "p50": sorted_lat[n // 2],
            "p95": sorted_lat[int(n * 0.95)] if n >= 20 else sorted_lat[-1],
            "p99": sorted_lat[int(n * 0.99)] if n >= 100 else sorted_lat[-1],
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get full statistics."""
        uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()

        return {
            "uptime_seconds": uptime,
            "total_events": self._counts.get("_total", 0),
            "events_per_minute": self.get_rate(),
            "counts_by_type": {
                k: v for k, v in self._counts.items() if not k.startswith("_")
            },
            "latency": self.get_latency_stats(),
        }


class ChainHandler(BaseHandler):
    """Handler that chains events - one event triggers another.

    Useful for creating event cascades:
    - tool_executed -> memory_updated
    - user_message -> agent_thinking -> agent_response
    - schedule_triggered -> workflow_started
    """

    def __init__(
        self,
        name: str = "ChainHandler",
        chains: Optional[Dict[str, Union[EventType, str]]] = None,
        transform_fn: Optional[Callable[[Event], Dict[str, Any]]] = None,
    ):
        """Initialize the chain handler.

        Args:
            name: Handler name
            chains: Mapping of source event type to target event type
            transform_fn: Optional function to transform event data
        """
        super().__init__(name)
        self._chains: Dict[str, str] = {}
        self._transform_fn = transform_fn

        if chains:
            for source, target in chains.items():
                self.add_chain(source, target)

    def add_chain(
        self,
        source_type: Union[EventType, str],
        target_type: Union[EventType, str],
    ) -> None:
        """Add a chain rule.

        Args:
            source_type: Event type to watch for
            target_type: Event type to emit when source is seen
        """
        source = source_type.value if isinstance(source_type, EventType) else source_type
        target = target_type.value if isinstance(target_type, EventType) else target_type
        self._chains[source] = target
        logger.debug(f"Chain added: {source} -> {target}")

    def remove_chain(self, source_type: Union[EventType, str]) -> None:
        """Remove a chain rule."""
        source = source_type.value if isinstance(source_type, EventType) else source_type
        self._chains.pop(source, None)

    async def handle(self, event: Event) -> None:
        """Handle event and emit chained event if configured."""
        source = event.type_str
        target = self._chains.get(source)

        if not target:
            return

        # Transform data if function provided
        if self._transform_fn:
            new_data = self._transform_fn(event)
        else:
            new_data = event.data.copy()

        # Create derived event
        chained_event = event.derive(
            new_type=target,
            new_data=new_data,
            source=f"{self.name}:chain",
        )
        chained_event.metadata["chained_from"] = event.type_str

        # Publish chained event
        bus = get_event_bus()
        await bus.publish(chained_event)

        logger.debug(f"Chained event: {source} -> {target}")


class ConditionalHandler(BaseHandler):
    """Handler that only executes when conditions are met.

    Supports complex conditions based on:
    - Event data fields
    - Event metadata
    - External state (via condition function)
    """

    def __init__(
        self,
        name: str = "ConditionalHandler",
        handler: Callable[[Event], Awaitable[None]] = None,
        condition: Optional[Callable[[Event], bool]] = None,
        require_fields: Optional[List[str]] = None,
        require_values: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the conditional handler.

        Args:
            name: Handler name
            handler: The actual handler to call when conditions are met
            condition: Custom condition function
            require_fields: Fields that must exist in event.data
            require_values: Field values that must match
        """
        super().__init__(name)
        self._handler = handler
        self._condition = condition
        self._require_fields = require_fields or []
        self._require_values = require_values or {}

    def set_handler(self, handler: Callable[[Event], Awaitable[None]]) -> None:
        """Set the handler function."""
        self._handler = handler

    def set_condition(self, condition: Callable[[Event], bool]) -> None:
        """Set the condition function."""
        self._condition = condition

    def _check_conditions(self, event: Event) -> bool:
        """Check if all conditions are met."""
        # Check required fields
        for field in self._require_fields:
            if field not in event.data:
                return False

        # Check required values
        for key, value in self._require_values.items():
            if event.data.get(key) != value:
                return False

        # Check custom condition
        if self._condition and not self._condition(event):
            return False

        return True

    async def handle(self, event: Event) -> None:
        """Handle event if conditions are met."""
        if not self._handler:
            return

        if self._check_conditions(event):
            try:
                await self._handler(event)
            except Exception as e:
                logger.error(f"Conditional handler error: {e}")


class ThrottledHandler(BaseHandler):
    """Handler that throttles event processing.

    Prevents handlers from being overwhelmed by rapid events.
    """

    def __init__(
        self,
        name: str = "ThrottledHandler",
        handler: Callable[[Event], Awaitable[None]] = None,
        min_interval_ms: int = 100,
        max_queue_size: int = 10,
    ):
        """Initialize the throttled handler.

        Args:
            name: Handler name
            handler: The actual handler to call
            min_interval_ms: Minimum milliseconds between handler calls
            max_queue_size: Maximum events to queue
        """
        super().__init__(name)
        self._handler = handler
        self._min_interval_ms = min_interval_ms
        self._max_queue_size = max_queue_size
        self._last_call: Dict[str, float] = {}
        self._queue: List[Event] = []
        self._processing = False
        self._lock = asyncio.Lock()

    async def handle(self, event: Event) -> None:
        """Handle event with throttling."""
        if not self._handler:
            return

        async with self._lock:
            now = time.time() * 1000
            event_type = event.type_str
            last_call = self._last_call.get(event_type, 0)

            if now - last_call >= self._min_interval_ms:
                # Enough time has passed, process immediately
                self._last_call[event_type] = now
                await self._handler(event)
            else:
                # Queue the event
                if len(self._queue) < self._max_queue_size:
                    self._queue.append(event)

                # Start processing queue if not already
                if not self._processing:
                    asyncio.create_task(self._process_queue())

    async def _process_queue(self) -> None:
        """Process queued events."""
        self._processing = True

        while self._queue:
            await asyncio.sleep(self._min_interval_ms / 1000)

            async with self._lock:
                if self._queue:
                    event = self._queue.pop(0)
                    self._last_call[event.type_str] = time.time() * 1000

            if event:
                await self._handler(event)

        self._processing = False


class AggregatingHandler(BaseHandler):
    """Handler that aggregates multiple events before processing.

    Useful for batching events:
    - Collect multiple memory updates, then persist
    - Aggregate metrics before sending
    """

    def __init__(
        self,
        name: str = "AggregatingHandler",
        handler: Callable[[List[Event]], Awaitable[None]] = None,
        flush_interval_seconds: float = 5.0,
        flush_count: int = 10,
    ):
        """Initialize the aggregating handler.

        Args:
            name: Handler name
            handler: Handler that receives batched events
            flush_interval_seconds: Time before automatic flush
            flush_count: Number of events before automatic flush
        """
        super().__init__(name)
        self._handler = handler
        self._flush_interval = flush_interval_seconds
        self._flush_count = flush_count
        self._buffer: List[Event] = []
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None

    async def handle(self, event: Event) -> None:
        """Buffer event for aggregation."""
        async with self._lock:
            self._buffer.append(event)

            # Start flush timer if not running
            if self._flush_task is None:
                self._flush_task = asyncio.create_task(self._flush_timer())

            # Flush if count reached
            if len(self._buffer) >= self._flush_count:
                await self._flush()

    async def _flush_timer(self) -> None:
        """Timer for periodic flushing."""
        await asyncio.sleep(self._flush_interval)
        async with self._lock:
            await self._flush()
            self._flush_task = None

    async def _flush(self) -> None:
        """Flush buffered events to handler."""
        if not self._buffer or not self._handler:
            return

        events = self._buffer.copy()
        self._buffer.clear()

        try:
            await self._handler(events)
        except Exception as e:
            logger.error(f"Aggregating handler flush error: {e}")

    async def force_flush(self) -> None:
        """Force an immediate flush."""
        async with self._lock:
            await self._flush()
