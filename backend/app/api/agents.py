"""API routes for multi-agent system.

This module provides endpoints for interacting with agents, managing delegations,
starting collaborations, and retrieving agent information and audit logs.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from pydantic import BaseModel

from app.schemas.agents import (
    AgentConversation,
    AgentInfo,
    AgentInfoDetailed,
    AgentMessage,
    AgentStatus,
    AuditAction,
    AuditLogEntry,
    AuditLogResponse,
    ChatRequest,
    ChatResponse,
    CollaborationRequest,
    CollaborationSession,
    DelegationRequest,
    DelegationResponse,
    TaskInfo,
    TaskPriority,
    TaskStatus,
)

# Import collaboration hub if available
try:
    from app.agents import get_collaboration_hub, INTEGRATION_AVAILABLE
    COLLAB_AVAILABLE = INTEGRATION_AVAILABLE
except ImportError:
    COLLAB_AVAILABLE = False
    get_collaboration_hub = None

# Import proactive engine if available
try:
    from app.agents.proactive import get_proactive_engine
    PROACTIVE_AVAILABLE = True
except ImportError:
    PROACTIVE_AVAILABLE = False
    get_proactive_engine = None

logger = logging.getLogger(__name__)


# Request/Response models for learning feedback
class FeedbackRequest(BaseModel):
    """Request to submit feedback on an interaction."""
    interaction_id: str
    accepted: bool
    reason: Optional[str] = ""


class CorrectionRequest(BaseModel):
    """Request to submit a correction for learning."""
    original: str
    corrected: str
    agent_id: Optional[str] = ""


class LearningStatsResponse(BaseModel):
    """Response with learning statistics."""
    total_entries: int
    by_category: dict
    by_feedback_type: dict
    avg_confidence: float
    high_confidence_count: int

router = APIRouter()

# In-memory storage for demo purposes
# In production, this would be replaced with database storage
_agents_registry: dict[str, AgentInfo] = {}
_tasks: dict[str, TaskInfo] = {}
_audit_logs: dict[str, list[AuditLogEntry]] = {}
_conversations: dict[str, AgentConversation] = {}
_collaboration_sessions: dict[str, CollaborationSession] = {}


def _get_or_create_default_agents() -> dict[str, AgentInfo]:
    """Initialize default agents if not already registered."""
    if not _agents_registry:
        _agents_registry["jarvis"] = AgentInfo(
            id="jarvis",
            name="JARVIS",
            autonomy_level=0.7,
            capabilities=[
                "chat",
                "task_management",
                "information_retrieval",
                "delegation",
                "scheduling",
            ],
            status=AgentStatus.ACTIVE,
            metadata={"persona": "Personal AI assistant"},
        )
        _agents_registry["ultron"] = AgentInfo(
            id="ultron",
            name="ULTRON",
            autonomy_level=0.75,  # 75% autonomy - user configurable
            capabilities=[
                "planning",
                "optimization",
                "monitoring",
                "autonomous_execution",
                "system_analysis",
            ],
            status=AgentStatus.ACTIVE,
            metadata={"persona": "Autonomous operations agent"},
        )
    return _agents_registry


def _log_audit(
    agent_id: str,
    action: AuditAction,
    description: str,
    details: dict = None,
    related_agent: str = None,
    related_task_id: str = None,
) -> AuditLogEntry:
    """Create an audit log entry."""
    entry = AuditLogEntry(
        id=str(uuid4()),
        agent_id=agent_id,
        action=action,
        description=description,
        timestamp=datetime.utcnow(),
        details=details or {},
        related_agent=related_agent,
        related_task_id=related_task_id,
    )
    if agent_id not in _audit_logs:
        _audit_logs[agent_id] = []
    _audit_logs[agent_id].append(entry)
    return entry


# Agent endpoints
@router.get(
    "/",
    response_model=List[AgentInfo],
    summary="List all agents",
    description="Returns a list of all registered agents with their current status and capabilities.",
)
async def list_agents() -> List[AgentInfo]:
    """List all registered agents.

    Returns:
        List of AgentInfo objects for all registered agents.
    """
    _get_or_create_default_agents()
    return list(_agents_registry.values())


@router.get(
    "/{agent_id}",
    response_model=AgentInfoDetailed,
    summary="Get agent details",
    description="Returns detailed information about a specific agent including persona and task statistics.",
)
async def get_agent(agent_id: str) -> AgentInfoDetailed:
    """Get detailed information about a specific agent.

    Args:
        agent_id: The unique identifier of the agent.

    Returns:
        Detailed agent information.

    Raises:
        HTTPException: If agent not found.
    """
    _get_or_create_default_agents()
    if agent_id not in _agents_registry:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    agent = _agents_registry[agent_id]

    # Count tasks for this agent
    agent_tasks = [t for t in _tasks.values() if t.assigned_to == agent_id]
    completed_count = len(
        [t for t in agent_tasks if t.status == TaskStatus.COMPLETED]
    )

    return AgentInfoDetailed(
        id=agent.id,
        name=agent.name,
        autonomy_level=agent.autonomy_level,
        capabilities=agent.capabilities,
        status=agent.status,
        metadata=agent.metadata,
        persona=agent.metadata.get("persona", "AI Assistant"),
        capabilities_detailed=[],  # Would be populated from agent config
        current_tasks=len(
            [t for t in agent_tasks if t.status in (TaskStatus.PENDING, TaskStatus.RUNNING)]
        ),
        total_tasks_completed=completed_count,
    )


@router.patch(
    "/{agent_id}/autonomy",
    response_model=AgentInfo,
    summary="Update agent autonomy level",
    description="Update the autonomy level for an agent (0.0 to 1.0). "
    "Higher values allow more autonomous actions without confirmation.",
)
async def update_autonomy(agent_id: str, level: float = Query(..., ge=0.0, le=1.0)) -> AgentInfo:
    """Update an agent's autonomy level.

    Args:
        agent_id: The agent ID (e.g., 'ultron', 'jarvis')
        level: Autonomy level from 0.0 (always confirm) to 1.0 (full autonomy)

    Returns:
        Updated agent info.
    """
    _get_or_create_default_agents()
    if agent_id not in _agents_registry:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    agent = _agents_registry[agent_id]
    agent.autonomy_level = level

    _log_audit(
        agent_id=agent_id,
        action=AuditAction.CONFIG_CHANGE,
        description=f"Autonomy level changed to {level * 100:.0f}%",
        details={"new_level": level},
    )

    logger.info(f"Agent {agent_id} autonomy level set to {level * 100:.0f}%")
    return agent


@router.post(
    "/{agent_id}/chat",
    response_model=ChatResponse,
    summary="Chat with agent",
    description="Send a message to a specific agent and receive a response. "
    "The agent may delegate to other agents if allowed.",
)
async def chat_with_agent(agent_id: str, request: ChatRequest) -> ChatResponse:
    """Chat with a specific agent.

    Args:
        agent_id: The unique identifier of the agent to chat with.
        request: Chat request containing the message and options.

    Returns:
        Chat response from the agent.

    Raises:
        HTTPException: If agent not found or unavailable.
    """
    _get_or_create_default_agents()
    if agent_id not in _agents_registry:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    agent = _agents_registry[agent_id]
    if agent.status == AgentStatus.OFFLINE:
        raise HTTPException(status_code=503, detail=f"Agent '{agent_id}' is offline")

    # Generate or use existing conversation ID
    conversation_id = request.conversation_id or str(uuid4())

    # Create or update conversation
    if conversation_id not in _conversations:
        _conversations[conversation_id] = AgentConversation(
            conversation_id=conversation_id,
            messages=[],
            participating_agents=[agent_id],
            started_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
        )

    conversation = _conversations[conversation_id]

    # Add user message
    user_message = AgentMessage(
        id=str(uuid4()),
        agent_id=agent_id,
        role="user",
        content=request.message,
        timestamp=datetime.utcnow(),
    )
    conversation.messages.append(user_message)

    # Log receipt
    _log_audit(
        agent_id=agent_id,
        action=AuditAction.MESSAGE_RECEIVED,
        description=f"Received message: {request.message[:100]}...",
        details={"conversation_id": conversation_id, "allow_delegation": request.allow_delegation},
    )

    # Use collaboration hub for actual agent interactions if available
    response_text = ""
    delegated_to = None
    interaction_id = None

    if COLLAB_AVAILABLE:
        try:
            hub = get_collaboration_hub()
            result = await hub.route_message(
                message=request.message,
                user_id=request.context.get("user_id", "") if request.context else "",
                preferred_agent=agent_id,
                context=request.context,
            )
            response_text = result.get("response", "")
            interaction_id = result.get("interaction_id")
            if result.get("delegated_to"):
                delegated_to = result.get("delegated_to")
        except Exception as e:
            logger.error(f"Collaboration hub error: {e}")
            response_text = ""

    # Fallback to placeholder if hub not available or failed
    if not response_text:
        response_text = f"Hello! I'm {agent.name}. I received your message: '{request.message}'. "
        response_text += "The full agent system is being initialized."

    # Add agent response
    agent_message = AgentMessage(
        id=str(uuid4()),
        agent_id=agent_id,
        role="assistant",
        content=response_text,
        timestamp=datetime.utcnow(),
    )
    conversation.messages.append(agent_message)
    conversation.last_activity = datetime.utcnow()

    # Log response
    _log_audit(
        agent_id=agent_id,
        action=AuditAction.MESSAGE_SENT,
        description=f"Sent response to conversation {conversation_id}",
        details={"conversation_id": conversation_id},
    )

    return ChatResponse(
        response=response_text,
        agent_id=agent_id,
        conversation_id=conversation_id,
        delegated_to=delegated_to,
        background_tasks=[],
        metadata={
            "model": "claude-3-haiku-20240307" if COLLAB_AVAILABLE else "placeholder",
            "interaction_id": interaction_id,
            "learning_enabled": COLLAB_AVAILABLE,
        },
    )


@router.post(
    "/delegate",
    response_model=DelegationResponse,
    summary="Delegate task between agents",
    description="Manually trigger delegation of a task from one agent to another.",
)
async def delegate_task(request: DelegationRequest) -> DelegationResponse:
    """Delegate a task from one agent to another.

    Args:
        request: Delegation request containing task details and agent IDs.

    Returns:
        Delegation response with task ID and status.

    Raises:
        HTTPException: If source or target agent not found.
    """
    _get_or_create_default_agents()

    # Validate agents
    if request.from_agent not in _agents_registry:
        raise HTTPException(
            status_code=404, detail=f"Source agent '{request.from_agent}' not found"
        )
    if request.to_agent not in _agents_registry:
        raise HTTPException(
            status_code=404, detail=f"Target agent '{request.to_agent}' not found"
        )

    target_agent = _agents_registry[request.to_agent]
    if target_agent.status == AgentStatus.OFFLINE:
        raise HTTPException(
            status_code=503, detail=f"Target agent '{request.to_agent}' is offline"
        )

    # Create task
    task_id = str(uuid4())
    task = TaskInfo(
        id=task_id,
        type="delegated",
        description=request.task,
        status=TaskStatus.PENDING,
        priority=TaskPriority(request.priority),
        assigned_to=request.to_agent,
        created_by=request.from_agent,
        created_at=datetime.utcnow(),
        metadata=request.context or {},
    )
    _tasks[task_id] = task

    # Log delegation
    _log_audit(
        agent_id=request.from_agent,
        action=AuditAction.TASK_DELEGATED,
        description=f"Delegated task to {request.to_agent}: {request.task[:100]}",
        details={"task_id": task_id, "priority": request.priority},
        related_agent=request.to_agent,
        related_task_id=task_id,
    )
    _log_audit(
        agent_id=request.to_agent,
        action=AuditAction.TASK_RECEIVED,
        description=f"Received delegated task from {request.from_agent}",
        details={"task_id": task_id, "priority": request.priority},
        related_agent=request.from_agent,
        related_task_id=task_id,
    )

    logger.info(
        f"Task {task_id} delegated from {request.from_agent} to {request.to_agent}"
    )

    return DelegationResponse(
        task_id=task_id,
        status="delegated",
        from_agent=request.from_agent,
        to_agent=request.to_agent,
        result=None,
    )


@router.get(
    "/{agent_id}/tasks",
    response_model=List[TaskInfo],
    summary="Get agent tasks",
    description="Returns pending and running tasks for a specific agent.",
)
async def get_agent_tasks(
    agent_id: str,
    status: Optional[TaskStatus] = Query(None, description="Filter by task status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of tasks"),
) -> List[TaskInfo]:
    """Get tasks assigned to a specific agent.

    Args:
        agent_id: The unique identifier of the agent.
        status: Optional filter by task status.
        limit: Maximum number of tasks to return.

    Returns:
        List of tasks assigned to the agent.

    Raises:
        HTTPException: If agent not found.
    """
    _get_or_create_default_agents()
    if agent_id not in _agents_registry:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    agent_tasks = [t for t in _tasks.values() if t.assigned_to == agent_id]

    if status:
        agent_tasks = [t for t in agent_tasks if t.status == status]

    # Sort by creation time (newest first) and limit
    agent_tasks.sort(key=lambda t: t.created_at, reverse=True)
    return agent_tasks[:limit]


@router.get(
    "/{agent_id}/audit",
    response_model=AuditLogResponse,
    summary="Get agent audit log",
    description="Returns the action audit log for a specific agent.",
)
async def get_agent_audit_log(
    agent_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Page size"),
    action: Optional[AuditAction] = Query(None, description="Filter by action type"),
) -> AuditLogResponse:
    """Get audit log for a specific agent.

    Args:
        agent_id: The unique identifier of the agent.
        page: Page number for pagination.
        page_size: Number of entries per page.
        action: Optional filter by action type.

    Returns:
        Paginated audit log entries.

    Raises:
        HTTPException: If agent not found.
    """
    _get_or_create_default_agents()
    if agent_id not in _agents_registry:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    entries = _audit_logs.get(agent_id, [])

    if action:
        entries = [e for e in entries if e.action == action]

    # Sort by timestamp (newest first)
    entries.sort(key=lambda e: e.timestamp, reverse=True)

    total_count = len(entries)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size

    return AuditLogResponse(
        entries=entries[start_idx:end_idx],
        total_count=total_count,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/collaborate",
    response_model=CollaborationSession,
    summary="Start collaborative task",
    description="Start a collaborative task between multiple agents.",
)
async def start_collaboration(request: CollaborationRequest) -> CollaborationSession:
    """Start a collaborative task between multiple agents.

    Args:
        request: Collaboration request with task and participating agents.

    Returns:
        Created collaboration session.

    Raises:
        HTTPException: If any participating agent not found.
    """
    _get_or_create_default_agents()

    # Validate all participating agents exist
    for aid in request.participating_agents:
        if aid not in _agents_registry:
            raise HTTPException(
                status_code=404, detail=f"Agent '{aid}' not found"
            )

    coordinator = request.coordinator or request.participating_agents[0]
    if coordinator not in request.participating_agents:
        raise HTTPException(
            status_code=400,
            detail="Coordinator must be one of the participating agents",
        )

    session_id = str(uuid4())
    session = CollaborationSession(
        id=session_id,
        task=request.task,
        participating_agents=request.participating_agents,
        coordinator=coordinator,
        strategy=request.strategy,
        status="active",
        created_at=datetime.utcnow(),
        messages=[],
        result=None,
    )
    _collaboration_sessions[session_id] = session

    # Log collaboration start for all agents
    for aid in request.participating_agents:
        _log_audit(
            agent_id=aid,
            action=AuditAction.COLLABORATION_STARTED,
            description=f"Joined collaboration session {session_id}",
            details={
                "session_id": session_id,
                "task": request.task,
                "strategy": request.strategy,
                "is_coordinator": aid == coordinator,
            },
        )

    logger.info(
        f"Collaboration session {session_id} started with agents: {request.participating_agents}"
    )

    return session


@router.get(
    "/conversations/{conversation_id}",
    response_model=AgentConversation,
    summary="Get conversation",
    description="Get a multi-agent conversation by ID.",
)
async def get_conversation(conversation_id: str) -> AgentConversation:
    """Get a conversation by ID.

    Args:
        conversation_id: The unique identifier of the conversation.

    Returns:
        The conversation with all messages.

    Raises:
        HTTPException: If conversation not found.
    """
    if conversation_id not in _conversations:
        raise HTTPException(
            status_code=404, detail=f"Conversation '{conversation_id}' not found"
        )

    return _conversations[conversation_id]


# ==================== Learning Feedback Endpoints ====================


@router.post(
    "/feedback",
    summary="Submit interaction feedback",
    description="Submit feedback on an agent interaction for learning. "
    "Helps agents improve over time based on what works and what doesn't.",
)
async def submit_feedback(request: FeedbackRequest) -> dict:
    """Submit feedback on an agent interaction.

    Args:
        request: Feedback containing interaction_id, accepted flag, and optional reason.

    Returns:
        Confirmation of feedback submission.
    """
    if not COLLAB_AVAILABLE:
        return {"status": "unavailable", "message": "Learning system not available"}

    hub = get_collaboration_hub()
    await hub.submit_feedback(
        interaction_id=request.interaction_id,
        accepted=request.accepted,
        reason=request.reason or "",
    )

    logger.info(
        f"Feedback submitted: {request.interaction_id} - "
        f"{'accepted' if request.accepted else 'rejected'}"
    )

    return {
        "status": "recorded",
        "interaction_id": request.interaction_id,
        "accepted": request.accepted,
        "message": "Feedback recorded for learning",
    }


@router.post(
    "/correction",
    summary="Submit a correction for learning",
    description="Submit a correction when an agent's response was wrong. "
    "The AI will learn from this to avoid the same mistake.",
)
async def submit_correction(request: CorrectionRequest) -> dict:
    """Submit a correction for the AI to learn from.

    Args:
        request: Correction containing original text, corrected text, and optional agent_id.

    Returns:
        Confirmation of correction submission.
    """
    if not COLLAB_AVAILABLE:
        return {"status": "unavailable", "message": "Learning system not available"}

    hub = get_collaboration_hub()
    await hub.submit_correction(
        original=request.original,
        corrected=request.corrected,
        agent_id=request.agent_id or "",
    )

    logger.info(f"Correction submitted: '{request.original[:50]}...' -> '{request.corrected[:50]}...'")

    return {
        "status": "learned",
        "message": "Correction recorded - I'll remember this for next time",
    }


@router.get(
    "/learning/stats",
    response_model=LearningStatsResponse,
    summary="Get learning statistics",
    description="Get statistics about what the AI has learned from interactions.",
)
async def get_learning_stats() -> LearningStatsResponse:
    """Get statistics about the learning system.

    Returns:
        Statistics including total entries, categories, and confidence levels.
    """
    try:
        from app.ai.learning import get_learning_engine
        engine = get_learning_engine()
        stats = engine.get_statistics()

        return LearningStatsResponse(
            total_entries=stats.get("total_entries", 0),
            by_category=stats.get("by_category", {}),
            by_feedback_type=stats.get("by_feedback_type", {}),
            avg_confidence=stats.get("avg_confidence", 0.0),
            high_confidence_count=stats.get("high_confidence_count", 0),
        )
    except ImportError:
        return LearningStatsResponse(
            total_entries=0,
            by_category={},
            by_feedback_type={},
            avg_confidence=0.0,
            high_confidence_count=0,
        )


@router.get(
    "/hub/status",
    summary="Get collaboration hub status",
    description="Get the status of the agent collaboration hub including "
    "connected systems and pending alerts.",
)
async def get_hub_status() -> dict:
    """Get the collaboration hub status.

    Returns:
        Status of the collaboration hub and connected systems.
    """
    status = {
        "collaboration_hub": COLLAB_AVAILABLE,
        "learning_enabled": False,
        "daemon_enabled": False,
        "notifications_enabled": False,
        "pending_alerts": 0,
    }

    if COLLAB_AVAILABLE:
        hub = get_collaboration_hub()
        pending = hub.daemon_bridge.get_pending_alerts()
        status["pending_alerts"] = len(pending)
        status["learning_enabled"] = hub.learning_bridge.learning_engine is not None
        status["daemon_enabled"] = hub.daemon_bridge._setup_complete

    try:
        from app.notifications import get_notification_manager
        status["notifications_enabled"] = get_notification_manager() is not None
    except ImportError:
        pass

    return status


# ==================== Proactive Suggestions Endpoints ====================


@router.get(
    "/proactive/suggestions",
    summary="Get proactive suggestions",
    description="Get AI-generated proactive suggestions. These are things the AI "
    "thinks you might want to know or do, without you having to ask.",
)
async def get_proactive_suggestions(
    limit: int = Query(10, ge=1, le=50, description="Maximum suggestions to return"),
    min_confidence: float = Query(0.5, ge=0.0, le=1.0, description="Minimum confidence threshold"),
) -> dict:
    """Get proactive suggestions from the AI.

    Returns:
        List of proactive suggestions sorted by priority and confidence.
    """
    if not PROACTIVE_AVAILABLE:
        return {"suggestions": [], "message": "Proactive engine not available"}

    engine = get_proactive_engine()
    suggestions = engine.get_active_suggestions(limit=limit, min_confidence=min_confidence)

    return {
        "suggestions": [s.to_dict() for s in suggestions],
        "count": len(suggestions),
        "message": "Here's what I think you should know" if suggestions else "No suggestions right now",
    }


@router.post(
    "/proactive/suggestions/{suggestion_id}/dismiss",
    summary="Dismiss a suggestion",
    description="Dismiss a proactive suggestion so it won't appear again.",
)
async def dismiss_suggestion(suggestion_id: str) -> dict:
    """Dismiss a proactive suggestion.

    Args:
        suggestion_id: The ID of the suggestion to dismiss.

    Returns:
        Confirmation of dismissal.
    """
    if not PROACTIVE_AVAILABLE:
        return {"status": "unavailable"}

    engine = get_proactive_engine()
    engine.dismiss_suggestion(suggestion_id)

    return {"status": "dismissed", "suggestion_id": suggestion_id}


@router.post(
    "/proactive/suggestions/{suggestion_id}/act",
    summary="Mark suggestion as acted upon",
    description="Mark a suggestion as acted upon to help improve future suggestions.",
)
async def act_on_suggestion(suggestion_id: str) -> dict:
    """Mark a suggestion as acted upon.

    Args:
        suggestion_id: The ID of the suggestion that was acted on.

    Returns:
        Confirmation.
    """
    if not PROACTIVE_AVAILABLE:
        return {"status": "unavailable"}

    engine = get_proactive_engine()
    engine.act_on_suggestion(suggestion_id)

    # Also record this as learning
    if COLLAB_AVAILABLE:
        hub = get_collaboration_hub()
        # Find the suggestion to record what was accepted
        for s in engine.suggestions:
            if s.id == suggestion_id:
                await hub.learning_bridge.record_interaction(
                    agent_id="proactive",
                    message=f"Suggestion: {s.title}",
                    response=s.description,
                    context={"type": s.type, "acted_upon": True},
                )
                break

    return {"status": "acted_upon", "suggestion_id": suggestion_id}
