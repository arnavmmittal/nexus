"""Ultron's background monitoring system.

This module provides the UltronMonitor class which runs periodic checks,
monitors system health, tracks tasks, and identifies optimization opportunities.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Severity levels for monitoring alerts."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class TaskStatus(str, Enum):
    """Status of a monitored task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STALLED = "stalled"
    CANCELLED = "cancelled"


@dataclass
class HealthReport:
    """System health report."""

    timestamp: datetime = field(default_factory=datetime.utcnow)
    overall_status: str = "healthy"  # healthy, degraded, unhealthy
    checks: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "overall_status": self.overall_status,
            "checks": self.checks,
            "recommendations": self.recommendations,
        }


@dataclass
class MonitoredTask:
    """A task being monitored by Ultron."""

    id: str = field(default_factory=lambda: str(uuid4())[:12])
    name: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    progress: float = 0.0  # 0.0 to 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": self.progress,
            "metadata": self.metadata,
        }


@dataclass
class Alert:
    """A monitoring alert."""

    id: str = field(default_factory=lambda: str(uuid4())[:8])
    timestamp: datetime = field(default_factory=datetime.utcnow)
    severity: AlertSeverity = AlertSeverity.INFO
    title: str = ""
    message: str = ""
    source: str = ""  # What generated the alert
    acknowledged: bool = False
    resolved: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "source": self.source,
            "acknowledged": self.acknowledged,
            "resolved": self.resolved,
            "metadata": self.metadata,
        }


@dataclass
class OptimizationSuggestion:
    """A suggested optimization."""

    id: str = field(default_factory=lambda: str(uuid4())[:8])
    category: str = ""  # performance, resources, workflow, etc.
    title: str = ""
    description: str = ""
    estimated_impact: str = ""  # e.g., "20% faster", "saves 1GB"
    implementation_steps: List[str] = field(default_factory=list)
    priority: int = 5  # 1 = highest, 10 = lowest

    def to_dict(self) -> Dict[str, Any]:
        """Convert suggestion to dictionary."""
        return {
            "id": self.id,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "estimated_impact": self.estimated_impact,
            "implementation_steps": self.implementation_steps,
            "priority": self.priority,
        }


class UltronMonitor:
    """Background monitoring system for Ultron.

    The monitor runs periodic checks, tracks task status, identifies
    optimization opportunities, and alerts users to issues.

    Example usage:
        monitor = UltronMonitor()

        # Start monitoring
        await monitor.start_monitoring(interval_seconds=60)

        # Check health on demand
        health = await monitor.check_system_health()

        # Stop monitoring
        await monitor.stop_monitoring()
    """

    def __init__(
        self,
        on_alert: Optional[Callable[[Alert], None]] = None,
        stalled_task_threshold_seconds: float = 300.0,
    ):
        """Initialize the monitor.

        Args:
            on_alert: Optional callback for handling alerts
            stalled_task_threshold_seconds: Seconds without heartbeat before task is stalled
        """
        self.on_alert = on_alert
        self.stalled_task_threshold = timedelta(seconds=stalled_task_threshold_seconds)

        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._tasks: Dict[str, MonitoredTask] = {}
        self._alerts: List[Alert] = []
        self._health_checks: Dict[str, Callable[[], Dict[str, Any]]] = {}
        self._last_health_report: Optional[HealthReport] = None

        logger.info("UltronMonitor initialized")

    async def start_monitoring(self, interval_seconds: float = 60.0) -> None:
        """Start the background monitoring loop.

        Args:
            interval_seconds: Seconds between monitoring cycles
        """
        if self._running:
            logger.warning("Monitor is already running")
            return

        self._running = True
        self._monitor_task = asyncio.create_task(
            self._monitoring_loop(interval_seconds)
        )
        logger.info(f"Started monitoring with {interval_seconds}s interval")

    async def stop_monitoring(self) -> None:
        """Stop the background monitoring loop."""
        self._running = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None

        logger.info("Stopped monitoring")

    async def _monitoring_loop(self, interval: float) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                # Run all monitoring checks
                await self._run_monitoring_cycle()
            except Exception as e:
                logger.error(f"Monitoring cycle error: {e}")
                await self.alert_user(
                    Alert(
                        severity=AlertSeverity.ERROR,
                        title="Monitoring Error",
                        message=f"Error during monitoring cycle: {str(e)}",
                        source="UltronMonitor",
                    )
                )

            await asyncio.sleep(interval)

    async def _run_monitoring_cycle(self) -> None:
        """Run a single monitoring cycle."""
        # Check system health
        health = await self.check_system_health()

        # Check for stalled tasks
        await self._check_stalled_tasks()

        # Look for optimizations
        await self.check_for_optimizations()

        # Log cycle completion
        logger.debug(f"Monitoring cycle complete, health status: {health.overall_status}")

    async def check_system_health(self) -> HealthReport:
        """Run all health checks and generate a report.

        Returns:
            HealthReport with current system status
        """
        report = HealthReport()
        degraded_count = 0
        unhealthy_count = 0

        # Run registered health checks
        for check_name, check_func in self._health_checks.items():
            try:
                result = await asyncio.wait_for(
                    asyncio.coroutine(check_func)()
                    if not asyncio.iscoroutinefunction(check_func)
                    else check_func(),
                    timeout=10.0
                )
                report.checks[check_name] = result

                status = result.get("status", "unknown")
                if status == "degraded":
                    degraded_count += 1
                elif status in ("unhealthy", "error"):
                    unhealthy_count += 1

            except asyncio.TimeoutError:
                report.checks[check_name] = {
                    "status": "timeout",
                    "error": "Health check timed out",
                }
                unhealthy_count += 1
            except Exception as e:
                report.checks[check_name] = {
                    "status": "error",
                    "error": str(e),
                }
                unhealthy_count += 1

        # Add task health
        task_health = await self._get_task_health()
        report.checks["tasks"] = task_health

        # Determine overall status
        if unhealthy_count > 0:
            report.overall_status = "unhealthy"
        elif degraded_count > 0:
            report.overall_status = "degraded"
        else:
            report.overall_status = "healthy"

        # Generate recommendations
        report.recommendations = self._generate_recommendations(report)

        self._last_health_report = report
        return report

    async def _get_task_health(self) -> Dict[str, Any]:
        """Get health summary of monitored tasks."""
        total = len(self._tasks)
        by_status = {}

        for task in self._tasks.values():
            status = task.status.value
            by_status[status] = by_status.get(status, 0) + 1

        stalled = by_status.get(TaskStatus.STALLED.value, 0)
        failed = by_status.get(TaskStatus.FAILED.value, 0)

        if stalled > 0 or failed > 0:
            status = "degraded"
        else:
            status = "healthy"

        return {
            "status": status,
            "total_tasks": total,
            "by_status": by_status,
        }

    def _generate_recommendations(self, report: HealthReport) -> List[str]:
        """Generate recommendations based on health report."""
        recommendations = []

        for check_name, result in report.checks.items():
            status = result.get("status", "unknown")

            if status == "unhealthy":
                recommendations.append(f"Investigate {check_name}: {result.get('error', 'Unknown issue')}")
            elif status == "degraded":
                recommendations.append(f"Monitor {check_name} closely: performance may be impacted")
            elif status == "timeout":
                recommendations.append(f"Check {check_name}: health check is timing out")

        return recommendations

    async def _check_stalled_tasks(self) -> None:
        """Check for and alert on stalled tasks."""
        now = datetime.utcnow()

        for task in self._tasks.values():
            if task.status != TaskStatus.RUNNING:
                continue

            last_activity = task.last_heartbeat or task.started_at
            if not last_activity:
                continue

            if now - last_activity > self.stalled_task_threshold:
                task.status = TaskStatus.STALLED

                await self.alert_user(
                    Alert(
                        severity=AlertSeverity.WARNING,
                        title=f"Task Stalled: {task.name}",
                        message=(
                            f"Task '{task.name}' has not reported progress "
                            f"for {self.stalled_task_threshold.seconds} seconds"
                        ),
                        source="TaskMonitor",
                        metadata={"task_id": task.id},
                    )
                )

    async def check_pending_tasks(self) -> Dict[str, Any]:
        """Get status of all pending and running tasks.

        Returns:
            Dictionary with task status summary
        """
        pending = []
        running = []
        stalled = []

        for task in self._tasks.values():
            task_info = task.to_dict()

            if task.status == TaskStatus.PENDING:
                pending.append(task_info)
            elif task.status == TaskStatus.RUNNING:
                running.append(task_info)
            elif task.status == TaskStatus.STALLED:
                stalled.append(task_info)

        return {
            "pending": pending,
            "running": running,
            "stalled": stalled,
            "summary": {
                "pending_count": len(pending),
                "running_count": len(running),
                "stalled_count": len(stalled),
            },
        }

    async def check_for_optimizations(self) -> List[OptimizationSuggestion]:
        """Look for potential optimizations.

        Returns:
            List of optimization suggestions
        """
        suggestions = []

        # Check for task patterns that could be optimized
        completed_tasks = [t for t in self._tasks.values() if t.status == TaskStatus.COMPLETED]

        # Suggest batching if many similar tasks were run
        task_types: Dict[str, int] = {}
        for task in completed_tasks:
            task_type = task.metadata.get("type", "unknown")
            task_types[task_type] = task_types.get(task_type, 0) + 1

        for task_type, count in task_types.items():
            if count >= 5:
                suggestions.append(
                    OptimizationSuggestion(
                        category="workflow",
                        title=f"Batch {task_type} tasks",
                        description=f"Found {count} similar '{task_type}' tasks that could be batched",
                        estimated_impact=f"Could reduce overhead by ~{count * 10}%",
                        implementation_steps=[
                            f"Group {task_type} tasks together",
                            "Execute as a single batch operation",
                            "Monitor combined execution time",
                        ],
                        priority=3,
                    )
                )

        # Check for failed tasks that could be retried
        failed_tasks = [t for t in self._tasks.values() if t.status == TaskStatus.FAILED]
        if failed_tasks:
            suggestions.append(
                OptimizationSuggestion(
                    category="reliability",
                    title="Implement retry strategy",
                    description=f"{len(failed_tasks)} tasks failed without retry",
                    estimated_impact="Improved task success rate",
                    implementation_steps=[
                        "Add exponential backoff retry",
                        "Configure max retry attempts",
                        "Add failure notifications",
                    ],
                    priority=2,
                )
            )

        return suggestions

    async def alert_user(self, alert: Alert) -> None:
        """Send an alert to the user.

        Args:
            alert: The alert to send
        """
        self._alerts.append(alert)

        # Log the alert
        log_level = {
            AlertSeverity.INFO: logging.INFO,
            AlertSeverity.WARNING: logging.WARNING,
            AlertSeverity.ERROR: logging.ERROR,
            AlertSeverity.CRITICAL: logging.CRITICAL,
        }.get(alert.severity, logging.INFO)

        logger.log(log_level, f"[{alert.severity.value.upper()}] {alert.title}: {alert.message}")

        # Call user callback if registered
        if self.on_alert:
            try:
                if asyncio.iscoroutinefunction(self.on_alert):
                    await self.on_alert(alert)
                else:
                    self.on_alert(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")

    # Task management methods

    def register_task(
        self,
        name: str,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Register a new task for monitoring.

        Args:
            name: Task name
            description: Task description
            metadata: Optional metadata

        Returns:
            Task ID
        """
        task = MonitoredTask(
            name=name,
            description=description,
            metadata=metadata or {},
        )
        self._tasks[task.id] = task
        logger.debug(f"Registered task: {task.id} ({name})")
        return task.id

    def start_task(self, task_id: str) -> None:
        """Mark a task as started."""
        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.utcnow()
            task.last_heartbeat = datetime.utcnow()
            logger.debug(f"Started task: {task_id}")

    def update_task_progress(self, task_id: str, progress: float) -> None:
        """Update task progress and heartbeat.

        Args:
            task_id: Task ID
            progress: Progress value (0.0 to 1.0)
        """
        task = self._tasks.get(task_id)
        if task:
            task.progress = min(max(progress, 0.0), 1.0)
            task.last_heartbeat = datetime.utcnow()

    def complete_task(self, task_id: str, success: bool = True) -> None:
        """Mark a task as completed.

        Args:
            task_id: Task ID
            success: Whether the task succeeded
        """
        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
            task.completed_at = datetime.utcnow()
            task.progress = 1.0 if success else task.progress
            logger.debug(f"Completed task: {task_id} (success={success})")

    def cancel_task(self, task_id: str) -> None:
        """Mark a task as cancelled."""
        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.utcnow()
            logger.debug(f"Cancelled task: {task_id}")

    def get_task(self, task_id: str) -> Optional[MonitoredTask]:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    # Health check registration

    def register_health_check(
        self,
        name: str,
        check_func: Callable[[], Dict[str, Any]],
    ) -> None:
        """Register a health check function.

        Args:
            name: Name of the health check
            check_func: Function that returns health status dict
        """
        self._health_checks[name] = check_func
        logger.debug(f"Registered health check: {name}")

    def unregister_health_check(self, name: str) -> None:
        """Unregister a health check."""
        if name in self._health_checks:
            del self._health_checks[name]
            logger.debug(f"Unregistered health check: {name}")

    # Alert management

    def get_alerts(
        self,
        since: Optional[datetime] = None,
        severity: Optional[AlertSeverity] = None,
        unacknowledged_only: bool = False,
    ) -> List[Alert]:
        """Get alerts with optional filtering.

        Args:
            since: Only return alerts after this time
            severity: Filter by severity
            unacknowledged_only: Only return unacknowledged alerts

        Returns:
            List of matching alerts
        """
        alerts = self._alerts

        if since:
            alerts = [a for a in alerts if a.timestamp >= since]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        if unacknowledged_only:
            alerts = [a for a in alerts if not a.acknowledged]

        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert.

        Args:
            alert_id: ID of the alert to acknowledge

        Returns:
            True if alert was found and acknowledged
        """
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def resolve_alert(self, alert_id: str) -> bool:
        """Mark an alert as resolved.

        Args:
            alert_id: ID of the alert to resolve

        Returns:
            True if alert was found and resolved
        """
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.resolved = True
                return True
        return False

    @property
    def is_running(self) -> bool:
        """Whether the monitor is currently running."""
        return self._running

    @property
    def last_health_report(self) -> Optional[HealthReport]:
        """Get the most recent health report."""
        return self._last_health_report
