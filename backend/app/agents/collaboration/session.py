"""Collaboration session management for multi-agent coordination.

This module provides session tracking and management for collaborative
tasks between Jarvis and Ultron.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from ..message_bus import AgentMessage, MessageBus, MessageType, MessagePriority

logger = logging.getLogger(__name__)


class CollaborationMode(Enum):
    """Modes of collaboration between agents."""

    PARALLEL = "parallel"      # Both agents work simultaneously on different aspects
    SEQUENTIAL = "sequential"  # One agent works after another
    DEBATE = "debate"          # Agents discuss and debate to reach consensus
    DELEGATION = "delegation"  # One agent delegates specific tasks to another


class SessionStatus(Enum):
    """Status of a collaboration session."""

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class CollaborationSession:
    """Represents a collaboration session between agents.

    A session tracks the goal, participating agents, messages exchanged,
    and results of a multi-agent collaboration.
    """

    id: UUID = field(default_factory=uuid4)
    goal: str = ""
    mode: CollaborationMode = CollaborationMode.PARALLEL
    participating_agents: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: SessionStatus = SessionStatus.ACTIVE
    messages: List[Dict[str, Any]] = field(default_factory=list)
    results: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_message(self, from_agent: str, content: str, intent: str = "general") -> None:
        """Add a message to the session.

        Args:
            from_agent: ID of the agent sending the message
            content: Message content
            intent: Intent of the message (propose, agree, disagree, clarify, conclude)
        """
        message = {
            "id": str(uuid4()),
            "from_agent": from_agent,
            "content": content,
            "intent": intent,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.messages.append(message)
        self.updated_at = datetime.now(timezone.utc)

    def set_result(self, agent_id: str, result: Any) -> None:
        """Set the result for a specific agent.

        Args:
            agent_id: ID of the agent
            result: The result to store
        """
        self.results[agent_id] = {
            "data": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.updated_at = datetime.now(timezone.utc)

    def get_result(self, agent_id: str) -> Optional[Any]:
        """Get the result for a specific agent.

        Args:
            agent_id: ID of the agent

        Returns:
            The result data if exists, None otherwise
        """
        result = self.results.get(agent_id)
        return result["data"] if result else None

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary representation."""
        return {
            "id": str(self.id),
            "goal": self.goal,
            "mode": self.mode.value,
            "participating_agents": self.participating_agents,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "status": self.status.value,
            "messages": self.messages,
            "results": self.results,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CollaborationSession":
        """Create session from dictionary representation."""
        return cls(
            id=UUID(data["id"]),
            goal=data["goal"],
            mode=CollaborationMode(data["mode"]),
            participating_agents=data["participating_agents"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            status=SessionStatus(data["status"]),
            messages=data["messages"],
            results=data["results"],
            metadata=data.get("metadata", {}),
        )


class CollaborationManager:
    """Manages collaboration sessions between agents.

    Handles creating, tracking, and coordinating multi-agent collaborations
    through the message bus.
    """

    def __init__(self, message_bus: MessageBus, agent_registry: Any):
        """Initialize the collaboration manager.

        Args:
            message_bus: The message bus for inter-agent communication
            agent_registry: The agent registry for looking up agents
        """
        self.message_bus = message_bus
        self.agent_registry = agent_registry
        self.active_sessions: Dict[UUID, CollaborationSession] = {}
        self._session_history: List[CollaborationSession] = []
        self._max_history = 100

        logger.info("CollaborationManager initialized")

    async def start_collaboration(
        self,
        goal: str,
        agents: List[str],
        mode: CollaborationMode,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CollaborationSession:
        """Start a new collaboration session.

        Args:
            goal: The goal of the collaboration
            agents: List of agent IDs to participate
            mode: The collaboration mode
            metadata: Optional additional metadata

        Returns:
            The created collaboration session
        """
        session = CollaborationSession(
            goal=goal,
            mode=mode,
            participating_agents=agents,
            metadata=metadata or {},
        )

        self.active_sessions[session.id] = session

        logger.info(
            f"Started collaboration session {session.id}: "
            f"goal='{goal}', mode={mode.value}, agents={agents}"
        )

        # Notify participating agents
        for agent_id in agents:
            message = AgentMessage(
                from_agent="collaboration_manager",
                to_agent=agent_id,
                type=MessageType.INFORM,
                content={
                    "event": "collaboration_started",
                    "session_id": str(session.id),
                    "goal": goal,
                    "mode": mode.value,
                    "participants": agents,
                },
                priority=MessagePriority.HIGH,
            )
            await self.message_bus.publish(message)

        return session

    async def add_message(
        self,
        session_id: UUID,
        from_agent: str,
        content: str,
        intent: str = "general",
    ) -> None:
        """Add a message to a collaboration session.

        Args:
            session_id: The session to add the message to
            from_agent: ID of the sending agent
            content: Message content
            intent: Intent of the message

        Raises:
            ValueError: If session not found
        """
        session = self.active_sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        session.add_message(from_agent, content, intent)

        logger.debug(
            f"Added message to session {session_id} from {from_agent}: "
            f"intent={intent}"
        )

        # Broadcast message to other participants
        for agent_id in session.participating_agents:
            if agent_id != from_agent:
                message = AgentMessage(
                    from_agent=from_agent,
                    to_agent=agent_id,
                    type=MessageType.DEBATE,
                    content={
                        "session_id": str(session_id),
                        "message": content,
                        "intent": intent,
                    },
                    priority=MessagePriority.NORMAL,
                )
                await self.message_bus.publish(message)

    async def get_session(self, session_id: UUID) -> Optional[CollaborationSession]:
        """Get a collaboration session by ID.

        Args:
            session_id: The session ID

        Returns:
            The session if found, None otherwise
        """
        return self.active_sessions.get(session_id)

    async def end_collaboration(
        self,
        session_id: UUID,
        result: Dict[str, Any],
        status: SessionStatus = SessionStatus.COMPLETED,
    ) -> CollaborationSession:
        """End a collaboration session.

        Args:
            session_id: The session to end
            result: The final result of the collaboration
            status: The final status of the session

        Returns:
            The ended session

        Raises:
            ValueError: If session not found
        """
        session = self.active_sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        session.status = status
        session.results["final"] = {
            "data": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        session.updated_at = datetime.now(timezone.utc)

        # Move to history
        del self.active_sessions[session_id]
        self._session_history.append(session)
        if len(self._session_history) > self._max_history:
            self._session_history = self._session_history[-self._max_history:]

        logger.info(
            f"Ended collaboration session {session_id}: "
            f"status={status.value}"
        )

        # Notify participating agents
        for agent_id in session.participating_agents:
            message = AgentMessage(
                from_agent="collaboration_manager",
                to_agent=agent_id,
                type=MessageType.INFORM,
                content={
                    "event": "collaboration_ended",
                    "session_id": str(session_id),
                    "status": status.value,
                    "result": result,
                },
                priority=MessagePriority.HIGH,
            )
            await self.message_bus.publish(message)

        return session

    async def pause_collaboration(self, session_id: UUID) -> CollaborationSession:
        """Pause an active collaboration session.

        Args:
            session_id: The session to pause

        Returns:
            The paused session

        Raises:
            ValueError: If session not found or not active
        """
        session = self.active_sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        if session.status != SessionStatus.ACTIVE:
            raise ValueError(f"Session {session_id} is not active")

        session.status = SessionStatus.PAUSED
        session.updated_at = datetime.now(timezone.utc)

        logger.info(f"Paused collaboration session {session_id}")

        return session

    async def resume_collaboration(self, session_id: UUID) -> CollaborationSession:
        """Resume a paused collaboration session.

        Args:
            session_id: The session to resume

        Returns:
            The resumed session

        Raises:
            ValueError: If session not found or not paused
        """
        session = self.active_sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        if session.status != SessionStatus.PAUSED:
            raise ValueError(f"Session {session_id} is not paused")

        session.status = SessionStatus.ACTIVE
        session.updated_at = datetime.now(timezone.utc)

        logger.info(f"Resumed collaboration session {session_id}")

        return session

    def get_active_sessions(self) -> List[CollaborationSession]:
        """Get all active collaboration sessions.

        Returns:
            List of active sessions
        """
        return list(self.active_sessions.values())

    def get_session_history(
        self,
        limit: int = 50,
        agent_filter: Optional[str] = None,
    ) -> List[CollaborationSession]:
        """Get session history.

        Args:
            limit: Maximum number of sessions to return
            agent_filter: Optional agent ID to filter by

        Returns:
            List of past sessions
        """
        sessions = self._session_history.copy()

        if agent_filter:
            sessions = [
                s for s in sessions
                if agent_filter in s.participating_agents
            ]

        return sessions[-limit:]
