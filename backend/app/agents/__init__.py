"""Multi-agent infrastructure for the Nexus AI system.

This module provides the core components for building and managing
multiple AI agents that can communicate, collaborate, and delegate tasks.

Components:
- BaseAgent: Abstract base class for all agents
- MessageBus: Inter-agent communication infrastructure
- AgentRegistry: Singleton registry for agent management
- SharedContext: Thread-safe shared memory/context
- TaskQueue: Priority-based background task processing

Usage:
    from app.agents import (
        BaseAgent, AgentConfig,
        MessageBus, MessageType, AgentMessage,
        get_registry,
        get_shared_context,
        get_task_queue, BackgroundTask, TaskPriority
    )

    # Create an agent
    class MyAgent(BaseAgent):
        async def process_message(self, message, context):
            return {"response": "Hello!", "status": "success"}

        async def handle_delegation(self, task, from_agent):
            return {"status": "success", "result": "Done"}

    # Register the agent
    registry = get_registry()
    agent = MyAgent(AgentConfig(name="MyAgent", capabilities=["chat"]))
    registry.register(agent)

    # Send messages between agents
    bus = registry.get_message_bus()
    await bus.publish(AgentMessage(
        from_agent="agent-1",
        to_agent="agent-2",
        type=MessageType.REQUEST,
        content={"query": "What's the weather?"}
    ))
"""

from .base import (
    AgentConfig,
    BaseAgent,
)
from .context import (
    ContextEntry,
    ConversationEntry,
    SharedContext,
    get_shared_context,
)
from .message_bus import (
    AgentMessage,
    MessageBus,
    MessagePriority,
    MessageType,
)
from .registry import (
    AgentRegistry,
    get_registry,
)
from .task_queue import (
    BackgroundTask,
    TaskHandler,
    TaskPriority,
    TaskQueue,
    TaskStatus,
    get_task_queue,
)

# Import integration layer for connecting agents with learning, daemon, etc.
try:
    from .integration import (
        AgentCollaborationHub,
        AgentLearningBridge,
        AgentDaemonBridge,
        get_collaboration_hub,
        start_collaboration_hub,
    )
    INTEGRATION_AVAILABLE = True
except ImportError:
    INTEGRATION_AVAILABLE = False
    AgentCollaborationHub = None
    get_collaboration_hub = None
    start_collaboration_hub = None

# Import Jarvis and Ultron agents
try:
    from .jarvis import JarvisAgent
    from .ultron import UltronAgent
    AGENTS_AVAILABLE = True
except ImportError:
    AGENTS_AVAILABLE = False
    JarvisAgent = None
    UltronAgent = None


def initialize_agents():
    """Initialize and register Jarvis and Ultron agents with the collaboration hub.

    This should be called during application startup to fully wire up the agents.

    Returns:
        Tuple of (JarvisAgent, UltronAgent, CollaborationHub)
    """
    if not AGENTS_AVAILABLE or not INTEGRATION_AVAILABLE:
        return None, None, None

    # Get or create the collaboration hub
    hub = get_collaboration_hub()

    # Create agent instances
    jarvis = JarvisAgent()
    ultron = UltronAgent()

    # Register with the hub
    hub.register_agent("jarvis", jarvis)
    hub.register_agent("ultron", ultron)

    # Start the hub (sets up daemon bridge, etc.)
    hub.start()

    return jarvis, ultron, hub

__all__ = [
    # Base agent
    "AgentConfig",
    "BaseAgent",
    # Message bus
    "AgentMessage",
    "MessageBus",
    "MessagePriority",
    "MessageType",
    # Registry
    "AgentRegistry",
    "get_registry",
    # Context
    "ContextEntry",
    "ConversationEntry",
    "SharedContext",
    "get_shared_context",
    # Task queue
    "BackgroundTask",
    "TaskHandler",
    "TaskPriority",
    "TaskQueue",
    "TaskStatus",
    "get_task_queue",
    # Integration
    "AgentCollaborationHub",
    "AgentLearningBridge",
    "AgentDaemonBridge",
    "get_collaboration_hub",
    "start_collaboration_hub",
    "INTEGRATION_AVAILABLE",
    # Agents
    "JarvisAgent",
    "UltronAgent",
    "AGENTS_AVAILABLE",
    "initialize_agents",
]
