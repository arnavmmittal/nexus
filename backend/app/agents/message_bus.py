"""Inter-agent message bus for communication between agents.

This module provides the messaging infrastructure for agents to communicate,
delegate tasks, request information, and broadcast updates.
"""

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of messages that can be sent between agents."""

    DELEGATE = "delegate"      # Request another agent to handle a task
    INFORM = "inform"          # Share information without expecting response
    REQUEST = "request"        # Ask for information or action
    DEBATE = "debate"          # Engage in multi-agent discussion/reasoning
    RESPONSE = "response"      # Reply to a previous message
    BROADCAST = "broadcast"    # Message to all agents


class MessagePriority(Enum):
    """Priority levels for messages."""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class AgentMessage:
    """A message passed between agents.

    Attributes:
        id: Unique message identifier
        from_agent: ID of the sending agent
        to_agent: ID of the receiving agent (or "*" for broadcast)
        type: Type of message
        content: Message payload
        priority: Message priority level
        timestamp: When the message was created
        requires_response: Whether sender expects a reply
        correlation_id: ID linking related messages (e.g., request/response)
        metadata: Additional message metadata
    """

    from_agent: str
    to_agent: str
    type: MessageType
    content: Dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid4()))
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    requires_response: bool = False
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def create_response(
        self,
        from_agent: str,
        content: Dict[str, Any],
        priority: Optional[MessagePriority] = None
    ) -> "AgentMessage":
        """Create a response message to this message.

        Args:
            from_agent: ID of the responding agent
            content: Response content
            priority: Optional priority override

        Returns:
            New AgentMessage configured as a response
        """
        return AgentMessage(
            from_agent=from_agent,
            to_agent=self.from_agent,
            type=MessageType.RESPONSE,
            content=content,
            priority=priority or self.priority,
            correlation_id=self.id,
            requires_response=False,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary representation."""
        return {
            "id": self.id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "type": self.type.value,
            "content": self.content,
            "priority": self.priority.value,
            "timestamp": self.timestamp.isoformat(),
            "requires_response": self.requires_response,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        """Create message from dictionary representation."""
        return cls(
            id=data["id"],
            from_agent=data["from_agent"],
            to_agent=data["to_agent"],
            type=MessageType(data["type"]),
            content=data["content"],
            priority=MessagePriority(data["priority"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            requires_response=data.get("requires_response", False),
            correlation_id=data.get("correlation_id"),
            metadata=data.get("metadata", {}),
        )


# Type alias for message handlers
MessageHandler = Callable[[AgentMessage], Coroutine[Any, Any, None]]


class MessageBus:
    """In-memory message bus for inter-agent communication.

    Provides publish/subscribe functionality for agents to communicate.
    Supports direct messages, broadcasts, and request/response patterns.
    """

    BROADCAST_TARGET = "*"

    def __init__(self):
        """Initialize the message bus."""
        # Queue of messages per agent
        self._queues: Dict[str, asyncio.Queue[AgentMessage]] = defaultdict(asyncio.Queue)

        # Subscribers per agent (handlers called on message receipt)
        self._subscribers: Dict[str, List[MessageHandler]] = defaultdict(list)

        # Pending responses (correlation_id -> Future)
        self._pending_responses: Dict[str, asyncio.Future[AgentMessage]] = {}

        # Message history for debugging/auditing
        self._message_history: List[AgentMessage] = []
        self._max_history = 1000

        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

        logger.info("MessageBus initialized")

    async def publish(self, message: AgentMessage) -> None:
        """Publish a message to the bus.

        Args:
            message: The message to publish
        """
        async with self._lock:
            # Store in history
            self._message_history.append(message)
            if len(self._message_history) > self._max_history:
                self._message_history = self._message_history[-self._max_history:]

            logger.debug(
                f"Publishing message: {message.type.value} from {message.from_agent} "
                f"to {message.to_agent}"
            )

            # Handle broadcast messages
            if message.to_agent == self.BROADCAST_TARGET:
                for agent_id in list(self._queues.keys()):
                    if agent_id != message.from_agent:  # Don't send to self
                        await self._queues[agent_id].put(message)
                        await self._notify_subscribers(agent_id, message)
            else:
                # Direct message
                await self._queues[message.to_agent].put(message)
                await self._notify_subscribers(message.to_agent, message)

            # Handle response to pending request
            if message.type == MessageType.RESPONSE and message.correlation_id:
                if message.correlation_id in self._pending_responses:
                    future = self._pending_responses.pop(message.correlation_id)
                    if not future.done():
                        future.set_result(message)

    async def _notify_subscribers(self, agent_id: str, message: AgentMessage) -> None:
        """Notify all subscribers for an agent about a new message.

        Args:
            agent_id: The agent to notify subscribers for
            message: The message that was received
        """
        for handler in self._subscribers.get(agent_id, []):
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"Error in message handler for {agent_id}: {e}")

    async def subscribe(
        self,
        agent_id: str,
        callback: MessageHandler
    ) -> Callable[[], None]:
        """Subscribe to messages for a specific agent.

        Args:
            agent_id: The agent to subscribe for
            callback: Async function to call when message is received

        Returns:
            Unsubscribe function
        """
        async with self._lock:
            self._subscribers[agent_id].append(callback)
            logger.debug(f"Subscriber added for agent {agent_id}")

        def unsubscribe():
            if callback in self._subscribers[agent_id]:
                self._subscribers[agent_id].remove(callback)
                logger.debug(f"Subscriber removed for agent {agent_id}")

        return unsubscribe

    async def get_messages(
        self,
        agent_id: str,
        since: Optional[datetime] = None,
        max_messages: int = 100
    ) -> List[AgentMessage]:
        """Get messages for an agent.

        Args:
            agent_id: The agent to get messages for
            since: Optional timestamp to filter messages after
            max_messages: Maximum number of messages to return

        Returns:
            List of messages for the agent
        """
        messages: List[AgentMessage] = []
        queue = self._queues[agent_id]

        while not queue.empty() and len(messages) < max_messages:
            try:
                message = queue.get_nowait()
                if since is None or message.timestamp > since:
                    messages.append(message)
                queue.task_done()
            except asyncio.QueueEmpty:
                break

        # Sort by priority (highest first) then timestamp
        messages.sort(
            key=lambda m: (-m.priority.value, m.timestamp)
        )

        logger.debug(f"Retrieved {len(messages)} messages for agent {agent_id}")
        return messages

    async def send_and_wait(
        self,
        message: AgentMessage,
        timeout: float = 30.0
    ) -> Optional[AgentMessage]:
        """Send a message and wait for a response.

        Args:
            message: The message to send (requires_response should be True)
            timeout: Maximum time to wait for response in seconds

        Returns:
            The response message, or None if timeout
        """
        # Ensure message is marked as requiring response
        message.requires_response = True

        # Create future for response
        loop = asyncio.get_event_loop()
        future: asyncio.Future[AgentMessage] = loop.create_future()

        async with self._lock:
            self._pending_responses[message.id] = future

        try:
            # Publish the message
            await self.publish(message)

            # Wait for response with timeout
            response = await asyncio.wait_for(future, timeout=timeout)
            logger.debug(
                f"Received response for message {message.id} from {response.from_agent}"
            )
            return response

        except asyncio.TimeoutError:
            logger.warning(
                f"Timeout waiting for response to message {message.id} "
                f"(from={message.from_agent}, to={message.to_agent})"
            )
            # Clean up pending response
            async with self._lock:
                self._pending_responses.pop(message.id, None)
            return None

    async def get_pending_count(self, agent_id: str) -> int:
        """Get count of pending messages for an agent.

        Args:
            agent_id: The agent to check

        Returns:
            Number of pending messages
        """
        return self._queues[agent_id].qsize()

    def get_message_history(
        self,
        limit: int = 100,
        agent_filter: Optional[str] = None,
        type_filter: Optional[MessageType] = None
    ) -> List[AgentMessage]:
        """Get recent message history for debugging.

        Args:
            limit: Maximum number of messages to return
            agent_filter: Optional agent ID to filter by (sender or receiver)
            type_filter: Optional message type to filter by

        Returns:
            List of recent messages
        """
        messages = self._message_history.copy()

        if agent_filter:
            messages = [
                m for m in messages
                if m.from_agent == agent_filter or m.to_agent == agent_filter
            ]

        if type_filter:
            messages = [m for m in messages if m.type == type_filter]

        return messages[-limit:]

    async def clear_queue(self, agent_id: str) -> int:
        """Clear all pending messages for an agent.

        Args:
            agent_id: The agent to clear messages for

        Returns:
            Number of messages cleared
        """
        count = 0
        queue = self._queues[agent_id]

        while not queue.empty():
            try:
                queue.get_nowait()
                queue.task_done()
                count += 1
            except asyncio.QueueEmpty:
                break

        logger.info(f"Cleared {count} messages for agent {agent_id}")
        return count

    async def shutdown(self) -> None:
        """Shutdown the message bus and clean up resources."""
        logger.info("Shutting down MessageBus")

        # Cancel all pending responses
        async with self._lock:
            for future in self._pending_responses.values():
                if not future.done():
                    future.cancel()
            self._pending_responses.clear()

        # Clear all queues
        for agent_id in list(self._queues.keys()):
            await self.clear_queue(agent_id)

        self._subscribers.clear()
        logger.info("MessageBus shutdown complete")
