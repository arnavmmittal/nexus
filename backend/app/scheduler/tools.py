"""AI tools for scheduling actions.

This module provides tools that AI agents can use to schedule,
manage, and query scheduled actions.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.scheduler.actions import (
    ActionStatus,
    ActionType,
    CreatedBy,
    CronPatterns,
    ScheduledAction,
)
from app.scheduler.store import get_action_store

logger = logging.getLogger(__name__)

# Default user ID for single-user mode
DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


def _parse_natural_time(time_str: str, reference: Optional[datetime] = None) -> datetime:
    """Parse natural language time expressions.

    Supports expressions like:
    - "5pm", "9am", "14:30"
    - "tomorrow at 9am"
    - "in 30 minutes"
    - "next monday at 10am"
    - "midnight", "noon"

    Args:
        time_str: Natural language time expression
        reference: Reference time (defaults to now)

    Returns:
        Parsed datetime in UTC
    """
    if reference is None:
        reference = datetime.now(timezone.utc)

    time_str = time_str.lower().strip()

    # Handle "in X minutes/hours/days"
    in_match = re.match(r"in\s+(\d+)\s+(minute|hour|day|week)s?", time_str)
    if in_match:
        amount = int(in_match.group(1))
        unit = in_match.group(2)
        if unit == "minute":
            return reference + timedelta(minutes=amount)
        elif unit == "hour":
            return reference + timedelta(hours=amount)
        elif unit == "day":
            return reference + timedelta(days=amount)
        elif unit == "week":
            return reference + timedelta(weeks=amount)

    # Handle "tomorrow"
    is_tomorrow = "tomorrow" in time_str
    if is_tomorrow:
        reference = reference + timedelta(days=1)
        time_str = time_str.replace("tomorrow", "").replace("at", "").strip()

    # Handle day names
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for i, day in enumerate(days):
        if day in time_str:
            current_day = reference.weekday()
            days_ahead = i - current_day
            if days_ahead <= 0:  # Target day already passed this week
                days_ahead += 7
            reference = reference + timedelta(days=days_ahead)
            time_str = time_str.replace(f"next {day}", "").replace(day, "").replace("at", "").strip()
            break

    # Handle special times
    if "midnight" in time_str:
        return reference.replace(hour=0, minute=0, second=0, microsecond=0)
    if "noon" in time_str:
        return reference.replace(hour=12, minute=0, second=0, microsecond=0)

    # Handle "X am/pm" format
    time_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", time_str)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2)) if time_match.group(2) else 0
        ampm = time_match.group(3)

        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0

        result = reference.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # If the time has already passed today and no specific date was given,
        # schedule for tomorrow
        if result <= datetime.now(timezone.utc) and not is_tomorrow and "next" not in time_str.lower():
            result += timedelta(days=1)

        return result

    # Fallback: try ISO format
    try:
        parsed = datetime.fromisoformat(time_str)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        pass

    # Default: schedule for next hour if nothing matched
    return reference + timedelta(hours=1)


def _parse_recurrence(pattern: str) -> Optional[str]:
    """Parse natural language recurrence patterns to cron.

    Supports expressions like:
    - "every day at 9am"
    - "every morning" (9am)
    - "every evening" (6pm)
    - "every weekday at 8am"
    - "every monday at 10am"
    - "hourly"
    - "daily"

    Args:
        pattern: Natural language recurrence pattern

    Returns:
        Cron pattern string, or None if not recurring
    """
    pattern = pattern.lower().strip()

    if not any(word in pattern for word in ["every", "hourly", "daily", "weekly"]):
        return None

    # Handle simple patterns
    if pattern in ["hourly", "every hour"]:
        return CronPatterns.EVERY_HOUR
    if pattern in ["daily", "every day"]:
        return CronPatterns.EVERY_DAY_9AM

    # Extract time if present
    hour = 9  # Default to 9am
    minute = 0

    time_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", pattern)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2)) if time_match.group(2) else 0
        ampm = time_match.group(3)

        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0

    # Handle time of day keywords
    if "morning" in pattern:
        hour = 9
    elif "noon" in pattern:
        hour = 12
    elif "afternoon" in pattern:
        hour = 14
    elif "evening" in pattern:
        hour = 18
    elif "night" in pattern or "midnight" in pattern:
        hour = 0

    # Handle day patterns
    if "weekday" in pattern:
        return f"{minute} {hour} * * 1-5"
    if "weekend" in pattern:
        return f"{minute} {hour} * * 0,6"

    # Handle specific days
    days = {
        "sunday": 0, "monday": 1, "tuesday": 2, "wednesday": 3,
        "thursday": 4, "friday": 5, "saturday": 6
    }
    for day_name, day_num in days.items():
        if day_name in pattern:
            return f"{minute} {hour} * * {day_num}"

    # Default: daily at the specified hour
    return f"{minute} {hour} * * *"


async def schedule_action(
    action_type: str,
    scheduled_time: str,
    payload: Optional[Dict[str, Any]] = None,
    description: str = "",
    recurring: str = "",
    user_id: Optional[str] = None,
    created_by: str = "jarvis",
) -> str:
    """Schedule a future action.

    Supports natural language time expressions like:
    - "5pm" - Today at 5pm (or tomorrow if already past)
    - "tomorrow at 9am" - Tomorrow at 9am
    - "in 30 minutes" - 30 minutes from now
    - "next monday at 10am" - Next Monday at 10am
    - "midnight" - Next midnight

    For recurring actions, use expressions like:
    - "every day at 9am"
    - "every weekday at 8am"
    - "every monday at 10am"
    - "hourly"

    Args:
        action_type: Type of action (reminder, send_message, execute_tool, run_workflow, check_condition)
        scheduled_time: When to execute (natural language or ISO format)
        payload: Action-specific data
        description: Human-readable description
        recurring: Recurrence pattern (natural language or cron)
        user_id: User ID (defaults to system user)
        created_by: Agent that created this (jarvis, ultron, user)

    Returns:
        JSON result with action details
    """
    store = get_action_store()
    await store.initialize()

    # Parse action type
    try:
        action_type_enum = ActionType(action_type)
    except ValueError:
        # Try to infer from description or payload
        if "remind" in description.lower() or "reminder" in action_type.lower():
            action_type_enum = ActionType.REMINDER
        elif "email" in description.lower() or "message" in action_type.lower():
            action_type_enum = ActionType.SEND_MESSAGE
        elif "tool" in action_type.lower() or "execute" in action_type.lower():
            action_type_enum = ActionType.EXECUTE_TOOL
        else:
            action_type_enum = ActionType.REMINDER

    # Parse scheduled time
    parsed_time = _parse_natural_time(scheduled_time)

    # Parse recurrence
    cron_pattern = None
    if recurring:
        # Check if it's already a cron pattern
        if re.match(r"^[\d\*\-\/\,]+\s+[\d\*\-\/\,]+\s+[\d\*\-\/\,]+\s+[\d\*\-\/\,]+\s+[\d\*\-\/\,]+$", recurring):
            cron_pattern = recurring
        else:
            cron_pattern = _parse_recurrence(recurring)

    # Parse created_by
    try:
        created_by_enum = CreatedBy(created_by.lower())
    except ValueError:
        created_by_enum = CreatedBy.JARVIS

    # Create the action
    action = ScheduledAction(
        action_type=action_type_enum,
        payload=payload or {},
        scheduled_time=parsed_time,
        user_id=UUID(user_id) if user_id else DEFAULT_USER_ID,
        recurring=cron_pattern,
        created_by=created_by_enum,
        description=description or f"Scheduled {action_type_enum.value}",
    )

    # Save to store
    await store.create(action)

    logger.info(f"Scheduled action {action.id}: {action.description} for {parsed_time.isoformat()}")

    return json.dumps({
        "status": "scheduled",
        "action": {
            "id": action.id,
            "type": action.action_type.value,
            "description": action.description,
            "scheduled_time": action.scheduled_time.isoformat(),
            "scheduled_time_local": action.scheduled_time.strftime("%Y-%m-%d %I:%M %p"),
            "recurring": action.recurring,
            "created_by": action.created_by.value,
        },
        "message": f"Action scheduled for {action.scheduled_time.strftime('%B %d at %I:%M %p')}"
        + (f" (recurring: {action.recurring})" if action.recurring else ""),
    }, indent=2)


async def list_scheduled_actions(
    status: str = "pending",
    hours_ahead: int = 24,
    user_id: Optional[str] = None,
    limit: int = 20,
) -> str:
    """List scheduled actions.

    Args:
        status: Filter by status (pending, running, completed, failed, cancelled, all)
        hours_ahead: For pending actions, how many hours ahead to look
        user_id: Filter by user ID
        limit: Maximum number of results

    Returns:
        JSON result with list of actions
    """
    store = get_action_store()
    await store.initialize()

    uid = UUID(user_id) if user_id else DEFAULT_USER_ID

    if status == "all":
        actions = await store.get_by_user(uid, limit=limit)
    elif status == "pending":
        actions = await store.list_upcoming(uid, hours_ahead=hours_ahead, limit=limit)
    else:
        try:
            status_enum = ActionStatus(status)
            actions = await store.get_by_user(uid, status=status_enum, limit=limit)
        except ValueError:
            actions = await store.get_by_user(uid, limit=limit)

    # Format actions for display
    formatted = []
    for action in actions:
        formatted.append({
            "id": action.id,
            "type": action.action_type.value,
            "description": action.description,
            "scheduled_time": action.scheduled_time.isoformat(),
            "scheduled_time_local": action.scheduled_time.strftime("%Y-%m-%d %I:%M %p"),
            "status": action.status.value,
            "recurring": action.recurring,
            "created_by": action.created_by.value,
        })

    # Get stats
    stats = await store.get_stats(uid)

    return json.dumps({
        "actions": formatted,
        "total": len(formatted),
        "stats": stats,
    }, indent=2)


async def cancel_scheduled_action(action_id: str) -> str:
    """Cancel a scheduled action.

    Args:
        action_id: The ID of the action to cancel

    Returns:
        JSON result with cancellation status
    """
    store = get_action_store()
    await store.initialize()

    action = await store.cancel(action_id)

    if not action:
        return json.dumps({
            "status": "error",
            "message": f"Action not found: {action_id}",
        }, indent=2)

    if action.status == ActionStatus.CANCELLED:
        return json.dumps({
            "status": "cancelled",
            "action": {
                "id": action.id,
                "description": action.description,
                "was_scheduled_for": action.scheduled_time.isoformat(),
            },
            "message": f"Action '{action.description}' has been cancelled",
        }, indent=2)
    else:
        return json.dumps({
            "status": "not_cancelled",
            "action": {
                "id": action.id,
                "description": action.description,
                "current_status": action.status.value,
            },
            "message": f"Action cannot be cancelled (status: {action.status.value})",
        }, indent=2)


async def reschedule_action(
    action_id: str,
    new_time: str,
    new_recurring: str = "",
) -> str:
    """Reschedule an action to a new time.

    Args:
        action_id: The ID of the action to reschedule
        new_time: New scheduled time (natural language or ISO format)
        new_recurring: Optional new recurrence pattern

    Returns:
        JSON result with rescheduling status
    """
    store = get_action_store()
    await store.initialize()

    # Parse the new time
    parsed_time = _parse_natural_time(new_time)

    # Parse new recurrence if provided
    cron_pattern = None
    if new_recurring:
        if re.match(r"^[\d\*\-\/\,]+\s+[\d\*\-\/\,]+\s+[\d\*\-\/\,]+\s+[\d\*\-\/\,]+\s+[\d\*\-\/\,]+$", new_recurring):
            cron_pattern = new_recurring
        else:
            cron_pattern = _parse_recurrence(new_recurring)

    action = await store.reschedule(action_id, parsed_time, cron_pattern)

    if not action:
        return json.dumps({
            "status": "error",
            "message": f"Action not found: {action_id}",
        }, indent=2)

    if action.scheduled_time == parsed_time:
        return json.dumps({
            "status": "rescheduled",
            "action": {
                "id": action.id,
                "description": action.description,
                "new_scheduled_time": action.scheduled_time.isoformat(),
                "new_scheduled_time_local": action.scheduled_time.strftime("%Y-%m-%d %I:%M %p"),
                "recurring": action.recurring,
            },
            "message": f"Action rescheduled to {action.scheduled_time.strftime('%B %d at %I:%M %p')}",
        }, indent=2)
    else:
        return json.dumps({
            "status": "not_rescheduled",
            "action": {
                "id": action.id,
                "description": action.description,
                "current_status": action.status.value,
            },
            "message": f"Action cannot be rescheduled (status: {action.status.value})",
        }, indent=2)


async def get_scheduled_action(action_id: str) -> str:
    """Get details of a scheduled action.

    Args:
        action_id: The ID of the action to retrieve

    Returns:
        JSON result with action details
    """
    store = get_action_store()
    await store.initialize()

    action = await store.get(action_id)

    if not action:
        return json.dumps({
            "status": "error",
            "message": f"Action not found: {action_id}",
        }, indent=2)

    return json.dumps({
        "status": "found",
        "action": action.to_dict(),
    }, indent=2)


# Tool definitions for AI integration
SCHEDULER_TOOLS = [
    {
        "name": "schedule_action",
        "description": """Schedule a future action like a reminder, email, or tool execution.

Supports natural language time expressions:
- "5pm" - Today at 5pm
- "tomorrow at 9am" - Tomorrow at 9am
- "in 30 minutes" - 30 minutes from now
- "next monday at 10am" - Next Monday at 10am

For recurring actions:
- "every day at 9am"
- "every weekday at 8am"
- "every monday"
- "hourly"

Examples:
- Remind me to call mom at 5pm
- Send this email tomorrow at 9am
- Check stock prices every morning
- Turn off lights at midnight""",
        "input_schema": {
            "type": "object",
            "properties": {
                "action_type": {
                    "type": "string",
                    "enum": ["reminder", "send_message", "execute_tool", "run_workflow", "check_condition"],
                    "description": "Type of action to schedule"
                },
                "scheduled_time": {
                    "type": "string",
                    "description": "When to execute (e.g., '5pm', 'tomorrow at 9am', 'in 30 minutes')"
                },
                "payload": {
                    "type": "object",
                    "description": "Action-specific data (e.g., message content, tool name and args)"
                },
                "description": {
                    "type": "string",
                    "description": "Human-readable description of the action"
                },
                "recurring": {
                    "type": "string",
                    "description": "Recurrence pattern (e.g., 'every day at 9am', 'hourly')"
                }
            },
            "required": ["action_type", "scheduled_time"]
        }
    },
    {
        "name": "list_scheduled_actions",
        "description": "List scheduled actions for the user. Shows upcoming reminders, scheduled tasks, and their status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["pending", "running", "completed", "failed", "cancelled", "all"],
                    "description": "Filter by status (default: pending)"
                },
                "hours_ahead": {
                    "type": "integer",
                    "description": "For pending actions, how many hours ahead to look (default: 24)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default: 20)"
                }
            }
        }
    },
    {
        "name": "cancel_scheduled_action",
        "description": "Cancel a scheduled action by its ID. Only pending actions can be cancelled.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action_id": {
                    "type": "string",
                    "description": "The ID of the action to cancel"
                }
            },
            "required": ["action_id"]
        }
    },
    {
        "name": "reschedule_action",
        "description": "Reschedule an action to a new time. Can also update the recurrence pattern.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action_id": {
                    "type": "string",
                    "description": "The ID of the action to reschedule"
                },
                "new_time": {
                    "type": "string",
                    "description": "New scheduled time (e.g., '6pm', 'tomorrow', 'next week')"
                },
                "new_recurring": {
                    "type": "string",
                    "description": "Optional new recurrence pattern"
                }
            },
            "required": ["action_id", "new_time"]
        }
    },
    {
        "name": "get_scheduled_action",
        "description": "Get full details of a scheduled action by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action_id": {
                    "type": "string",
                    "description": "The ID of the action to retrieve"
                }
            },
            "required": ["action_id"]
        }
    },
]
