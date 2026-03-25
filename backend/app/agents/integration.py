"""Agent Integration Layer - Connects agents with learning, daemon, and notifications.

This module wires together all the "movie-level" components:
- Learning system: Agents learn from every interaction
- Background daemon: Ultron gets alerts from always-on monitoring
- Notifications: Agents can proactively notify users
- Auto-apply: Ultron can autonomously handle job applications

This is what makes Jarvis/Ultron feel truly intelligent and proactive.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)

# Import learning system
try:
    from app.ai.learning import (
        get_learning_engine,
        LearningCategory,
        FeedbackType,
        learn,
    )
    LEARNING_AVAILABLE = True
except ImportError:
    LEARNING_AVAILABLE = False
    get_learning_engine = None

# Import background daemon
try:
    from app.daemon import (
        get_background_monitor,
        Alert,
        AlertCategory,
        AlertPriority,
        get_auto_apply_pipeline,
    )
    DAEMON_AVAILABLE = True
except ImportError:
    DAEMON_AVAILABLE = False
    get_background_monitor = None

# Import notifications
try:
    from app.notifications import (
        get_notification_manager,
        notify,
        NotificationPriority,
    )
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False
    get_notification_manager = None

# Import user profile
try:
    from app.core.user_profile import (
        get_user_profile,
        ActionCategory,
        ConfirmationLevel,
    )
    PROFILE_AVAILABLE = True
except ImportError:
    PROFILE_AVAILABLE = False
    get_user_profile = None


@dataclass
class AgentInteraction:
    """Records a single interaction for learning."""
    agent_id: str
    message: str
    response: str
    context: Dict[str, Any]
    user_feedback: Optional[str] = None
    was_accepted: Optional[bool] = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()


class AgentLearningBridge:
    """Bridges agents with the learning system.

    Records interactions and outcomes to make agents smarter over time.
    """

    def __init__(self):
        self.pending_interactions: Dict[str, AgentInteraction] = {}
        self._learning_engine = None

    @property
    def learning_engine(self):
        if self._learning_engine is None and LEARNING_AVAILABLE:
            self._learning_engine = get_learning_engine()
        return self._learning_engine

    async def record_interaction(
        self,
        agent_id: str,
        message: str,
        response: str,
        context: Dict[str, Any] = None,
    ) -> str:
        """Record an interaction for potential learning.

        Returns an interaction ID for later feedback.
        """
        import uuid
        interaction_id = str(uuid.uuid4())[:12]

        interaction = AgentInteraction(
            agent_id=agent_id,
            message=message,
            response=response,
            context=context or {},
        )
        self.pending_interactions[interaction_id] = interaction

        # Auto-cleanup old interactions (keep last 100)
        if len(self.pending_interactions) > 100:
            oldest = sorted(
                self.pending_interactions.items(),
                key=lambda x: x[1].timestamp
            )[:50]
            for key, _ in oldest:
                del self.pending_interactions[key]

        return interaction_id

    async def record_acceptance(
        self,
        interaction_id: str,
        context: str = "",
    ):
        """User accepted the agent's suggestion."""
        interaction = self.pending_interactions.get(interaction_id)
        if not interaction or not self.learning_engine:
            return

        interaction.was_accepted = True

        # Learn from acceptance
        self.learning_engine.learn_from_acceptance(
            suggestion_type=f"{interaction.agent_id}_response",
            suggestion=interaction.response[:500],
            context=f"User accepted response to: {interaction.message[:100]}",
        )

        logger.info(f"Learned from acceptance: {interaction_id}")

    async def record_rejection(
        self,
        interaction_id: str,
        reason: str = "",
    ):
        """User rejected the agent's suggestion."""
        interaction = self.pending_interactions.get(interaction_id)
        if not interaction or not self.learning_engine:
            return

        interaction.was_accepted = False
        interaction.user_feedback = reason

        # Learn from rejection
        self.learning_engine.learn_from_rejection(
            suggestion_type=f"{interaction.agent_id}_response",
            suggestion=interaction.response[:500],
            context=f"User rejected: {reason or 'No reason given'}. Original: {interaction.message[:100]}",
        )

        logger.info(f"Learned from rejection: {interaction_id} - {reason}")

    async def record_correction(
        self,
        original: str,
        corrected: str,
        agent_id: str = "",
        conversation_id: str = "",
    ):
        """User corrected the agent's output."""
        if not self.learning_engine:
            return

        self.learning_engine.learn_from_correction(
            original=original,
            corrected=corrected,
            context=f"Agent: {agent_id}",
            conversation_id=conversation_id,
        )

        logger.info(f"Learned correction: '{original[:50]}...' -> '{corrected[:50]}...'")

    def get_learned_context(self) -> str:
        """Get accumulated learned context for prompts."""
        if not self.learning_engine:
            return ""
        return self.learning_engine.get_context_for_prompt()


class AgentDaemonBridge:
    """Bridges agents with the background daemon.

    Allows Ultron to receive alerts and act on them autonomously.
    """

    def __init__(self, ultron_agent=None, jarvis_agent=None):
        self.ultron = ultron_agent
        self.jarvis = jarvis_agent
        self._alert_handlers: Dict[AlertCategory, Callable] = {}
        self._pending_alerts: List[Alert] = []
        self._setup_complete = False

    def setup(self):
        """Set up the daemon bridge with alert handlers."""
        if self._setup_complete or not DAEMON_AVAILABLE:
            return

        monitor = get_background_monitor()

        # Register to receive alerts
        monitor.on_alert(self._handle_alert_sync)

        self._setup_complete = True
        logger.info("AgentDaemonBridge setup complete")

    def _handle_alert_sync(self, alert: Alert):
        """Synchronous wrapper for async alert handling."""
        asyncio.create_task(self._handle_alert(alert))

    async def _handle_alert(self, alert: Alert):
        """Handle an incoming alert from the daemon.

        Routes alerts to appropriate agents based on type and autonomy settings.
        """
        logger.info(f"Received alert: {alert.category.value} - {alert.title}")

        # Check autonomy settings
        if PROFILE_AVAILABLE:
            profile = get_user_profile()
            autonomy = profile.autonomy

            # Determine if action can be taken autonomously
            can_auto_act = self._can_auto_act(alert, autonomy)
        else:
            can_auto_act = False

        # Route based on alert category
        if alert.category == AlertCategory.JOB_OPPORTUNITY:
            await self._handle_job_alert(alert, can_auto_act)

        elif alert.category == AlertCategory.JOB_RESPONSE:
            await self._handle_job_response_alert(alert, can_auto_act)

        elif alert.category == AlertCategory.EMAIL_IMPORTANT:
            await self._handle_email_alert(alert, can_auto_act)

        elif alert.category == AlertCategory.CALENDAR_REMINDER:
            await self._handle_calendar_alert(alert, can_auto_act)

        elif alert.category == AlertCategory.DAILY_BRIEFING:
            await self._handle_briefing_alert(alert)

        else:
            # Store for manual review
            self._pending_alerts.append(alert)

    def _can_auto_act(self, alert: Alert, autonomy) -> bool:
        """Determine if we can act autonomously on this alert."""
        # Map alert categories to action categories
        category_map = {
            AlertCategory.JOB_OPPORTUNITY: ActionCategory.JOB_APPLICATION,
            AlertCategory.JOB_RESPONSE: ActionCategory.EMAIL_SINGLE,
            AlertCategory.EMAIL_IMPORTANT: ActionCategory.EMAIL_SINGLE,
            AlertCategory.CALENDAR_REMINDER: ActionCategory.CALENDAR_MODIFY,
        }

        action_cat = category_map.get(alert.category)
        if not action_cat:
            return False

        return not autonomy.requires_confirmation(action_cat)

    async def _handle_job_alert(self, alert: Alert, can_auto_act: bool):
        """Handle a job opportunity alert."""
        job_data = alert.data.get("job", {})
        match_score = alert.data.get("match_score", 0)

        if can_auto_act and match_score >= 0.85:
            # Add to auto-apply queue
            if DAEMON_AVAILABLE:
                from app.daemon.auto_apply import JobOpportunity, get_auto_apply_pipeline

                pipeline = get_auto_apply_pipeline()

                job = JobOpportunity(
                    title=job_data.get("title", ""),
                    company=job_data.get("company", ""),
                    location=job_data.get("location", ""),
                    description=job_data.get("description", ""),
                    url=job_data.get("url", ""),
                    source=job_data.get("source", ""),
                    match_score=match_score,
                )

                pipeline.add_opportunity(job)
                pipeline.queue_for_application(job.id)

                logger.info(f"Auto-queued job application: {job.title} at {job.company}")

        else:
            # Notify for manual review
            if NOTIFICATIONS_AVAILABLE:
                await notify(
                    title=f"Job Match: {job_data.get('title', 'New opportunity')}",
                    body=f"{job_data.get('company', 'Unknown')} - {match_score*100:.0f}% match",
                    priority=NotificationPriority.HIGH if match_score >= 0.8 else NotificationPriority.NORMAL,
                    data={"alert_id": alert.id, "job": job_data},
                )

    async def _handle_job_response_alert(self, alert: Alert, can_auto_act: bool):
        """Handle a job response alert (interview request, offer, etc)."""
        # These are always high priority - notify immediately
        if NOTIFICATIONS_AVAILABLE:
            await notify(
                title=alert.title,
                body=alert.message,
                priority=NotificationPriority.CRITICAL if "offer" in alert.title.lower() else NotificationPriority.HIGH,
                data={"alert_id": alert.id},
            )

    async def _handle_email_alert(self, alert: Alert, can_auto_act: bool):
        """Handle an important email alert."""
        if NOTIFICATIONS_AVAILABLE:
            await notify(
                title=alert.title,
                body=alert.message[:200],
                priority=NotificationPriority.HIGH,
                data={"alert_id": alert.id, "email_id": alert.data.get("email_id")},
            )

    async def _handle_calendar_alert(self, alert: Alert, can_auto_act: bool):
        """Handle a calendar reminder alert."""
        if NOTIFICATIONS_AVAILABLE:
            await notify(
                title=alert.title,
                body=alert.message,
                priority=NotificationPriority.HIGH,
                data={"alert_id": alert.id, "event": alert.data.get("event")},
            )

    async def _handle_briefing_alert(self, alert: Alert):
        """Handle the daily briefing."""
        # Daily briefings are always sent as notifications
        if NOTIFICATIONS_AVAILABLE:
            await notify(
                title=alert.title,
                body=alert.message,
                priority=NotificationPriority.NORMAL,
                icon="📊",
                data=alert.data,
            )

    def get_pending_alerts(self) -> List[Alert]:
        """Get alerts pending manual review."""
        return self._pending_alerts.copy()

    def dismiss_alert(self, alert_id: str):
        """Dismiss a pending alert."""
        self._pending_alerts = [a for a in self._pending_alerts if a.id != alert_id]


class AgentCollaborationHub:
    """Central hub for agent collaboration.

    Provides the high-level interface for:
    - Routing requests to the right agent
    - Coordinating multi-agent tasks
    - Tracking collaborative work
    """

    def __init__(self):
        self.learning_bridge = AgentLearningBridge()
        self.daemon_bridge = AgentDaemonBridge()
        self._agents: Dict[str, Any] = {}
        self._active_collaborations: Dict[str, Dict] = {}

    def register_agent(self, agent_id: str, agent: Any):
        """Register an agent with the hub."""
        self._agents[agent_id] = agent

        # Set up cross-references if both agents exist
        if "jarvis" in self._agents and "ultron" in self._agents:
            self.daemon_bridge.jarvis = self._agents["jarvis"]
            self.daemon_bridge.ultron = self._agents["ultron"]

        logger.info(f"Registered agent: {agent_id}")

    def start(self):
        """Start the collaboration hub."""
        self.daemon_bridge.setup()
        logger.info("AgentCollaborationHub started")

    async def route_message(
        self,
        message: str,
        user_id: str,
        preferred_agent: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Route a message to the most appropriate agent.

        If preferred_agent is specified, routes there directly.
        Otherwise, analyzes the message to determine the best agent.
        """
        # Determine target agent
        if preferred_agent and preferred_agent in self._agents:
            target_agent = preferred_agent
        else:
            target_agent = self._determine_best_agent(message)

        agent = self._agents.get(target_agent)
        if not agent:
            return {
                "status": "error",
                "error": f"No agent available: {target_agent}",
            }

        # Add learned context to the request
        learned = self.learning_bridge.get_learned_context()
        full_context = context or {}
        full_context["learned_context"] = learned

        # Process message
        result = await agent.process_message(message, full_context)

        # Record for learning
        response_text = result.get("response", "")
        interaction_id = await self.learning_bridge.record_interaction(
            agent_id=target_agent,
            message=message,
            response=response_text,
            context=full_context,
        )

        result["interaction_id"] = interaction_id
        result["agent_id"] = target_agent

        return result

    def _determine_best_agent(self, message: str) -> str:
        """Determine which agent should handle this message."""
        message_lower = message.lower()

        # Keywords that suggest Ultron (autonomous tasks)
        ultron_keywords = [
            "optimize", "automate", "analyze", "scan", "monitor",
            "background", "autonomous", "batch", "efficiency",
            "apply to jobs", "auto", "schedule", "track",
        ]

        # Keywords that suggest Jarvis (user-facing)
        jarvis_keywords = [
            "explain", "help", "show", "tell me", "what is",
            "how do i", "can you", "please", "thanks",
            "schedule", "remind", "note",
        ]

        ultron_score = sum(1 for kw in ultron_keywords if kw in message_lower)
        jarvis_score = sum(1 for kw in jarvis_keywords if kw in message_lower)

        if ultron_score > jarvis_score:
            return "ultron"
        else:
            return "jarvis"  # Default to Jarvis

    async def start_collaboration(
        self,
        goal: str,
        agents: List[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Start a collaborative task between agents."""
        import uuid
        collab_id = str(uuid.uuid4())[:12]

        self._active_collaborations[collab_id] = {
            "goal": goal,
            "agents": agents,
            "context": context,
            "started_at": datetime.utcnow().isoformat(),
            "status": "active",
            "results": {},
        }

        logger.info(f"Started collaboration {collab_id}: {goal}")

        return collab_id

    async def submit_feedback(
        self,
        interaction_id: str,
        accepted: bool,
        reason: str = "",
    ):
        """Submit user feedback on an interaction."""
        if accepted:
            await self.learning_bridge.record_acceptance(interaction_id)
        else:
            await self.learning_bridge.record_rejection(interaction_id, reason)

    async def submit_correction(
        self,
        original: str,
        corrected: str,
        agent_id: str = "",
    ):
        """Submit a correction to learn from."""
        await self.learning_bridge.record_correction(original, corrected, agent_id)


# Global hub instance
_collaboration_hub: Optional[AgentCollaborationHub] = None


def get_collaboration_hub() -> AgentCollaborationHub:
    """Get the global collaboration hub."""
    global _collaboration_hub
    if _collaboration_hub is None:
        _collaboration_hub = AgentCollaborationHub()
    return _collaboration_hub


def start_collaboration_hub():
    """Start the collaboration hub."""
    hub = get_collaboration_hub()
    hub.start()
    return hub
