"""Scheduler module for deferred action execution.

This module provides a complete system for scheduling and executing
future actions, supporting natural language time expressions and
recurring patterns.

Usage:
    from app.scheduler import (
        ScheduledAction,
        ActionType,
        ActionStore,
        SchedulerExecutor,
        schedule_action,
        list_scheduled_actions,
        cancel_scheduled_action,
        reschedule_action,
    )

    # Schedule a reminder
    result = await schedule_action(
        action_type="reminder",
        scheduled_time="5pm",
        payload={"message": "Call mom"},
        description="Reminder to call mom",
    )

    # List pending actions
    actions = await list_scheduled_actions()

    # Start the background executor
    from app.scheduler import start_scheduler_executor
    executor = await start_scheduler_executor()

Examples supported:
    - "Remind me to call mom at 5pm"
    - "Send this email tomorrow at 9am"
    - "Check stock prices every morning"
    - "Turn off lights at midnight"
"""

from app.scheduler.actions import (
    ActionStatus,
    ActionType,
    CreatedBy,
    CronPatterns,
    ScheduledAction,
)
from app.scheduler.store import (
    ActionStore,
    get_action_store,
    init_action_store,
)
from app.scheduler.executor import (
    SchedulerExecutor,
    get_scheduler_executor,
    start_scheduler_executor,
    stop_scheduler_executor,
)
from app.scheduler.tools import (
    schedule_action,
    list_scheduled_actions,
    cancel_scheduled_action,
    reschedule_action,
    get_scheduled_action,
    SCHEDULER_TOOLS,
)

__all__ = [
    # Data models
    "ScheduledAction",
    "ActionType",
    "ActionStatus",
    "CreatedBy",
    "CronPatterns",
    # Store
    "ActionStore",
    "get_action_store",
    "init_action_store",
    # Executor
    "SchedulerExecutor",
    "get_scheduler_executor",
    "start_scheduler_executor",
    "stop_scheduler_executor",
    # Tools
    "schedule_action",
    "list_scheduled_actions",
    "cancel_scheduled_action",
    "reschedule_action",
    "get_scheduled_action",
    "SCHEDULER_TOOLS",
]
