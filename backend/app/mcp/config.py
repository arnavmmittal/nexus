"""MCP Server Configuration for Nexus.

This module defines configuration for connecting to MCP (Model Context Protocol) servers.
MCP servers provide external tools that Jarvis and Ultron can use dynamically.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
import os
import json

# Load .env file before reading environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class MCPTransport(Enum):
    """Transport methods for MCP connections."""
    STDIO = "stdio"      # Subprocess with stdin/stdout
    SSE = "sse"          # Server-sent events over HTTP
    WEBSOCKET = "ws"     # WebSocket connection


@dataclass
class MCPServerConfig:
    """Configuration for a single MCP server."""
    name: str
    description: str
    transport: MCPTransport = MCPTransport.STDIO

    # For STDIO transport
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)

    # For SSE/WebSocket transport
    url: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)

    # Connection settings
    timeout: int = 30
    auto_reconnect: bool = True
    max_retries: int = 3

    # Tool filtering
    allowed_tools: Optional[List[str]] = None  # None = all tools
    blocked_tools: List[str] = field(default_factory=list)

    # Agent permissions
    agents: List[str] = field(default_factory=lambda: ["jarvis", "ultron"])

    # Confirmation requirements
    requires_confirmation: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "transport": self.transport.value,
            "command": self.command,
            "args": self.args,
            "env": self.env,
            "url": self.url,
            "headers": self.headers,
            "timeout": self.timeout,
            "auto_reconnect": self.auto_reconnect,
            "max_retries": self.max_retries,
            "allowed_tools": self.allowed_tools,
            "blocked_tools": self.blocked_tools,
            "agents": self.agents,
            "requires_confirmation": self.requires_confirmation,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPServerConfig":
        """Create from dictionary."""
        data = data.copy()
        if "transport" in data:
            data["transport"] = MCPTransport(data["transport"])
        return cls(**data)


# Default MCP server configurations
DEFAULT_MCP_SERVERS: Dict[str, MCPServerConfig] = {}

# Add filesystem server if configured
if os.environ.get("MCP_FILESYSTEM_ENABLED", "false").lower() == "true":
    DEFAULT_MCP_SERVERS["filesystem"] = MCPServerConfig(
        name="filesystem",
        description="File system operations - read, write, and manage files",
        transport=MCPTransport.STDIO,
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem",
              os.environ.get("MCP_FILESYSTEM_ROOT", os.path.expanduser("~"))],
        agents=["jarvis", "ultron"],
        requires_confirmation=True,  # Require confirmation for file operations
    )

# Add GitHub server if configured
if os.environ.get("GITHUB_TOKEN"):
    DEFAULT_MCP_SERVERS["github"] = MCPServerConfig(
        name="github",
        description="GitHub operations - repos, issues, PRs, and more",
        transport=MCPTransport.STDIO,
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env={"GITHUB_TOKEN": os.environ.get("GITHUB_TOKEN", "")},
        agents=["jarvis", "ultron"],
    )

# Add Brave Search if configured
if os.environ.get("BRAVE_API_KEY"):
    DEFAULT_MCP_SERVERS["brave-search"] = MCPServerConfig(
        name="brave-search",
        description="Web search using Brave Search API",
        transport=MCPTransport.STDIO,
        command="npx",
        args=["-y", "@modelcontextprotocol/server-brave-search"],
        env={"BRAVE_API_KEY": os.environ.get("BRAVE_API_KEY", "")},
        agents=["jarvis", "ultron"],
    )

# Add Memory server for persistent memory
DEFAULT_MCP_SERVERS["memory"] = MCPServerConfig(
    name="memory",
    description="Persistent memory across conversations using knowledge graphs",
    transport=MCPTransport.STDIO,
    command="npx",
    args=["-y", "@modelcontextprotocol/server-memory"],
    agents=["jarvis", "ultron"],
)

# Add PostgreSQL if database URL configured
if os.environ.get("MCP_POSTGRES_URL"):
    DEFAULT_MCP_SERVERS["postgres"] = MCPServerConfig(
        name="postgres",
        description="PostgreSQL database operations",
        transport=MCPTransport.STDIO,
        command="npx",
        args=["-y", "@modelcontextprotocol/server-postgres",
              os.environ.get("MCP_POSTGRES_URL", "")],
        agents=["ultron"],  # Only Ultron can access database directly
        requires_confirmation=True,
    )


def load_mcp_config_file(path: str) -> Dict[str, MCPServerConfig]:
    """Load MCP server configurations from a JSON file.

    Expected format:
    {
        "servers": {
            "server-name": {
                "name": "server-name",
                "description": "Description",
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "@scope/package"],
                ...
            }
        }
    }
    """
    configs = {}

    if not os.path.exists(path):
        return configs

    try:
        with open(path, "r") as f:
            data = json.load(f)

        for name, server_data in data.get("servers", {}).items():
            configs[name] = MCPServerConfig.from_dict(server_data)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to load MCP config from {path}: {e}")

    return configs


def get_all_mcp_configs() -> Dict[str, MCPServerConfig]:
    """Get all configured MCP servers including user configs."""
    configs = DEFAULT_MCP_SERVERS.copy()

    # Load user config if exists
    user_config_path = os.path.expanduser("~/.nexus/mcp_servers.json")
    configs.update(load_mcp_config_file(user_config_path))

    # Load project config if exists
    project_config_path = os.environ.get("MCP_CONFIG_PATH", "mcp_servers.json")
    configs.update(load_mcp_config_file(project_config_path))

    return configs
