"""Agentic Executor - Handles confirmation flow and action execution.

This is the central orchestrator for all agentic capabilities.
It handles:
- Action planning and display
- User confirmation flow
- Step-by-step execution
- Progress reporting
- Error handling and rollback
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Generic
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class ActionStatus(str, Enum):
    """Status of an action in the execution plan."""
    PENDING = "pending"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CONFIRMED = "confirmed"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ConfirmationLevel(str, Enum):
    """Level of confirmation required for an action."""
    NONE = "none"           # Auto-execute (safe read operations)
    STANDARD = "standard"   # Normal confirmation
    DANGEROUS = "dangerous" # Extra warning (delete, sudo, etc.)


@dataclass
class Action:
    """A single action in an execution plan."""
    id: str
    tool_name: str
    description: str
    parameters: Dict[str, Any]
    confirmation_level: ConfirmationLevel = ConfirmationLevel.STANDARD
    estimated_cost: float = 0.0
    status: ActionStatus = ActionStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tool_name": self.tool_name,
            "description": self.description,
            "parameters": self.parameters,
            "confirmation_level": self.confirmation_level.value,
            "estimated_cost": self.estimated_cost,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
        }


@dataclass
class ExecutionPlan:
    """A plan containing multiple actions to execute."""
    id: str
    title: str
    description: str
    actions: List[Action] = field(default_factory=list)
    total_estimated_cost: float = 0.0
    status: ActionStatus = ActionStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    confirmed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def add_action(self, action: Action) -> None:
        """Add an action to the plan."""
        self.actions.append(action)
        self.total_estimated_cost += action.estimated_cost

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "actions": [a.to_dict() for a in self.actions],
            "total_estimated_cost": self.total_estimated_cost,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
        }

    def to_confirmation_message(self) -> str:
        """Generate a human-readable confirmation message."""
        lines = [
            f"**{self.title}**",
            "",
            self.description,
            "",
            "**Steps:**",
        ]

        for i, action in enumerate(self.actions, 1):
            cost_str = f" (${action.estimated_cost:.2f})" if action.estimated_cost > 0 else ""
            confirm_str = " ⚠️" if action.confirmation_level == ConfirmationLevel.DANGEROUS else ""
            lines.append(f"{i}. {action.description}{cost_str}{confirm_str}")

        if self.total_estimated_cost > 0:
            lines.extend([
                "",
                f"**Estimated cost:** ${self.total_estimated_cost:.2f}",
            ])

        lines.extend([
            "",
            "Shall I proceed?",
        ])

        return "\n".join(lines)


class AgenticExecutor:
    """
    Executes agentic actions with confirmation flow.

    Usage:
        executor = AgenticExecutor(db, user_id, cost_tracker)

        # Create a plan
        plan = executor.create_plan("Create GitHub Repo", "Setting up new project")
        plan.add_action(executor.action("create_github_repo", {"name": "my-project"}))
        plan.add_action(executor.action("git_commit_push", {"message": "Initial commit"}))

        # Get confirmation message
        message = plan.to_confirmation_message()

        # After user confirms
        results = await executor.execute_plan(plan)
    """

    def __init__(
        self,
        db,
        user_id: UUID,
        cost_tracker=None,
        tool_registry: Dict[str, Callable] = None,
    ):
        self.db = db
        self.user_id = user_id
        self.cost_tracker = cost_tracker
        self.tool_registry = tool_registry or {}
        self._pending_plans: Dict[str, ExecutionPlan] = {}

    def register_tool(
        self,
        name: str,
        handler: Callable,
        confirmation_level: ConfirmationLevel = ConfirmationLevel.STANDARD,
        base_cost: float = 0.0,
    ) -> None:
        """Register a tool for execution."""
        self.tool_registry[name] = {
            "handler": handler,
            "confirmation_level": confirmation_level,
            "base_cost": base_cost,
        }

    def create_plan(self, title: str, description: str) -> ExecutionPlan:
        """Create a new execution plan."""
        plan = ExecutionPlan(
            id=str(uuid4())[:8],
            title=title,
            description=description,
        )
        self._pending_plans[plan.id] = plan
        return plan

    def action(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        description: Optional[str] = None,
        cost_override: Optional[float] = None,
    ) -> Action:
        """Create an action for a tool."""
        tool_info = self.tool_registry.get(tool_name, {})

        return Action(
            id=str(uuid4())[:8],
            tool_name=tool_name,
            description=description or f"Execute {tool_name}",
            parameters=parameters,
            confirmation_level=tool_info.get("confirmation_level", ConfirmationLevel.STANDARD),
            estimated_cost=cost_override if cost_override is not None else tool_info.get("base_cost", 0.0),
        )

    async def execute_plan(
        self,
        plan: ExecutionPlan,
        on_progress: Optional[Callable[[Action, ActionStatus], None]] = None,
    ) -> Dict[str, Any]:
        """
        Execute all actions in a plan.

        Args:
            plan: The execution plan to run
            on_progress: Optional callback for progress updates

        Returns:
            Dict with success status and results for each action
        """
        plan.status = ActionStatus.EXECUTING
        plan.confirmed_at = datetime.utcnow()
        results = []

        for action in plan.actions:
            # Check budget before executing paid actions
            if action.estimated_cost > 0 and self.cost_tracker:
                if not await self.cost_tracker.is_within_budget(action.estimated_cost):
                    action.status = ActionStatus.FAILED
                    action.error = "Daily budget exceeded"
                    results.append(action.to_dict())
                    continue

            # Execute the action
            action.status = ActionStatus.EXECUTING
            action.started_at = datetime.utcnow()

            if on_progress:
                on_progress(action, ActionStatus.EXECUTING)

            try:
                tool_info = self.tool_registry.get(action.tool_name)
                if not tool_info:
                    raise ValueError(f"Unknown tool: {action.tool_name}")

                handler = tool_info["handler"]
                result = await handler(**action.parameters)

                action.status = ActionStatus.COMPLETED
                action.result = result
                action.completed_at = datetime.utcnow()

                # Track cost
                if action.estimated_cost > 0 and self.cost_tracker:
                    await self.cost_tracker.track_cost(
                        operation=action.tool_name,
                        actual_cost=action.estimated_cost,
                    )

                if on_progress:
                    on_progress(action, ActionStatus.COMPLETED)

            except Exception as e:
                logger.error(f"Action {action.id} failed: {e}")
                action.status = ActionStatus.FAILED
                action.error = str(e)
                action.completed_at = datetime.utcnow()

                if on_progress:
                    on_progress(action, ActionStatus.FAILED)

            results.append(action.to_dict())

        # Update plan status
        failed_count = sum(1 for a in plan.actions if a.status == ActionStatus.FAILED)
        if failed_count == 0:
            plan.status = ActionStatus.COMPLETED
        elif failed_count == len(plan.actions):
            plan.status = ActionStatus.FAILED
        else:
            plan.status = ActionStatus.COMPLETED  # Partial success

        plan.completed_at = datetime.utcnow()

        # Clean up
        if plan.id in self._pending_plans:
            del self._pending_plans[plan.id]

        return {
            "success": plan.status == ActionStatus.COMPLETED,
            "plan_id": plan.id,
            "status": plan.status.value,
            "results": results,
            "failed_count": failed_count,
            "total_actions": len(plan.actions),
        }

    def get_pending_plan(self, plan_id: str) -> Optional[ExecutionPlan]:
        """Get a pending plan by ID."""
        return self._pending_plans.get(plan_id)

    def cancel_plan(self, plan_id: str) -> bool:
        """Cancel a pending plan."""
        if plan_id in self._pending_plans:
            del self._pending_plans[plan_id]
            return True
        return False


# Singleton-style helper for creating executor with all tools registered
_executor_instance: Optional[AgenticExecutor] = None


async def get_executor(db, user_id: UUID, cost_tracker=None) -> AgenticExecutor:
    """Get or create an executor with all agentic tools registered."""
    executor = AgenticExecutor(db, user_id, cost_tracker)

    # Import and register tools from each module
    # These will be populated as the modules are built
    try:
        from app.agent.coder import CODER_TOOLS, CoderToolExecutor
        coder = CoderToolExecutor(db, user_id)
        for tool in CODER_TOOLS:
            executor.register_tool(
                name=tool["name"],
                handler=getattr(coder, f"_tool_{tool['name']}"),
                confirmation_level=ConfirmationLevel.STANDARD if tool.get("requires_confirmation", True) else ConfirmationLevel.NONE,
                base_cost=tool.get("estimated_cost", 0.0),
            )
    except ImportError:
        logger.debug("Coder module not yet available")

    try:
        from app.agent.researcher import RESEARCHER_TOOLS, ResearcherToolExecutor
        researcher = ResearcherToolExecutor(db, user_id)
        for tool in RESEARCHER_TOOLS:
            executor.register_tool(
                name=tool["name"],
                handler=getattr(researcher, f"_tool_{tool['name']}"),
                confirmation_level=ConfirmationLevel.STANDARD if tool.get("requires_confirmation", True) else ConfirmationLevel.NONE,
                base_cost=tool.get("estimated_cost", 0.0),
            )
    except ImportError:
        logger.debug("Researcher module not yet available")

    try:
        from app.agent.system_control import SYSTEM_TOOLS, SystemToolExecutor
        system = SystemToolExecutor(db, user_id)
        for tool in SYSTEM_TOOLS:
            confirmation = ConfirmationLevel.DANGEROUS if tool.get("dangerous", False) else (
                ConfirmationLevel.STANDARD if tool.get("requires_confirmation", True) else ConfirmationLevel.NONE
            )
            executor.register_tool(
                name=tool["name"],
                handler=getattr(system, f"_tool_{tool['name']}"),
                confirmation_level=confirmation,
                base_cost=tool.get("estimated_cost", 0.0),
            )
    except ImportError:
        logger.debug("System control module not yet available")

    try:
        from app.agent.finance import FINANCE_TOOLS, FinanceToolExecutor
        finance = FinanceToolExecutor(db, user_id)
        for tool in FINANCE_TOOLS:
            executor.register_tool(
                name=tool["name"],
                handler=getattr(finance, f"_tool_{tool['name']}"),
                confirmation_level=ConfirmationLevel.STANDARD if tool.get("requires_confirmation", True) else ConfirmationLevel.NONE,
                base_cost=tool.get("estimated_cost", 0.0),
            )
    except ImportError:
        logger.debug("Finance module not yet available")

    return executor
