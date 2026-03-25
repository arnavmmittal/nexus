"""Background Monitor Daemon - The always-watching system.

This is Ultron's continuous monitoring system that runs 24/7:
- Scans email for important messages
- Monitors job boards for matching opportunities
- Tracks calendar for upcoming events
- Watches financial accounts
- Generates proactive alerts

This is what makes the difference between "a chatbot" and "Jarvis".
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


class AlertPriority(str, Enum):
    """Alert priority levels."""
    CRITICAL = "critical"   # Immediate attention needed
    HIGH = "high"           # Important, act today
    MEDIUM = "medium"       # Should review soon
    LOW = "low"             # FYI, when you have time
    INFO = "info"           # Background information


class AlertCategory(str, Enum):
    """Categories of alerts."""
    JOB_OPPORTUNITY = "job_opportunity"
    JOB_RESPONSE = "job_response"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    EMAIL_IMPORTANT = "email_important"
    CALENDAR_REMINDER = "calendar_reminder"
    CALENDAR_CONFLICT = "calendar_conflict"
    FINANCIAL_ALERT = "financial_alert"
    GITHUB_ACTIVITY = "github_activity"
    DEADLINE_APPROACHING = "deadline_approaching"
    DAILY_BRIEFING = "daily_briefing"
    PROACTIVE_SUGGESTION = "proactive_suggestion"
    INFO = "info"


@dataclass
class Alert:
    """A proactive alert from the monitoring system."""
    id: str = field(default_factory=lambda: str(uuid4())[:12])
    category: AlertCategory = AlertCategory.INFO
    priority: AlertPriority = AlertPriority.MEDIUM
    title: str = ""
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    action_required: bool = False
    suggested_actions: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    dismissed: bool = False
    acted_upon: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "priority": self.priority.value,
            "title": self.title,
            "message": self.message,
            "data": self.data,
            "action_required": self.action_required,
            "suggested_actions": self.suggested_actions,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "dismissed": self.dismissed,
            "acted_upon": self.acted_upon,
        }


@dataclass
class MonitorTask:
    """A background monitoring task."""
    name: str
    interval_seconds: int
    handler: Callable
    last_run: Optional[datetime] = None
    running: bool = False
    enabled: bool = True
    error_count: int = 0


class BackgroundMonitor:
    """The always-on monitoring system.

    Runs multiple monitoring tasks in parallel:
    - Email scanner (every 5 minutes)
    - Job board scanner (every 30 minutes)
    - Calendar monitor (every 15 minutes)
    - Daily briefing generator (once per day)

    Generates alerts that are surfaced to the user via Jarvis.
    """

    def __init__(self):
        self.alerts: List[Alert] = []
        self.tasks: Dict[str, MonitorTask] = {}
        self.running = False
        self._alert_callbacks: List[Callable[[Alert], None]] = []
        self._last_daily_briefing: Optional[datetime] = None

        # Register default monitoring tasks
        self._register_default_tasks()

    def _register_default_tasks(self):
        """Register the default monitoring tasks."""
        self.register_task(MonitorTask(
            name="email_scanner",
            interval_seconds=300,  # 5 minutes
            handler=self._scan_emails,
        ))

        self.register_task(MonitorTask(
            name="job_scanner",
            interval_seconds=1800,  # 30 minutes
            handler=self._scan_jobs,
        ))

        self.register_task(MonitorTask(
            name="calendar_monitor",
            interval_seconds=900,  # 15 minutes
            handler=self._check_calendar,
        ))

        self.register_task(MonitorTask(
            name="github_monitor",
            interval_seconds=3600,  # 1 hour
            handler=self._check_github,
        ))

        self.register_task(MonitorTask(
            name="daily_briefing",
            interval_seconds=86400,  # 24 hours
            handler=self._generate_daily_briefing,
        ))

    def register_task(self, task: MonitorTask):
        """Register a monitoring task."""
        self.tasks[task.name] = task
        logger.info(f"Registered monitoring task: {task.name} (every {task.interval_seconds}s)")

    def on_alert(self, callback: Callable[[Alert], None]):
        """Register a callback for new alerts."""
        self._alert_callbacks.append(callback)

    def _emit_alert(self, alert: Alert):
        """Emit an alert to all registered callbacks."""
        self.alerts.append(alert)
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

    async def start(self):
        """Start the background monitoring loop."""
        if self.running:
            logger.warning("Monitor already running")
            return

        self.running = True
        logger.info("Starting background monitor daemon...")

        # Start all tasks
        tasks = [
            self._run_task_loop(task)
            for task in self.tasks.values()
            if task.enabled
        ]

        await asyncio.gather(*tasks)

    async def stop(self):
        """Stop the background monitor."""
        self.running = False
        logger.info("Stopping background monitor daemon...")

    async def _run_task_loop(self, task: MonitorTask):
        """Run a single task in a loop."""
        while self.running:
            if not task.enabled:
                await asyncio.sleep(60)
                continue

            try:
                # Check if it's time to run
                if task.last_run is None or \
                   (datetime.utcnow() - task.last_run).seconds >= task.interval_seconds:

                    task.running = True
                    logger.debug(f"Running task: {task.name}")

                    await task.handler()

                    task.last_run = datetime.utcnow()
                    task.error_count = 0
                    task.running = False

            except Exception as e:
                logger.error(f"Task {task.name} failed: {e}")
                task.error_count += 1
                task.running = False

                # Disable task after 5 consecutive failures
                if task.error_count >= 5:
                    task.enabled = False
                    logger.warning(f"Task {task.name} disabled after 5 failures")

            await asyncio.sleep(60)  # Check every minute

    # ================== MONITORING HANDLERS ==================

    async def _scan_emails(self):
        """Scan for important emails."""
        from app.core.user_profile import get_user_profile

        profile = get_user_profile()
        logger.debug("Scanning emails...")

        try:
            from app.integrations.email_tools import search_emails
            import json

            # Search for job-related emails
            job_queries = [
                "interview",
                "application status",
                "offer letter",
                "next steps",
            ]

            for query in job_queries:
                result = await search_emails(query=query, limit=5)
                data = json.loads(result)

                for email in data.get("emails", []):
                    # Check if this is a new important email
                    email_date = email.get("date", "")
                    subject = email.get("subject", "").lower()

                    # Determine priority based on content
                    priority = AlertPriority.MEDIUM
                    category = AlertCategory.EMAIL_IMPORTANT

                    if "interview" in subject:
                        priority = AlertPriority.HIGH
                        category = AlertCategory.INTERVIEW_SCHEDULED
                    elif "offer" in subject:
                        priority = AlertPriority.CRITICAL
                        category = AlertCategory.JOB_RESPONSE
                    elif "rejected" in subject or "unfortunately" in subject:
                        priority = AlertPriority.MEDIUM
                        category = AlertCategory.JOB_RESPONSE

                    # Only alert for recent emails (last 24 hours)
                    # TODO: Implement proper date checking

                    alert = Alert(
                        category=category,
                        priority=priority,
                        title=f"New email: {email.get('subject', 'No subject')[:50]}",
                        message=email.get("snippet", "")[:200],
                        data={"email_id": email.get("id"), "from": email.get("from")},
                        action_required=priority in [AlertPriority.CRITICAL, AlertPriority.HIGH],
                        suggested_actions=["Read email", "Draft response"],
                    )
                    self._emit_alert(alert)

        except Exception as e:
            logger.warning(f"Email scanning failed: {e}")

    async def _scan_jobs(self):
        """Scan job boards for matching opportunities."""
        from app.core.user_profile import get_user_profile

        profile = get_user_profile()
        prefs = profile.job_preferences

        logger.debug("Scanning job boards...")

        try:
            from app.integrations.jobs import search_jobs
            import json

            # Search for each target role
            for role in prefs.target_roles[:3]:
                for location in prefs.locations[:2]:
                    result = await search_jobs(
                        query=role,
                        location=location,
                    )
                    data = json.loads(result)

                    for job in data.get("jobs", [])[:5]:
                        # Check if this matches preferences
                        salary = job.get("salary_min", 0)
                        if salary > 0 and salary < prefs.min_salary:
                            continue

                        company = job.get("company", "Unknown")
                        if company in prefs.excluded_companies:
                            continue

                        # Calculate match score
                        match_score = self._calculate_job_match(job, prefs)

                        if match_score >= 0.7:
                            alert = Alert(
                                category=AlertCategory.JOB_OPPORTUNITY,
                                priority=AlertPriority.HIGH if match_score >= 0.85 else AlertPriority.MEDIUM,
                                title=f"Job Match: {job.get('title', 'Unknown')} at {company}",
                                message=f"Match score: {match_score*100:.0f}%. {job.get('description', '')[:150]}...",
                                data={
                                    "job": job,
                                    "match_score": match_score,
                                    "url": job.get("url"),
                                },
                                action_required=match_score >= prefs.auto_apply_confidence_threshold,
                                suggested_actions=[
                                    "View job details",
                                    "Apply now" if match_score >= 0.85 else "Save for later",
                                    "Research company",
                                ],
                            )
                            self._emit_alert(alert)

        except Exception as e:
            logger.warning(f"Job scanning failed: {e}")

    def _calculate_job_match(self, job: Dict, prefs: 'JobPreferences') -> float:
        """Calculate how well a job matches user preferences."""
        score = 0.5  # Base score

        # Title match
        title = job.get("title", "").lower()
        for role in prefs.target_roles:
            if role.lower() in title:
                score += 0.2
                break

        # Company match
        company = job.get("company", "")
        if company in prefs.target_companies:
            score += 0.15
        elif company in prefs.excluded_companies:
            score -= 0.5

        # Salary match
        salary = job.get("salary_min", 0)
        if salary >= prefs.min_salary:
            score += 0.1
        elif salary > 0:
            score -= 0.1

        # Remote match
        remote = job.get("remote", False)
        if prefs.remote_preference == "remote" and remote:
            score += 0.1
        elif prefs.remote_preference == "onsite" and not remote:
            score += 0.1

        return min(1.0, max(0.0, score))

    async def _check_calendar(self):
        """Check calendar for upcoming events and conflicts."""
        logger.debug("Checking calendar...")

        try:
            # Get upcoming events for next 24 hours
            from app.integrations.google_calendar import get_google_calendar_integration

            calendar = await get_google_calendar_integration()
            if calendar:
                events = await calendar.get_upcoming_events(hours=24)

                for event in events:
                    start_time = event.get("start", {}).get("dateTime", "")
                    summary = event.get("summary", "Event")

                    # Alert for events starting within 1 hour
                    alert = Alert(
                        category=AlertCategory.CALENDAR_REMINDER,
                        priority=AlertPriority.HIGH,
                        title=f"Upcoming: {summary}",
                        message=f"Starts at {start_time}",
                        data={"event": event},
                        suggested_actions=["View event", "Join meeting", "Reschedule"],
                    )
                    self._emit_alert(alert)

        except Exception as e:
            logger.warning(f"Calendar check failed: {e}")

    async def _check_github(self):
        """Check GitHub for activity on repos."""
        logger.debug("Checking GitHub...")

        try:
            from app.integrations.github_tools import get_user_activity
            import json

            result = await get_user_activity()
            data = json.loads(result)

            for event in data.get("events", [])[:5]:
                event_type = event.get("type", "")
                repo = event.get("repo", {}).get("name", "")

                if event_type in ["PullRequestEvent", "IssueCommentEvent"]:
                    alert = Alert(
                        category=AlertCategory.GITHUB_ACTIVITY,
                        priority=AlertPriority.LOW,
                        title=f"GitHub: {event_type} on {repo}",
                        message=event.get("payload", {}).get("action", ""),
                        data={"event": event},
                    )
                    self._emit_alert(alert)

        except Exception as e:
            logger.warning(f"GitHub check failed: {e}")

    async def _generate_daily_briefing(self):
        """Generate the daily morning briefing."""
        from app.core.user_profile import get_user_profile

        profile = get_user_profile()

        # Only generate once per day
        now = datetime.utcnow()
        if self._last_daily_briefing and \
           (now - self._last_daily_briefing).days < 1:
            return

        logger.info("Generating daily briefing...")

        # Gather all relevant data
        briefing_data = {
            "date": now.strftime("%A, %B %d, %Y"),
            "pending_alerts": len([a for a in self.alerts if not a.dismissed]),
            "job_opportunities": len([a for a in self.alerts if a.category == AlertCategory.JOB_OPPORTUNITY]),
            "interviews_scheduled": 0,
            "tasks_due_today": 0,
            "calendar_events": [],
        }

        # Create briefing alert
        alert = Alert(
            category=AlertCategory.DAILY_BRIEFING,
            priority=AlertPriority.MEDIUM,
            title=f"Good morning, {profile.name}! Here's your briefing",
            message=self._format_briefing(briefing_data),
            data=briefing_data,
            action_required=briefing_data["job_opportunities"] > 0,
            suggested_actions=[
                "Review job opportunities" if briefing_data["job_opportunities"] > 0 else "Search for jobs",
                "Check calendar",
                "Review pending tasks",
            ],
        )
        self._emit_alert(alert)
        self._last_daily_briefing = now

    def _format_briefing(self, data: Dict) -> str:
        """Format the daily briefing message."""
        lines = [
            f"📅 {data['date']}",
            "",
            f"📬 {data['pending_alerts']} pending alerts",
            f"💼 {data['job_opportunities']} new job opportunities",
        ]

        if data["interviews_scheduled"]:
            lines.append(f"🎯 {data['interviews_scheduled']} interviews scheduled")

        if data["tasks_due_today"]:
            lines.append(f"✅ {data['tasks_due_today']} tasks due today")

        return "\n".join(lines)

    # ================== ALERT MANAGEMENT ==================

    def get_pending_alerts(self, limit: int = 20) -> List[Alert]:
        """Get pending (undismissed) alerts."""
        return [
            a for a in self.alerts
            if not a.dismissed
        ][:limit]

    def get_alerts_by_priority(self, priority: AlertPriority) -> List[Alert]:
        """Get alerts by priority level."""
        return [a for a in self.alerts if a.priority == priority]

    def dismiss_alert(self, alert_id: str):
        """Dismiss an alert."""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.dismissed = True
                return

    def mark_acted_upon(self, alert_id: str):
        """Mark an alert as acted upon."""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.acted_upon = True
                return


# Global monitor instance
_monitor: Optional[BackgroundMonitor] = None


def get_background_monitor() -> BackgroundMonitor:
    """Get the global background monitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = BackgroundMonitor()
    return _monitor


async def start_background_monitor():
    """Start the global background monitor."""
    monitor = get_background_monitor()
    await monitor.start()


async def stop_background_monitor():
    """Stop the global background monitor."""
    global _monitor
    if _monitor:
        await _monitor.stop()
