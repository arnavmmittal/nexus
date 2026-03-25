"""MCP Tool Executor for Nexus.

This module provides the executor that handles MCP tool calls within the
existing tool execution framework. It integrates with the AIEngine to
seamlessly route MCP tool calls to the appropriate servers.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from .registry import get_mcp_registry, MCPRegistry

logger = logging.getLogger(__name__)


class MCPToolExecutor:
    """Executor for MCP tools that integrates with the Nexus tool system."""

    def __init__(
        self,
        agent_name: str = "jarvis",
        require_confirmation_callback: Optional[callable] = None,
    ):
        """
        Initialize MCP tool executor.

        Args:
            agent_name: The agent using this executor (jarvis/ultron)
            require_confirmation_callback: Optional callback to request user confirmation
        """
        self.agent_name = agent_name
        self.confirmation_callback = require_confirmation_callback
        self._registry: Optional[MCPRegistry] = None

    @property
    def registry(self) -> MCPRegistry:
        """Get the MCP registry (lazy initialization)."""
        if self._registry is None:
            self._registry = get_mcp_registry()
        return self._registry

    def get_available_tools(self) -> list[Dict[str, Any]]:
        """Get all MCP tools available for this agent."""
        return self.registry.get_tools_for_agent(self.agent_name)

    def is_mcp_tool(self, tool_name: str) -> bool:
        """Check if a tool name is an MCP tool."""
        return self.registry.is_mcp_tool(tool_name)

    async def execute(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        skip_confirmation: bool = False,
    ) -> str:
        """
        Execute an MCP tool.

        Args:
            tool_name: Full MCP tool name (e.g., mcp_github_create_issue)
            arguments: Tool arguments
            skip_confirmation: Skip confirmation even if required

        Returns:
            Tool result as a string
        """
        if not self.is_mcp_tool(tool_name):
            return json.dumps({"error": f"Not an MCP tool: {tool_name}"})

        # Check if confirmation is required
        if (
            not skip_confirmation
            and self.registry.requires_confirmation(tool_name)
            and self.confirmation_callback
        ):
            # Request confirmation from user
            confirmed = await self.confirmation_callback(
                tool_name=tool_name,
                arguments=arguments,
                reason="This tool requires user confirmation before execution.",
            )
            if not confirmed:
                return json.dumps({
                    "status": "cancelled",
                    "message": "User did not confirm tool execution",
                })

        # Execute the tool
        try:
            logger.info(f"Executing MCP tool {tool_name} for agent {self.agent_name}")
            result = await self.registry.execute_tool(tool_name, arguments)

            # Format result for Claude
            if isinstance(result, dict):
                if "error" in result:
                    return json.dumps({"error": result["error"]})

                # Handle MCP content format
                if "content" in result:
                    content = result["content"]
                    if isinstance(content, list):
                        # Extract text content
                        texts = []
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                texts.append(item.get("text", ""))
                        return "\n".join(texts) if texts else json.dumps(result)
                    return str(content)

                return json.dumps(result)
            else:
                return str(result)

        except Exception as e:
            logger.error(f"Error executing MCP tool {tool_name}: {e}")
            return json.dumps({"error": str(e)})

    async def execute_batch(
        self,
        tool_calls: list[Dict[str, Any]],
    ) -> list[Dict[str, Any]]:
        """
        Execute multiple MCP tools.

        Args:
            tool_calls: List of {"name": str, "arguments": dict}

        Returns:
            List of {"name": str, "result": str}
        """
        results = []
        for call in tool_calls:
            result = await self.execute(call["name"], call["arguments"])
            results.append({"name": call["name"], "result": result})
        return results


def create_mcp_executor(
    agent_name: str = "jarvis",
    confirmation_callback: Optional[callable] = None,
) -> MCPToolExecutor:
    """Create an MCP tool executor for an agent.

    Args:
        agent_name: The agent name (jarvis/ultron)
        confirmation_callback: Optional async callback(tool_name, arguments, reason) -> bool

    Returns:
        Configured MCPToolExecutor
    """
    return MCPToolExecutor(
        agent_name=agent_name,
        require_confirmation_callback=confirmation_callback,
    )


# Convenience function for integration with existing ToolExecutor
async def execute_mcp_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    agent_name: str = "jarvis",
) -> str:
    """
    Execute an MCP tool directly.

    This is a convenience function for quick tool execution without
    creating an executor instance.

    Args:
        tool_name: Full MCP tool name
        arguments: Tool arguments
        agent_name: Agent making the call

    Returns:
        Tool result as string
    """
    executor = MCPToolExecutor(agent_name=agent_name)
    return await executor.execute(tool_name, arguments)
