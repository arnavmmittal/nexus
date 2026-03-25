"""Pydantic schemas for multi-agent system.

This module contains all schemas related to agents, tasks, delegation,
collaboration, and audit logging.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# Enums
class AgentStatus(str, Enum):
    """Agent operational status."""

    ACTIVE = "active"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Task priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class AuditAction(str, Enum):
    """Types of audit log actions."""

    MESSAGE_RECEIVED = "message_received"
    MESSAGE_SENT = "message_sent"
    TASK_DELEGATED = "task_delegated"
    TASK_RECEIVED = "task_received"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    CAPABILITY_USED = "capability_used"
    COLLABORATION_STARTED = "collaboration_started"
    COLLABORATION_ENDED = "collaboration_ended"
    CONFIG_CHANGE = "config_change"
    ERROR = "error"


# Agent-related schemas
class AgentCapability(BaseModel):
    """Schema for agent capability."""

    name: str = Field(..., description="Capability name/identifier")
    description: str = Field(..., description="Human-readable description")
    risk_level: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Risk level: 0.0=safe, 1.0=risky",
    )
    requires_confirmation: bool = Field(
        default=False, description="Whether this capability always requires user confirmation"
    )


class AgentInfo(BaseModel):
    """Schema for agent information."""

    id: str = Field(..., description="Unique agent identifier")
    name: str = Field(..., description="Agent display name")
    autonomy_level: float = Field(
        ..., ge=0.0, le=1.0, description="Agent autonomy level"
    )
    capabilities: List[str] = Field(
        default_factory=list, description="List of agent capabilities"
    )
    status: AgentStatus = Field(
        default=AgentStatus.ACTIVE, description="Current agent status"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional agent metadata"
    )

    class Config:
        use_enum_values = True


class AgentInfoDetailed(AgentInfo):
    """Extended agent information with additional details."""

    persona: str = Field(..., description="Agent persona/system prompt")
    capabilities_detailed: List[AgentCapability] = Field(
        default_factory=list, description="Detailed capability information"
    )
    current_tasks: int = Field(default=0, description="Number of current tasks")
    total_tasks_completed: int = Field(
        default=0, description="Total tasks completed by this agent"
    )


# Message-related schemas
class AgentMessage(BaseModel):
    """Schema for a message in agent conversation."""

    id: str = Field(..., description="Unique message identifier")
    agent_id: str = Field(..., description="ID of the agent that sent/received")
    role: Literal["user", "assistant", "system"] = Field(
        ..., description="Message role"
    )
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Message timestamp"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional message metadata"
    )


class ChatRequest(BaseModel):
    """Schema for chat request to an agent."""

    message: str = Field(..., min_length=1, description="User message")
    agent_id: str = Field(
        default="jarvis", description="Target agent ID (default: jarvis)"
    )
    conversation_id: Optional[str] = Field(
        default=None, description="Conversation ID for context continuity"
    )
    allow_delegation: bool = Field(
        default=True, description="Allow agent to delegate to other agents"
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional context for the request"
    )


class ChatResponse(BaseModel):
    """Schema for chat response from an agent."""

    response: str = Field(..., description="Agent response text")
    agent_id: str = Field(..., description="ID of the responding agent")
    conversation_id: str = Field(..., description="Conversation ID")
    delegated_to: Optional[str] = Field(
        default=None, description="Agent ID if task was delegated"
    )
    background_tasks: List[str] = Field(
        default_factory=list, description="List of background task IDs spawned"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional response metadata"
    )


# Task-related schemas
class TaskInfo(BaseModel):
    """Schema for task information."""

    id: str = Field(..., description="Unique task identifier")
    type: str = Field(..., description="Task type")
    description: str = Field(..., description="Task description")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Task status")
    priority: TaskPriority = Field(
        default=TaskPriority.NORMAL, description="Task priority"
    )
    assigned_to: str = Field(..., description="Agent ID assigned to this task")
    created_by: Optional[str] = Field(
        default=None, description="Agent ID that created/delegated this task"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Task creation time"
    )
    started_at: Optional[datetime] = Field(
        default=None, description="Task start time"
    )
    completed_at: Optional[datetime] = Field(
        default=None, description="Task completion time"
    )
    result: Optional[Dict[str, Any]] = Field(
        default=None, description="Task result if completed"
    )
    error: Optional[str] = Field(default=None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional task metadata"
    )

    class Config:
        use_enum_values = True


class DelegationRequest(BaseModel):
    """Schema for task delegation request."""

    task: str = Field(..., description="Task description")
    from_agent: str = Field(..., description="Source agent ID")
    to_agent: str = Field(..., description="Target agent ID")
    priority: TaskPriority = Field(
        default=TaskPriority.NORMAL, description="Task priority"
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional task context"
    )
    wait_for_result: bool = Field(
        default=False, description="Wait for task completion before returning"
    )

    class Config:
        use_enum_values = True


class DelegationResponse(BaseModel):
    """Schema for delegation response."""

    task_id: str = Field(..., description="Created task ID")
    status: str = Field(..., description="Delegation status")
    from_agent: str = Field(..., description="Source agent ID")
    to_agent: str = Field(..., description="Target agent ID")
    result: Optional[Dict[str, Any]] = Field(
        default=None, description="Task result if wait_for_result was True"
    )


# Collaboration schemas
class CollaborationRequest(BaseModel):
    """Schema for starting a collaborative task."""

    task: str = Field(..., description="Task description")
    participating_agents: List[str] = Field(
        ..., min_items=2, description="List of agent IDs to participate"
    )
    coordinator: Optional[str] = Field(
        default=None, description="Agent ID to coordinate (defaults to first agent)"
    )
    strategy: Literal["sequential", "parallel", "consensus"] = Field(
        default="sequential", description="Collaboration strategy"
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional context"
    )


class CollaborationSession(BaseModel):
    """Schema for collaboration session."""

    id: str = Field(..., description="Session ID")
    task: str = Field(..., description="Task description")
    participating_agents: List[str] = Field(..., description="Participating agent IDs")
    coordinator: str = Field(..., description="Coordinating agent ID")
    strategy: str = Field(..., description="Collaboration strategy")
    status: str = Field(default="active", description="Session status")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Session creation time"
    )
    messages: List[AgentMessage] = Field(
        default_factory=list, description="Session messages"
    )
    result: Optional[Dict[str, Any]] = Field(
        default=None, description="Final result if completed"
    )


class AgentConversation(BaseModel):
    """Schema for multi-agent conversation."""

    conversation_id: str = Field(..., description="Conversation ID")
    messages: List[AgentMessage] = Field(
        default_factory=list, description="Conversation messages"
    )
    participating_agents: List[str] = Field(
        default_factory=list, description="Agents that participated"
    )
    started_at: datetime = Field(
        default_factory=datetime.utcnow, description="Conversation start time"
    )
    last_activity: datetime = Field(
        default_factory=datetime.utcnow, description="Last activity time"
    )


# Audit log schemas
class AuditLogEntry(BaseModel):
    """Schema for audit log entry."""

    id: str = Field(..., description="Unique entry identifier")
    agent_id: str = Field(..., description="Agent that performed the action")
    action: AuditAction = Field(..., description="Action type")
    description: str = Field(..., description="Human-readable description")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Entry timestamp"
    )
    details: Dict[str, Any] = Field(
        default_factory=dict, description="Additional action details"
    )
    related_agent: Optional[str] = Field(
        default=None, description="Related agent if applicable"
    )
    related_task_id: Optional[str] = Field(
        default=None, description="Related task ID if applicable"
    )

    class Config:
        use_enum_values = True


class AuditLogResponse(BaseModel):
    """Schema for audit log response."""

    entries: List[AuditLogEntry] = Field(
        default_factory=list, description="Audit log entries"
    )
    total_count: int = Field(..., description="Total number of entries")
    page: int = Field(default=1, description="Current page")
    page_size: int = Field(default=50, description="Page size")


# WebSocket-related schemas
class AgentWebSocketMessage(BaseModel):
    """Schema for WebSocket messages."""

    type: Literal[
        "agent_update",
        "task_update",
        "message",
        "delegation",
        "error",
        "ping",
        "pong",
    ] = Field(..., description="Message type")
    agent_id: Optional[str] = Field(default=None, description="Related agent ID")
    content: Optional[Any] = Field(default=None, description="Message content")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Message timestamp"
    )


# Ultron-specific schemas
class UltronPlanRequest(BaseModel):
    """Schema for Ultron plan request."""

    goal: str = Field(..., description="Goal to plan for")
    constraints: Optional[List[str]] = Field(
        default=None, description="Constraints to consider"
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional context"
    )
    max_steps: int = Field(default=10, ge=1, le=50, description="Maximum plan steps")


class UltronPlanStep(BaseModel):
    """Schema for a step in Ultron's plan."""

    step_number: int = Field(..., description="Step number")
    description: str = Field(..., description="Step description")
    agent: Optional[str] = Field(
        default=None, description="Agent to execute this step"
    )
    estimated_duration: Optional[str] = Field(
        default=None, description="Estimated duration"
    )
    dependencies: List[int] = Field(
        default_factory=list, description="Step dependencies (step numbers)"
    )
    risk_level: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Step risk level"
    )


class UltronPlanResponse(BaseModel):
    """Schema for Ultron plan response."""

    plan_id: str = Field(..., description="Plan ID")
    goal: str = Field(..., description="Original goal")
    steps: List[UltronPlanStep] = Field(..., description="Plan steps")
    estimated_total_duration: Optional[str] = Field(
        default=None, description="Total estimated duration"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Plan confidence score"
    )
    warnings: List[str] = Field(
        default_factory=list, description="Plan warnings"
    )


class UltronExecuteRequest(BaseModel):
    """Schema for Ultron execute request."""

    plan_id: Optional[str] = Field(
        default=None, description="Existing plan ID to execute"
    )
    goal: Optional[str] = Field(
        default=None, description="Goal to plan and execute (if no plan_id)"
    )
    auto_approve: bool = Field(
        default=False, description="Auto-approve intermediate steps"
    )
    notify_on_completion: bool = Field(
        default=True, description="Send notification on completion"
    )


class UltronExecuteResponse(BaseModel):
    """Schema for Ultron execute response."""

    execution_id: str = Field(..., description="Execution ID")
    plan_id: str = Field(..., description="Plan being executed")
    status: str = Field(..., description="Execution status")
    current_step: Optional[int] = Field(default=None, description="Current step")
    message: str = Field(..., description="Status message")


class UltronMonitoringStatus(BaseModel):
    """Schema for Ultron monitoring status."""

    is_active: bool = Field(..., description="Whether monitoring is active")
    started_at: Optional[datetime] = Field(
        default=None, description="Monitoring start time"
    )
    monitored_areas: List[str] = Field(
        default_factory=list, description="Areas being monitored"
    )
    last_check: Optional[datetime] = Field(
        default=None, description="Last check timestamp"
    )
    findings_count: int = Field(
        default=0, description="Number of findings since start"
    )


class UltronSuggestion(BaseModel):
    """Schema for Ultron proactive suggestion."""

    id: str = Field(..., description="Suggestion ID")
    type: Literal["optimization", "warning", "opportunity", "maintenance"] = Field(
        ..., description="Suggestion type"
    )
    title: str = Field(..., description="Suggestion title")
    description: str = Field(..., description="Detailed description")
    priority: TaskPriority = Field(..., description="Suggestion priority")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation time"
    )
    expires_at: Optional[datetime] = Field(
        default=None, description="Expiration time if applicable"
    )
    action_required: bool = Field(
        default=False, description="Whether action is required"
    )
    auto_executable: bool = Field(
        default=False, description="Whether Ultron can execute automatically"
    )

    class Config:
        use_enum_values = True


class UltronOptimizeRequest(BaseModel):
    """Schema for Ultron optimize request."""

    target: str = Field(..., description="What to optimize")
    constraints: Optional[List[str]] = Field(
        default=None, description="Optimization constraints"
    )
    dry_run: bool = Field(
        default=True, description="Preview changes without applying"
    )
