"""MCP API endpoints for Nexus.

This module provides REST API endpoints for managing MCP server connections
and viewing MCP status.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any

from app.api.deps import get_current_user
from app.models import User

# Import MCP components
try:
    from app.mcp import (
        get_mcp_registry,
        start_mcp_registry,
        stop_mcp_registry,
        MCPServerConfig,
        MCPTransport,
    )
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

router = APIRouter(prefix="/mcp", tags=["mcp"])


# ========== Schemas ==========

class MCPServerCreate(BaseModel):
    """Request to add a new MCP server."""
    name: str = Field(..., description="Unique server name")
    description: str = Field(..., description="Server description")
    transport: str = Field("stdio", description="Transport method: stdio, sse, ws")
    command: Optional[str] = Field(None, description="Command for STDIO transport")
    args: List[str] = Field(default_factory=list, description="Command arguments")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables")
    url: Optional[str] = Field(None, description="URL for SSE/WebSocket transport")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers")
    timeout: int = Field(30, description="Connection timeout in seconds")
    allowed_tools: Optional[List[str]] = Field(None, description="Allowed tool names (null = all)")
    blocked_tools: List[str] = Field(default_factory=list, description="Blocked tool names")
    agents: List[str] = Field(default_factory=lambda: ["jarvis", "ultron"])
    requires_confirmation: bool = Field(False, description="Require user confirmation for tools")


class MCPServerStatus(BaseModel):
    """MCP server status response."""
    name: str
    connected: bool
    tools_count: int
    resources_count: int
    prompts_count: int


class MCPStatusResponse(BaseModel):
    """MCP system status response."""
    enabled: bool
    servers: Dict[str, MCPServerStatus]


class MCPToolInfo(BaseModel):
    """MCP tool information."""
    name: str
    description: str
    server: str


class MCPToolsResponse(BaseModel):
    """MCP tools list response."""
    tools: List[MCPToolInfo]


# ========== Endpoints ==========

@router.get("/status", response_model=MCPStatusResponse)
async def get_mcp_status(
    current_user: User = Depends(get_current_user),
):
    """Get MCP system status."""
    if not MCP_AVAILABLE:
        return MCPStatusResponse(enabled=False, servers={})

    registry = get_mcp_registry()
    raw_status = registry.get_server_status()

    servers = {
        name: MCPServerStatus(
            name=name,
            connected=info["connected"],
            tools_count=info["tools_count"],
            resources_count=info["resources_count"],
            prompts_count=info["prompts_count"],
        )
        for name, info in raw_status.items()
    }

    return MCPStatusResponse(enabled=True, servers=servers)


@router.get("/tools", response_model=MCPToolsResponse)
async def get_mcp_tools(
    agent: str = "jarvis",
    current_user: User = Depends(get_current_user),
):
    """Get available MCP tools for an agent."""
    if not MCP_AVAILABLE:
        return MCPToolsResponse(tools=[])

    registry = get_mcp_registry()
    raw_tools = registry.get_tools_for_agent(agent)

    tools = []
    for tool in raw_tools:
        # Parse server name from prefixed tool name
        name = tool["name"]
        parts = name.split("_", 2)  # mcp_<server>_<tool>
        server = parts[1] if len(parts) > 1 else "unknown"

        tools.append(MCPToolInfo(
            name=name,
            description=tool.get("description", ""),
            server=server,
        ))

    return MCPToolsResponse(tools=tools)


@router.post("/servers", response_model=Dict[str, Any])
async def add_mcp_server(
    server: MCPServerCreate,
    current_user: User = Depends(get_current_user),
):
    """Add a new MCP server connection."""
    if not MCP_AVAILABLE:
        raise HTTPException(status_code=501, detail="MCP not available")

    try:
        transport = MCPTransport(server.transport)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transport: {server.transport}. Use: stdio, sse, ws"
        )

    config = MCPServerConfig(
        name=server.name,
        description=server.description,
        transport=transport,
        command=server.command,
        args=server.args,
        env=server.env,
        url=server.url,
        headers=server.headers,
        timeout=server.timeout,
        allowed_tools=server.allowed_tools,
        blocked_tools=server.blocked_tools,
        agents=server.agents,
        requires_confirmation=server.requires_confirmation,
    )

    registry = get_mcp_registry()
    success = await registry.add_server(config)

    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to connect to MCP server: {server.name}"
        )

    return {
        "status": "connected",
        "server": server.name,
        "message": f"MCP server '{server.name}' connected successfully",
    }


@router.delete("/servers/{server_name}")
async def remove_mcp_server(
    server_name: str,
    current_user: User = Depends(get_current_user),
):
    """Remove an MCP server connection."""
    if not MCP_AVAILABLE:
        raise HTTPException(status_code=501, detail="MCP not available")

    registry = get_mcp_registry()
    success = await registry.remove_server(server_name)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"MCP server not found: {server_name}"
        )

    return {
        "status": "disconnected",
        "server": server_name,
        "message": f"MCP server '{server_name}' disconnected",
    }


@router.post("/servers/{server_name}/reconnect")
async def reconnect_mcp_server(
    server_name: str,
    current_user: User = Depends(get_current_user),
):
    """Reconnect to an MCP server."""
    if not MCP_AVAILABLE:
        raise HTTPException(status_code=501, detail="MCP not available")

    registry = get_mcp_registry()
    connection = registry.get_connection(server_name)

    if connection is None:
        raise HTTPException(
            status_code=404,
            detail=f"MCP server not found: {server_name}"
        )

    success = await connection.connect()

    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reconnect to MCP server: {server_name}"
        )

    return {
        "status": "connected",
        "server": server_name,
        "tools_count": len(connection.tools),
    }


@router.post("/execute")
async def execute_mcp_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    agent: str = "jarvis",
    current_user: User = Depends(get_current_user),
):
    """Execute an MCP tool directly."""
    if not MCP_AVAILABLE:
        raise HTTPException(status_code=501, detail="MCP not available")

    registry = get_mcp_registry()

    if not registry.is_mcp_tool(tool_name):
        raise HTTPException(
            status_code=404,
            detail=f"Unknown MCP tool: {tool_name}"
        )

    result = await registry.execute_tool(tool_name, arguments)

    return {
        "tool": tool_name,
        "result": result,
    }
