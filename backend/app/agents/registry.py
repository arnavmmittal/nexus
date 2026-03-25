"""Agent registry for managing multiple agents.

This module provides a singleton registry for registering, unregistering,
and discovering agents in the multi-agent system.
"""

import logging
from threading import Lock
from typing import Dict, List, Optional, Type

from .base import BaseAgent
from .message_bus import MessageBus

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Singleton registry for managing agents in the system.

    Provides methods to:
    - Register and unregister agents
    - Find agents by ID or capability
    - Access the shared message bus

    Usage:
        registry = AgentRegistry()
        registry.register(my_agent)
        agent = registry.get("agent-id")
    """

    _instance: Optional["AgentRegistry"] = None
    _lock: Lock = Lock()

    def __new__(cls) -> "AgentRegistry":
        """Ensure only one instance exists (singleton pattern)."""
        if cls._instance is None:
            with cls._lock:
                # Double-check locking
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self):
        """Initialize the registry if not already initialized."""
        if self._initialized:
            return

        self._agents: Dict[str, BaseAgent] = {}
        self._message_bus: MessageBus = MessageBus()
        self._agent_lock: Lock = Lock()
        self._initialized = True

        logger.info("AgentRegistry initialized")

    def register(self, agent: BaseAgent) -> None:
        """Register an agent with the registry.

        Args:
            agent: The agent to register

        Raises:
            ValueError: If an agent with the same ID is already registered
        """
        with self._agent_lock:
            if agent.agent_id in self._agents:
                raise ValueError(
                    f"Agent with ID '{agent.agent_id}' is already registered"
                )

            self._agents[agent.agent_id] = agent
            logger.info(
                f"Registered agent: {agent.name} (id={agent.agent_id}, "
                f"capabilities={agent.capabilities})"
            )

    def unregister(self, agent_id: str) -> Optional[BaseAgent]:
        """Unregister an agent from the registry.

        Args:
            agent_id: The ID of the agent to unregister

        Returns:
            The unregistered agent, or None if not found
        """
        with self._agent_lock:
            agent = self._agents.pop(agent_id, None)
            if agent:
                agent.deactivate()
                logger.info(f"Unregistered agent: {agent.name} (id={agent_id})")
            else:
                logger.warning(f"Attempted to unregister unknown agent: {agent_id}")
            return agent

    def get(self, agent_id: str) -> Optional[BaseAgent]:
        """Get an agent by its ID.

        Args:
            agent_id: The ID of the agent to retrieve

        Returns:
            The agent if found, None otherwise
        """
        with self._agent_lock:
            return self._agents.get(agent_id)

    def get_by_name(self, name: str) -> Optional[BaseAgent]:
        """Get an agent by its display name.

        Args:
            name: The display name of the agent

        Returns:
            The first agent with matching name, or None
        """
        with self._agent_lock:
            for agent in self._agents.values():
                if agent.name.lower() == name.lower():
                    return agent
            return None

    def get_all(self, active_only: bool = False) -> List[BaseAgent]:
        """Get all registered agents.

        Args:
            active_only: If True, only return active agents

        Returns:
            List of all registered agents
        """
        with self._agent_lock:
            agents = list(self._agents.values())
            if active_only:
                agents = [a for a in agents if a.is_active]
            return agents

    def find_capable(self, task_type: str, active_only: bool = True) -> List[BaseAgent]:
        """Find agents capable of handling a specific task type.

        Args:
            task_type: The type of task to find agents for
            active_only: If True, only return active agents

        Returns:
            List of agents that can handle the task type, sorted by
            specificity of capability match
        """
        with self._agent_lock:
            capable_agents = []

            for agent in self._agents.values():
                if active_only and not agent.is_active:
                    continue

                if agent.can_handle(task_type):
                    # Calculate specificity score (exact match = 2, wildcard = 1)
                    specificity = 2 if task_type in agent.capabilities else 1
                    capable_agents.append((agent, specificity))

            # Sort by specificity (higher first), then by autonomy (higher first)
            capable_agents.sort(
                key=lambda x: (x[1], x[0].autonomy_level),
                reverse=True
            )

            result = [agent for agent, _ in capable_agents]

            logger.debug(
                f"Found {len(result)} capable agents for task type '{task_type}': "
                f"{[a.name for a in result]}"
            )

            return result

    def get_message_bus(self) -> MessageBus:
        """Get the shared message bus.

        Returns:
            The MessageBus instance for inter-agent communication
        """
        return self._message_bus

    def count(self, active_only: bool = False) -> int:
        """Get the number of registered agents.

        Args:
            active_only: If True, only count active agents

        Returns:
            Number of registered agents
        """
        with self._agent_lock:
            if active_only:
                return sum(1 for a in self._agents.values() if a.is_active)
            return len(self._agents)

    def clear(self) -> None:
        """Remove all registered agents.

        Warning: This is primarily for testing purposes.
        """
        with self._agent_lock:
            for agent in self._agents.values():
                agent.deactivate()
            self._agents.clear()
            logger.warning("AgentRegistry cleared - all agents unregistered")

    async def shutdown(self) -> None:
        """Shutdown the registry and all components."""
        logger.info("Shutting down AgentRegistry")

        # Shutdown message bus
        await self._message_bus.shutdown()

        # Deactivate all agents
        with self._agent_lock:
            for agent in self._agents.values():
                agent.deactivate()

        logger.info("AgentRegistry shutdown complete")

    def __repr__(self) -> str:
        """String representation of the registry."""
        return f"AgentRegistry(agents={self.count()}, active={self.count(active_only=True)})"

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance.

        Warning: This is primarily for testing purposes.
        """
        with cls._lock:
            if cls._instance is not None:
                cls._instance._agents.clear()
            cls._instance = None


def get_registry() -> AgentRegistry:
    """Get the global agent registry instance.

    Returns:
        The singleton AgentRegistry instance
    """
    return AgentRegistry()
