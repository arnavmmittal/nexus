"""WebSocket support for real-time agent communication.

This module provides WebSocket endpoints and connection management for
real-time updates from agents, including task progress, messages, and delegations.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.schemas.agents import AgentWebSocketMessage

logger = logging.getLogger(__name__)

router = APIRouter()


class AgentWebSocketManager:
    """Manager for WebSocket connections to agents.

    Handles connection lifecycle, message broadcasting, and agent-specific
    subscriptions for real-time updates.
    """

    def __init__(self):
        """Initialize the WebSocket manager."""
        # Maps agent_id -> set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Maps WebSocket -> agent_id for reverse lookup
        self.connection_agents: Dict[WebSocket, str] = {}
        # Connections subscribed to all agent updates
        self.all_agent_connections: Set[WebSocket] = set()
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, agent_id: Optional[str] = None) -> None:
        """Accept a new WebSocket connection.

        Args:
            websocket: The WebSocket connection to accept.
            agent_id: Optional agent ID to subscribe to. If None, subscribes to all agents.
        """
        await websocket.accept()

        async with self._lock:
            if agent_id:
                if agent_id not in self.active_connections:
                    self.active_connections[agent_id] = set()
                self.active_connections[agent_id].add(websocket)
                self.connection_agents[websocket] = agent_id
                logger.info(f"WebSocket connected for agent: {agent_id}")
            else:
                self.all_agent_connections.add(websocket)
                logger.info("WebSocket connected for all agents")

    async def disconnect(self, websocket: WebSocket) -> None:
        """Handle WebSocket disconnection.

        Args:
            websocket: The WebSocket connection that disconnected.
        """
        async with self._lock:
            # Remove from agent-specific connections
            if websocket in self.connection_agents:
                agent_id = self.connection_agents[websocket]
                if agent_id in self.active_connections:
                    self.active_connections[agent_id].discard(websocket)
                    if not self.active_connections[agent_id]:
                        del self.active_connections[agent_id]
                del self.connection_agents[websocket]
                logger.info(f"WebSocket disconnected for agent: {agent_id}")

            # Remove from all-agent connections
            self.all_agent_connections.discard(websocket)

    async def send_message(self, websocket: WebSocket, message: dict) -> bool:
        """Send a message to a specific WebSocket connection.

        Args:
            websocket: The target WebSocket connection.
            message: The message to send.

        Returns:
            True if message sent successfully, False otherwise.
        """
        try:
            await websocket.send_json(message)
            return True
        except Exception as e:
            logger.warning(f"Failed to send WebSocket message: {e}")
            return False

    async def broadcast_to_agent(self, agent_id: str, message: dict) -> int:
        """Broadcast a message to all connections subscribed to an agent.

        Args:
            agent_id: The agent ID to broadcast to.
            message: The message to broadcast.

        Returns:
            Number of connections the message was sent to.
        """
        sent_count = 0
        disconnected: Set[WebSocket] = set()

        # Send to agent-specific connections
        if agent_id in self.active_connections:
            for connection in self.active_connections[agent_id].copy():
                if await self.send_message(connection, message):
                    sent_count += 1
                else:
                    disconnected.add(connection)

        # Send to all-agent connections
        for connection in self.all_agent_connections.copy():
            if await self.send_message(connection, message):
                sent_count += 1
            else:
                disconnected.add(connection)

        # Clean up disconnected connections
        for conn in disconnected:
            await self.disconnect(conn)

        return sent_count

    async def broadcast_all(self, message: dict) -> int:
        """Broadcast a message to all connected WebSocket clients.

        Args:
            message: The message to broadcast.

        Returns:
            Number of connections the message was sent to.
        """
        sent_count = 0
        disconnected: Set[WebSocket] = set()

        # Send to all agent-specific connections
        for connections in self.active_connections.values():
            for connection in connections.copy():
                if await self.send_message(connection, message):
                    sent_count += 1
                else:
                    disconnected.add(connection)

        # Send to all-agent connections
        for connection in self.all_agent_connections.copy():
            if await self.send_message(connection, message):
                sent_count += 1
            else:
                disconnected.add(connection)

        # Clean up disconnected connections
        for conn in disconnected:
            await self.disconnect(conn)

        return sent_count

    def get_connection_count(self, agent_id: Optional[str] = None) -> int:
        """Get the number of active connections.

        Args:
            agent_id: Optional agent ID to count connections for.
                     If None, returns total connection count.

        Returns:
            Number of active connections.
        """
        if agent_id:
            return len(self.active_connections.get(agent_id, set()))
        else:
            total = len(self.all_agent_connections)
            for connections in self.active_connections.values():
                total += len(connections)
            return total


# Global WebSocket manager instance
ws_manager = AgentWebSocketManager()


async def _handle_client_message(
    websocket: WebSocket, data: dict, agent_id: Optional[str] = None
) -> None:
    """Handle incoming message from WebSocket client.

    Args:
        websocket: The WebSocket connection.
        data: The received message data.
        agent_id: Optional agent ID the connection is subscribed to.
    """
    message_type = data.get("type", "unknown")

    if message_type == "ping":
        # Respond to ping with pong
        await websocket.send_json(
            {
                "type": "pong",
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    elif message_type == "subscribe":
        # Handle subscription changes (future enhancement)
        logger.info(f"Subscription request: {data}")
    else:
        logger.debug(f"Received message type: {message_type}")


@router.websocket("/ws/agents/{agent_id}")
async def websocket_agent_endpoint(websocket: WebSocket, agent_id: str) -> None:
    """WebSocket endpoint for real-time updates from a specific agent.

    Connect to receive real-time updates including:
    - Task progress and completion
    - Agent messages
    - Delegation events
    - Status changes

    Args:
        websocket: The WebSocket connection.
        agent_id: The agent ID to subscribe to.
    """
    await ws_manager.connect(websocket, agent_id)

    # Send initial connection confirmation
    await websocket.send_json(
        {
            "type": "connected",
            "agent_id": agent_id,
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"Connected to agent {agent_id} updates",
        }
    )

    try:
        while True:
            # Wait for incoming messages
            data = await websocket.receive_json()
            await _handle_client_message(websocket, data, agent_id)

    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
        logger.info(f"WebSocket disconnected for agent: {agent_id}")
    except Exception as e:
        logger.error(f"WebSocket error for agent {agent_id}: {e}")
        await ws_manager.disconnect(websocket)


@router.websocket("/ws/agents/all")
async def websocket_all_agents_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time updates from all agents.

    Connect to receive real-time updates from all agents in the system,
    including cross-agent delegations and collaborations.

    Args:
        websocket: The WebSocket connection.
    """
    await ws_manager.connect(websocket, agent_id=None)

    # Send initial connection confirmation
    await websocket.send_json(
        {
            "type": "connected",
            "agent_id": None,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Connected to all agent updates",
        }
    )

    try:
        while True:
            # Wait for incoming messages
            data = await websocket.receive_json()
            await _handle_client_message(websocket, data, agent_id=None)

    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
        logger.info("WebSocket disconnected for all agents")
    except Exception as e:
        logger.error(f"WebSocket error for all agents: {e}")
        await ws_manager.disconnect(websocket)


# Helper functions for other modules to emit events
async def emit_agent_event(
    agent_id: str,
    event_type: str,
    content: Any,
    related_agent: Optional[str] = None,
) -> None:
    """Emit an event to WebSocket subscribers.

    Args:
        agent_id: The agent emitting the event.
        event_type: Type of event (e.g., 'task_update', 'message').
        content: Event content.
        related_agent: Optional related agent ID.
    """
    message = {
        "type": event_type,
        "agent_id": agent_id,
        "content": content,
        "timestamp": datetime.utcnow().isoformat(),
    }
    if related_agent:
        message["related_agent"] = related_agent

    await ws_manager.broadcast_to_agent(agent_id, message)


async def emit_delegation_event(
    from_agent: str,
    to_agent: str,
    task_id: str,
    task_description: str,
) -> None:
    """Emit a delegation event to WebSocket subscribers.

    Args:
        from_agent: Source agent ID.
        to_agent: Target agent ID.
        task_id: The delegated task ID.
        task_description: Description of the delegated task.
    """
    message = {
        "type": "delegation",
        "from_agent": from_agent,
        "to_agent": to_agent,
        "task_id": task_id,
        "task_description": task_description,
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Broadcast to both agents and all-agent subscribers
    await ws_manager.broadcast_to_agent(from_agent, message)
    await ws_manager.broadcast_to_agent(to_agent, message)


async def emit_broadcast_event(event_type: str, content: Any) -> None:
    """Emit an event to all WebSocket subscribers.

    Args:
        event_type: Type of event.
        content: Event content.
    """
    message = {
        "type": event_type,
        "content": content,
        "timestamp": datetime.utcnow().isoformat(),
    }
    await ws_manager.broadcast_all(message)
