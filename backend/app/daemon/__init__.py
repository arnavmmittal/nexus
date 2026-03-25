"""Daemon Module - Always-on background systems.

This module contains the always-running services that make Nexus proactive:
- Background Monitor: Continuously scans email, jobs, calendar
- Auto-Apply Pipeline: Autonomous job application system
- Scheduled Tasks: Daily briefings, follow-ups, reminders

These systems run 24/7 and generate alerts that Jarvis/Ultron act on.
"""

from app.daemon.monitor import (
    BackgroundMonitor,
    Alert,
    AlertPriority,
    AlertCategory,
    MonitorTask,
    get_background_monitor,
    start_background_monitor,
    stop_background_monitor,
)

from app.daemon.auto_apply import (
    AutoApplyPipeline,
    JobOpportunity,
    ApplicationStatus,
    get_auto_apply_pipeline,
)

__all__ = [
    # Monitor
    "BackgroundMonitor",
    "Alert",
    "AlertPriority",
    "AlertCategory",
    "MonitorTask",
    "get_background_monitor",
    "start_background_monitor",
    "stop_background_monitor",
    # Auto-Apply
    "AutoApplyPipeline",
    "JobOpportunity",
    "ApplicationStatus",
    "get_auto_apply_pipeline",
]
