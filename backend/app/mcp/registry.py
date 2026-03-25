"""MCP Server Registry for Nexus.

This module provides a centralized registry for managing MCP server connections.
Both Jarvis and Ultron use this registry to access external tools.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from threading import Lock

from .config import MCPServerConfig, get_all_mcp_configs
from .client import MCPConnection, MCPTool

logger = logging.getLogger(__name__)


@dataclass
class MCPToolInfo:
    """Combined info about a tool including its source server."""
    tool: MCPTool
    connection: MCPConnection
    requires_confirmation: bool = False


class MCPRegistry:
    """Singleton registry for managing MCP server connections."""

    _instance: Optional["MCPRegistry"] = None
    _lock = Lock()

    def __new__(cls) -> "MCPRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._connections: Dict[str, MCPConnection] = {}
        self._tool_index: Dict[str, MCPToolInfo] = {}  # Full tool name -> info
        self._agent_tools: Dict[str, Set[str]] = {}  # Agent -> set of tool names
        self._startup_lock = asyncio.Lock()
        self._started = False
        self._initialized = True

    async def start(self, configs: Optional[Dict[str, MCPServerConfig]] = None):
        """Start the registry and connect to all configured servers."""
        async with self._startup_lock:
            if self._started:
                return

            # Load configs
            configs = configs or get_all_mcp_configs()
            logger.info(f"Starting MCP registry with {len(configs)} servers")

            # Connect to each server
            connect_tasks = []
            for name, config in configs.items():
                connect_tasks.append(self._connect_server(name, config))

            results = await asyncio.gather(*connect_tasks, return_exceptions=True)

            success_count = sum(1 for r in results if r is True)
            logger.info(f"Connected to {success_count}/{len(configs)} MCP servers")

            self._started = True

    async def _connect_server(
        self, name: str, config: MCPServerConfig
    ) -> bool:
        """Connect to a single MCP server."""
        try:
            connection = MCPConnection(config)
            if await connection.connect():
                self._connections[name] = connection

                # Index tools
                for tool_name, tool in connection.tools.items():
                    full_name = f"mcp_{name}_{tool_name}"
                    self._tool_index[full_name] = MCPToolInfo(
                        tool=tool,
                        connection=connection,
                        requires_confirmation=config.requires_confirmation,
                    )

                    # Index by agent
                    for agent in config.agents:
                        if agent not in self._agent_tools:
                            self._agent_tools[agent] = set()
                        self._agent_tools[agent].add(full_name)

                return True
            return False

        except Exception as e:
            logger.error(f"Failed to connect to MCP server {name}: {e}")
            return False

    async def stop(self):
        """Stop the registry and disconnect from all servers."""
        for name, connection in self._connections.items():
            try:
                await connection.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting from {name}: {e}")

        self._connections.clear()
        self._tool_index.clear()
        self._agent_tools.clear()
        self._started = False

    def get_tools_for_agent(self, agent_name: str) -> List[Dict[str, Any]]:
        """Get all MCP tools available for an agent in Claude format."""
        tools = []
        tool_names = self._agent_tools.get(agent_name.lower(), set())

        for name in tool_names:
            if name in self._tool_index:
                tool_info = self._tool_index[name]
                tools.append(tool_info.tool.to_claude_format())

        return tools

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """Get all available MCP tools in Claude format."""
        return [info.tool.to_claude_format() for info in self._tool_index.values()]

    def is_mcp_tool(self, tool_name: str) -> bool:
        """Check if a tool name is an MCP tool."""
        return tool_name.startswith("mcp_") and tool_name in self._tool_index

    def requires_confirmation(self, tool_name: str) -> bool:
        """Check if an MCP tool requires user confirmation."""
        if tool_name in self._tool_index:
            return self._tool_index[tool_name].requires_confirmation
        return False

    async def execute_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an MCP tool by its full name."""
        if tool_name not in self._tool_index:
            return {"error": f"Unknown MCP tool: {tool_name}"}

        tool_info = self._tool_index[tool_name]

        if not tool_info.connection.connected:
            # Try to reconnect
            if not await tool_info.connection.connect():
                return {"error": f"Server {tool_info.tool.server_name} is not connected"}

        # Call the tool (using original name, not prefixed name)
        result = await tool_info.connection.call_tool(
            tool_info.tool.name,
            arguments
        )

        return result

    def get_server_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all MCP servers."""
        status = {}
        for name, connection in self._connections.items():
            status[name] = {
                "connected": connection.connected,
                "tools_count": len(connection.tools),
                "resources_count": len(connection.resources),
                "prompts_count": len(connection.prompts),
            }
        return status

    def get_connection(self, server_name: str) -> Optional[MCPConnection]:
        """Get a specific MCP connection."""
        return self._connections.get(server_name)

    async def add_server(self, config: MCPServerConfig) -> bool:
        """Dynamically add a new MCP server."""
        if config.name in self._connections:
            logger.warning(f"Server {config.name} already exists")
            return False

        return await self._connect_server(config.name, config)

    async def remove_server(self, server_name: str) -> bool:
        """Disconnect and remove an MCP server."""
        if server_name not in self._connections:
            return False

        connection = self._connections.pop(server_name)
        await connection.disconnect()

        # Remove tools from index
        tools_to_remove = [
            name for name, info in self._tool_index.items()
            if info.tool.server_name == server_name
        ]
        for name in tools_to_remove:
            del self._tool_index[name]

        # Remove from agent tools
        for agent_tools in self._agent_tools.values():
            agent_tools.difference_update(tools_to_remove)

        return True


# Global registry instance
_registry: Optional[MCPRegistry] = None


def get_mcp_registry() -> MCPRegistry:
    """Get the global MCP registry instance."""
    global _registry
    if _registry is None:
        _registry = MCPRegistry()
    return _registry


async def start_mcp_registry(
    configs: Optional[Dict[str, MCPServerConfig]] = None
) -> MCPRegistry:
    """Start and return the global MCP registry."""
    registry = get_mcp_registry()
    await registry.start(configs)
    return registry


async def stop_mcp_registry():
    """Stop the global MCP registry."""
    global _registry
    if _registry:
        await _registry.stop()
        _registry = None
