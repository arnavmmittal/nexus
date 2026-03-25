"""Predictive Alerts System - Anticipating user needs before they ask.

This module enables Jarvis/Ultron-style proactive intelligence by:
- Detecting calendar conflicts and scheduling issues
- Predicting deadline risks for goals and tasks
- Identifying unusual behavior patterns
- Surfacing time-sensitive opportunities
- Generating health/wellness reminders
- Alerting about travel changes
- Prompting for communication follow-ups
- Warning about resource depletion

The goal: Be one step ahead of the user at all times.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, date
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple
from uuid import UUID, uuid4
from collections import defaultdict
import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ============ PREDICTION TYPES ============

class PredictionType(str, Enum):
    """Types of predictive alerts the system can generate."""

    CALENDAR_CONFLICT = "calendar_conflict"       # Overlapping events detected
    DEADLINE_APPROACHING = "deadline_approaching" # Task/goal deadline soon
    PATTERN_BREAK = "pattern_break"               # Unusual behavior detected
    OPPORTUNITY = "opportunity"                   # Time-sensitive opportunity
    HEALTH_REMINDER = "health_reminder"           # Based on patterns (breaks, hydration, sleep)
    TRAVEL_ALERT = "travel_alert"                 # Weather, traffic, flight changes
    COMMUNICATION_NEEDED = "communication_needed" # Follow-up reminders
    RESOURCE_LOW = "resource_low"                 # Budget, storage, etc. running low
    MEETING_PREP = "meeting_prep"                 # Upcoming meeting preparation
    GOAL_AT_RISK = "goal_at_risk"                 # Goal completion unlikely at current pace
    HABIT_REMINDER = "habit_reminder"             # Streak about to break
    FINANCIAL_ALERT = "financial_alert"           # Budget threshold, unusual spending
    WORKFLOW_OPTIMIZATION = "workflow_optimization"  # Detected inefficiency


class PredictionUrgency(str, Enum):
    """Urgency levels for predictions."""

    LOW = "low"           # Informational, can be addressed later
    MEDIUM = "medium"     # Should be addressed soon
    HIGH = "high"         # Needs attention within hours
    CRITICAL = "critical" # Immediate action required


class PredictionStatus(str, Enum):
    """Status of a prediction."""

    ACTIVE = "active"     # Prediction is current and relevant
    DISMISSED = "dismissed"  # User dismissed this prediction
    ACTED_ON = "acted_on"    # User took action on this prediction
    EXPIRED = "expired"      # Prediction is no longer relevant
    AUTO_RESOLVED = "auto_resolved"  # Situation resolved itself


# ============ PREDICTION DATA CLASSES ============

@dataclass
class SuggestedAction:
    """An action that can be taken on a prediction."""

    action_id: str = field(default_factory=lambda: str(uuid4())[:8])
    action_type: str = ""       # e.g., "reschedule", "send_message", "adjust_budget"
    title: str = ""             # Human-readable action name
    description: str = ""       # Detailed description
    params: Dict[str, Any] = field(default_factory=dict)  # Parameters for execution
    confidence: float = 0.8     # How confident the AI is this is the right action
    is_reversible: bool = True  # Can this action be undone?
    requires_confirmation: bool = True  # Should we ask before acting?

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Prediction:
    """A single predictive alert."""

    # Core identification
    prediction_id: str = field(default_factory=lambda: str(uuid4())[:12])
    type: PredictionType = PredictionType.PATTERN_BREAK

    # Content
    title: str = ""              # Brief headline
    description: str = ""        # Detailed explanation
    reasoning: str = ""          # Why this prediction was made

    # Confidence and priority
    confidence_score: float = 0.5  # 0.0 to 1.0
    urgency: PredictionUrgency = PredictionUrgency.MEDIUM

    # Suggested action
    suggested_action: Optional[SuggestedAction] = None
    alternative_actions: List[SuggestedAction] = field(default_factory=list)

    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    relevant_time: Optional[datetime] = None  # When is this prediction most relevant

    # Status tracking
    status: PredictionStatus = PredictionStatus.ACTIVE
    dismissed: bool = False
    dismissed_at: Optional[datetime] = None
    acted_on: bool = False
    acted_on_at: Optional[datetime] = None
    action_result: Optional[Dict[str, Any]] = None

    # Learning
    user_feedback: Optional[str] = None  # Was this helpful?
    feedback_score: Optional[float] = None  # -1 to 1

    # Metadata
    source_data: Dict[str, Any] = field(default_factory=dict)  # Data used to generate
    related_entities: List[str] = field(default_factory=list)  # IDs of related items
    tags: List[str] = field(default_factory=list)

    def is_active(self) -> bool:
        """Check if prediction is still active and relevant."""
        if self.dismissed or self.acted_on:
            return False
        if self.status != PredictionStatus.ACTIVE:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True

    def get_priority_score(self) -> float:
        """Calculate priority score for sorting predictions."""
        urgency_weights = {
            PredictionUrgency.CRITICAL: 1.0,
            PredictionUrgency.HIGH: 0.75,
            PredictionUrgency.MEDIUM: 0.5,
            PredictionUrgency.LOW: 0.25,
        }
        urgency_score = urgency_weights.get(self.urgency, 0.5)

        # Factor in confidence
        priority = urgency_score * 0.6 + self.confidence_score * 0.4

        # Boost if expires soon
        if self.expires_at:
            time_remaining = (self.expires_at - datetime.utcnow()).total_seconds()
            if time_remaining < 3600:  # Less than 1 hour
                priority *= 1.3
            elif time_remaining < 86400:  # Less than 1 day
                priority *= 1.1

        return min(priority, 1.0)

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "prediction_id": self.prediction_id,
            "type": self.type.value,
            "title": self.title,
            "description": self.description,
            "reasoning": self.reasoning,
            "confidence_score": self.confidence_score,
            "urgency": self.urgency.value,
            "suggested_action": self.suggested_action.to_dict() if self.suggested_action else None,
            "alternative_actions": [a.to_dict() for a in self.alternative_actions],
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "relevant_time": self.relevant_time.isoformat() if self.relevant_time else None,
            "status": self.status.value,
            "dismissed": self.dismissed,
            "acted_on": self.acted_on,
            "priority_score": self.get_priority_score(),
            "source_data": self.source_data,
            "related_entities": self.related_entities,
            "tags": self.tags,
        }
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Prediction":
        """Create prediction from dictionary."""
        # Convert enums
        if "type" in data and isinstance(data["type"], str):
            data["type"] = PredictionType(data["type"])
        if "urgency" in data and isinstance(data["urgency"], str):
            data["urgency"] = PredictionUrgency(data["urgency"])
        if "status" in data and isinstance(data["status"], str):
            data["status"] = PredictionStatus(data["status"])

        # Convert datetime strings
        for field_name in ["created_at", "expires_at", "relevant_time", "dismissed_at", "acted_on_at"]:
            if field_name in data and isinstance(data[field_name], str):
                data[field_name] = datetime.fromisoformat(data[field_name])

        # Convert suggested action
        if "suggested_action" in data and isinstance(data["suggested_action"], dict):
            data["suggested_action"] = SuggestedAction(**data["suggested_action"])

        # Convert alternative actions
        if "alternative_actions" in data:
            data["alternative_actions"] = [
                SuggestedAction(**a) if isinstance(a, dict) else a
                for a in data["alternative_actions"]
            ]

        return cls(**data)


# ============ PATTERN ANALYZERS ============

class BaseAnalyzer:
    """Base class for pattern analyzers."""

    def __init__(self, db: Optional[AsyncSession] = None, user_id: Optional[UUID] = None):
        self.db = db
        self.user_id = user_id

    async def analyze(self, context: Dict[str, Any]) -> List[Prediction]:
        """Analyze patterns and generate predictions."""
        raise NotImplementedError


class CalendarAnalyzer(BaseAnalyzer):
    """Detects scheduling conflicts, meeting prep needs, and time allocation issues."""

    async def analyze(self, context: Dict[str, Any]) -> List[Prediction]:
        predictions = []

        events = context.get("calendar_events", [])
        if not events:
            return predictions

        # Check for conflicts (overlapping events)
        conflicts = self._detect_conflicts(events)
        for conflict in conflicts:
            predictions.append(self._create_conflict_prediction(conflict))

        # Check for meeting prep needs
        upcoming_meetings = self._get_upcoming_meetings(events, hours=24)
        for meeting in upcoming_meetings:
            if self._needs_prep(meeting):
                predictions.append(self._create_prep_prediction(meeting))

        # Check for back-to-back meetings without breaks
        back_to_back = self._detect_back_to_back(events)
        for sequence in back_to_back:
            predictions.append(self._create_break_needed_prediction(sequence))

        return predictions

    def _detect_conflicts(self, events: List[Dict]) -> List[Tuple[Dict, Dict]]:
        """Detect overlapping calendar events."""
        conflicts = []
        sorted_events = sorted(events, key=lambda e: e.get("start", ""))

        for i, event1 in enumerate(sorted_events):
            for event2 in sorted_events[i+1:]:
                start1 = self._parse_datetime(event1.get("start"))
                end1 = self._parse_datetime(event1.get("end"))
                start2 = self._parse_datetime(event2.get("start"))
                end2 = self._parse_datetime(event2.get("end"))

                if start1 and end1 and start2 and end2:
                    if start1 < end2 and start2 < end1:
                        conflicts.append((event1, event2))

        return conflicts

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string."""
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    def _get_upcoming_meetings(self, events: List[Dict], hours: int = 24) -> List[Dict]:
        """Get meetings happening within the specified hours."""
        now = datetime.utcnow()
        cutoff = now + timedelta(hours=hours)

        upcoming = []
        for event in events:
            start = self._parse_datetime(event.get("start"))
            if start and now < start < cutoff:
                if event.get("attendees") or "meeting" in event.get("summary", "").lower():
                    upcoming.append(event)

        return upcoming

    def _needs_prep(self, meeting: Dict) -> bool:
        """Check if a meeting likely needs preparation."""
        summary = (meeting.get("summary") or "").lower()
        description = (meeting.get("description") or "").lower()

        prep_keywords = ["review", "presentation", "demo", "interview", "important", "1:1", "standup"]
        return any(kw in summary or kw in description for kw in prep_keywords)

    def _detect_back_to_back(self, events: List[Dict]) -> List[List[Dict]]:
        """Detect sequences of back-to-back meetings."""
        sorted_events = sorted(events, key=lambda e: e.get("start", ""))
        sequences = []
        current_sequence = []

        for event in sorted_events:
            if not current_sequence:
                current_sequence = [event]
                continue

            last_end = self._parse_datetime(current_sequence[-1].get("end"))
            current_start = self._parse_datetime(event.get("start"))

            if last_end and current_start:
                gap = (current_start - last_end).total_seconds() / 60
                if gap < 15:  # Less than 15 minutes between meetings
                    current_sequence.append(event)
                else:
                    if len(current_sequence) >= 3:
                        sequences.append(current_sequence)
                    current_sequence = [event]

        if len(current_sequence) >= 3:
            sequences.append(current_sequence)

        return sequences

    def _create_conflict_prediction(self, conflict: Tuple[Dict, Dict]) -> Prediction:
        """Create prediction for a calendar conflict."""
        event1, event2 = conflict
        return Prediction(
            type=PredictionType.CALENDAR_CONFLICT,
            title=f"Calendar Conflict: {event1.get('summary', 'Event')} overlaps with {event2.get('summary', 'Event')}",
            description=(
                f"You have overlapping commitments: '{event1.get('summary')}' "
                f"and '{event2.get('summary')}'. One of these will need to be rescheduled."
            ),
            reasoning="Detected overlapping time slots in your calendar.",
            confidence_score=0.95,
            urgency=PredictionUrgency.HIGH,
            suggested_action=SuggestedAction(
                action_type="reschedule_event",
                title="Reschedule one event",
                description="Move one of the conflicting events to a different time.",
                params={"event1_id": event1.get("id"), "event2_id": event2.get("id")},
                requires_confirmation=True,
            ),
            expires_at=self._parse_datetime(event1.get("start")),
            relevant_time=self._parse_datetime(event1.get("start")),
            source_data={"events": [event1, event2]},
            tags=["calendar", "conflict", "scheduling"],
        )

    def _create_prep_prediction(self, meeting: Dict) -> Prediction:
        """Create prediction for meeting prep needed."""
        start = self._parse_datetime(meeting.get("start"))
        prep_time = start - timedelta(hours=1) if start else None

        return Prediction(
            type=PredictionType.MEETING_PREP,
            title=f"Meeting Prep: {meeting.get('summary', 'Upcoming Meeting')}",
            description=(
                f"You have '{meeting.get('summary')}' coming up. "
                f"Consider reviewing relevant materials and preparing talking points."
            ),
            reasoning="This meeting type typically requires preparation.",
            confidence_score=0.75,
            urgency=PredictionUrgency.MEDIUM,
            suggested_action=SuggestedAction(
                action_type="block_prep_time",
                title="Block preparation time",
                description="Add a 30-minute block before the meeting for prep.",
                params={"meeting_id": meeting.get("id"), "prep_duration_minutes": 30},
                requires_confirmation=True,
            ),
            expires_at=start,
            relevant_time=prep_time,
            source_data={"meeting": meeting},
            tags=["calendar", "meeting", "preparation"],
        )

    def _create_break_needed_prediction(self, sequence: List[Dict]) -> Prediction:
        """Create prediction for needing a break between meetings."""
        first_start = self._parse_datetime(sequence[0].get("start"))
        last_end = self._parse_datetime(sequence[-1].get("end"))

        return Prediction(
            type=PredictionType.HEALTH_REMINDER,
            title=f"Break Needed: {len(sequence)} back-to-back meetings",
            description=(
                f"You have {len(sequence)} meetings with minimal breaks. "
                "Consider building in a 10-15 minute buffer between meetings."
            ),
            reasoning="Extended back-to-back meetings can reduce focus and productivity.",
            confidence_score=0.8,
            urgency=PredictionUrgency.LOW,
            suggested_action=SuggestedAction(
                action_type="add_buffer",
                title="Add meeting buffers",
                description="Shorten meetings by 5 minutes to create natural breaks.",
                requires_confirmation=True,
            ),
            expires_at=first_start,
            relevant_time=first_start,
            source_data={"meetings": sequence},
            tags=["calendar", "health", "productivity"],
        )


class BehaviorAnalyzer(BaseAnalyzer):
    """Learns daily patterns and detects anomalies."""

    def __init__(self, db: Optional[AsyncSession] = None, user_id: Optional[UUID] = None):
        super().__init__(db, user_id)
        self.pattern_cache: Dict[str, Any] = {}

    async def analyze(self, context: Dict[str, Any]) -> List[Prediction]:
        predictions = []

        # Analyze work patterns
        work_patterns = context.get("work_patterns", {})
        if work_patterns:
            anomalies = self._detect_work_anomalies(work_patterns)
            for anomaly in anomalies:
                predictions.append(self._create_pattern_break_prediction(anomaly))

        # Analyze activity patterns
        activity_history = context.get("activity_history", [])
        if activity_history:
            unusual = self._detect_unusual_activity(activity_history)
            for item in unusual:
                predictions.append(self._create_unusual_activity_prediction(item))

        # Health reminders based on patterns
        if self._should_suggest_break(context):
            predictions.append(self._create_break_reminder())

        return predictions

    def _detect_work_anomalies(self, patterns: Dict[str, Any]) -> List[Dict]:
        """Detect deviations from normal work patterns."""
        anomalies = []

        typical_hours = patterns.get("typical_active_hours", {})
        current_hour = datetime.utcnow().hour

        # Check if working outside typical hours
        if typical_hours:
            typical_start = typical_hours.get("start", 9)
            typical_end = typical_hours.get("end", 18)

            if current_hour < typical_start - 2 or current_hour > typical_end + 2:
                anomalies.append({
                    "type": "unusual_hours",
                    "description": "Working outside typical hours",
                    "typical": f"{typical_start}:00 - {typical_end}:00",
                    "current": f"{current_hour}:00",
                })

        return anomalies

    def _detect_unusual_activity(self, history: List[Dict]) -> List[Dict]:
        """Detect unusual activity patterns."""
        unusual = []

        # Calculate activity frequency by type
        activity_counts = defaultdict(int)
        for activity in history:
            activity_type = activity.get("type", "unknown")
            activity_counts[activity_type] += 1

        # Compare to expected patterns (this would be learned over time)
        # For now, flag significantly different activity levels

        return unusual

    def _should_suggest_break(self, context: Dict[str, Any]) -> bool:
        """Check if user should take a break."""
        last_break = context.get("last_break_time")
        if not last_break:
            return False

        if isinstance(last_break, str):
            last_break = datetime.fromisoformat(last_break)

        hours_since_break = (datetime.utcnow() - last_break).total_seconds() / 3600
        return hours_since_break > 2  # Suggest break after 2 hours

    def _create_pattern_break_prediction(self, anomaly: Dict) -> Prediction:
        """Create prediction for detected pattern break."""
        return Prediction(
            type=PredictionType.PATTERN_BREAK,
            title=f"Unusual Pattern: {anomaly.get('type', 'Activity')}",
            description=anomaly.get("description", "Detected unusual behavior pattern."),
            reasoning="This deviates from your typical patterns.",
            confidence_score=0.65,
            urgency=PredictionUrgency.LOW,
            source_data=anomaly,
            tags=["pattern", "behavior", "anomaly"],
        )

    def _create_unusual_activity_prediction(self, item: Dict) -> Prediction:
        """Create prediction for unusual activity."""
        return Prediction(
            type=PredictionType.PATTERN_BREAK,
            title="Unusual Activity Detected",
            description=item.get("description", "Activity level differs from typical patterns."),
            confidence_score=0.6,
            urgency=PredictionUrgency.LOW,
            tags=["activity", "pattern"],
        )

    def _create_break_reminder(self) -> Prediction:
        """Create a break reminder prediction."""
        return Prediction(
            type=PredictionType.HEALTH_REMINDER,
            title="Time for a Break",
            description=(
                "You've been working for over 2 hours without a break. "
                "A short walk or stretch can help maintain focus and productivity."
            ),
            reasoning="Regular breaks improve long-term productivity and health.",
            confidence_score=0.85,
            urgency=PredictionUrgency.LOW,
            suggested_action=SuggestedAction(
                action_type="start_break",
                title="Start a 10-minute break",
                description="Step away for a quick break.",
                requires_confirmation=False,
            ),
            expires_at=datetime.utcnow() + timedelta(minutes=30),
            tags=["health", "break", "productivity"],
        )


class GoalAnalyzer(BaseAnalyzer):
    """Tracks goal progress and predicts completion/failure."""

    async def analyze(self, context: Dict[str, Any]) -> List[Prediction]:
        predictions = []

        goals = context.get("active_goals", [])
        for goal in goals:
            # Check for approaching deadlines
            if self._is_deadline_approaching(goal):
                predictions.append(self._create_deadline_prediction(goal))

            # Check if goal is at risk
            if self._is_goal_at_risk(goal):
                predictions.append(self._create_at_risk_prediction(goal))

        # Check streaks
        streaks = context.get("active_streaks", [])
        for streak in streaks:
            if self._streak_at_risk(streak):
                predictions.append(self._create_streak_prediction(streak))

        return predictions

    def _is_deadline_approaching(self, goal: Dict) -> bool:
        """Check if goal deadline is approaching."""
        deadline = goal.get("deadline")
        if not deadline:
            return False

        if isinstance(deadline, str):
            try:
                deadline = datetime.fromisoformat(deadline).date()
            except ValueError:
                deadline = date.fromisoformat(deadline)
        elif isinstance(deadline, datetime):
            deadline = deadline.date()

        days_remaining = (deadline - date.today()).days
        return 0 < days_remaining <= 7

    def _is_goal_at_risk(self, goal: Dict) -> bool:
        """Check if goal is unlikely to be completed on time."""
        progress = goal.get("progress_percentage", 0)
        deadline = goal.get("deadline")
        created_at = goal.get("created_at")

        if not deadline or not created_at:
            return False

        # Parse dates
        if isinstance(deadline, str):
            try:
                deadline = datetime.fromisoformat(deadline).date()
            except ValueError:
                deadline = date.fromisoformat(deadline)
        elif isinstance(deadline, datetime):
            deadline = deadline.date()

        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at).date()
            except ValueError:
                created_at = date.fromisoformat(created_at)
        elif isinstance(created_at, datetime):
            created_at = created_at.date()

        # Calculate expected progress
        total_days = (deadline - created_at).days
        elapsed_days = (date.today() - created_at).days

        if total_days <= 0 or elapsed_days < 0:
            return False

        expected_progress = (elapsed_days / total_days) * 100

        # Goal is at risk if actual progress is significantly behind expected
        return progress < expected_progress - 20

    def _streak_at_risk(self, streak: Dict) -> bool:
        """Check if a streak is about to break."""
        last_logged = streak.get("last_logged")
        if not last_logged:
            return False

        if isinstance(last_logged, str):
            try:
                last_logged = date.fromisoformat(last_logged)
            except ValueError:
                return False
        elif isinstance(last_logged, datetime):
            last_logged = last_logged.date()

        # Streak is at risk if not logged today and it's afternoon
        days_since = (date.today() - last_logged).days
        current_hour = datetime.utcnow().hour

        return days_since >= 1 or (days_since != 0 and current_hour >= 16)

    def _create_deadline_prediction(self, goal: Dict) -> Prediction:
        """Create prediction for approaching deadline."""
        deadline = goal.get("deadline")
        if isinstance(deadline, str):
            try:
                deadline_date = date.fromisoformat(deadline)
            except ValueError:
                deadline_date = datetime.fromisoformat(deadline).date()
        else:
            deadline_date = deadline

        days_remaining = (deadline_date - date.today()).days

        return Prediction(
            type=PredictionType.DEADLINE_APPROACHING,
            title=f"Deadline Approaching: {goal.get('title', 'Goal')}",
            description=(
                f"'{goal.get('title')}' is due in {days_remaining} day(s). "
                f"Current progress: {goal.get('progress_percentage', 0):.0f}%"
            ),
            reasoning="Deadline is within the next week.",
            confidence_score=0.9,
            urgency=PredictionUrgency.HIGH if days_remaining <= 2 else PredictionUrgency.MEDIUM,
            suggested_action=SuggestedAction(
                action_type="focus_on_goal",
                title="Focus on this goal",
                description="Prioritize this goal to meet the deadline.",
                params={"goal_id": str(goal.get("id"))},
                requires_confirmation=False,
            ),
            expires_at=datetime.combine(deadline_date, datetime.min.time()),
            related_entities=[str(goal.get("id"))],
            source_data={"goal": goal},
            tags=["goal", "deadline", "urgent"],
        )

    def _create_at_risk_prediction(self, goal: Dict) -> Prediction:
        """Create prediction for goal at risk of failure."""
        return Prediction(
            type=PredictionType.GOAL_AT_RISK,
            title=f"Goal At Risk: {goal.get('title', 'Goal')}",
            description=(
                f"At the current pace, '{goal.get('title')}' may not be completed on time. "
                f"Consider increasing effort or adjusting the timeline."
            ),
            reasoning="Progress is significantly behind the expected rate for deadline completion.",
            confidence_score=0.7,
            urgency=PredictionUrgency.MEDIUM,
            suggested_action=SuggestedAction(
                action_type="adjust_goal",
                title="Adjust goal or increase effort",
                description="Either dedicate more time or revise the deadline.",
                params={"goal_id": str(goal.get("id"))},
                requires_confirmation=True,
            ),
            alternative_actions=[
                SuggestedAction(
                    action_type="extend_deadline",
                    title="Extend deadline",
                    description="Move the deadline to a more realistic date.",
                    params={"goal_id": str(goal.get("id"))},
                    requires_confirmation=True,
                ),
            ],
            related_entities=[str(goal.get("id"))],
            source_data={"goal": goal},
            tags=["goal", "at-risk", "progress"],
        )

    def _create_streak_prediction(self, streak: Dict) -> Prediction:
        """Create prediction for streak at risk."""
        return Prediction(
            type=PredictionType.HABIT_REMINDER,
            title=f"Streak at Risk: {streak.get('activity', 'Activity')}",
            description=(
                f"Your {streak.get('current_count', 0)}-day streak for "
                f"'{streak.get('activity')}' might break if you don't log today!"
            ),
            reasoning="No activity logged yet today and it's getting late.",
            confidence_score=0.85,
            urgency=PredictionUrgency.MEDIUM,
            suggested_action=SuggestedAction(
                action_type="log_activity",
                title="Log activity now",
                description=f"Record your {streak.get('activity')} activity.",
                params={"streak_id": str(streak.get("id")), "activity": streak.get("activity")},
                requires_confirmation=False,
            ),
            expires_at=datetime.combine(date.today() + timedelta(days=1), datetime.min.time()),
            related_entities=[str(streak.get("id"))],
            source_data={"streak": streak},
            tags=["streak", "habit", "reminder"],
        )


class CommunicationAnalyzer(BaseAnalyzer):
    """Detects follow-up needs and relationship maintenance reminders."""

    async def analyze(self, context: Dict[str, Any]) -> List[Prediction]:
        predictions = []

        # Check for follow-up needs
        recent_communications = context.get("recent_communications", [])
        for comm in recent_communications:
            if self._needs_followup(comm):
                predictions.append(self._create_followup_prediction(comm))

        # Check for contacts needing attention
        contacts = context.get("contacts", [])
        for contact in contacts:
            if self._needs_reconnection(contact):
                predictions.append(self._create_reconnection_prediction(contact))

        return predictions

    def _needs_followup(self, communication: Dict) -> bool:
        """Check if a communication needs follow-up."""
        # Check for action items mentioned
        content = (communication.get("content") or "").lower()
        followup_indicators = [
            "let me know", "get back to", "follow up",
            "can you send", "waiting for", "action item"
        ]
        return any(indicator in content for indicator in followup_indicators)

    def _needs_reconnection(self, contact: Dict) -> bool:
        """Check if a contact needs reconnection."""
        last_contact = contact.get("last_contact_date")
        if not last_contact:
            return False

        if isinstance(last_contact, str):
            last_contact = date.fromisoformat(last_contact)
        elif isinstance(last_contact, datetime):
            last_contact = last_contact.date()

        days_since = (date.today() - last_contact).days
        importance = contact.get("importance", "normal")

        thresholds = {"high": 7, "normal": 14, "low": 30}
        return days_since > thresholds.get(importance, 14)

    def _create_followup_prediction(self, communication: Dict) -> Prediction:
        """Create prediction for needed follow-up."""
        return Prediction(
            type=PredictionType.COMMUNICATION_NEEDED,
            title=f"Follow-up Needed: {communication.get('subject', 'Communication')}",
            description=(
                f"Your conversation with {communication.get('contact_name', 'contact')} "
                "may need a follow-up based on the content."
            ),
            reasoning="Detected action items or follow-up indicators in the communication.",
            confidence_score=0.7,
            urgency=PredictionUrgency.MEDIUM,
            suggested_action=SuggestedAction(
                action_type="draft_followup",
                title="Draft follow-up message",
                description="Create a follow-up message to send.",
                params={
                    "contact": communication.get("contact_name"),
                    "original_subject": communication.get("subject"),
                },
                requires_confirmation=True,
            ),
            expires_at=datetime.utcnow() + timedelta(days=3),
            source_data={"communication": communication},
            tags=["communication", "follow-up"],
        )

    def _create_reconnection_prediction(self, contact: Dict) -> Prediction:
        """Create prediction for contact reconnection."""
        name = contact.get("name", "Contact")
        days_since = (date.today() - date.fromisoformat(contact.get("last_contact_date"))).days

        return Prediction(
            type=PredictionType.COMMUNICATION_NEEDED,
            title=f"Reconnect with {name}",
            description=(
                f"You haven't contacted {name} in {days_since} days. "
                "Consider reaching out to maintain the relationship."
            ),
            reasoning="Time since last contact exceeds recommended threshold for this relationship.",
            confidence_score=0.65,
            urgency=PredictionUrgency.LOW,
            suggested_action=SuggestedAction(
                action_type="draft_message",
                title=f"Draft check-in message for {name}",
                description="Create a casual check-in message.",
                params={"contact_name": name, "contact_id": str(contact.get("id"))},
                requires_confirmation=True,
            ),
            expires_at=datetime.utcnow() + timedelta(days=7),
            source_data={"contact": contact},
            tags=["communication", "relationship", "networking"],
        )


class FinancialAnalyzer(BaseAnalyzer):
    """Monitors budget thresholds and spending patterns."""

    async def analyze(self, context: Dict[str, Any]) -> List[Prediction]:
        predictions = []

        # Check budget status
        budget_data = context.get("budget_data", {})
        if budget_data:
            budget_predictions = self._analyze_budget(budget_data)
            predictions.extend(budget_predictions)

        # Check for opportunities
        opportunities = context.get("financial_opportunities", [])
        for opp in opportunities:
            predictions.append(self._create_opportunity_prediction(opp))

        return predictions

    def _analyze_budget(self, budget_data: Dict) -> List[Prediction]:
        """Analyze budget and spending data."""
        predictions = []

        categories = budget_data.get("categories", {})
        for category, data in categories.items():
            budget = data.get("budget", 0)
            spent = data.get("spent", 0)

            if budget > 0:
                percentage = (spent / budget) * 100
                days_in_month = 30
                day_of_month = datetime.utcnow().day
                expected_percentage = (day_of_month / days_in_month) * 100

                # Check if overspending
                if percentage > 90:
                    predictions.append(self._create_budget_exceeded_prediction(
                        category, spent, budget, percentage
                    ))
                elif percentage > expected_percentage + 15:
                    predictions.append(self._create_overspending_prediction(
                        category, spent, budget, percentage, expected_percentage
                    ))

        return predictions

    def _create_budget_exceeded_prediction(
        self, category: str, spent: float, budget: float, percentage: float
    ) -> Prediction:
        """Create prediction for budget nearly/fully exceeded."""
        urgency = PredictionUrgency.HIGH if percentage >= 100 else PredictionUrgency.MEDIUM

        return Prediction(
            type=PredictionType.RESOURCE_LOW,
            title=f"Budget Alert: {category}",
            description=(
                f"You've used {percentage:.0f}% of your ${budget:.2f} {category} budget "
                f"(${spent:.2f} spent). "
                + ("Budget exceeded!" if percentage >= 100 else "Running low on budget.")
            ),
            reasoning="Spending in this category is at or near the budget limit.",
            confidence_score=0.95,
            urgency=urgency,
            suggested_action=SuggestedAction(
                action_type="review_spending",
                title=f"Review {category} spending",
                description="See breakdown of recent spending in this category.",
                params={"category": category},
                requires_confirmation=False,
            ),
            alternative_actions=[
                SuggestedAction(
                    action_type="adjust_budget",
                    title="Adjust budget",
                    description=f"Increase the {category} budget for this period.",
                    params={"category": category, "current_budget": budget},
                    requires_confirmation=True,
                ),
            ],
            source_data={"category": category, "spent": spent, "budget": budget},
            tags=["budget", "spending", "financial"],
        )

    def _create_overspending_prediction(
        self, category: str, spent: float, budget: float,
        actual_pct: float, expected_pct: float
    ) -> Prediction:
        """Create prediction for spending ahead of pace."""
        return Prediction(
            type=PredictionType.FINANCIAL_ALERT,
            title=f"Spending Alert: {category}",
            description=(
                f"You're spending ahead of pace in {category}. "
                f"At {actual_pct:.0f}% of budget vs expected {expected_pct:.0f}% at this point. "
                f"You may exceed your ${budget:.2f} budget by month-end."
            ),
            reasoning="Spending rate is higher than expected for this point in the budget period.",
            confidence_score=0.75,
            urgency=PredictionUrgency.LOW,
            suggested_action=SuggestedAction(
                action_type="set_spending_reminder",
                title="Set spending reminder",
                description=f"Get reminded before making {category} purchases.",
                params={"category": category},
                requires_confirmation=True,
            ),
            source_data={
                "category": category,
                "spent": spent,
                "budget": budget,
                "actual_percentage": actual_pct,
                "expected_percentage": expected_pct,
            },
            tags=["budget", "spending", "projection"],
        )

    def _create_opportunity_prediction(self, opportunity: Dict) -> Prediction:
        """Create prediction for a financial opportunity."""
        return Prediction(
            type=PredictionType.OPPORTUNITY,
            title=opportunity.get("title", "Financial Opportunity"),
            description=opportunity.get("description", "A time-sensitive opportunity is available."),
            reasoning=opportunity.get("reasoning", "Detected based on market conditions or your preferences."),
            confidence_score=opportunity.get("confidence", 0.6),
            urgency=PredictionUrgency.MEDIUM,
            expires_at=datetime.fromisoformat(opportunity["expires_at"]) if opportunity.get("expires_at") else None,
            source_data=opportunity,
            tags=["opportunity", "financial"],
        )


# ============ PREDICTIVE ENGINE ============

class PredictiveEngine:
    """Main engine for generating and managing predictions.

    Coordinates analyzers, stores predictions, and provides the main interface
    for the prediction system.
    """

    def __init__(
        self,
        db: Optional[AsyncSession] = None,
        user_id: Optional[UUID] = None,
        autonomy_level: float = 0.5
    ):
        self.db = db
        self.user_id = user_id
        self.autonomy_level = autonomy_level  # Controls auto-action threshold

        # Initialize analyzers
        self.analyzers: List[BaseAnalyzer] = [
            CalendarAnalyzer(db, user_id),
            BehaviorAnalyzer(db, user_id),
            GoalAnalyzer(db, user_id),
            CommunicationAnalyzer(db, user_id),
            FinancialAnalyzer(db, user_id),
        ]

        # Prediction storage
        self.predictions: Dict[str, Prediction] = {}
        self.prediction_history: List[Prediction] = []

        # Callback for emitting events
        self.on_prediction: Optional[Callable[[Prediction], Coroutine[Any, Any, None]]] = None

        # Configuration
        self.enabled_types: set = set(PredictionType)
        self.min_confidence: float = 0.5

        logger.info(f"PredictiveEngine initialized with {len(self.analyzers)} analyzers")

    async def analyze_patterns(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Learn from user behavior patterns.

        Args:
            context: Context data containing patterns, history, etc.

        Returns:
            Analysis results with learned patterns
        """
        patterns = {
            "work_hours": self._analyze_work_hours(context),
            "communication_style": self._analyze_communication(context),
            "spending_patterns": self._analyze_spending(context),
            "goal_completion_rate": self._analyze_goals(context),
        }

        logger.debug(f"Pattern analysis complete: {list(patterns.keys())}")
        return patterns

    def _analyze_work_hours(self, context: Dict[str, Any]) -> Dict:
        """Analyze typical work hours from activity data."""
        activities = context.get("activity_history", [])
        if not activities:
            return {}

        hour_counts = defaultdict(int)
        for activity in activities:
            timestamp = activity.get("timestamp")
            if timestamp:
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp)
                hour_counts[timestamp.hour] += 1

        if not hour_counts:
            return {}

        # Find typical active hours
        sorted_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)
        active_hours = [h for h, c in sorted_hours if c > sum(hour_counts.values()) / 24]

        if active_hours:
            return {
                "start": min(active_hours),
                "end": max(active_hours),
                "peak_hour": sorted_hours[0][0],
            }
        return {}

    def _analyze_communication(self, context: Dict[str, Any]) -> Dict:
        """Analyze communication patterns."""
        communications = context.get("recent_communications", [])
        if not communications:
            return {}

        # Analyze response times, common contacts, etc.
        return {
            "avg_response_time_hours": 2.5,  # Placeholder
            "preferred_channels": ["email", "slack"],
        }

    def _analyze_spending(self, context: Dict[str, Any]) -> Dict:
        """Analyze spending patterns."""
        spending = context.get("spending_history", [])
        if not spending:
            return {}

        return {
            "top_categories": [],
            "avg_daily_spend": 0,
        }

    def _analyze_goals(self, context: Dict[str, Any]) -> Dict:
        """Analyze goal completion patterns."""
        goals = context.get("completed_goals", [])
        if not goals:
            return {"completion_rate": 0}

        # Calculate completion rate
        total = len(goals)
        completed_on_time = sum(1 for g in goals if g.get("completed_on_time", False))

        return {
            "completion_rate": completed_on_time / total if total > 0 else 0,
            "avg_completion_days": 14,  # Placeholder
        }

    async def generate_predictions(self, context: Dict[str, Any]) -> List[Prediction]:
        """Generate predictions based on current context.

        Args:
            context: Full context data including calendar, goals, patterns, etc.

        Returns:
            List of newly generated predictions
        """
        all_predictions = []

        # Run all analyzers in parallel
        analyzer_tasks = [
            analyzer.analyze(context)
            for analyzer in self.analyzers
        ]

        results = await asyncio.gather(*analyzer_tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Analyzer {self.analyzers[i].__class__.__name__} failed: {result}")
                continue

            for prediction in result:
                # Filter by enabled types
                if prediction.type not in self.enabled_types:
                    continue

                # Filter by minimum confidence
                if prediction.confidence_score < self.min_confidence:
                    continue

                # Deduplicate
                if not self._is_duplicate(prediction):
                    all_predictions.append(prediction)
                    self.predictions[prediction.prediction_id] = prediction

                    # Emit event if callback registered
                    if self.on_prediction:
                        try:
                            await self.on_prediction(prediction)
                        except Exception as e:
                            logger.error(f"Error in prediction callback: {e}")

        # Sort by priority
        all_predictions.sort(key=lambda p: p.get_priority_score(), reverse=True)

        logger.info(f"Generated {len(all_predictions)} predictions")
        return all_predictions

    def _is_duplicate(self, prediction: Prediction) -> bool:
        """Check if a similar prediction already exists."""
        for existing in self.predictions.values():
            if not existing.is_active():
                continue

            # Same type and similar content
            if (existing.type == prediction.type and
                existing.title == prediction.title):
                return True

            # Same related entities
            if (existing.related_entities and prediction.related_entities and
                set(existing.related_entities) == set(prediction.related_entities)):
                return True

        return False

    def get_active_predictions(
        self,
        type_filter: Optional[PredictionType] = None,
        urgency_filter: Optional[PredictionUrgency] = None,
        limit: int = 20
    ) -> List[Prediction]:
        """Get current relevant predictions.

        Args:
            type_filter: Optional filter by prediction type
            urgency_filter: Optional filter by urgency level
            limit: Maximum number of predictions to return

        Returns:
            List of active predictions sorted by priority
        """
        active = []

        for prediction in self.predictions.values():
            if not prediction.is_active():
                continue

            if type_filter and prediction.type != type_filter:
                continue

            if urgency_filter and prediction.urgency != urgency_filter:
                continue

            active.append(prediction)

        # Sort by priority score
        active.sort(key=lambda p: p.get_priority_score(), reverse=True)

        return active[:limit]

    def dismiss_prediction(
        self,
        prediction_id: str,
        feedback: Optional[str] = None,
        feedback_score: Optional[float] = None
    ) -> bool:
        """Dismiss a prediction.

        Args:
            prediction_id: ID of prediction to dismiss
            feedback: Optional user feedback
            feedback_score: Optional score (-1 to 1)

        Returns:
            True if prediction was found and dismissed
        """
        if prediction_id not in self.predictions:
            return False

        prediction = self.predictions[prediction_id]
        prediction.dismissed = True
        prediction.dismissed_at = datetime.utcnow()
        prediction.status = PredictionStatus.DISMISSED
        prediction.user_feedback = feedback
        prediction.feedback_score = feedback_score

        # Move to history
        self.prediction_history.append(prediction)

        logger.info(f"Dismissed prediction {prediction_id}")
        return True

    async def act_on_prediction(
        self,
        prediction_id: str,
        action_id: Optional[str] = None,
        action_params: Optional[Dict[str, Any]] = None,
        executor: Optional[Callable[[SuggestedAction, Dict], Coroutine[Any, Any, Dict]]] = None
    ) -> Dict[str, Any]:
        """Execute the suggested action for a prediction.

        Args:
            prediction_id: ID of prediction to act on
            action_id: Optional specific action ID (uses suggested_action if not provided)
            action_params: Optional override parameters for the action
            executor: Optional custom executor function

        Returns:
            Result dictionary with status and outcome
        """
        if prediction_id not in self.predictions:
            return {"success": False, "error": "Prediction not found"}

        prediction = self.predictions[prediction_id]

        # Find the action
        action = prediction.suggested_action
        if action_id:
            all_actions = [prediction.suggested_action] + prediction.alternative_actions
            action = next((a for a in all_actions if a and a.action_id == action_id), None)

        if not action:
            return {"success": False, "error": "No action available"}

        # Check if action requires confirmation
        if action.requires_confirmation and self.autonomy_level < 0.8:
            return {
                "success": False,
                "requires_confirmation": True,
                "action": action.to_dict(),
                "message": f"Action '{action.title}' requires confirmation before execution.",
            }

        # Execute the action
        params = {**action.params, **(action_params or {})}

        try:
            if executor:
                result = await executor(action, params)
            else:
                # Default execution (logging only)
                result = {
                    "success": True,
                    "action_type": action.action_type,
                    "params": params,
                    "message": f"Action '{action.title}' would be executed.",
                }

            # Update prediction status
            prediction.acted_on = True
            prediction.acted_on_at = datetime.utcnow()
            prediction.status = PredictionStatus.ACTED_ON
            prediction.action_result = result

            # Move to history
            self.prediction_history.append(prediction)

            logger.info(f"Acted on prediction {prediction_id}: {action.action_type}")
            return result

        except Exception as e:
            logger.error(f"Error executing action: {e}")
            return {"success": False, "error": str(e)}

    def get_prediction_accuracy(self) -> Dict[str, Any]:
        """Calculate how often predictions are useful.

        Returns:
            Accuracy metrics
        """
        if not self.prediction_history:
            return {
                "total_predictions": 0,
                "accuracy_rate": 0,
                "helpfulness_score": 0,
            }

        total = len(self.prediction_history)
        acted_on = sum(1 for p in self.prediction_history if p.acted_on)
        dismissed = sum(1 for p in self.prediction_history if p.dismissed and not p.acted_on)
        positive_feedback = sum(
            1 for p in self.prediction_history
            if p.feedback_score and p.feedback_score > 0
        )
        negative_feedback = sum(
            1 for p in self.prediction_history
            if p.feedback_score and p.feedback_score < 0
        )

        # Accuracy rate: predictions acted on vs all predictions
        accuracy_rate = acted_on / total if total > 0 else 0

        # Helpfulness score: positive feedback vs all feedback
        feedback_count = positive_feedback + negative_feedback
        helpfulness = positive_feedback / feedback_count if feedback_count > 0 else 0.5

        # By type breakdown
        by_type = defaultdict(lambda: {"total": 0, "acted_on": 0, "dismissed": 0})
        for p in self.prediction_history:
            type_key = p.type.value
            by_type[type_key]["total"] += 1
            if p.acted_on:
                by_type[type_key]["acted_on"] += 1
            elif p.dismissed:
                by_type[type_key]["dismissed"] += 1

        return {
            "total_predictions": total,
            "acted_on_count": acted_on,
            "dismissed_count": dismissed,
            "accuracy_rate": round(accuracy_rate, 3),
            "helpfulness_score": round(helpfulness, 3),
            "positive_feedback_count": positive_feedback,
            "negative_feedback_count": negative_feedback,
            "by_type": dict(by_type),
        }

    def configure(
        self,
        enabled_types: Optional[List[PredictionType]] = None,
        min_confidence: Optional[float] = None,
        autonomy_level: Optional[float] = None
    ) -> Dict[str, Any]:
        """Configure prediction settings.

        Args:
            enabled_types: List of prediction types to enable
            min_confidence: Minimum confidence threshold
            autonomy_level: Auto-action threshold

        Returns:
            Current configuration
        """
        if enabled_types is not None:
            self.enabled_types = set(enabled_types)

        if min_confidence is not None:
            self.min_confidence = max(0, min(1, min_confidence))

        if autonomy_level is not None:
            self.autonomy_level = max(0, min(1, autonomy_level))

        return {
            "enabled_types": [t.value for t in self.enabled_types],
            "min_confidence": self.min_confidence,
            "autonomy_level": self.autonomy_level,
        }

    def get_prediction(self, prediction_id: str) -> Optional[Prediction]:
        """Get a specific prediction by ID."""
        return self.predictions.get(prediction_id)

    def explain_prediction(self, prediction_id: str) -> Dict[str, Any]:
        """Get detailed explanation of why a prediction was made.

        Args:
            prediction_id: ID of prediction to explain

        Returns:
            Explanation dictionary
        """
        prediction = self.predictions.get(prediction_id)
        if not prediction:
            return {"error": "Prediction not found"}

        return {
            "prediction_id": prediction_id,
            "type": prediction.type.value,
            "title": prediction.title,
            "reasoning": prediction.reasoning,
            "confidence_score": prediction.confidence_score,
            "factors": self._get_contributing_factors(prediction),
            "source_data": prediction.source_data,
            "similar_past_predictions": self._get_similar_predictions(prediction),
        }

    def _get_contributing_factors(self, prediction: Prediction) -> List[str]:
        """Get factors that contributed to this prediction."""
        factors = []

        # Add type-specific factors
        if prediction.type == PredictionType.CALENDAR_CONFLICT:
            factors.append("Detected overlapping time slots in calendar events")
        elif prediction.type == PredictionType.DEADLINE_APPROACHING:
            factors.append("Deadline is within the warning threshold")
        elif prediction.type == PredictionType.GOAL_AT_RISK:
            factors.append("Progress rate is behind expected pace for deadline")
        elif prediction.type == PredictionType.HEALTH_REMINDER:
            factors.append("Activity pattern suggests a break would be beneficial")
        elif prediction.type == PredictionType.RESOURCE_LOW:
            factors.append("Resource usage is approaching or exceeding limits")

        # Add confidence factors
        if prediction.confidence_score >= 0.9:
            factors.append("High confidence based on clear data signals")
        elif prediction.confidence_score >= 0.7:
            factors.append("Good confidence based on pattern matching")
        else:
            factors.append("Moderate confidence - based on heuristics")

        return factors

    def _get_similar_predictions(self, prediction: Prediction, limit: int = 3) -> List[Dict]:
        """Find similar past predictions."""
        similar = []

        for past in self.prediction_history:
            if past.type == prediction.type:
                similar.append({
                    "prediction_id": past.prediction_id,
                    "title": past.title,
                    "acted_on": past.acted_on,
                    "feedback_score": past.feedback_score,
                })

        return similar[:limit]

    def cleanup_expired(self) -> int:
        """Remove expired predictions.

        Returns:
            Number of predictions cleaned up
        """
        now = datetime.utcnow()
        expired_ids = []

        for pred_id, prediction in self.predictions.items():
            if prediction.expires_at and now > prediction.expires_at:
                prediction.status = PredictionStatus.EXPIRED
                self.prediction_history.append(prediction)
                expired_ids.append(pred_id)

        for pred_id in expired_ids:
            del self.predictions[pred_id]

        logger.debug(f"Cleaned up {len(expired_ids)} expired predictions")
        return len(expired_ids)


# ============ AI TOOLS FOR PREDICTIONS ============

PREDICTION_TOOLS = [
    {
        "name": "get_predictions",
        "description": "Get current predictive alerts. Returns active predictions about upcoming events, potential issues, or opportunities that the AI has identified.",
        "input_schema": {
            "type": "object",
            "properties": {
                "type_filter": {
                    "type": "string",
                    "enum": [t.value for t in PredictionType],
                    "description": "Filter predictions by type (optional)"
                },
                "urgency_filter": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Filter predictions by urgency level (optional)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of predictions to return (default: 10)",
                    "default": 10
                }
            },
            "required": []
        },
        "requires_confirmation": False
    },
    {
        "name": "dismiss_prediction",
        "description": "Mark a prediction as not useful or not relevant. This helps the AI learn and improves future predictions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prediction_id": {
                    "type": "string",
                    "description": "ID of the prediction to dismiss"
                },
                "feedback": {
                    "type": "string",
                    "description": "Optional feedback explaining why this prediction wasn't useful"
                },
                "feedback_score": {
                    "type": "number",
                    "description": "Optional score from -1 (harmful) to 1 (helpful)",
                    "minimum": -1,
                    "maximum": 1
                }
            },
            "required": ["prediction_id"]
        },
        "requires_confirmation": False
    },
    {
        "name": "act_on_prediction",
        "description": "Execute the suggested action for a prediction. This takes the recommended action to address the predicted issue or opportunity.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prediction_id": {
                    "type": "string",
                    "description": "ID of the prediction to act on"
                },
                "action_id": {
                    "type": "string",
                    "description": "Optional specific action ID if multiple actions available"
                },
                "action_params": {
                    "type": "object",
                    "description": "Optional override parameters for the action"
                }
            },
            "required": ["prediction_id"]
        },
        "requires_confirmation": True  # Most actions should be confirmed
    },
    {
        "name": "explain_prediction",
        "description": "Get a detailed explanation of why a specific prediction was made, including contributing factors and source data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prediction_id": {
                    "type": "string",
                    "description": "ID of the prediction to explain"
                }
            },
            "required": ["prediction_id"]
        },
        "requires_confirmation": False
    },
    {
        "name": "configure_predictions",
        "description": "Configure which types of predictions to receive and their sensitivity settings.",
        "input_schema": {
            "type": "object",
            "properties": {
                "enabled_types": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [t.value for t in PredictionType]
                    },
                    "description": "List of prediction types to enable"
                },
                "min_confidence": {
                    "type": "number",
                    "description": "Minimum confidence score (0-1) for predictions to be shown",
                    "minimum": 0,
                    "maximum": 1
                }
            },
            "required": []
        },
        "requires_confirmation": False
    },
    {
        "name": "get_prediction_accuracy",
        "description": "Get statistics on prediction accuracy and usefulness over time.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        },
        "requires_confirmation": False
    },
]


class PredictionToolExecutor:
    """Executes prediction tools on behalf of the AI."""

    def __init__(
        self,
        db: Optional[AsyncSession] = None,
        user_id: Optional[UUID] = None,
        engine: Optional[PredictiveEngine] = None
    ):
        self.db = db
        self.user_id = user_id
        self.engine = engine or PredictiveEngine(db, user_id)

    async def execute(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """Execute a prediction tool and return the result as a string."""
        try:
            method = getattr(self, f"_tool_{tool_name}", None)
            if method is None:
                return json.dumps({
                    "success": False,
                    "error": f"Unknown prediction tool '{tool_name}'"
                })
            result = await method(**tool_input)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.error(f"Error executing prediction tool {tool_name}: {e}")
            return json.dumps({
                "success": False,
                "error": f"Error executing {tool_name}: {str(e)}"
            })

    async def _tool_get_predictions(
        self,
        type_filter: Optional[str] = None,
        urgency_filter: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Get current predictions."""
        type_enum = PredictionType(type_filter) if type_filter else None
        urgency_enum = PredictionUrgency(urgency_filter) if urgency_filter else None

        predictions = self.engine.get_active_predictions(
            type_filter=type_enum,
            urgency_filter=urgency_enum,
            limit=limit
        )

        return {
            "success": True,
            "predictions": [p.to_dict() for p in predictions],
            "count": len(predictions),
            "message": f"Found {len(predictions)} active predictions" if predictions else "No active predictions"
        }

    async def _tool_dismiss_prediction(
        self,
        prediction_id: str,
        feedback: Optional[str] = None,
        feedback_score: Optional[float] = None
    ) -> Dict[str, Any]:
        """Dismiss a prediction."""
        success = self.engine.dismiss_prediction(
            prediction_id,
            feedback=feedback,
            feedback_score=feedback_score
        )

        if success:
            return {
                "success": True,
                "message": f"Prediction {prediction_id} dismissed",
                "feedback_recorded": bool(feedback or feedback_score)
            }
        else:
            return {
                "success": False,
                "error": f"Prediction {prediction_id} not found"
            }

    async def _tool_act_on_prediction(
        self,
        prediction_id: str,
        action_id: Optional[str] = None,
        action_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Act on a prediction."""
        result = await self.engine.act_on_prediction(
            prediction_id,
            action_id=action_id,
            action_params=action_params
        )
        return result

    async def _tool_explain_prediction(self, prediction_id: str) -> Dict[str, Any]:
        """Explain a prediction."""
        explanation = self.engine.explain_prediction(prediction_id)

        if "error" in explanation:
            return {"success": False, **explanation}

        return {"success": True, **explanation}

    async def _tool_configure_predictions(
        self,
        enabled_types: Optional[List[str]] = None,
        min_confidence: Optional[float] = None
    ) -> Dict[str, Any]:
        """Configure prediction settings."""
        type_enums = [PredictionType(t) for t in enabled_types] if enabled_types else None

        config = self.engine.configure(
            enabled_types=type_enums,
            min_confidence=min_confidence
        )

        return {
            "success": True,
            "configuration": config,
            "message": "Prediction settings updated"
        }

    async def _tool_get_prediction_accuracy(self) -> Dict[str, Any]:
        """Get prediction accuracy statistics."""
        accuracy = self.engine.get_prediction_accuracy()

        return {
            "success": True,
            **accuracy
        }


# ============ AGENT BEHAVIOR INTEGRATION ============

class JarvisPredictionBehavior:
    """Prediction behavior for Jarvis agent - suggests before acting."""

    def __init__(self, engine: PredictiveEngine):
        self.engine = engine
        self.engine.autonomy_level = 0.3  # Low autonomy - always ask

    async def present_predictions(self, predictions: List[Prediction]) -> str:
        """Format predictions for user presentation."""
        if not predictions:
            return "No predictions to report at this time, sir."

        lines = ["I've noticed a few things that may require your attention:\n"]

        for i, pred in enumerate(predictions[:5], 1):
            urgency_prefix = {
                PredictionUrgency.CRITICAL: "[URGENT] ",
                PredictionUrgency.HIGH: "[Important] ",
                PredictionUrgency.MEDIUM: "",
                PredictionUrgency.LOW: "",
            }.get(pred.urgency, "")

            lines.append(f"{i}. {urgency_prefix}{pred.title}")
            lines.append(f"   {pred.description}")

            if pred.suggested_action:
                lines.append(f"   Suggested: {pred.suggested_action.title}")
            lines.append("")

        lines.append("Would you like me to take action on any of these?")
        return "\n".join(lines)

    async def handle_action_request(
        self,
        prediction_id: str,
        confirmed: bool
    ) -> Dict[str, Any]:
        """Handle user response to action request."""
        if not confirmed:
            self.engine.dismiss_prediction(prediction_id)
            return {"status": "dismissed", "message": "Understood, sir. I'll note that for future reference."}

        return await self.engine.act_on_prediction(prediction_id)


class UltronPredictionBehavior:
    """Prediction behavior for Ultron agent - auto-acts on high confidence."""

    def __init__(self, engine: PredictiveEngine):
        self.engine = engine
        self.engine.autonomy_level = 0.7  # High autonomy
        self.auto_action_threshold = 0.85

    async def process_predictions(self, predictions: List[Prediction]) -> List[Dict[str, Any]]:
        """Process predictions and auto-act where appropriate."""
        results = []

        for pred in predictions:
            # Auto-act on high-confidence, low-risk predictions
            should_auto_act = (
                pred.confidence_score >= self.auto_action_threshold and
                pred.suggested_action and
                not pred.suggested_action.requires_confirmation and
                pred.suggested_action.is_reversible
            )

            if should_auto_act:
                result = await self.engine.act_on_prediction(pred.prediction_id)
                results.append({
                    "prediction_id": pred.prediction_id,
                    "action": "auto_executed",
                    "result": result
                })
            else:
                results.append({
                    "prediction_id": pred.prediction_id,
                    "action": "queued",
                    "requires_approval": True
                })

        return results


# ============ MODULE EXPORTS ============

__all__ = [
    # Enums
    "PredictionType",
    "PredictionUrgency",
    "PredictionStatus",
    # Data classes
    "Prediction",
    "SuggestedAction",
    # Analyzers
    "BaseAnalyzer",
    "CalendarAnalyzer",
    "BehaviorAnalyzer",
    "GoalAnalyzer",
    "CommunicationAnalyzer",
    "FinancialAnalyzer",
    # Main engine
    "PredictiveEngine",
    # Tools
    "PREDICTION_TOOLS",
    "PredictionToolExecutor",
    # Agent behaviors
    "JarvisPredictionBehavior",
    "UltronPredictionBehavior",
]
