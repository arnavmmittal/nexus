"""Scheduler executor for running scheduled actions.

This module provides the background execution engine that:
- Polls for due actions every 10 seconds
- Executes actions through the AI engine or tool executor
- Handles failures with retry logic
- Emits events via the event bus
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional
from uuid import UUID

from app.scheduler.actions import (
    ActionStatus,
    ActionType,
    CreatedBy,
    ScheduledAction,
)
from app.scheduler.store import ActionStore, get_action_store

logger = logging.getLogger(__name__)

# Type for action handlers
ActionHandler = Callable[[ScheduledAction], Coroutine[Any, Any, Dict[str, Any]]]

# Type for event callbacks
EventCallback = Callable[[str, Dict[str, Any]], Coroutine[Any, Any, None]]


class SchedulerExecutor:
    """Background executor for scheduled actions.

    Runs in the background, polling for due actions and executing them
    through appropriate handlers. Supports retry logic and event emission.
    """

    def __init__(
        self,
        store: Optional[ActionStore] = None,
        poll_interval: float = 10.0,
        max_concurrent: int = 5,
    ):
        """Initialize the scheduler executor.

        Args:
            store: ActionStore instance. Uses global store if not provided.
            poll_interval: Seconds between polling for due actions.
            max_concurrent: Maximum number of concurrent action executions.
        """
        self.store = store or get_action_store()
        self.poll_interval = poll_interval
        self.max_concurrent = max_concurrent

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._semaphore = asyncio.Semaphore(max_concurrent)

        # Action handlers by type
        self._handlers: Dict[ActionType, ActionHandler] = {}

        # Event callbacks
        self._event_callbacks: List[EventCallback] = []

        # Statistics
        self._stats = {
            "actions_executed": 0,
            "actions_succeeded": 0,
            "actions_failed": 0,
            "last_poll": None,
            "last_execution": None,
        }

        # Register default handlers
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """Register default action handlers."""
        self.register_handler(ActionType.REMINDER, self._handle_reminder)
        self.register_handler(ActionType.SEND_MESSAGE, self._handle_send_message)
        self.register_handler(ActionType.EXECUTE_TOOL, self._handle_execute_tool)
        self.register_handler(ActionType.RUN_WORKFLOW, self._handle_run_workflow)
        self.register_handler(ActionType.CHECK_CONDITION, self._handle_check_condition)

    def register_handler(
        self,
        action_type: ActionType,
        handler: ActionHandler,
    ) -> None:
        """Register a handler for an action type.

        Args:
            action_type: The action type to handle
            handler: Async function that executes the action
        """
        self._handlers[action_type] = handler
        logger.debug(f"Registered handler for action type: {action_type.value}")

    def add_event_callback(self, callback: EventCallback) -> None:
        """Add a callback for scheduler events.

        Args:
            callback: Async function called with (event_type, data)
        """
        self._event_callbacks.append(callback)

    async def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit an event to all registered callbacks.

        Args:
            event_type: Type of event (e.g., "action_started", "action_completed")
            data: Event data
        """
        for callback in self._event_callbacks:
            try:
                await callback(event_type, data)
            except Exception as e:
                logger.error(f"Event callback error: {e}")

        # Also try to emit via message bus if available
        try:
            from app.agents.message_bus import MessageBus, AgentMessage, MessageType

            # Get or create a global message bus instance
            from app.agents.registry import get_message_bus
            bus = get_message_bus()
            if bus:
                await bus.publish(AgentMessage(
                    from_agent="scheduler",
                    to_agent="*",  # Broadcast
                    type=MessageType.INFORM,
                    content={
                        "event": event_type,
                        "data": data,
                    },
                ))
        except ImportError:
            pass  # Message bus not available
        except Exception as e:
            logger.debug(f"Could not emit to message bus: {e}")

    async def start(self) -> None:
        """Start the scheduler executor background task."""
        if self._running:
            logger.warning("Scheduler executor already running")
            return

        await self.store.initialize()
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Scheduler executor started (poll interval: {self.poll_interval}s)")

        await self._emit_event("scheduler_started", {
            "poll_interval": self.poll_interval,
            "max_concurrent": self.max_concurrent,
        })

    async def stop(self) -> None:
        """Stop the scheduler executor."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        logger.info("Scheduler executor stopped")
        await self._emit_event("scheduler_stopped", {"stats": self._stats})

    async def _run_loop(self) -> None:
        """Main execution loop."""
        while self._running:
            try:
                await self._poll_and_execute()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}", exc_info=True)

            await asyncio.sleep(self.poll_interval)

    async def _poll_and_execute(self) -> None:
        """Poll for due actions and execute them."""
        self._stats["last_poll"] = datetime.now(timezone.utc).isoformat()

        # Get due actions
        actions = await self.store.list_pending()

        if not actions:
            return

        logger.debug(f"Found {len(actions)} due actions")

        # Execute actions concurrently with semaphore limit
        tasks = []
        for action in actions:
            task = asyncio.create_task(self._execute_with_semaphore(action))
            tasks.append(task)

        # Wait for all to complete
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_with_semaphore(self, action: ScheduledAction) -> None:
        """Execute an action with semaphore limit.

        Args:
            action: The action to execute
        """
        async with self._semaphore:
            await self._execute_action(action)

    async def _execute_action(self, action: ScheduledAction) -> None:
        """Execute a single scheduled action.

        Args:
            action: The action to execute
        """
        self._stats["actions_executed"] += 1
        self._stats["last_execution"] = datetime.now(timezone.utc).isoformat()

        logger.info(f"Executing action {action.id}: {action.description}")

        # Mark as running
        action.mark_running()
        await self.store.update(action)

        await self._emit_event("action_started", {
            "action_id": action.id,
            "action_type": action.action_type.value,
            "description": action.description,
        })

        try:
            # Get handler for action type
            handler = self._handlers.get(action.action_type)
            if not handler:
                raise ValueError(f"No handler for action type: {action.action_type.value}")

            # Execute the handler
            result = await handler(action)

            # Mark completed
            await self.store.mark_completed(action.id, result)
            self._stats["actions_succeeded"] += 1

            logger.info(f"Action {action.id} completed successfully")

            await self._emit_event("action_completed", {
                "action_id": action.id,
                "action_type": action.action_type.value,
                "result": result,
            })

            # Schedule next occurrence if recurring
            if action.recurring:
                await self._schedule_next_occurrence(action)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Action {action.id} failed: {error_msg}")

            # Mark failed (with retry logic)
            updated_action = await self.store.mark_failed(action.id, error_msg)
            self._stats["actions_failed"] += 1

            await self._emit_event("action_failed", {
                "action_id": action.id,
                "action_type": action.action_type.value,
                "error": error_msg,
                "retry_count": updated_action.retry_count if updated_action else 0,
                "will_retry": updated_action.status == ActionStatus.RETRYING if updated_action else False,
            })

    async def _schedule_next_occurrence(self, action: ScheduledAction) -> None:
        """Schedule the next occurrence of a recurring action.

        Args:
            action: The completed recurring action
        """
        try:
            next_action = action.schedule_next_occurrence()
            if next_action:
                await self.store.create(next_action)
                logger.info(
                    f"Scheduled next occurrence of {action.id} for "
                    f"{next_action.scheduled_time.isoformat()}"
                )

                await self._emit_event("recurring_scheduled", {
                    "original_action_id": action.id,
                    "new_action_id": next_action.id,
                    "scheduled_time": next_action.scheduled_time.isoformat(),
                })
        except Exception as e:
            logger.error(f"Failed to schedule next occurrence: {e}")

    # Default action handlers

    async def _handle_reminder(self, action: ScheduledAction) -> Dict[str, Any]:
        """Handle a reminder action.

        Args:
            action: The reminder action

        Returns:
            Result dictionary
        """
        message = action.payload.get("message", "Reminder")
        title = action.payload.get("title", "Reminder")

        # Try to send push notification
        try:
            from app.notifications.push import send_push_notification
            await send_push_notification(
                user_id=str(action.user_id),
                title=title,
                body=message,
                data={"action_id": action.id, "type": "reminder"},
            )
            return {"status": "notification_sent", "message": message}
        except ImportError:
            logger.debug("Push notifications not available")
        except Exception as e:
            logger.warning(f"Failed to send push notification: {e}")

        # Fallback: just log and return success
        logger.info(f"Reminder for user {action.user_id}: {message}")
        return {"status": "reminder_logged", "message": message}

    async def _handle_send_message(self, action: ScheduledAction) -> Dict[str, Any]:
        """Handle a send message action.

        Args:
            action: The send message action

        Returns:
            Result dictionary
        """
        message = action.payload.get("message", "")
        channel = action.payload.get("channel", "default")
        recipient = action.payload.get("recipient")

        # Handle different message channels
        if channel == "email":
            # Use email tools
            try:
                from app.integrations.email_tools import send_email
                result = await send_email(
                    to=recipient or action.payload.get("to", ""),
                    subject=action.payload.get("subject", "Scheduled Message"),
                    body=message,
                )
                return {"status": "email_sent", "result": json.loads(result)}
            except Exception as e:
                raise Exception(f"Failed to send email: {e}")

        elif channel == "slack":
            # Use Slack tools
            try:
                from app.integrations.slack_tools import send_slack_message
                result = await send_slack_message(
                    channel=recipient or action.payload.get("channel_id", ""),
                    message=message,
                )
                return {"status": "slack_sent", "result": json.loads(result)}
            except Exception as e:
                raise Exception(f"Failed to send Slack message: {e}")

        else:
            # Default: send as push notification
            try:
                from app.notifications.push import send_push_notification
                await send_push_notification(
                    user_id=str(action.user_id),
                    title="Scheduled Message",
                    body=message,
                    data={"action_id": action.id, "type": "message"},
                )
                return {"status": "notification_sent", "message": message}
            except ImportError:
                return {"status": "message_logged", "message": message}

    async def _handle_execute_tool(self, action: ScheduledAction) -> Dict[str, Any]:
        """Handle an execute tool action.

        Args:
            action: The execute tool action

        Returns:
            Result dictionary
        """
        tool_name = action.payload.get("tool_name")
        tool_args = action.payload.get("args", {})

        if not tool_name:
            raise ValueError("No tool_name specified in payload")

        # Try integration executor first
        try:
            from app.integrations.executor import execute_integration_tool, is_integration_tool

            if is_integration_tool(tool_name):
                result = await execute_integration_tool(tool_name, tool_args)
                return {"status": "tool_executed", "tool": tool_name, "result": json.loads(result)}
        except ImportError:
            pass

        # Try MCP executor
        try:
            from app.mcp.executor import execute_tool

            result = await execute_tool(tool_name, tool_args)
            return {"status": "tool_executed", "tool": tool_name, "result": result}
        except ImportError:
            pass
        except Exception as e:
            raise Exception(f"Failed to execute tool {tool_name}: {e}")

        raise ValueError(f"Tool not found: {tool_name}")

    async def _handle_run_workflow(self, action: ScheduledAction) -> Dict[str, Any]:
        """Handle a run workflow action.

        Args:
            action: The run workflow action

        Returns:
            Result dictionary
        """
        workflow_name = action.payload.get("workflow_name")
        workflow_steps = action.payload.get("steps", [])
        workflow_args = action.payload.get("args", {})

        if not workflow_name and not workflow_steps:
            raise ValueError("No workflow_name or steps specified in payload")

        results = []

        # Execute workflow steps sequentially
        for i, step in enumerate(workflow_steps):
            step_type = step.get("type", "execute_tool")
            step_payload = step.get("payload", {})

            logger.debug(f"Executing workflow step {i + 1}/{len(workflow_steps)}: {step_type}")

            if step_type == "execute_tool":
                step_action = ScheduledAction(
                    action_type=ActionType.EXECUTE_TOOL,
                    payload=step_payload,
                    scheduled_time=action.scheduled_time,
                    user_id=action.user_id,
                )
                step_result = await self._handle_execute_tool(step_action)
                results.append({"step": i + 1, "type": step_type, "result": step_result})

            elif step_type == "send_message":
                step_action = ScheduledAction(
                    action_type=ActionType.SEND_MESSAGE,
                    payload=step_payload,
                    scheduled_time=action.scheduled_time,
                    user_id=action.user_id,
                )
                step_result = await self._handle_send_message(step_action)
                results.append({"step": i + 1, "type": step_type, "result": step_result})

            elif step_type == "wait":
                wait_seconds = step_payload.get("seconds", 1)
                await asyncio.sleep(wait_seconds)
                results.append({"step": i + 1, "type": step_type, "waited": wait_seconds})

            else:
                results.append({"step": i + 1, "type": step_type, "error": f"Unknown step type: {step_type}"})

        return {
            "status": "workflow_completed",
            "workflow_name": workflow_name,
            "steps_completed": len(results),
            "results": results,
        }

    async def _handle_check_condition(self, action: ScheduledAction) -> Dict[str, Any]:
        """Handle a check condition action.

        Args:
            action: The check condition action

        Returns:
            Result dictionary
        """
        condition_type = action.payload.get("condition_type", "tool_result")
        condition = action.payload.get("condition", {})
        on_true = action.payload.get("on_true")
        on_false = action.payload.get("on_false")

        result = False
        check_result = None

        # Evaluate condition based on type
        if condition_type == "tool_result":
            # Execute a tool and check the result
            tool_name = condition.get("tool_name")
            tool_args = condition.get("args", {})
            expected = condition.get("expected")
            check_field = condition.get("check_field")

            if tool_name:
                step_action = ScheduledAction(
                    action_type=ActionType.EXECUTE_TOOL,
                    payload={"tool_name": tool_name, "args": tool_args},
                    scheduled_time=action.scheduled_time,
                    user_id=action.user_id,
                )
                check_result = await self._handle_execute_tool(step_action)

                # Check the condition
                if check_field and "result" in check_result:
                    actual_value = check_result["result"].get(check_field)
                    result = actual_value == expected
                elif expected is not None:
                    result = check_result == expected
                else:
                    result = check_result.get("status") == "tool_executed"

        elif condition_type == "time_based":
            # Time-based condition (e.g., is it a weekday?)
            now = datetime.now(timezone.utc)
            time_check = condition.get("check", "is_weekday")

            if time_check == "is_weekday":
                result = now.weekday() < 5
            elif time_check == "is_weekend":
                result = now.weekday() >= 5
            elif time_check == "is_morning":
                result = 6 <= now.hour < 12
            elif time_check == "is_afternoon":
                result = 12 <= now.hour < 18
            elif time_check == "is_evening":
                result = 18 <= now.hour < 22

            check_result = {"time_check": time_check, "current_hour": now.hour, "weekday": now.weekday()}

        # Execute action based on result
        follow_up_result = None
        follow_up_action = on_true if result else on_false

        if follow_up_action:
            follow_up_type = ActionType(follow_up_action.get("action_type", "reminder"))
            follow_up = ScheduledAction(
                action_type=follow_up_type,
                payload=follow_up_action.get("payload", {}),
                scheduled_time=action.scheduled_time,
                user_id=action.user_id,
            )

            handler = self._handlers.get(follow_up_type)
            if handler:
                follow_up_result = await handler(follow_up)

        return {
            "status": "condition_checked",
            "condition_type": condition_type,
            "condition_result": result,
            "check_result": check_result,
            "follow_up_executed": follow_up_action is not None,
            "follow_up_result": follow_up_result,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get executor statistics.

        Returns:
            Dictionary with execution statistics
        """
        return {
            **self._stats,
            "running": self._running,
            "poll_interval": self.poll_interval,
            "max_concurrent": self.max_concurrent,
            "registered_handlers": list(self._handlers.keys()),
        }


# Global executor instance
_executor: Optional[SchedulerExecutor] = None


def get_scheduler_executor() -> SchedulerExecutor:
    """Get or create the global scheduler executor instance."""
    global _executor
    if _executor is None:
        _executor = SchedulerExecutor()
    return _executor


async def start_scheduler_executor() -> SchedulerExecutor:
    """Start and return the global scheduler executor."""
    executor = get_scheduler_executor()
    await executor.start()
    return executor


async def stop_scheduler_executor() -> None:
    """Stop the global scheduler executor."""
    global _executor
    if _executor:
        await _executor.stop()
        _executor = None
