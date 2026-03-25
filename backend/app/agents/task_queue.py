"""Background task queue for autonomous agents.

This module provides a priority-based task queue for agents to process
background work independently.
"""

import asyncio
import heapq
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any, Callable, Coroutine, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class TaskPriority(IntEnum):
    """Priority levels for background tasks.

    Lower values = higher priority (for heap ordering).
    """

    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


class TaskStatus(IntEnum):
    """Status of a background task."""

    PENDING = 0
    RUNNING = 1
    COMPLETED = 2
    FAILED = 3
    CANCELLED = 4


@dataclass(order=True)
class BackgroundTask:
    """A background task for an agent to process.

    Attributes:
        id: Unique task identifier
        agent_id: ID of the agent that should process this task
        task_type: Type/category of the task
        payload: Task-specific data
        priority: Task priority level
        created_at: When the task was created
        status: Current task status
        result: Task result (when completed)
        error: Error message (when failed)
        started_at: When task processing started
        completed_at: When task processing finished
        retries: Number of retry attempts
        max_retries: Maximum retry attempts allowed
        metadata: Additional task metadata
    """

    # Fields used for ordering (priority queue)
    sort_index: tuple = field(init=False, repr=False)

    # Required fields
    agent_id: str = field(compare=False)
    task_type: str = field(compare=False)
    payload: Dict[str, Any] = field(compare=False)

    # Optional fields with defaults
    id: str = field(default_factory=lambda: str(uuid4()), compare=False)
    priority: TaskPriority = field(default=TaskPriority.NORMAL, compare=False)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
        compare=False
    )
    status: TaskStatus = field(default=TaskStatus.PENDING, compare=False)
    result: Optional[Any] = field(default=None, compare=False)
    error: Optional[str] = field(default=None, compare=False)
    started_at: Optional[datetime] = field(default=None, compare=False)
    completed_at: Optional[datetime] = field(default=None, compare=False)
    retries: int = field(default=0, compare=False)
    max_retries: int = field(default=3, compare=False)
    metadata: Dict[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self):
        """Set sort index for priority queue ordering."""
        # Lower priority value and earlier timestamp = higher priority
        self.sort_index = (self.priority.value, self.created_at.timestamp())

    def can_retry(self) -> bool:
        """Check if this task can be retried."""
        return self.retries < self.max_retries

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary representation."""
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "task_type": self.task_type,
            "payload": self.payload,
            "priority": self.priority.name,
            "status": self.status.name,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
            "retries": self.retries,
            "max_retries": self.max_retries,
            "metadata": self.metadata,
        }


# Type alias for task handlers
TaskHandler = Callable[[BackgroundTask], Coroutine[Any, Any, Any]]


class TaskQueue:
    """Priority-based task queue for autonomous agent work.

    Provides methods to enqueue, dequeue, and manage background tasks
    for agents. Tasks are processed in priority order (critical first).

    Usage:
        queue = TaskQueue()
        task = BackgroundTask(
            agent_id="agent-1",
            task_type="research",
            payload={"query": "weather"}
        )
        await queue.enqueue(task)
        next_task = await queue.dequeue("agent-1")
    """

    def __init__(self):
        """Initialize the task queue."""
        # Priority queue per agent
        self._queues: Dict[str, List[BackgroundTask]] = {}

        # All tasks by ID for lookup
        self._tasks: Dict[str, BackgroundTask] = {}

        # Locks for thread-safe access
        self._queue_locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

        # Task event for waiting on new tasks
        self._task_events: Dict[str, asyncio.Event] = {}

        # Task handlers per type
        self._handlers: Dict[str, TaskHandler] = {}

        logger.info("TaskQueue initialized")

    async def _get_queue_lock(self, agent_id: str) -> asyncio.Lock:
        """Get or create a lock for an agent's queue."""
        async with self._global_lock:
            if agent_id not in self._queue_locks:
                self._queue_locks[agent_id] = asyncio.Lock()
            return self._queue_locks[agent_id]

    async def _get_task_event(self, agent_id: str) -> asyncio.Event:
        """Get or create an event for an agent's queue."""
        async with self._global_lock:
            if agent_id not in self._task_events:
                self._task_events[agent_id] = asyncio.Event()
            return self._task_events[agent_id]

    def register_handler(
        self,
        task_type: str,
        handler: TaskHandler
    ) -> None:
        """Register a handler for a task type.

        Args:
            task_type: The task type to handle
            handler: Async function to process tasks of this type
        """
        self._handlers[task_type] = handler
        logger.info(f"Registered handler for task type: {task_type}")

    async def enqueue(self, task: BackgroundTask) -> str:
        """Add a task to the queue.

        Args:
            task: The task to enqueue

        Returns:
            The task ID
        """
        lock = await self._get_queue_lock(task.agent_id)
        async with lock:
            # Initialize queue if needed
            if task.agent_id not in self._queues:
                self._queues[task.agent_id] = []

            # Add to heap queue
            heapq.heappush(self._queues[task.agent_id], task)

            # Store for lookup
            self._tasks[task.id] = task

            logger.info(
                f"Enqueued task {task.id} for agent {task.agent_id}: "
                f"type={task.task_type}, priority={task.priority.name}"
            )

        # Signal that a new task is available
        event = await self._get_task_event(task.agent_id)
        event.set()

        return task.id

    async def dequeue(
        self,
        agent_id: str,
        timeout: Optional[float] = None
    ) -> Optional[BackgroundTask]:
        """Get the next task for an agent.

        Args:
            agent_id: The agent ID to get tasks for
            timeout: Optional timeout in seconds to wait for a task

        Returns:
            The highest priority pending task, or None if queue is empty
        """
        event = await self._get_task_event(agent_id)

        # Wait for task if timeout specified and queue is empty
        if timeout is not None:
            pending = await self.get_pending(agent_id)
            if not pending:
                try:
                    await asyncio.wait_for(event.wait(), timeout=timeout)
                except asyncio.TimeoutError:
                    return None

        lock = await self._get_queue_lock(agent_id)
        async with lock:
            queue = self._queues.get(agent_id, [])

            # Find next pending task
            while queue:
                task = heapq.heappop(queue)
                if task.status == TaskStatus.PENDING:
                    task.status = TaskStatus.RUNNING
                    task.started_at = datetime.now(timezone.utc)
                    logger.debug(f"Dequeued task {task.id} for agent {agent_id}")

                    # Clear event if queue is empty
                    if not queue:
                        event.clear()

                    return task

            event.clear()
            return None

    async def get_pending(self, agent_id: str) -> List[BackgroundTask]:
        """Get all pending tasks for an agent.

        Args:
            agent_id: The agent ID to get tasks for

        Returns:
            List of pending tasks sorted by priority
        """
        lock = await self._get_queue_lock(agent_id)
        async with lock:
            queue = self._queues.get(agent_id, [])
            pending = [t for t in queue if t.status == TaskStatus.PENDING]
            return sorted(pending, key=lambda t: t.sort_index)

    async def get_task(self, task_id: str) -> Optional[BackgroundTask]:
        """Get a task by ID.

        Args:
            task_id: The task ID

        Returns:
            The task if found, None otherwise
        """
        return self._tasks.get(task_id)

    async def mark_complete(
        self,
        task_id: str,
        result: Any = None
    ) -> bool:
        """Mark a task as completed.

        Args:
            task_id: The task ID
            result: Optional result to store

        Returns:
            True if task was found and updated
        """
        task = self._tasks.get(task_id)
        if task is None:
            logger.warning(f"Attempted to complete unknown task: {task_id}")
            return False

        task.status = TaskStatus.COMPLETED
        task.result = result
        task.completed_at = datetime.now(timezone.utc)

        logger.info(
            f"Task {task_id} completed in "
            f"{(task.completed_at - task.started_at).total_seconds():.2f}s"
        )

        return True

    async def mark_failed(
        self,
        task_id: str,
        error: str,
        retry: bool = True
    ) -> bool:
        """Mark a task as failed.

        Args:
            task_id: The task ID
            error: Error message
            retry: Whether to retry if possible

        Returns:
            True if task was found and updated
        """
        task = self._tasks.get(task_id)
        if task is None:
            logger.warning(f"Attempted to fail unknown task: {task_id}")
            return False

        task.error = error
        task.completed_at = datetime.now(timezone.utc)

        # Check if we should retry
        if retry and task.can_retry():
            task.retries += 1
            task.status = TaskStatus.PENDING
            task.started_at = None
            task.completed_at = None

            # Re-enqueue the task
            lock = await self._get_queue_lock(task.agent_id)
            async with lock:
                if task.agent_id not in self._queues:
                    self._queues[task.agent_id] = []
                heapq.heappush(self._queues[task.agent_id], task)

            logger.warning(
                f"Task {task_id} failed (attempt {task.retries}/{task.max_retries}), "
                f"retrying: {error}"
            )
        else:
            task.status = TaskStatus.FAILED
            logger.error(f"Task {task_id} failed permanently: {error}")

        return True

    async def cancel(self, task_id: str) -> bool:
        """Cancel a pending task.

        Args:
            task_id: The task ID

        Returns:
            True if task was cancelled
        """
        task = self._tasks.get(task_id)
        if task is None:
            return False

        if task.status != TaskStatus.PENDING:
            logger.warning(f"Cannot cancel task {task_id}: status is {task.status.name}")
            return False

        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now(timezone.utc)
        logger.info(f"Task {task_id} cancelled")

        return True

    async def get_stats(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """Get queue statistics.

        Args:
            agent_id: Optional agent ID to filter by

        Returns:
            Dictionary with queue statistics
        """
        if agent_id:
            tasks = [t for t in self._tasks.values() if t.agent_id == agent_id]
        else:
            tasks = list(self._tasks.values())

        stats = {
            "total": len(tasks),
            "pending": sum(1 for t in tasks if t.status == TaskStatus.PENDING),
            "running": sum(1 for t in tasks if t.status == TaskStatus.RUNNING),
            "completed": sum(1 for t in tasks if t.status == TaskStatus.COMPLETED),
            "failed": sum(1 for t in tasks if t.status == TaskStatus.FAILED),
            "cancelled": sum(1 for t in tasks if t.status == TaskStatus.CANCELLED),
        }

        # Calculate average completion time for completed tasks
        completed = [
            t for t in tasks
            if t.status == TaskStatus.COMPLETED and t.started_at and t.completed_at
        ]
        if completed:
            durations = [
                (t.completed_at - t.started_at).total_seconds()
                for t in completed
            ]
            stats["avg_duration_seconds"] = sum(durations) / len(durations)
        else:
            stats["avg_duration_seconds"] = None

        return stats

    async def clear(self, agent_id: Optional[str] = None) -> int:
        """Clear all tasks.

        Args:
            agent_id: Optional agent ID to clear only that agent's tasks

        Returns:
            Number of tasks cleared
        """
        count = 0

        if agent_id:
            lock = await self._get_queue_lock(agent_id)
            async with lock:
                if agent_id in self._queues:
                    count = len(self._queues[agent_id])
                    self._queues[agent_id] = []

                # Remove from tasks dict
                task_ids = [
                    tid for tid, t in self._tasks.items()
                    if t.agent_id == agent_id
                ]
                for tid in task_ids:
                    del self._tasks[tid]
        else:
            async with self._global_lock:
                count = len(self._tasks)
                self._queues.clear()
                self._tasks.clear()

        logger.info(f"Cleared {count} tasks" + (f" for agent {agent_id}" if agent_id else ""))
        return count

    async def shutdown(self) -> None:
        """Shutdown the task queue and cleanup resources."""
        logger.info("Shutting down TaskQueue")

        # Cancel all pending tasks
        for task in self._tasks.values():
            if task.status == TaskStatus.PENDING:
                task.status = TaskStatus.CANCELLED

        await self.clear()
        logger.info("TaskQueue shutdown complete")

    def __repr__(self) -> str:
        """String representation of the queue."""
        return f"TaskQueue(tasks={len(self._tasks)}, agents={len(self._queues)})"


# Global task queue instance
_task_queue: Optional[TaskQueue] = None


def get_task_queue() -> TaskQueue:
    """Get the global task queue instance.

    Returns:
        The singleton TaskQueue instance
    """
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueue()
    return _task_queue
