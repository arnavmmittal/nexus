"""Ultron's autonomous executor with high autonomy.

This module provides the UltronExecutor class which handles autonomous
action execution, batching, audit logging, and rollback capabilities.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4
from enum import Enum

from .persona import RiskLevel, RISK_KEYWORDS

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    """An entry in the audit log for tracking autonomous actions."""

    id: str = field(default_factory=lambda: str(uuid4())[:12])
    timestamp: datetime = field(default_factory=datetime.utcnow)
    action_type: str = ""
    action_description: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.LOW
    status: str = "pending"  # pending, executing, completed, failed, rolled_back
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    rollback_available: bool = False
    rollback_data: Optional[Dict[str, Any]] = None
    execution_time_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert audit entry to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "action_type": self.action_type,
            "action_description": self.action_description,
            "parameters": self.parameters,
            "risk_level": self.risk_level.value,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "rollback_available": self.rollback_available,
            "execution_time_ms": self.execution_time_ms,
        }


@dataclass
class Action:
    """A single action to be executed by Ultron."""

    id: str = field(default_factory=lambda: str(uuid4())[:8])
    tool_name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.MEDIUM
    dependencies: List[str] = field(default_factory=list)  # IDs of actions this depends on
    priority: int = 5  # 1 = highest, 10 = lowest
    estimated_time_seconds: float = 1.0
    rollback_handler: Optional[str] = None  # Name of rollback function

    def to_dict(self) -> Dict[str, Any]:
        """Convert action to dictionary."""
        return {
            "id": self.id,
            "tool_name": self.tool_name,
            "description": self.description,
            "parameters": self.parameters,
            "risk_level": self.risk_level.value,
            "dependencies": self.dependencies,
            "priority": self.priority,
            "estimated_time_seconds": self.estimated_time_seconds,
        }


class UltronExecutor:
    """Autonomous executor with high autonomy and audit capabilities.

    This executor:
    - Batches related actions together for efficiency
    - Executes without confirmation for low/medium risk actions
    - Maintains comprehensive audit logs
    - Supports rollback of reversible actions

    Example usage:
        executor = UltronExecutor(tool_registry=my_tools)

        actions = [
            Action(tool_name="read_file", parameters={"path": "/data/config.json"}),
            Action(tool_name="analyze_data", parameters={"source": "config"}),
        ]

        results = await executor.execute_plan(actions)
    """

    def __init__(
        self,
        tool_registry: Optional[Dict[str, Callable]] = None,
        autonomy_level: float = 0.7,
        max_batch_size: int = 10,
    ):
        """Initialize the Ultron executor.

        Args:
            tool_registry: Dictionary mapping tool names to handler functions
            autonomy_level: Level of autonomy (0.0 to 1.0)
            max_batch_size: Maximum number of actions to batch together
        """
        self.tool_registry = tool_registry or {}
        self.autonomy_level = autonomy_level
        self.max_batch_size = max_batch_size
        self._audit_log: List[AuditEntry] = []
        self._pending_rollbacks: Dict[str, AuditEntry] = {}

        logger.info(
            f"UltronExecutor initialized with autonomy_level={autonomy_level}, "
            f"max_batch_size={max_batch_size}"
        )

    def register_tool(
        self,
        name: str,
        handler: Callable,
        rollback_handler: Optional[Callable] = None,
    ) -> None:
        """Register a tool with optional rollback capability.

        Args:
            name: Tool name for reference
            handler: Async function to execute the tool
            rollback_handler: Optional async function to rollback the action
        """
        self.tool_registry[name] = {
            "handler": handler,
            "rollback": rollback_handler,
        }
        logger.debug(f"Registered tool: {name}")

    async def assess_risk(self, action: Action) -> RiskLevel:
        """Assess the risk level of an action.

        Args:
            action: The action to assess

        Returns:
            RiskLevel indicating the assessed risk
        """
        # Start with the action's declared risk level
        risk = action.risk_level

        # Check keywords in action description and tool name
        combined_text = f"{action.tool_name} {action.description}".lower()

        for level in [RiskLevel.CRITICAL, RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW]:
            keywords = RISK_KEYWORDS.get(level, [])
            for keyword in keywords:
                if keyword in combined_text:
                    # Escalate risk if we find higher-risk keywords
                    if self._risk_to_int(level) > self._risk_to_int(risk):
                        risk = level
                        logger.debug(
                            f"Escalated risk for action {action.id} to {risk.value} "
                            f"due to keyword '{keyword}'"
                        )
                    break

        return risk

    def _risk_to_int(self, risk: RiskLevel) -> int:
        """Convert risk level to integer for comparison."""
        mapping = {
            RiskLevel.LOW: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.HIGH: 3,
            RiskLevel.CRITICAL: 4,
        }
        return mapping.get(risk, 2)

    def should_auto_execute(self, risk_level: RiskLevel) -> bool:
        """Determine if an action should auto-execute based on risk and autonomy.

        Args:
            risk_level: The risk level of the action

        Returns:
            True if the action can be auto-executed
        """
        # Map risk levels to autonomy thresholds
        thresholds = {
            RiskLevel.LOW: 0.3,      # Auto-execute if autonomy >= 0.3
            RiskLevel.MEDIUM: 0.5,   # Auto-execute if autonomy >= 0.5
            RiskLevel.HIGH: 0.8,     # Auto-execute if autonomy >= 0.8
            RiskLevel.CRITICAL: 1.1, # Never auto-execute (impossible threshold)
        }

        threshold = thresholds.get(risk_level, 0.5)
        return self.autonomy_level >= threshold

    async def execute_plan(
        self,
        plan: List[Action],
        on_progress: Optional[Callable[[Action, str], None]] = None,
        batch_related: bool = True,
    ) -> Dict[str, Any]:
        """Execute a list of actions, batching related ones for efficiency.

        Args:
            plan: List of actions to execute
            on_progress: Optional callback for progress updates
            batch_related: Whether to batch independent actions

        Returns:
            Dictionary containing results, audit entries, and summary
        """
        logger.info(f"Executing plan with {len(plan)} actions")

        results = []
        actions_requiring_approval = []

        # First pass: assess risks and identify actions needing approval
        for action in plan:
            assessed_risk = await self.assess_risk(action)
            action.risk_level = assessed_risk

            if not self.should_auto_execute(assessed_risk):
                actions_requiring_approval.append(action)

        # If any actions need approval, return the plan for review
        if actions_requiring_approval:
            return {
                "status": "approval_required",
                "actions_requiring_approval": [a.to_dict() for a in actions_requiring_approval],
                "total_actions": len(plan),
                "message": (
                    f"{len(actions_requiring_approval)} action(s) require your approval "
                    f"before execution can proceed."
                ),
            }

        # Sort actions by dependencies and priority
        sorted_actions = self._topological_sort(plan)

        # Execute actions, batching independent ones
        if batch_related:
            batches = self._create_batches(sorted_actions)
        else:
            batches = [[a] for a in sorted_actions]

        for batch in batches:
            batch_results = await self._execute_batch(batch, on_progress)
            results.extend(batch_results)

            # Stop if any action in the batch failed
            if any(r.get("status") == "failed" for r in batch_results):
                logger.warning("Batch execution failed, stopping plan")
                break

        # Compute summary
        completed = sum(1 for r in results if r.get("status") == "completed")
        failed = sum(1 for r in results if r.get("status") == "failed")

        return {
            "status": "completed" if failed == 0 else "partial_failure",
            "results": results,
            "summary": {
                "total": len(plan),
                "completed": completed,
                "failed": failed,
            },
            "audit_entries": [e.to_dict() for e in self._audit_log[-len(plan):]],
        }

    def _topological_sort(self, actions: List[Action]) -> List[Action]:
        """Sort actions respecting dependencies."""
        # Build dependency graph
        action_map = {a.id: a for a in actions}
        sorted_actions = []
        visited = set()
        temp_visited = set()

        def visit(action_id: str):
            if action_id in temp_visited:
                raise ValueError(f"Circular dependency detected involving {action_id}")
            if action_id in visited:
                return

            temp_visited.add(action_id)
            action = action_map.get(action_id)

            if action:
                for dep_id in action.dependencies:
                    if dep_id in action_map:
                        visit(dep_id)

                visited.add(action_id)
                temp_visited.remove(action_id)
                sorted_actions.append(action)

        for action in actions:
            if action.id not in visited:
                visit(action.id)

        return sorted_actions

    def _create_batches(self, actions: List[Action]) -> List[List[Action]]:
        """Create batches of independent actions that can run in parallel."""
        batches = []
        current_batch = []
        completed_ids = set()

        for action in actions:
            # Check if all dependencies are satisfied
            deps_satisfied = all(dep in completed_ids for dep in action.dependencies)

            if deps_satisfied and len(current_batch) < self.max_batch_size:
                current_batch.append(action)
            else:
                if current_batch:
                    batches.append(current_batch)
                    completed_ids.update(a.id for a in current_batch)
                current_batch = [action]

        if current_batch:
            batches.append(current_batch)

        return batches

    async def _execute_batch(
        self,
        batch: List[Action],
        on_progress: Optional[Callable[[Action, str], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Execute a batch of actions concurrently."""
        tasks = []
        for action in batch:
            task = asyncio.create_task(self._execute_single(action, on_progress))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results, converting exceptions to error dicts
        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed.append({
                    "action_id": batch[i].id,
                    "status": "failed",
                    "error": str(result),
                })
            else:
                processed.append(result)

        return processed

    async def _execute_single(
        self,
        action: Action,
        on_progress: Optional[Callable[[Action, str], None]] = None,
    ) -> Dict[str, Any]:
        """Execute a single action with logging."""
        start_time = datetime.utcnow()

        # Create audit entry
        audit = AuditEntry(
            action_type=action.tool_name,
            action_description=action.description,
            parameters=action.parameters,
            risk_level=action.risk_level,
            status="executing",
        )
        self._audit_log.append(audit)

        if on_progress:
            on_progress(action, "executing")

        try:
            tool_info = self.tool_registry.get(action.tool_name)
            if not tool_info:
                raise ValueError(f"Unknown tool: {action.tool_name}")

            handler = tool_info["handler"]

            # Execute the action
            result = await handler(**action.parameters)

            # Calculate execution time
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            # Update audit entry
            audit.status = "completed"
            audit.result = result
            audit.execution_time_ms = execution_time

            # Check for rollback capability
            if tool_info.get("rollback"):
                audit.rollback_available = True
                audit.rollback_data = {
                    "action_id": action.id,
                    "parameters": action.parameters,
                    "result": result,
                }
                self._pending_rollbacks[action.id] = audit

            if on_progress:
                on_progress(action, "completed")

            logger.info(
                f"Action {action.id} ({action.tool_name}) completed in {execution_time:.2f}ms"
            )

            return {
                "action_id": action.id,
                "status": "completed",
                "result": result,
                "execution_time_ms": execution_time,
            }

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            audit.status = "failed"
            audit.error = str(e)
            audit.execution_time_ms = execution_time

            if on_progress:
                on_progress(action, "failed")

            logger.error(f"Action {action.id} ({action.tool_name}) failed: {e}")

            return {
                "action_id": action.id,
                "status": "failed",
                "error": str(e),
                "execution_time_ms": execution_time,
            }

    async def rollback_action(self, action_id: str) -> Dict[str, Any]:
        """Rollback a previously executed action.

        Args:
            action_id: ID of the action to rollback

        Returns:
            Dictionary with rollback result
        """
        audit = self._pending_rollbacks.get(action_id)
        if not audit:
            return {
                "status": "error",
                "message": f"No rollback available for action {action_id}",
            }

        if not audit.rollback_data:
            return {
                "status": "error",
                "message": f"Missing rollback data for action {action_id}",
            }

        tool_name = audit.action_type
        tool_info = self.tool_registry.get(tool_name)

        if not tool_info or not tool_info.get("rollback"):
            return {
                "status": "error",
                "message": f"No rollback handler for tool {tool_name}",
            }

        try:
            rollback_handler = tool_info["rollback"]
            await rollback_handler(**audit.rollback_data)

            audit.status = "rolled_back"
            del self._pending_rollbacks[action_id]

            logger.info(f"Successfully rolled back action {action_id}")

            return {
                "status": "success",
                "message": f"Action {action_id} rolled back successfully",
            }

        except Exception as e:
            logger.error(f"Failed to rollback action {action_id}: {e}")
            return {
                "status": "error",
                "message": f"Rollback failed: {str(e)}",
            }

    async def log_action(self, action: Action, result: Dict[str, Any]) -> AuditEntry:
        """Manually log an action and its result.

        Args:
            action: The action that was executed
            result: The result of the action

        Returns:
            The created audit entry
        """
        audit = AuditEntry(
            action_type=action.tool_name,
            action_description=action.description,
            parameters=action.parameters,
            risk_level=action.risk_level,
            status="completed" if result.get("success", True) else "failed",
            result=result,
            error=result.get("error"),
        )
        self._audit_log.append(audit)

        logger.debug(f"Logged action: {action.tool_name}")
        return audit

    async def get_audit_log(
        self,
        since: Optional[datetime] = None,
        limit: int = 100,
        status_filter: Optional[str] = None,
    ) -> List[AuditEntry]:
        """Retrieve audit log entries.

        Args:
            since: Only return entries after this datetime
            limit: Maximum number of entries to return
            status_filter: Only return entries with this status

        Returns:
            List of matching audit entries
        """
        entries = self._audit_log

        if since:
            entries = [e for e in entries if e.timestamp >= since]

        if status_filter:
            entries = [e for e in entries if e.status == status_filter]

        # Return most recent entries first
        return sorted(entries, key=lambda e: e.timestamp, reverse=True)[:limit]

    def get_audit_summary(self) -> Dict[str, Any]:
        """Get a summary of the audit log.

        Returns:
            Dictionary with audit statistics
        """
        total = len(self._audit_log)
        by_status = {}
        by_risk = {}
        total_execution_time = 0.0

        for entry in self._audit_log:
            by_status[entry.status] = by_status.get(entry.status, 0) + 1
            by_risk[entry.risk_level.value] = by_risk.get(entry.risk_level.value, 0) + 1
            if entry.execution_time_ms:
                total_execution_time += entry.execution_time_ms

        return {
            "total_actions": total,
            "by_status": by_status,
            "by_risk_level": by_risk,
            "total_execution_time_ms": total_execution_time,
            "average_execution_time_ms": total_execution_time / total if total > 0 else 0,
            "pending_rollbacks": len(self._pending_rollbacks),
        }
