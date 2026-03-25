"""Ultron's multi-step planning system.

This module provides the UltronPlanner class which creates, decomposes,
optimizes, and risk-assesses execution plans.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .persona import RiskLevel
from .executor import Action

logger = logging.getLogger(__name__)


@dataclass
class PlanStep:
    """A single step in an execution plan."""

    id: str = field(default_factory=lambda: str(uuid4())[:8])
    action: Action = field(default_factory=Action)
    order: int = 0
    parallel_group: Optional[int] = None  # Steps with same group can run in parallel
    condition: Optional[str] = None  # Optional condition for execution
    fallback_step_id: Optional[str] = None  # Step to execute if this one fails

    def to_dict(self) -> Dict[str, Any]:
        """Convert step to dictionary."""
        return {
            "id": self.id,
            "action": self.action.to_dict(),
            "order": self.order,
            "parallel_group": self.parallel_group,
            "condition": self.condition,
            "fallback_step_id": self.fallback_step_id,
        }


@dataclass
class Plan:
    """A multi-step execution plan."""

    id: str = field(default_factory=lambda: str(uuid4())[:12])
    goal: str = ""
    description: str = ""
    steps: List[PlanStep] = field(default_factory=list)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)  # step_id -> list of dependency step_ids
    estimated_time_seconds: float = 0.0
    risk_level: RiskLevel = RiskLevel.MEDIUM
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_step(
        self,
        action: Action,
        depends_on: Optional[List[str]] = None,
        parallel_group: Optional[int] = None,
    ) -> PlanStep:
        """Add a step to the plan.

        Args:
            action: The action to execute in this step
            depends_on: List of step IDs this step depends on
            parallel_group: Group ID for parallel execution

        Returns:
            The created PlanStep
        """
        step = PlanStep(
            action=action,
            order=len(self.steps),
            parallel_group=parallel_group,
        )

        self.steps.append(step)
        self.estimated_time_seconds += action.estimated_time_seconds

        if depends_on:
            self.dependencies[step.id] = depends_on
            action.dependencies = depends_on

        return step

    def get_actions(self) -> List[Action]:
        """Extract all actions from the plan in order."""
        return [step.action for step in sorted(self.steps, key=lambda s: s.order)]

    def to_dict(self) -> Dict[str, Any]:
        """Convert plan to dictionary."""
        return {
            "id": self.id,
            "goal": self.goal,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "dependencies": self.dependencies,
            "estimated_time_seconds": self.estimated_time_seconds,
            "risk_level": self.risk_level.value,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    def to_summary(self) -> str:
        """Generate a human-readable summary of the plan."""
        lines = [
            f"Plan: {self.goal}",
            f"Description: {self.description}",
            f"Steps ({len(self.steps)}):",
        ]

        for i, step in enumerate(sorted(self.steps, key=lambda s: s.order), 1):
            risk_indicator = {
                RiskLevel.LOW: "",
                RiskLevel.MEDIUM: " [M]",
                RiskLevel.HIGH: " [H]",
                RiskLevel.CRITICAL: " [!]",
            }.get(step.action.risk_level, "")

            lines.append(f"  {i}. {step.action.description}{risk_indicator}")

        lines.extend([
            "",
            f"Estimated time: {self.estimated_time_seconds:.1f}s",
            f"Overall risk: {self.risk_level.value.upper()}",
        ])

        return "\n".join(lines)


class UltronPlanner:
    """Multi-step planner for Ultron's autonomous operations.

    The planner creates optimized execution plans from high-level goals,
    decomposes complex tasks, and assesses overall risk.

    Example usage:
        planner = UltronPlanner()

        plan = await planner.create_plan(
            goal="Set up new project",
            context={"project_name": "my-app", "language": "python"}
        )

        optimized = await planner.optimize_plan(plan)
    """

    def __init__(
        self,
        max_steps_per_plan: int = 20,
        default_step_time: float = 2.0,
    ):
        """Initialize the planner.

        Args:
            max_steps_per_plan: Maximum number of steps allowed in a plan
            default_step_time: Default estimated time per step in seconds
        """
        self.max_steps_per_plan = max_steps_per_plan
        self.default_step_time = default_step_time

        # Template library for common task patterns
        self._task_templates: Dict[str, List[Dict[str, Any]]] = {
            "file_analysis": [
                {"tool": "read_file", "description": "Read file contents"},
                {"tool": "analyze_content", "description": "Analyze file structure"},
            ],
            "code_review": [
                {"tool": "read_file", "description": "Read source code"},
                {"tool": "analyze_code", "description": "Analyze code patterns"},
                {"tool": "check_style", "description": "Check code style"},
                {"tool": "report_findings", "description": "Generate review report"},
            ],
            "system_health": [
                {"tool": "check_disk", "description": "Check disk usage"},
                {"tool": "check_memory", "description": "Check memory usage"},
                {"tool": "check_cpu", "description": "Check CPU usage"},
                {"tool": "check_processes", "description": "Check running processes"},
            ],
            "deployment": [
                {"tool": "run_tests", "description": "Run test suite"},
                {"tool": "build_project", "description": "Build project"},
                {"tool": "deploy", "description": "Deploy to environment"},
                {"tool": "verify_deployment", "description": "Verify deployment"},
            ],
        }

        logger.info(f"UltronPlanner initialized with max_steps={max_steps_per_plan}")

    async def create_plan(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        template: Optional[str] = None,
    ) -> Plan:
        """Create an execution plan for a goal.

        Args:
            goal: High-level description of what to accomplish
            context: Additional context for planning
            template: Optional template name to base the plan on

        Returns:
            A Plan object with steps to execute
        """
        context = context or {}

        plan = Plan(
            goal=goal,
            description=f"Automatically generated plan for: {goal}",
            metadata={"context": context},
        )

        # Use template if specified
        if template and template in self._task_templates:
            steps = self._task_templates[template]
            for i, step_template in enumerate(steps):
                action = Action(
                    tool_name=step_template["tool"],
                    description=step_template["description"],
                    parameters=context.copy(),
                    estimated_time_seconds=self.default_step_time,
                )

                # Set up dependencies (each step depends on the previous)
                depends_on = [plan.steps[-1].id] if plan.steps else None
                plan.add_step(action, depends_on=depends_on)
        else:
            # Create a simple single-step plan
            action = Action(
                tool_name="execute_goal",
                description=goal,
                parameters=context.copy(),
                estimated_time_seconds=self.default_step_time,
            )
            plan.add_step(action)

        # Assess overall risk
        plan.risk_level = await self.estimate_risk(plan)

        logger.info(f"Created plan '{plan.id}' with {len(plan.steps)} steps for goal: {goal}")
        return plan

    async def decompose_task(
        self,
        complex_task: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Decompose a complex task into subtasks.

        This is a heuristic-based decomposition. In production, this could
        use an LLM for more sophisticated task breakdown.

        Args:
            complex_task: Description of the complex task
            context: Additional context

        Returns:
            List of subtask dictionaries
        """
        subtasks = []
        task_lower = complex_task.lower()

        # Heuristic decomposition based on keywords
        if "analyze" in task_lower or "review" in task_lower:
            subtasks = [
                {"type": "gather", "description": f"Gather data for: {complex_task}"},
                {"type": "process", "description": f"Process and analyze data"},
                {"type": "report", "description": f"Generate analysis report"},
            ]
        elif "setup" in task_lower or "configure" in task_lower:
            subtasks = [
                {"type": "check", "description": f"Check prerequisites"},
                {"type": "configure", "description": f"Apply configuration"},
                {"type": "verify", "description": f"Verify setup"},
            ]
        elif "deploy" in task_lower or "release" in task_lower:
            subtasks = [
                {"type": "test", "description": f"Run pre-deployment tests"},
                {"type": "build", "description": f"Build artifacts"},
                {"type": "deploy", "description": f"Deploy to target"},
                {"type": "verify", "description": f"Verify deployment"},
            ]
        elif "clean" in task_lower or "optimize" in task_lower:
            subtasks = [
                {"type": "scan", "description": f"Scan for issues"},
                {"type": "process", "description": f"Apply optimizations"},
                {"type": "report", "description": f"Report changes"},
            ]
        else:
            # Default: single task
            subtasks = [
                {"type": "execute", "description": complex_task},
            ]

        # Add context to each subtask
        for subtask in subtasks:
            subtask["context"] = context or {}

        logger.debug(f"Decomposed task into {len(subtasks)} subtasks")
        return subtasks

    async def optimize_plan(self, plan: Plan) -> Plan:
        """Optimize a plan for efficiency.

        Optimizations include:
        - Identifying parallelizable steps
        - Reordering steps for efficiency
        - Merging redundant steps

        Args:
            plan: The plan to optimize

        Returns:
            An optimized version of the plan
        """
        if len(plan.steps) <= 1:
            return plan

        # Create optimized plan
        optimized = Plan(
            goal=plan.goal,
            description=f"Optimized: {plan.description}",
            metadata=plan.metadata.copy(),
        )

        # Group independent steps for parallel execution
        parallel_group = 0
        processed_ids = set()

        for step in plan.steps:
            # Check if this step has unmet dependencies
            deps = plan.dependencies.get(step.id, [])
            unmet_deps = [d for d in deps if d not in processed_ids]

            if not unmet_deps:
                # This step can run in the current parallel group
                new_step = PlanStep(
                    action=step.action,
                    order=len(optimized.steps),
                    parallel_group=parallel_group,
                )
                optimized.steps.append(new_step)
            else:
                # Start a new parallel group
                parallel_group += 1
                new_step = PlanStep(
                    action=step.action,
                    order=len(optimized.steps),
                    parallel_group=parallel_group,
                )
                optimized.steps.append(new_step)

            processed_ids.add(step.id)

        # Recalculate estimated time accounting for parallelism
        time_by_group: Dict[int, float] = {}
        for step in optimized.steps:
            group = step.parallel_group or 0
            step_time = step.action.estimated_time_seconds
            time_by_group[group] = max(time_by_group.get(group, 0), step_time)

        optimized.estimated_time_seconds = sum(time_by_group.values())
        optimized.risk_level = plan.risk_level

        savings = plan.estimated_time_seconds - optimized.estimated_time_seconds
        if savings > 0:
            logger.info(
                f"Plan optimized: {len(optimized.steps)} steps, "
                f"estimated time reduced by {savings:.1f}s"
            )

        return optimized

    async def estimate_risk(self, plan: Plan) -> RiskLevel:
        """Estimate the overall risk level of a plan.

        The overall risk is based on:
        - Maximum risk of any single step
        - Number of high-risk steps
        - Presence of critical operations

        Args:
            plan: The plan to assess

        Returns:
            Overall RiskLevel for the plan
        """
        if not plan.steps:
            return RiskLevel.LOW

        risk_counts = {
            RiskLevel.LOW: 0,
            RiskLevel.MEDIUM: 0,
            RiskLevel.HIGH: 0,
            RiskLevel.CRITICAL: 0,
        }

        for step in plan.steps:
            risk_counts[step.action.risk_level] += 1

        # If any step is critical, plan is critical
        if risk_counts[RiskLevel.CRITICAL] > 0:
            return RiskLevel.CRITICAL

        # If more than 2 high-risk steps, escalate to critical
        if risk_counts[RiskLevel.HIGH] > 2:
            return RiskLevel.CRITICAL

        # If any step is high-risk, plan is high-risk
        if risk_counts[RiskLevel.HIGH] > 0:
            return RiskLevel.HIGH

        # If more than half are medium-risk, plan is high-risk
        if risk_counts[RiskLevel.MEDIUM] > len(plan.steps) / 2:
            return RiskLevel.HIGH

        # If any step is medium-risk, plan is medium-risk
        if risk_counts[RiskLevel.MEDIUM] > 0:
            return RiskLevel.MEDIUM

        return RiskLevel.LOW

    def add_template(self, name: str, steps: List[Dict[str, Any]]) -> None:
        """Add a new task template.

        Args:
            name: Template name
            steps: List of step definitions with 'tool' and 'description'
        """
        self._task_templates[name] = steps
        logger.debug(f"Added template '{name}' with {len(steps)} steps")

    def get_templates(self) -> List[str]:
        """Get list of available template names."""
        return list(self._task_templates.keys())

    async def merge_plans(self, plans: List[Plan]) -> Plan:
        """Merge multiple plans into one.

        Args:
            plans: List of plans to merge

        Returns:
            A single merged plan
        """
        if not plans:
            return Plan(goal="Empty merged plan")

        if len(plans) == 1:
            return plans[0]

        merged = Plan(
            goal=f"Merged plan: {', '.join(p.goal for p in plans)}",
            description="Combined multiple plans into one execution sequence",
        )

        step_order = 0
        for plan in plans:
            for step in plan.steps:
                new_step = PlanStep(
                    action=step.action,
                    order=step_order,
                )
                merged.steps.append(new_step)
                step_order += 1

            merged.estimated_time_seconds += plan.estimated_time_seconds

        # Set risk to maximum of all plans
        max_risk = max((p.risk_level for p in plans), key=lambda r: {
            RiskLevel.LOW: 0,
            RiskLevel.MEDIUM: 1,
            RiskLevel.HIGH: 2,
            RiskLevel.CRITICAL: 3,
        }.get(r, 0))
        merged.risk_level = max_risk

        logger.info(f"Merged {len(plans)} plans into plan with {len(merged.steps)} steps")
        return merged
