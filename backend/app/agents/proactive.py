"""Proactive Agent Behaviors - AI that takes initiative.

This module implements behaviors that make the AI feel truly intelligent:
- Suggests improvements without being asked
- Anticipates needs based on patterns
- Takes preemptive actions within autonomy boundaries
- Generates insights from accumulated data

"I took the liberty of..." - This is what separates a good AI from a great one.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class ProactiveSuggestion:
    """A proactive suggestion from the AI."""
    id: str = field(default_factory=lambda: str(uuid4())[:12])
    type: str = ""  # job_insight, schedule_optimization, skill_suggestion, etc.
    title: str = ""
    description: str = ""
    reasoning: str = ""  # Why we're suggesting this
    confidence: float = 0.0  # How confident we are this is useful
    priority: int = 5  # 1-10, 10 being highest
    data: Dict[str, Any] = field(default_factory=dict)
    actions: List[str] = field(default_factory=list)  # Suggested actions
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    expires_at: Optional[str] = None
    dismissed: bool = False
    acted_upon: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "description": self.description,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "priority": self.priority,
            "data": self.data,
            "actions": self.actions,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "dismissed": self.dismissed,
            "acted_upon": self.acted_upon,
        }


class ProactiveEngine:
    """Engine for generating proactive suggestions and insights.

    Analyzes patterns, opportunities, and context to suggest
    helpful actions before the user asks.

    MOVIE-LEVEL ENHANCEMENT:
    - Auto-executes low-risk suggestions without asking
    - Learns from user responses to improve future actions
    - "I took the liberty of..." is the goal
    """

    # Actions that can be auto-executed without confirmation
    AUTO_EXECUTABLE_TYPES = {
        "pattern_observation",  # Just informational
        "follow_up_reminder",  # Drafting email is safe
    }

    # Threshold for auto-execution
    AUTO_EXECUTE_CONFIDENCE = 0.85
    AUTO_EXECUTE_PRIORITY = 3  # Only low-priority or below

    def __init__(self):
        self.suggestions: List[ProactiveSuggestion] = []
        self._generators: Dict[str, Callable] = {}
        self._last_run: Dict[str, datetime] = {}
        self._running = False
        self._auto_executed: List[str] = []  # Track auto-executed suggestion IDs

        # Register default generators
        self._register_default_generators()

    def _register_default_generators(self):
        """Register the default proactive suggestion generators."""
        self._generators["job_insights"] = self._generate_job_insights
        self._generators["schedule_optimization"] = self._generate_schedule_suggestions
        self._generators["skill_development"] = self._generate_skill_suggestions
        self._generators["follow_up_reminders"] = self._generate_follow_up_reminders
        self._generators["pattern_observations"] = self._generate_pattern_insights
        self._generators["anticipation"] = self._generate_anticipation_suggestions

    async def start(self, interval_minutes: int = 30):
        """Start the proactive engine."""
        self._running = True
        logger.info("Proactive engine starting...")

        while self._running:
            try:
                await self._run_all_generators()
            except Exception as e:
                logger.error(f"Proactive engine error: {e}")

            await asyncio.sleep(interval_minutes * 60)

    async def stop(self):
        """Stop the proactive engine."""
        self._running = False
        logger.info("Proactive engine stopped")

    async def _run_all_generators(self):
        """Run all registered suggestion generators."""
        for name, generator in self._generators.items():
            try:
                # Rate limit: don't run more than once per hour
                last_run = self._last_run.get(name)
                if last_run and (datetime.utcnow() - last_run).seconds < 3600:
                    continue

                suggestions = await generator()
                for suggestion in suggestions:
                    self._add_suggestion(suggestion)

                    # AUTO-EXECUTE low-risk suggestions (movie-level behavior)
                    if await self._should_auto_execute(suggestion):
                        await self._auto_execute_suggestion(suggestion)

                self._last_run[name] = datetime.utcnow()

            except Exception as e:
                logger.warning(f"Generator {name} failed: {e}")

    async def _should_auto_execute(self, suggestion: ProactiveSuggestion) -> bool:
        """Determine if a suggestion should be auto-executed.

        Only execute if:
        - Type is in AUTO_EXECUTABLE_TYPES
        - Confidence is high enough
        - Priority is low enough (not important enough to ask)
        - User has autonomy enabled
        """
        if suggestion.type not in self.AUTO_EXECUTABLE_TYPES:
            return False

        if suggestion.confidence < self.AUTO_EXECUTE_CONFIDENCE:
            return False

        if suggestion.priority > self.AUTO_EXECUTE_PRIORITY:
            return False  # Too important - should ask

        # Check user autonomy settings
        try:
            from app.core.user_profile import get_user_profile
            profile = get_user_profile()
            if not profile.autonomy.background_monitoring_enabled:
                return False
        except ImportError:
            return False

        return True

    async def _auto_execute_suggestion(self, suggestion: ProactiveSuggestion):
        """Auto-execute a suggestion without user confirmation.

        This is the "I took the liberty of..." moment.
        """
        try:
            logger.info(f"Auto-executing suggestion: {suggestion.title}")

            # For now, mark as acted upon and notify
            suggestion.acted_upon = True
            self._auto_executed.append(suggestion.id)

            # Send notification about what was done
            try:
                from app.notifications import notify, NotificationPriority

                await notify(
                    title="I took the liberty of...",
                    body=suggestion.title,
                    priority=NotificationPriority.LOW,
                    icon="🤖",
                    data={
                        "suggestion_id": suggestion.id,
                        "type": suggestion.type,
                        "reasoning": suggestion.reasoning,
                    },
                )
            except ImportError:
                pass

            logger.info(f"Auto-executed: {suggestion.title}")

        except Exception as e:
            logger.error(f"Failed to auto-execute suggestion: {e}")

    def _add_suggestion(self, suggestion: ProactiveSuggestion):
        """Add a suggestion if it's not a duplicate."""
        # Check for duplicates (same type and similar title)
        for existing in self.suggestions:
            if existing.type == suggestion.type and existing.title == suggestion.title:
                if not existing.dismissed:
                    return  # Already have this suggestion

        self.suggestions.append(suggestion)

        # Trim old suggestions
        if len(self.suggestions) > 100:
            # Keep non-dismissed, sort by priority and recency
            self.suggestions = sorted(
                [s for s in self.suggestions if not s.dismissed],
                key=lambda s: (s.priority, s.created_at),
                reverse=True
            )[:50]

        logger.info(f"New proactive suggestion: {suggestion.title}")

    async def _generate_job_insights(self) -> List[ProactiveSuggestion]:
        """Generate insights about job search patterns and opportunities."""
        suggestions = []

        try:
            from app.daemon import get_auto_apply_pipeline
            from app.core.user_profile import get_user_profile

            profile = get_user_profile()
            pipeline = get_auto_apply_pipeline()

            # Check pending approvals
            pending = pipeline.get_pending_approvals()
            if len(pending) >= 3:
                suggestions.append(ProactiveSuggestion(
                    type="job_insight",
                    title=f"You have {len(pending)} job applications ready for review",
                    description=f"I've found {len(pending)} positions that match your criteria. "
                    f"Would you like me to walk you through them?",
                    reasoning="Multiple high-match opportunities identified - timely review increases chances.",
                    confidence=0.9,
                    priority=8,
                    data={"pending_count": len(pending)},
                    actions=["Review applications", "Auto-approve all above 90% match", "Dismiss"],
                ))

            # Check application patterns
            stats = pipeline.get_statistics()
            if stats.get("daily_applications", 0) == 0 and profile.autonomy.auto_apply_jobs_enabled:
                suggestions.append(ProactiveSuggestion(
                    type="job_insight",
                    title="No applications sent today",
                    description="Auto-apply is enabled but no applications have been sent. "
                    "Should I check the job queue?",
                    reasoning="Consistent application activity improves job search outcomes.",
                    confidence=0.7,
                    priority=5,
                    actions=["Check job queue", "Lower match threshold", "Dismiss"],
                ))

        except ImportError:
            pass

        return suggestions

    async def _generate_schedule_suggestions(self) -> List[ProactiveSuggestion]:
        """Generate suggestions for schedule optimization."""
        suggestions = []

        try:
            # Check for interview prep opportunities
            from app.daemon import get_background_monitor

            monitor = get_background_monitor()
            alerts = monitor.get_pending_alerts()

            interview_alerts = [a for a in alerts if "interview" in a.title.lower()]
            if interview_alerts:
                suggestions.append(ProactiveSuggestion(
                    type="schedule_optimization",
                    title="Interview coming up - preparation reminder",
                    description=f"You have {len(interview_alerts)} interview-related items. "
                    "Would you like me to help prepare?",
                    reasoning="Interview preparation significantly improves outcomes.",
                    confidence=0.85,
                    priority=9,
                    actions=["Research company", "Prepare questions", "Review job description"],
                ))

        except ImportError:
            pass

        return suggestions

    async def _generate_skill_suggestions(self) -> List[ProactiveSuggestion]:
        """Generate suggestions for skill development."""
        suggestions = []

        try:
            from app.ai.learning import get_learning_engine, LearningCategory

            engine = get_learning_engine()
            job_learnings = engine.recall(LearningCategory.JOB_PREFERENCES)

            # Analyze rejections to suggest skill improvements
            rejections = [l for l in job_learnings if "rejected" in l.key.lower()]
            if len(rejections) >= 3:
                # Look for patterns in rejections
                suggestions.append(ProactiveSuggestion(
                    type="skill_development",
                    title="Pattern detected in job rejections",
                    description="I've noticed some patterns in jobs you've declined. "
                    "Would you like me to analyze and suggest adjustments?",
                    reasoning="Understanding rejection patterns helps refine job search strategy.",
                    confidence=0.75,
                    priority=6,
                    data={"rejection_count": len(rejections)},
                    actions=["Analyze patterns", "Adjust preferences", "Dismiss"],
                ))

        except ImportError:
            pass

        return suggestions

    async def _generate_follow_up_reminders(self) -> List[ProactiveSuggestion]:
        """Generate reminders for pending follow-ups."""
        suggestions = []

        try:
            from app.daemon import get_auto_apply_pipeline
            from app.daemon.auto_apply import ApplicationStatus

            pipeline = get_auto_apply_pipeline()

            # Check for applications needing follow-up
            submitted_apps = [
                j for j in pipeline.opportunities.values()
                if j.status == ApplicationStatus.SUBMITTED
                and j.follow_up_date
            ]

            overdue_followups = []
            now = datetime.utcnow()
            for app in submitted_apps:
                follow_up = datetime.fromisoformat(app.follow_up_date)
                if now >= follow_up:
                    overdue_followups.append(app)

            if overdue_followups:
                companies = [a.company for a in overdue_followups[:3]]
                suggestions.append(ProactiveSuggestion(
                    type="follow_up_reminder",
                    title=f"{len(overdue_followups)} applications ready for follow-up",
                    description=f"It's been a week since applying to {', '.join(companies)}. "
                    "Follow-up emails can increase response rates by 40%.",
                    reasoning="Timely follow-ups demonstrate genuine interest and increase response rates.",
                    confidence=0.85,
                    priority=7,
                    data={"companies": companies},
                    actions=["Draft follow-up emails", "Mark as no response", "Snooze 3 days"],
                ))

        except ImportError:
            pass

        return suggestions

    async def _generate_anticipation_suggestions(self) -> List[ProactiveSuggestion]:
        """Generate anticipation-based suggestions.

        This is what makes the AI feel psychic - knowing what you need before you ask.
        "Sir, you have a meeting in 30 minutes. Shall I prepare the briefing?"
        """
        suggestions = []

        try:
            # Check for upcoming calendar events
            from app.daemon import get_background_monitor

            monitor = get_background_monitor()
            alerts = monitor.get_pending_alerts()

            # Look for meetings/interviews coming up
            now = datetime.utcnow()
            for alert in alerts:
                if "interview" in alert.title.lower() or "meeting" in alert.title.lower():
                    # Check if it's coming up soon (within 2 hours)
                    event_time = alert.data.get("start_time")
                    if event_time:
                        try:
                            event_dt = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
                            time_until = (event_dt - now).total_seconds() / 60  # minutes

                            if 30 <= time_until <= 120:  # 30 min to 2 hours
                                company = alert.data.get("company", "")
                                suggestions.append(ProactiveSuggestion(
                                    type="anticipation",
                                    title=f"Upcoming: {alert.title}",
                                    description=f"You have {int(time_until)} minutes until your {alert.title}. "
                                    f"Would you like me to prepare a briefing?",
                                    reasoning="Preparation before meetings improves performance and reduces anxiety.",
                                    confidence=0.9,
                                    priority=9,  # High priority but not auto-execute
                                    data={
                                        "event": alert.data,
                                        "time_until_minutes": int(time_until),
                                    },
                                    actions=[
                                        "Prepare briefing",
                                        f"Research {company}" if company else "Research company",
                                        "Review notes",
                                        "Dismiss",
                                    ],
                                ))
                        except (ValueError, TypeError):
                            pass

        except ImportError:
            pass

        # Check for goal deadlines approaching
        try:
            from sqlalchemy import select
            from app.models.goal import Goal
            from app.core.database import get_db_session

            # This would need proper async context - simplified for now
            deadline_approaching = []
            # TODO: Actually query goals with approaching deadlines

            if deadline_approaching:
                suggestions.append(ProactiveSuggestion(
                    type="anticipation",
                    title="Goal deadline approaching",
                    description="Some of your goals have deadlines coming up. Would you like a progress check?",
                    reasoning="Awareness of deadlines helps prioritize efforts.",
                    confidence=0.8,
                    priority=6,
                    actions=["Show goals", "Create action plan", "Dismiss"],
                ))

        except Exception:
            pass

        return suggestions

    async def _generate_pattern_insights(self) -> List[ProactiveSuggestion]:
        """Generate insights from observed patterns."""
        suggestions = []

        try:
            from app.ai.learning import get_learning_engine

            engine = get_learning_engine()
            stats = engine.get_statistics()

            # If we've learned a lot, share that
            if stats.get("total_entries", 0) >= 20:
                high_conf = stats.get("high_confidence_count", 0)
                if high_conf >= 5:
                    suggestions.append(ProactiveSuggestion(
                        type="pattern_observation",
                        title="I've learned a lot about your preferences",
                        description=f"I now have {high_conf} high-confidence learnings about "
                        "how you like things done. My suggestions should be more accurate now.",
                        reasoning="Transparency about AI learning builds trust.",
                        confidence=0.95,
                        priority=3,
                        data=stats,
                        actions=["View learned preferences", "Clear learnings", "Dismiss"],
                    ))

        except ImportError:
            pass

        return suggestions

    def get_active_suggestions(
        self,
        limit: int = 10,
        min_confidence: float = 0.5,
    ) -> List[ProactiveSuggestion]:
        """Get active (non-dismissed) suggestions."""
        active = [
            s for s in self.suggestions
            if not s.dismissed and s.confidence >= min_confidence
        ]

        # Sort by priority and confidence
        active.sort(key=lambda s: (s.priority, s.confidence), reverse=True)

        return active[:limit]

    def dismiss_suggestion(self, suggestion_id: str):
        """Dismiss a suggestion."""
        for s in self.suggestions:
            if s.id == suggestion_id:
                s.dismissed = True
                return

    def act_on_suggestion(self, suggestion_id: str):
        """Mark a suggestion as acted upon."""
        for s in self.suggestions:
            if s.id == suggestion_id:
                s.acted_upon = True
                return

    def get_auto_executed_suggestions(self) -> List[ProactiveSuggestion]:
        """Get suggestions that were auto-executed.

        This lets users see what the AI did autonomously - transparency is key.
        """
        return [
            s for s in self.suggestions
            if s.id in self._auto_executed
        ]

    def get_anticipation_suggestions(self) -> List[ProactiveSuggestion]:
        """Get time-sensitive anticipation suggestions.

        These are the "You have a meeting in 30 min" type suggestions.
        """
        return [
            s for s in self.suggestions
            if s.type == "anticipation" and not s.dismissed
        ]


# Global proactive engine
_proactive_engine: Optional[ProactiveEngine] = None


def get_proactive_engine() -> ProactiveEngine:
    """Get the global proactive engine."""
    global _proactive_engine
    if _proactive_engine is None:
        _proactive_engine = ProactiveEngine()
    return _proactive_engine


async def start_proactive_engine():
    """Start the global proactive engine."""
    engine = get_proactive_engine()
    await engine.start()


async def stop_proactive_engine():
    """Stop the global proactive engine."""
    global _proactive_engine
    if _proactive_engine:
        await _proactive_engine.stop()
