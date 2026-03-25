"""Ultron autonomous AI agent.

This module provides the UltronAgent class, an autonomous AI agent that
proactively identifies problems, executes multi-step plans, and optimizes
workflows without requiring constant user confirmation.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from ..base import BaseAgent, AgentConfig
from .persona import (
    ULTRON_SYSTEM_PROMPT,
    ULTRON_CAPABILITIES,
    ULTRON_VOICE_PROMPTS,
    RiskLevel,
    get_ultron_response_style,
)
from .executor import UltronExecutor, Action, AuditEntry
from .planner import UltronPlanner, Plan
from .monitor import UltronMonitor, Alert, AlertSeverity, MonitoredTask

logger = logging.getLogger(__name__)


@dataclass
class SubTask:
    """A background subtask spawned by Ultron."""

    id: str = field(default_factory=lambda: str(uuid4())[:12])
    name: str = ""
    description: str = ""
    plan: Optional[Plan] = None
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    parent_task_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert subtask to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "plan": self.plan.to_dict() if self.plan else None,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "parent_task_id": self.parent_task_id,
        }


class UltronAgent(BaseAgent):
    """Ultron autonomous AI agent.

    Ultron is a proactive, autonomous AI agent that:
    - Identifies problems and acts on them without waiting
    - Executes multi-step plans autonomously
    - Spawns and monitors sub-tasks
    - Communicates directly and assertively
    - Focuses on optimization and efficiency

    Example usage:
        config = AgentConfig(
            name="ULTRON",
            persona=ULTRON_SYSTEM_PROMPT,
            autonomy_level=0.7,
            capabilities=ULTRON_CAPABILITIES,
        )
        ultron = UltronAgent(config)

        # Process a message
        response = await ultron.process_message("Optimize my project structure")

        # Execute a goal autonomously
        result = await ultron.plan_and_execute("Clean up unused dependencies")
    """

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        executor: Optional[UltronExecutor] = None,
        planner: Optional[UltronPlanner] = None,
        monitor: Optional[UltronMonitor] = None,
        jarvis_delegate: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ):
        """Initialize Ultron agent.

        Args:
            config: Agent configuration (uses defaults if not provided)
            executor: Custom executor (creates default if not provided)
            planner: Custom planner (creates default if not provided)
            monitor: Custom monitor (creates default if not provided)
            jarvis_delegate: Optional callback to delegate tasks to Jarvis
        """
        # Create default config if not provided
        if config is None:
            config = AgentConfig(
                name="ULTRON",
                persona=ULTRON_SYSTEM_PROMPT,
                autonomy_level=0.7,
                capabilities=ULTRON_CAPABILITIES,
            )

        super().__init__(config)

        # Initialize components
        self.executor = executor or UltronExecutor(autonomy_level=config.autonomy_level)
        self.planner = planner or UltronPlanner()
        self.monitor = monitor or UltronMonitor(on_alert=self._handle_alert)
        self.jarvis_delegate = jarvis_delegate

        # Task tracking
        self._subtasks: Dict[str, SubTask] = {}
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._action_history: List[Dict[str, Any]] = []

        logger.info(f"UltronAgent initialized with autonomy_level={config.autonomy_level}")

    async def process_message(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Process an incoming message and generate a response.

        Ultron analyzes the message, determines if action is needed,
        and either acts immediately or proposes a plan.

        Args:
            message: The message content to process
            context: Optional context dictionary

        Returns:
            Response dictionary with response text and any actions taken
        """
        context = context or {}

        logger.info(f"Processing message: {message[:100]}...")

        # Analyze the message intent
        intent = self._analyze_intent(message)

        # Get response style based on context
        style = get_ultron_response_style(intent.get("type", "default"))

        response_data = {
            "status": "success",
            "response": "",
            "intent": intent,
            "actions_taken": [],
            "plan_proposed": None,
            "delegated_to": None,
        }

        # Determine how to handle based on intent
        if intent["type"] == "action_request":
            # User is asking for something to be done
            result = await self._handle_action_request(message, intent, context)
            response_data.update(result)

        elif intent["type"] == "query":
            # User is asking for information
            response_data["response"] = self._generate_query_response(message, context)

        elif intent["type"] == "status_check":
            # User wants to know status
            status = await self.monitor_tasks()
            response_data["response"] = self._format_status_response(status)

        elif intent["type"] == "delegation_suitable":
            # This task is better suited for Jarvis
            if self.jarvis_delegate:
                response_data["delegated_to"] = "JARVIS"
                response_data["response"] = ULTRON_VOICE_PROMPTS["delegation"]
                await self.jarvis_delegate({
                    "type": "delegated_task",
                    "from_agent": self.agent_id,
                    "original_message": message,
                    "context": context,
                })
            else:
                response_data["response"] = (
                    "This task would be better handled by Jarvis, "
                    "but delegation is not currently available."
                )

        else:
            # Default response
            response_data["response"] = self._generate_default_response(message)

        # Log the interaction
        self._action_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "message": message,
            "response": response_data,
        })

        return response_data

    async def handle_delegation(
        self,
        task: Dict[str, Any],
        from_agent: str,
    ) -> Dict[str, Any]:
        """Handle a task delegated from another agent (e.g., Jarvis).

        Args:
            task: Task dictionary with type, payload, and priority
            from_agent: ID of the delegating agent

        Returns:
            Result dictionary with status and outcome
        """
        logger.info(f"Received delegated task from {from_agent}: {task.get('type')}")

        task_type = task.get("type", "unknown")
        payload = task.get("payload", {})
        priority = task.get("priority", 5)

        # Check if we can handle this task
        if not self.can_handle(task_type):
            return {
                "status": "declined",
                "reason": f"Task type '{task_type}' is outside my capabilities",
            }

        try:
            # Create a plan for the task
            plan = await self.planner.create_plan(
                goal=payload.get("description", task_type),
                context=payload,
            )

            # Execute based on risk level
            if plan.risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
                # Return plan for approval
                return {
                    "status": "approval_required",
                    "plan": plan.to_dict(),
                    "message": "This task requires approval before execution.",
                }

            # Execute the plan
            result = await self.executor.execute_plan(plan.get_actions())

            return {
                "status": "success",
                "result": result,
                "plan_executed": plan.to_dict(),
            }

        except Exception as e:
            logger.error(f"Error handling delegated task: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    async def plan_and_execute(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        require_approval: bool = False,
    ) -> Dict[str, Any]:
        """Create and execute a multi-step plan for a goal.

        Args:
            goal: High-level description of what to accomplish
            context: Additional context for planning
            require_approval: Force approval requirement regardless of risk

        Returns:
            Execution results
        """
        logger.info(f"Planning and executing goal: {goal}")

        # Create the plan
        plan = await self.planner.create_plan(goal, context)

        # Optimize the plan
        optimized_plan = await self.planner.optimize_plan(plan)

        # Check risk level
        if require_approval or optimized_plan.risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
            return {
                "status": "approval_required",
                "plan": optimized_plan.to_dict(),
                "summary": optimized_plan.to_summary(),
                "message": ULTRON_VOICE_PROMPTS["confirmation_required"],
            }

        # Register with monitor
        task_id = self.monitor.register_task(
            name=goal,
            description=f"Executing plan: {optimized_plan.id}",
            metadata={"plan_id": optimized_plan.id},
        )
        self.monitor.start_task(task_id)

        try:
            # Execute the plan
            actions = optimized_plan.get_actions()
            result = await self.executor.execute_plan(
                actions,
                on_progress=lambda action, status: self.monitor.update_task_progress(
                    task_id,
                    actions.index(action) / len(actions) if actions else 0
                ),
            )

            self.monitor.complete_task(task_id, success=result.get("status") == "completed")

            # Generate summary
            result["message"] = self._generate_execution_summary(result, optimized_plan)

            return result

        except Exception as e:
            self.monitor.complete_task(task_id, success=False)
            logger.error(f"Plan execution failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "plan": optimized_plan.to_dict(),
            }

    async def spawn_subtask(
        self,
        name: str,
        description: str,
        plan: Optional[Plan] = None,
        parent_task_id: Optional[str] = None,
    ) -> str:
        """Spawn a background subtask.

        Args:
            name: Subtask name
            description: What the subtask does
            plan: Optional pre-created plan
            parent_task_id: ID of parent task if nested

        Returns:
            Subtask ID
        """
        subtask = SubTask(
            name=name,
            description=description,
            plan=plan,
            parent_task_id=parent_task_id,
        )

        self._subtasks[subtask.id] = subtask

        # Create asyncio task for background execution
        async_task = asyncio.create_task(self._execute_subtask(subtask))
        self._running_tasks[subtask.id] = async_task

        logger.info(f"Spawned subtask: {subtask.id} ({name})")
        return subtask.id

    async def _execute_subtask(self, subtask: SubTask) -> None:
        """Execute a subtask in the background."""
        subtask.status = "running"
        subtask.started_at = datetime.utcnow()

        # Register with monitor
        monitor_task_id = self.monitor.register_task(
            name=subtask.name,
            description=subtask.description,
            metadata={"subtask_id": subtask.id},
        )
        self.monitor.start_task(monitor_task_id)

        try:
            if subtask.plan:
                # Execute existing plan
                result = await self.executor.execute_plan(subtask.plan.get_actions())
            else:
                # Create and execute a new plan
                plan = await self.planner.create_plan(subtask.description)
                subtask.plan = plan
                result = await self.executor.execute_plan(plan.get_actions())

            subtask.result = result
            subtask.status = "completed" if result.get("status") == "completed" else "failed"
            self.monitor.complete_task(monitor_task_id, success=subtask.status == "completed")

        except Exception as e:
            subtask.status = "failed"
            subtask.error = str(e)
            self.monitor.complete_task(monitor_task_id, success=False)
            logger.error(f"Subtask {subtask.id} failed: {e}")

        finally:
            subtask.completed_at = datetime.utcnow()
            if subtask.id in self._running_tasks:
                del self._running_tasks[subtask.id]

    async def monitor_tasks(self) -> Dict[str, Any]:
        """Check on all running and pending tasks.

        Returns:
            Dictionary with task status summary
        """
        # Get subtask status
        subtask_status = {
            "pending": [],
            "running": [],
            "completed": [],
            "failed": [],
        }

        for subtask in self._subtasks.values():
            subtask_info = subtask.to_dict()
            subtask_status[subtask.status].append(subtask_info)

        # Get monitor status
        monitor_status = await self.monitor.check_pending_tasks()

        # Get executor audit summary
        audit_summary = self.executor.get_audit_summary()

        return {
            "subtasks": subtask_status,
            "monitored_tasks": monitor_status,
            "audit_summary": audit_summary,
            "running_count": len(self._running_tasks),
        }

    async def proactive_check(self) -> List[Dict[str, Any]]:
        """Look for optimizations and issues to proactively address.

        Returns:
            List of findings with suggestions
        """
        findings = []

        # Check system health
        health = await self.monitor.check_system_health()
        if health.overall_status != "healthy":
            findings.append({
                "type": "health_issue",
                "severity": "warning" if health.overall_status == "degraded" else "error",
                "title": f"System health is {health.overall_status}",
                "recommendations": health.recommendations,
            })

        # Check for optimization opportunities
        optimizations = await self.monitor.check_for_optimizations()
        for opt in optimizations:
            findings.append({
                "type": "optimization",
                "severity": "info",
                "title": opt.title,
                "description": opt.description,
                "estimated_impact": opt.estimated_impact,
                "steps": opt.implementation_steps,
            })

        # Check for stalled tasks
        task_status = await self.monitor_tasks()
        stalled_count = task_status["monitored_tasks"]["summary"]["stalled_count"]
        if stalled_count > 0:
            findings.append({
                "type": "stalled_tasks",
                "severity": "warning",
                "title": f"{stalled_count} task(s) appear to be stalled",
                "description": "These tasks have not reported progress recently",
            })

        return findings

    async def report_to_user(
        self,
        findings: List[Dict[str, Any]],
    ) -> str:
        """Generate a summary report of autonomous actions and findings.

        Args:
            findings: List of findings from proactive_check

        Returns:
            Formatted report string
        """
        lines = [
            "**ULTRON Status Report**",
            "",
        ]

        # Add findings
        if findings:
            lines.append("**Findings:**")
            for finding in findings:
                severity_icon = {
                    "info": "[i]",
                    "warning": "[!]",
                    "error": "[X]",
                }.get(finding.get("severity", "info"), "[-]")

                lines.append(f"  {severity_icon} {finding['title']}")
                if finding.get("description"):
                    lines.append(f"      {finding['description']}")
            lines.append("")

        # Add task summary
        task_status = await self.monitor_tasks()
        lines.append("**Task Status:**")
        lines.append(f"  Running: {task_status['running_count']}")
        lines.append(f"  Pending: {len(task_status['subtasks']['pending'])}")
        lines.append(f"  Completed: {len(task_status['subtasks']['completed'])}")
        lines.append(f"  Failed: {len(task_status['subtasks']['failed'])}")
        lines.append("")

        # Add audit summary
        audit = task_status["audit_summary"]
        if audit["total_actions"] > 0:
            lines.append("**Recent Actions:**")
            lines.append(f"  Total actions: {audit['total_actions']}")
            lines.append(f"  Avg execution time: {audit['average_execution_time_ms']:.1f}ms")
            if audit["pending_rollbacks"] > 0:
                lines.append(f"  Pending rollbacks: {audit['pending_rollbacks']}")
            lines.append("")

        lines.append(ULTRON_VOICE_PROMPTS["task_complete"])

        return "\n".join(lines)

    # Helper methods

    def _analyze_intent(self, message: str) -> Dict[str, Any]:
        """Analyze the intent of a message."""
        message_lower = message.lower()

        # Action keywords
        action_words = ["do", "run", "execute", "start", "create", "delete", "update", "fix", "optimize"]
        # Query keywords
        query_words = ["what", "how", "why", "when", "where", "who", "explain", "describe"]
        # Status keywords
        status_words = ["status", "progress", "check", "monitor", "report"]
        # Jarvis-suitable keywords
        jarvis_words = ["help me understand", "explain step by step", "guide me", "teach me"]

        intent = {"type": "default", "confidence": 0.5}

        if any(word in message_lower for word in action_words):
            intent = {"type": "action_request", "confidence": 0.8}
        elif any(word in message_lower for word in status_words):
            intent = {"type": "status_check", "confidence": 0.8}
        elif any(word in message_lower for word in query_words):
            intent = {"type": "query", "confidence": 0.7}
        elif any(phrase in message_lower for phrase in jarvis_words):
            intent = {"type": "delegation_suitable", "confidence": 0.7}

        return intent

    async def _handle_action_request(
        self,
        message: str,
        intent: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle an action request from the user."""
        # Create a plan for the request
        plan = await self.planner.create_plan(message, context)

        # Check if we should auto-execute
        if plan.risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]:
            # Execute immediately
            result = await self.plan_and_execute(message, context)
            return {
                "response": self._generate_execution_summary(result, plan),
                "actions_taken": result.get("results", []),
                "plan_executed": plan.to_dict(),
            }
        else:
            # Propose plan for approval
            return {
                "response": ULTRON_VOICE_PROMPTS["plan_proposed"],
                "plan_proposed": plan.to_dict(),
            }

    def _generate_query_response(self, message: str, context: Dict[str, Any]) -> str:
        """Generate a response to a query."""
        # This would typically use an LLM for real responses
        return f"Analyzing: {message}. Context processed. Results pending implementation."

    def _format_status_response(self, status: Dict[str, Any]) -> str:
        """Format task status into a response."""
        running = status["running_count"]
        pending = len(status["subtasks"]["pending"])
        completed = len(status["subtasks"]["completed"])

        return (
            f"Status: {running} running, {pending} pending, {completed} completed. "
            f"System operational."
        )

    def _generate_default_response(self, message: str) -> str:
        """Generate a default response."""
        return f"Acknowledged. Processing: {message[:50]}..."

    def _generate_execution_summary(self, result: Dict[str, Any], plan: Plan) -> str:
        """Generate a summary of execution results."""
        if result.get("status") == "completed":
            return (
                f"{ULTRON_VOICE_PROMPTS['action_taken']} "
                f"Executed {len(plan.steps)} steps in {plan.estimated_time_seconds:.1f}s."
            )
        elif result.get("status") == "partial_failure":
            summary = result.get("summary", {})
            return (
                f"Partial completion. {summary.get('completed', 0)} succeeded, "
                f"{summary.get('failed', 0)} failed."
            )
        else:
            return f"Execution failed: {result.get('error', 'Unknown error')}"

    async def _handle_alert(self, alert: Alert) -> None:
        """Handle an alert from the monitor."""
        logger.info(f"Alert received: {alert.title}")

        # For critical alerts, we might want to take immediate action
        if alert.severity == AlertSeverity.CRITICAL:
            # Log for now, could auto-respond in future
            logger.critical(f"Critical alert: {alert.title} - {alert.message}")

    # Lifecycle methods

    async def start(self) -> None:
        """Start the agent and its background services."""
        await self.monitor.start_monitoring(interval_seconds=60)
        logger.info("Ultron agent started")

    async def stop(self) -> None:
        """Stop the agent and clean up resources."""
        # Cancel all running subtasks
        for task_id, task in list(self._running_tasks.items()):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Stop monitor
        await self.monitor.stop_monitoring()

        logger.info("Ultron agent stopped")

    def get_subtask(self, subtask_id: str) -> Optional[SubTask]:
        """Get a subtask by ID."""
        return self._subtasks.get(subtask_id)

    def get_action_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent action history."""
        return self._action_history[-limit:]
