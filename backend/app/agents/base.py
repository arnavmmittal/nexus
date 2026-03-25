"""Base agent class for the multi-agent system.

This module defines the abstract BaseAgent class that all agents must inherit from.
Each agent has a unique identity, persona, capabilities, and autonomy level.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for an agent."""

    agent_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = "Agent"
    persona: str = "You are a helpful AI assistant."
    autonomy_level: float = 0.5  # 0.0 = always confirm, 1.0 = fully autonomous
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not 0.0 <= self.autonomy_level <= 1.0:
            raise ValueError(f"autonomy_level must be between 0.0 and 1.0, got {self.autonomy_level}")


class BaseAgent(ABC):
    """Abstract base class for all agents in the multi-agent system.

    Each agent has:
    - A unique identifier (agent_id)
    - A display name (e.g., "JARVIS" or "ULTRON")
    - A persona defining its personality and behavior
    - An autonomy level determining how independently it can act
    - A list of capabilities it can perform

    Subclasses must implement:
    - process_message: Handle incoming messages
    - handle_delegation: Handle tasks delegated from other agents
    """

    def __init__(self, config: AgentConfig):
        """Initialize the agent with configuration.

        Args:
            config: AgentConfig containing agent settings
        """
        self._config = config
        self._agent_id = config.agent_id
        self._name = config.name
        self._persona = config.persona
        self._autonomy_level = config.autonomy_level
        self._capabilities = config.capabilities.copy()
        self._metadata = config.metadata.copy()
        self._active = True

        logger.info(
            f"Agent initialized: {self._name} (id={self._agent_id}, "
            f"autonomy={self._autonomy_level}, capabilities={self._capabilities})"
        )

    @property
    def agent_id(self) -> str:
        """Unique identifier for this agent."""
        return self._agent_id

    @property
    def name(self) -> str:
        """Display name for this agent."""
        return self._name

    @property
    def persona(self) -> str:
        """System prompt personality for this agent."""
        return self._persona

    @property
    def autonomy_level(self) -> float:
        """Autonomy level: 0.0 = always confirm, 1.0 = fully autonomous."""
        return self._autonomy_level

    @property
    def capabilities(self) -> List[str]:
        """List of capabilities this agent possesses."""
        return self._capabilities.copy()

    @property
    def is_active(self) -> bool:
        """Whether this agent is currently active."""
        return self._active

    def activate(self) -> None:
        """Activate this agent."""
        self._active = True
        logger.info(f"Agent {self._name} activated")

    def deactivate(self) -> None:
        """Deactivate this agent."""
        self._active = False
        logger.info(f"Agent {self._name} deactivated")

    def can_handle(self, task_type: str) -> bool:
        """Check if this agent can handle a specific task type.

        Args:
            task_type: The type of task to check

        Returns:
            True if this agent has the capability to handle the task
        """
        # Check exact match first
        if task_type in self._capabilities:
            return True

        # Check for wildcard capabilities (e.g., "code:*" matches "code:review")
        for capability in self._capabilities:
            if capability.endswith("*"):
                prefix = capability[:-1]
                if task_type.startswith(prefix):
                    return True

        return False

    def get_system_prompt(self) -> str:
        """Generate the full system prompt for this agent.

        Returns:
            Complete system prompt including persona and capabilities
        """
        capabilities_str = ", ".join(self._capabilities) if self._capabilities else "general assistance"

        return f"""{self._persona}

Agent Identity:
- Name: {self._name}
- ID: {self._agent_id}
- Capabilities: {capabilities_str}
- Autonomy Level: {self._autonomy_level:.1%}

Operating Guidelines:
- When autonomy level is low (<0.3), always seek confirmation before taking actions.
- When autonomy level is high (>0.7), proceed independently but report outcomes.
- Collaborate with other agents when tasks fall outside your capabilities.
- Maintain clear communication about your actions and reasoning.
"""

    def requires_confirmation(self, action_risk: float = 0.5) -> bool:
        """Determine if an action requires user confirmation.

        Args:
            action_risk: Risk level of the action (0.0 = safe, 1.0 = risky)

        Returns:
            True if confirmation should be requested
        """
        # Higher autonomy means less need for confirmation
        # Higher risk means more need for confirmation
        threshold = self._autonomy_level * (1 - action_risk * 0.5)
        return action_risk > threshold

    @abstractmethod
    async def process_message(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process an incoming message and generate a response.

        Args:
            message: The message content to process
            context: Optional context dictionary with additional information

        Returns:
            Response dictionary containing at minimum:
            - 'response': The agent's response text
            - 'status': 'success' or 'error'

        Raises:
            NotImplementedError: If not implemented by subclass
        """
        pass

    @abstractmethod
    async def handle_delegation(
        self,
        task: Dict[str, Any],
        from_agent: str
    ) -> Dict[str, Any]:
        """Handle a task delegated from another agent.

        Args:
            task: Task dictionary containing:
                - 'type': The task type
                - 'payload': Task-specific data
                - 'priority': Task priority
            from_agent: ID of the agent delegating the task

        Returns:
            Result dictionary containing:
            - 'status': 'success', 'error', or 'declined'
            - 'result': Task result if successful
            - 'error': Error message if failed

        Raises:
            NotImplementedError: If not implemented by subclass
        """
        pass

    def __repr__(self) -> str:
        """String representation of the agent."""
        return (
            f"{self.__class__.__name__}("
            f"id='{self._agent_id}', "
            f"name='{self._name}', "
            f"autonomy={self._autonomy_level}, "
            f"active={self._active})"
        )

    def __str__(self) -> str:
        """Human-readable string representation."""
        return f"{self._name} ({self._agent_id})"
