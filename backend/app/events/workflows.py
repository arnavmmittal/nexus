"""Workflow Engine - Automated action workflows triggered by events.

This module enables complex, multi-step workflows that respond to events.
Workflows can run in two modes:
- Jarvis mode: User confirmation required before actions
- Ultron mode: Auto-execute within autonomy boundaries

Pre-built workflows:
- morning_routine: Daily briefing, calendar review, priority tasks
- leaving_home: Check calendar, weather, commute info
- meeting_prep: Research attendees, prepare talking points
- job_search: Scan listings, match skills, prepare applications

"If you'll forgive me, sir, I've already taken the liberty..."
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union
from uuid import uuid4

from .bus import Event, EventPriority, EventType, get_event_bus, emit

logger = logging.getLogger(__name__)


class WorkflowMode(str, Enum):
    """Execution mode for workflows."""

    JARVIS = "jarvis"  # Confirm with user before each action
    ULTRON = "ultron"  # Auto-execute within autonomy boundaries
    HYBRID = "hybrid"  # Confirm high-risk actions, auto-execute safe ones


class StepStatus(str, Enum):
    """Status of a workflow step."""

    PENDING = "pending"
    RUNNING = "running"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class WorkflowStatus(str, Enum):
    """Status of a workflow."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Type for step actions
StepAction = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]


@dataclass
class WorkflowStep:
    """A single step in a workflow."""

    name: str
    action: StepAction
    description: str = ""
    risk_level: float = 0.5  # 0.0 = safe, 1.0 = risky
    requires_confirmation: bool = False
    timeout_seconds: float = 60.0
    retry_count: int = 0
    max_retries: int = 3
    depends_on: List[str] = field(default_factory=list)
    on_failure: str = "stop"  # stop, skip, retry
    condition: Optional[Callable[[Dict[str, Any]], bool]] = None

    # Runtime state
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "risk_level": self.risk_level,
            "requires_confirmation": self.requires_confirmation,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
        }


@dataclass
class Workflow:
    """A workflow consisting of multiple steps.

    Workflows define a sequence of actions that can be triggered by events.
    They support conditional execution, parallel steps, and different
    execution modes (Jarvis/Ultron).
    """

    name: str
    description: str = ""
    steps: List[WorkflowStep] = field(default_factory=list)
    mode: WorkflowMode = WorkflowMode.HYBRID
    trigger_events: List[str] = field(default_factory=list)
    trigger_condition: Optional[Callable[[Event], bool]] = None
    id: str = field(default_factory=lambda: str(uuid4())[:12])

    # Runtime state
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_step_index: int = 0
    context: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    triggered_by: Optional[Event] = None
    error: Optional[str] = None

    def add_step(
        self,
        name: str,
        action: StepAction,
        description: str = "",
        risk_level: float = 0.5,
        requires_confirmation: bool = False,
        **kwargs,
    ) -> "Workflow":
        """Add a step to the workflow. Returns self for chaining."""
        step = WorkflowStep(
            name=name,
            action=action,
            description=description,
            risk_level=risk_level,
            requires_confirmation=requires_confirmation,
            **kwargs,
        )
        self.steps.append(step)
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "mode": self.mode.value,
            "status": self.status.value,
            "trigger_events": self.trigger_events,
            "current_step": self.current_step_index,
            "total_steps": len(self.steps),
            "steps": [s.to_dict() for s in self.steps],
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
        }


class WorkflowEngine:
    """Engine that manages and executes workflows.

    The engine:
    - Registers workflow definitions
    - Listens for trigger events
    - Executes workflows in appropriate mode
    - Manages confirmation flows for Jarvis mode
    - Tracks execution history
    """

    def __init__(self):
        self._workflows: Dict[str, Workflow] = {}
        self._running: Dict[str, Workflow] = {}
        self._history: List[Workflow] = []
        self._max_history = 100
        self._pending_confirmations: Dict[str, Dict] = {}
        self._subscriptions: List[str] = []
        self._lock = asyncio.Lock()

        logger.info("WorkflowEngine initialized")

    def register(self, workflow: Workflow) -> None:
        """Register a workflow.

        Args:
            workflow: The workflow to register
        """
        self._workflows[workflow.name] = workflow
        logger.info(f"Workflow registered: {workflow.name}")

        # Subscribe to trigger events
        bus = get_event_bus()
        for event_pattern in workflow.trigger_events:
            sub_id = bus.subscribe(
                pattern=event_pattern,
                handler=self._create_trigger_handler(workflow.name),
                name=f"workflow:{workflow.name}:{event_pattern}",
            )
            self._subscriptions.append(sub_id)

    def unregister(self, workflow_name: str) -> None:
        """Unregister a workflow."""
        self._workflows.pop(workflow_name, None)

    def _create_trigger_handler(self, workflow_name: str) -> Callable:
        """Create an event handler that triggers a workflow."""

        async def handler(event: Event) -> None:
            workflow = self._workflows.get(workflow_name)
            if not workflow:
                return

            # Check trigger condition if set
            if workflow.trigger_condition:
                if not workflow.trigger_condition(event):
                    return

            # Start the workflow
            await self.start(workflow_name, triggered_by=event)

        return handler

    async def start(
        self,
        workflow_name: str,
        context: Optional[Dict[str, Any]] = None,
        triggered_by: Optional[Event] = None,
        mode_override: Optional[WorkflowMode] = None,
    ) -> str:
        """Start executing a workflow.

        Args:
            workflow_name: Name of the workflow to start
            context: Initial context data
            triggered_by: The event that triggered this workflow
            mode_override: Override the workflow's default mode

        Returns:
            Execution ID
        """
        template = self._workflows.get(workflow_name)
        if not template:
            raise ValueError(f"Unknown workflow: {workflow_name}")

        # Create a copy for execution
        workflow = Workflow(
            name=template.name,
            description=template.description,
            steps=[
                WorkflowStep(
                    name=s.name,
                    action=s.action,
                    description=s.description,
                    risk_level=s.risk_level,
                    requires_confirmation=s.requires_confirmation,
                    timeout_seconds=s.timeout_seconds,
                    max_retries=s.max_retries,
                    depends_on=s.depends_on.copy(),
                    on_failure=s.on_failure,
                    condition=s.condition,
                )
                for s in template.steps
            ],
            mode=mode_override or template.mode,
            trigger_events=template.trigger_events.copy(),
            trigger_condition=template.trigger_condition,
        )

        workflow.context = context or {}
        workflow.triggered_by = triggered_by
        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = datetime.now(timezone.utc)

        async with self._lock:
            self._running[workflow.id] = workflow

        # Emit workflow started event
        await emit(
            EventType.WORKFLOW_STARTED,
            data={
                "workflow_id": workflow.id,
                "workflow_name": workflow.name,
                "mode": workflow.mode.value,
            },
            source="workflow_engine",
        )

        # Start execution in background
        asyncio.create_task(self._execute(workflow))

        logger.info(f"Workflow started: {workflow.name} (id={workflow.id})")
        return workflow.id

    async def _execute(self, workflow: Workflow) -> None:
        """Execute a workflow."""
        try:
            for i, step in enumerate(workflow.steps):
                workflow.current_step_index = i

                # Check if workflow was cancelled
                if workflow.status == WorkflowStatus.CANCELLED:
                    break

                # Check step condition
                if step.condition and not step.condition(workflow.context):
                    step.status = StepStatus.SKIPPED
                    continue

                # Determine if confirmation needed
                needs_confirmation = self._needs_confirmation(workflow, step)

                if needs_confirmation:
                    # Wait for user confirmation
                    step.status = StepStatus.AWAITING_CONFIRMATION
                    approved = await self._wait_for_confirmation(workflow, step)

                    if not approved:
                        step.status = StepStatus.SKIPPED
                        continue

                # Execute the step
                await self._execute_step(workflow, step)

                # Stop if step failed and configured to stop
                if step.status == StepStatus.FAILED and step.on_failure == "stop":
                    workflow.status = WorkflowStatus.FAILED
                    workflow.error = step.error
                    break

            # Mark workflow complete if not failed/cancelled
            if workflow.status == WorkflowStatus.RUNNING:
                workflow.status = WorkflowStatus.COMPLETED

        except Exception as e:
            workflow.status = WorkflowStatus.FAILED
            workflow.error = str(e)
            logger.error(f"Workflow {workflow.name} failed: {e}")

        finally:
            workflow.completed_at = datetime.now(timezone.utc)

            # Move to history
            async with self._lock:
                self._running.pop(workflow.id, None)
                self._history.append(workflow)
                if len(self._history) > self._max_history:
                    self._history = self._history[-self._max_history :]

            # Emit completion event
            event_type = (
                EventType.WORKFLOW_COMPLETED
                if workflow.status == WorkflowStatus.COMPLETED
                else EventType.WORKFLOW_FAILED
            )
            await emit(
                event_type,
                data=workflow.to_dict(),
                source="workflow_engine",
            )

    def _needs_confirmation(self, workflow: Workflow, step: WorkflowStep) -> bool:
        """Determine if a step needs user confirmation."""
        # Always confirm if step explicitly requires it
        if step.requires_confirmation:
            return True

        # Mode-based logic
        if workflow.mode == WorkflowMode.JARVIS:
            return True  # Always confirm in Jarvis mode

        if workflow.mode == WorkflowMode.ULTRON:
            return False  # Never confirm in Ultron mode

        # Hybrid mode: confirm risky actions
        if workflow.mode == WorkflowMode.HYBRID:
            # Check autonomy settings
            try:
                from app.core.user_profile import get_user_profile

                profile = get_user_profile()
                autonomy = profile.autonomy

                # If Ultron is disabled, always confirm
                if not autonomy.ultron_enabled:
                    return True

                # Check risk level against autonomy threshold
                # Higher risk = more likely to need confirmation
                if step.risk_level > 0.7:
                    return True

            except ImportError:
                return True  # Safe default

        return False

    async def _wait_for_confirmation(
        self, workflow: Workflow, step: WorkflowStep
    ) -> bool:
        """Wait for user confirmation to proceed with a step.

        Returns True if approved, False if rejected or timeout.
        """
        confirmation_id = f"{workflow.id}:{step.name}"

        # Store pending confirmation
        self._pending_confirmations[confirmation_id] = {
            "workflow_id": workflow.id,
            "step_name": step.name,
            "description": step.description,
            "risk_level": step.risk_level,
            "future": asyncio.Future(),
        }

        # Notify user (via notification system)
        try:
            from app.notifications import notify, NotificationPriority

            await notify(
                title=f"Confirm: {step.name}",
                body=step.description or f"Workflow '{workflow.name}' wants to: {step.name}",
                priority=NotificationPriority.HIGH,
                data={
                    "type": "workflow_confirmation",
                    "confirmation_id": confirmation_id,
                    "workflow_name": workflow.name,
                    "step_name": step.name,
                    "actions": ["approve", "reject"],
                },
            )
        except ImportError:
            logger.warning("Notification system not available for confirmation")

        # Wait for response with timeout
        try:
            future = self._pending_confirmations[confirmation_id]["future"]
            approved = await asyncio.wait_for(future, timeout=300)  # 5 min timeout
            return approved
        except asyncio.TimeoutError:
            logger.warning(f"Confirmation timeout for {confirmation_id}")
            return False
        finally:
            self._pending_confirmations.pop(confirmation_id, None)

    def respond_to_confirmation(
        self, confirmation_id: str, approved: bool
    ) -> bool:
        """Respond to a pending confirmation request.

        Args:
            confirmation_id: The confirmation ID
            approved: Whether to approve the action

        Returns:
            True if confirmation was found and responded to
        """
        if confirmation_id not in self._pending_confirmations:
            return False

        future = self._pending_confirmations[confirmation_id]["future"]
        if not future.done():
            future.set_result(approved)

        return True

    async def _execute_step(self, workflow: Workflow, step: WorkflowStep) -> None:
        """Execute a single workflow step."""
        step.status = StepStatus.RUNNING
        step.started_at = datetime.now(timezone.utc)

        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                step.action(workflow.context),
                timeout=step.timeout_seconds,
            )

            step.status = StepStatus.COMPLETED
            step.result = result
            workflow.context.update(result or {})

            # Emit step completed event
            await emit(
                EventType.WORKFLOW_STEP_COMPLETED,
                data={
                    "workflow_id": workflow.id,
                    "step_name": step.name,
                    "result": result,
                },
                source="workflow_engine",
            )

        except asyncio.TimeoutError:
            step.status = StepStatus.FAILED
            step.error = "Step timed out"
            logger.warning(f"Step {step.name} timed out in workflow {workflow.name}")

        except Exception as e:
            step.retry_count += 1

            if step.retry_count < step.max_retries and step.on_failure == "retry":
                # Retry after delay
                await asyncio.sleep(2 ** step.retry_count)  # Exponential backoff
                await self._execute_step(workflow, step)
            else:
                step.status = StepStatus.FAILED
                step.error = str(e)
                logger.error(f"Step {step.name} failed: {e}")

        finally:
            step.completed_at = datetime.now(timezone.utc)

    async def cancel(self, workflow_id: str) -> bool:
        """Cancel a running workflow."""
        workflow = self._running.get(workflow_id)
        if workflow:
            workflow.status = WorkflowStatus.CANCELLED
            logger.info(f"Workflow {workflow_id} cancelled")
            return True
        return False

    async def pause(self, workflow_id: str) -> bool:
        """Pause a running workflow."""
        workflow = self._running.get(workflow_id)
        if workflow and workflow.status == WorkflowStatus.RUNNING:
            workflow.status = WorkflowStatus.PAUSED
            logger.info(f"Workflow {workflow_id} paused")
            return True
        return False

    def get_running(self) -> List[Dict[str, Any]]:
        """Get all running workflows."""
        return [w.to_dict() for w in self._running.values()]

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent workflow history."""
        return [w.to_dict() for w in self._history[-limit:]]

    def get_pending_confirmations(self) -> List[Dict[str, Any]]:
        """Get all pending confirmation requests."""
        return [
            {
                "confirmation_id": cid,
                "workflow_id": info["workflow_id"],
                "step_name": info["step_name"],
                "description": info["description"],
                "risk_level": info["risk_level"],
            }
            for cid, info in self._pending_confirmations.items()
        ]

    async def shutdown(self) -> None:
        """Shutdown the workflow engine."""
        # Cancel all running workflows
        for workflow_id in list(self._running.keys()):
            await self.cancel(workflow_id)

        # Unsubscribe from events
        bus = get_event_bus()
        for sub_id in self._subscriptions:
            bus.unsubscribe(sub_id)

        self._subscriptions.clear()
        logger.info("WorkflowEngine shutdown complete")


# ============================================================================
# Pre-built Workflows
# ============================================================================


def create_morning_routine_workflow() -> Workflow:
    """Create the morning routine workflow.

    Triggers: schedule_triggered with routine="morning"
    Actions:
    1. Get today's calendar
    2. Check weather
    3. Summarize top priorities
    4. Check for urgent emails
    5. Generate daily briefing
    """
    workflow = Workflow(
        name="morning_routine",
        description="Daily morning briefing and preparation",
        mode=WorkflowMode.ULTRON,  # Auto-execute (low risk)
        trigger_events=["schedule_triggered"],
        trigger_condition=lambda e: e.data.get("routine") == "morning",
    )

    async def get_calendar(ctx: Dict) -> Dict:
        """Fetch today's calendar events."""
        try:
            from app.integrations.google_calendar import get_today_events

            events = await get_today_events()
            return {"calendar_events": events}
        except Exception as e:
            logger.warning(f"Failed to get calendar: {e}")
            return {"calendar_events": []}

    async def check_weather(ctx: Dict) -> Dict:
        """Check today's weather."""
        # TODO: Integrate with weather API
        return {"weather": {"summary": "Clear skies", "temp": 72}}

    async def get_priorities(ctx: Dict) -> Dict:
        """Get top priorities for today."""
        try:
            from app.models.goal import Goal
            from app.core.database import get_db_session

            # TODO: Actually query priorities
            return {"priorities": ["Focus on key tasks"]}
        except Exception:
            return {"priorities": []}

    async def check_emails(ctx: Dict) -> Dict:
        """Check for urgent emails."""
        try:
            from app.integrations.email_tools import check_urgent_emails

            urgent = await check_urgent_emails()
            return {"urgent_emails": urgent}
        except Exception:
            return {"urgent_emails": []}

    async def generate_briefing(ctx: Dict) -> Dict:
        """Generate the morning briefing."""
        events = ctx.get("calendar_events", [])
        weather = ctx.get("weather", {})
        priorities = ctx.get("priorities", [])
        emails = ctx.get("urgent_emails", [])

        briefing = [
            "Good morning, sir.",
            "",
            f"**Weather**: {weather.get('summary', 'Unknown')}, {weather.get('temp', '--')}°",
            "",
            f"**Calendar**: {len(events)} events today",
        ]

        if events:
            for e in events[:3]:
                briefing.append(f"  - {e.get('summary', 'Event')} at {e.get('start', 'TBD')}")

        if priorities:
            briefing.append("")
            briefing.append(f"**Priorities**: {len(priorities)} items")

        if emails:
            briefing.append("")
            briefing.append(f"**Urgent emails**: {len(emails)} require attention")

        # Send notification
        try:
            from app.notifications import notify, NotificationPriority

            await notify(
                title="Morning Briefing",
                body="\n".join(briefing),
                priority=NotificationPriority.NORMAL,
            )
        except ImportError:
            pass

        return {"briefing": "\n".join(briefing)}

    workflow.add_step("get_calendar", get_calendar, "Fetch today's calendar", risk_level=0.1)
    workflow.add_step("check_weather", check_weather, "Check weather forecast", risk_level=0.1)
    workflow.add_step("get_priorities", get_priorities, "Get top priorities", risk_level=0.1)
    workflow.add_step("check_emails", check_emails, "Check urgent emails", risk_level=0.1)
    workflow.add_step("generate_briefing", generate_briefing, "Generate briefing", risk_level=0.1)

    return workflow


def create_leaving_home_workflow() -> Workflow:
    """Create the leaving home workflow.

    Triggers: smart_home_changed with presence="leaving"
    Actions:
    1. Check if anything important today
    2. Get commute information
    3. Check weather for outdoor prep
    4. Remind about items to bring
    """
    workflow = Workflow(
        name="leaving_home",
        description="Preparation assistance when leaving home",
        mode=WorkflowMode.ULTRON,
        trigger_events=["smart_home_changed", "location_changed"],
        trigger_condition=lambda e: (
            e.data.get("presence") == "leaving"
            or e.data.get("action") == "departing"
        ),
    )

    async def check_calendar(ctx: Dict) -> Dict:
        """Check for important events."""
        try:
            from app.integrations.google_calendar import get_next_event

            next_event = await get_next_event()
            return {"next_event": next_event}
        except Exception:
            return {"next_event": None}

    async def get_commute(ctx: Dict) -> Dict:
        """Get commute information."""
        destination = ctx.get("next_event", {}).get("location")
        if destination:
            # TODO: Integrate with maps API
            return {"commute": {"destination": destination, "duration": "30 min"}}
        return {"commute": None}

    async def prepare_reminder(ctx: Dict) -> Dict:
        """Prepare departure reminder."""
        next_event = ctx.get("next_event")
        commute = ctx.get("commute")

        message_parts = ["Have a good trip!"]

        if next_event:
            message_parts.insert(0, f"Next: {next_event.get('summary', 'Event')}")

        if commute:
            message_parts.append(f"ETA: {commute.get('duration', 'Unknown')}")

        try:
            from app.notifications import notify, NotificationPriority

            await notify(
                title="Leaving Home",
                body=" | ".join(message_parts),
                priority=NotificationPriority.NORMAL,
            )
        except ImportError:
            pass

        return {"reminder_sent": True}

    workflow.add_step("check_calendar", check_calendar, "Check upcoming events", risk_level=0.1)
    workflow.add_step("get_commute", get_commute, "Calculate commute", risk_level=0.1)
    workflow.add_step("prepare_reminder", prepare_reminder, "Send reminder", risk_level=0.2)

    return workflow


def create_meeting_prep_workflow() -> Workflow:
    """Create the meeting preparation workflow.

    Triggers: schedule_triggered with type="meeting_prep"
    Actions:
    1. Get meeting details
    2. Research attendees (LinkedIn, etc.)
    3. Review past interactions
    4. Prepare talking points
    5. Send preparation summary
    """
    workflow = Workflow(
        name="meeting_prep",
        description="Prepare for upcoming meetings",
        mode=WorkflowMode.HYBRID,  # Some actions need confirmation
        trigger_events=["schedule_triggered", "calendar_event"],
        trigger_condition=lambda e: (
            e.data.get("type") == "meeting_prep"
            or (e.data.get("event_type") == "meeting" and e.data.get("minutes_until", 999) <= 30)
        ),
    )

    async def get_meeting_details(ctx: Dict) -> Dict:
        """Get meeting details from calendar."""
        meeting_id = ctx.get("meeting_id")
        # TODO: Fetch actual meeting details
        return {
            "meeting": {
                "title": ctx.get("title", "Meeting"),
                "attendees": ctx.get("attendees", []),
                "description": ctx.get("description", ""),
            }
        }

    async def research_attendees(ctx: Dict) -> Dict:
        """Research meeting attendees."""
        meeting = ctx.get("meeting", {})
        attendees = meeting.get("attendees", [])

        research = []
        for attendee in attendees[:5]:  # Limit to 5 attendees
            # TODO: Actually research via LinkedIn, etc.
            research.append({
                "name": attendee.get("name", attendee.get("email", "Unknown")),
                "title": "Unknown",
                "company": "Unknown",
            })

        return {"attendee_research": research}

    async def review_past_interactions(ctx: Dict) -> Dict:
        """Review past interactions with attendees."""
        meeting = ctx.get("meeting", {})
        attendees = meeting.get("attendees", [])

        # TODO: Search memory for past interactions
        return {"past_interactions": []}

    async def prepare_talking_points(ctx: Dict) -> Dict:
        """Generate talking points for the meeting."""
        meeting = ctx.get("meeting", {})
        research = ctx.get("attendee_research", [])

        # TODO: Use AI to generate talking points
        talking_points = [
            "Introduction and context setting",
            "Key discussion items",
            "Next steps and action items",
        ]

        return {"talking_points": talking_points}

    async def send_prep_summary(ctx: Dict) -> Dict:
        """Send preparation summary."""
        meeting = ctx.get("meeting", {})
        talking_points = ctx.get("talking_points", [])

        summary = [
            f"**Meeting**: {meeting.get('title', 'Meeting')}",
            "",
            "**Talking Points**:",
        ]
        for i, point in enumerate(talking_points, 1):
            summary.append(f"{i}. {point}")

        try:
            from app.notifications import notify, NotificationPriority

            await notify(
                title=f"Prep: {meeting.get('title', 'Meeting')}",
                body="\n".join(summary),
                priority=NotificationPriority.HIGH,
            )
        except ImportError:
            pass

        return {"summary_sent": True}

    workflow.add_step(
        "get_meeting_details",
        get_meeting_details,
        "Get meeting information",
        risk_level=0.1,
    )
    workflow.add_step(
        "research_attendees",
        research_attendees,
        "Research attendees online",
        risk_level=0.3,
        requires_confirmation=True,  # Needs confirmation for privacy
    )
    workflow.add_step(
        "review_past_interactions",
        review_past_interactions,
        "Review past interactions",
        risk_level=0.1,
    )
    workflow.add_step(
        "prepare_talking_points",
        prepare_talking_points,
        "Prepare talking points",
        risk_level=0.1,
    )
    workflow.add_step(
        "send_prep_summary",
        send_prep_summary,
        "Send preparation summary",
        risk_level=0.2,
    )

    return workflow


# ============================================================================
# Global Engine Instance
# ============================================================================

_workflow_engine: Optional[WorkflowEngine] = None


def get_workflow_engine() -> WorkflowEngine:
    """Get the global workflow engine instance."""
    global _workflow_engine
    if _workflow_engine is None:
        _workflow_engine = WorkflowEngine()
    return _workflow_engine


def register_default_workflows() -> None:
    """Register the default/built-in workflows."""
    engine = get_workflow_engine()

    engine.register(create_morning_routine_workflow())
    engine.register(create_leaving_home_workflow())
    engine.register(create_meeting_prep_workflow())

    logger.info("Default workflows registered")


async def start_workflow_engine() -> WorkflowEngine:
    """Start the workflow engine with default workflows."""
    engine = get_workflow_engine()
    register_default_workflows()
    return engine


async def stop_workflow_engine() -> None:
    """Stop the workflow engine."""
    global _workflow_engine
    if _workflow_engine:
        await _workflow_engine.shutdown()
