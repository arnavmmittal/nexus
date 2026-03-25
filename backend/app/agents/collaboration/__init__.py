"""Agent collaboration module for multi-agent coordination.

This module provides the infrastructure for Jarvis and Ultron to work together,
including session management, collaboration protocols, orchestration, and dialogue.
"""

from .session import (
    CollaborationMode,
    CollaborationSession,
    CollaborationManager,
)
from .protocols import (
    DebateProtocol,
    DelegationProtocol,
    ParallelExecutionProtocol,
)
from .orchestrator import AgentOrchestrator
from .dialogue import DialogueTurn, AgentDialogue

__all__ = [
    # Session management
    "CollaborationMode",
    "CollaborationSession",
    "CollaborationManager",
    # Protocols
    "DebateProtocol",
    "DelegationProtocol",
    "ParallelExecutionProtocol",
    # Orchestration
    "AgentOrchestrator",
    # Dialogue
    "DialogueTurn",
    "AgentDialogue",
]
