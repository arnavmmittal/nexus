"""MCP (Model Context Protocol) Integration for Nexus.

This module provides MCP server connectivity for Jarvis and Ultron,
allowing them to dynamically access external tools without code changes.

Example usage:
    from app.mcp import get_mcp_registry, start_mcp_registry, MCPToolExecutor

    # Start the registry (usually at app startup)
    registry = await start_mcp_registry()

    # Get tools for an agent
    tools = registry.get_tools_for_agent("jarvis")

    # Execute an MCP tool
    executor = MCPToolExecutor(agent_name="jarvis")
    result = await executor.execute("mcp_github_create_issue", {
        "repo": "owner/repo",
        "title": "Issue title",
        "body": "Issue body",
    })

Available MCP servers (configured via environment):
- filesystem: File system operations (MCP_FILESYSTEM_ENABLED=true)
- github: GitHub operations (GITHUB_TOKEN required)
- brave-search: Web search (BRAVE_API_KEY required)
- memory: Persistent memory across conversations
- postgres: Database operations (MCP_POSTGRES_URL required)

Custom servers can be added via:
- ~/.nexus/mcp_servers.json
- MCP_CONFIG_PATH environment variable
"""

from .config import (
    MCPServerConfig,
    MCPTransport,
    get_all_mcp_configs,
    load_mcp_config_file,
)
from .client import (
    MCPConnection,
    MCPPrompt,
    MCPResource,
    MCPTool,
)
from .registry import (
    MCPRegistry,
    MCPToolInfo,
    get_mcp_registry,
    start_mcp_registry,
    stop_mcp_registry,
)
from .executor import (
    MCPToolExecutor,
    create_mcp_executor,
    execute_mcp_tool,
)

__all__ = [
    # Config
    "MCPServerConfig",
    "MCPTransport",
    "get_all_mcp_configs",
    "load_mcp_config_file",
    # Client
    "MCPConnection",
    "MCPPrompt",
    "MCPResource",
    "MCPTool",
    # Registry
    "MCPRegistry",
    "MCPToolInfo",
    "get_mcp_registry",
    "start_mcp_registry",
    "stop_mcp_registry",
    # Executor
    "MCPToolExecutor",
    "create_mcp_executor",
    "execute_mcp_tool",
]
