"""MCP Client for Nexus.

This module provides the MCP client that connects to MCP servers and executes tools.
It supports multiple transport methods: STDIO, SSE, and WebSocket.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from .config import MCPServerConfig, MCPTransport

logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """Represents a tool from an MCP server."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    server_name: str

    def to_claude_format(self) -> Dict[str, Any]:
        """Convert to Claude API tool format."""
        return {
            "name": f"mcp_{self.server_name}_{self.name}",
            "description": f"[{self.server_name}] {self.description}",
            "input_schema": self.input_schema,
        }


@dataclass
class MCPResource:
    """Represents a resource from an MCP server."""
    uri: str
    name: str
    description: Optional[str] = None
    mime_type: Optional[str] = None


@dataclass
class MCPPrompt:
    """Represents a prompt template from an MCP server."""
    name: str
    description: Optional[str] = None
    arguments: List[Dict[str, Any]] = field(default_factory=list)


class MCPConnection:
    """Manages connection to a single MCP server."""

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.connected = False
        self.tools: Dict[str, MCPTool] = {}
        self.resources: Dict[str, MCPResource] = {}
        self.prompts: Dict[str, MCPPrompt] = {}

        # For STDIO transport
        self._process: Optional[subprocess.Popen] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._request_id = 0

        # For SSE/WebSocket transport
        self._session = None
        self._ws = None

        # Event handlers
        self._on_notification: Optional[Callable] = None

    async def connect(self) -> bool:
        """Establish connection to the MCP server."""
        try:
            if self.config.transport == MCPTransport.STDIO:
                return await self._connect_stdio()
            elif self.config.transport == MCPTransport.SSE:
                return await self._connect_sse()
            elif self.config.transport == MCPTransport.WEBSOCKET:
                return await self._connect_websocket()
            else:
                logger.error(f"Unknown transport: {self.config.transport}")
                return False
        except Exception as e:
            logger.error(f"Failed to connect to MCP server {self.config.name}: {e}")
            return False

    async def _connect_stdio(self) -> bool:
        """Connect using STDIO transport (subprocess)."""
        if not self.config.command:
            logger.error(f"No command specified for STDIO server {self.config.name}")
            return False

        # Build environment
        env = dict(subprocess.os.environ)
        env.update(self.config.env)

        # Start subprocess
        cmd = [self.config.command] + self.config.args
        logger.info(f"Starting MCP server {self.config.name}: {' '.join(cmd)}")

        try:
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                bufsize=0,
            )

            # Start reader task
            self._reader_task = asyncio.create_task(self._read_stdio())

            # Initialize the connection
            init_response = await self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "roots": {"listChanged": True},
                    "sampling": {},
                },
                "clientInfo": {
                    "name": "nexus",
                    "version": "1.0.0",
                },
            })

            if init_response and "result" in init_response:
                # Send initialized notification
                await self._send_notification("notifications/initialized", {})

                # Fetch available tools
                await self._fetch_capabilities()
                self.connected = True
                logger.info(f"Connected to MCP server {self.config.name} with {len(self.tools)} tools")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to start MCP server {self.config.name}: {e}")
            return False

    async def _connect_sse(self) -> bool:
        """Connect using SSE transport."""
        try:
            import aiohttp

            if not self.config.url:
                logger.error(f"No URL specified for SSE server {self.config.name}")
                return False

            self._session = aiohttp.ClientSession()

            # Send initialization
            async with self._session.post(
                f"{self.config.url}/initialize",
                json={
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "nexus", "version": "1.0.0"},
                },
                headers=self.config.headers,
            ) as resp:
                if resp.status == 200:
                    await self._fetch_capabilities()
                    self.connected = True
                    return True
                return False

        except Exception as e:
            logger.error(f"Failed to connect to SSE server {self.config.name}: {e}")
            return False

    async def _connect_websocket(self) -> bool:
        """Connect using WebSocket transport."""
        try:
            import aiohttp

            if not self.config.url:
                logger.error(f"No URL specified for WebSocket server {self.config.name}")
                return False

            self._session = aiohttp.ClientSession()
            self._ws = await self._session.ws_connect(
                self.config.url,
                headers=self.config.headers,
            )

            # Send initialization
            await self._ws.send_json({
                "jsonrpc": "2.0",
                "id": self._get_request_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "nexus", "version": "1.0.0"},
                },
            })

            response = await self._ws.receive_json()
            if "result" in response:
                await self._fetch_capabilities()
                self.connected = True
                return True
            return False

        except Exception as e:
            logger.error(f"Failed to connect to WebSocket server {self.config.name}: {e}")
            return False

    async def _read_stdio(self):
        """Read messages from STDIO subprocess."""
        if not self._process or not self._process.stdout:
            return

        buffer = b""
        while True:
            try:
                # Read line by line (JSON-RPC uses line-delimited JSON)
                line = await asyncio.get_event_loop().run_in_executor(
                    None, self._process.stdout.readline
                )

                if not line:
                    break

                try:
                    message = json.loads(line.decode())
                    await self._handle_message(message)
                except json.JSONDecodeError:
                    buffer += line
                    try:
                        message = json.loads(buffer.decode())
                        await self._handle_message(message)
                        buffer = b""
                    except json.JSONDecodeError:
                        continue

            except Exception as e:
                logger.error(f"Error reading from MCP server {self.config.name}: {e}")
                break

    async def _handle_message(self, message: Dict[str, Any]):
        """Handle incoming message from MCP server."""
        if "id" in message and message["id"] in self._pending_requests:
            # Response to a request
            future = self._pending_requests.pop(message["id"])
            future.set_result(message)

        elif "method" in message:
            # Notification or request from server
            if self._on_notification:
                await self._on_notification(message)

    def _get_request_id(self) -> int:
        """Get next request ID."""
        self._request_id += 1
        return self._request_id

    async def _send_request(
        self, method: str, params: Dict[str, Any], timeout: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Send a JSON-RPC request and wait for response."""
        request_id = self._get_request_id()
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        future = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future

        try:
            if self.config.transport == MCPTransport.STDIO:
                if self._process and self._process.stdin:
                    message = json.dumps(request) + "\n"
                    self._process.stdin.write(message.encode())
                    self._process.stdin.flush()
            elif self.config.transport == MCPTransport.WEBSOCKET:
                if self._ws:
                    await self._ws.send_json(request)
            elif self.config.transport == MCPTransport.SSE:
                if self._session:
                    async with self._session.post(
                        f"{self.config.url}/message",
                        json=request,
                        headers=self.config.headers,
                    ) as resp:
                        return await resp.json()

            # Wait for response
            timeout_val = timeout or self.config.timeout
            return await asyncio.wait_for(future, timeout=timeout_val)

        except asyncio.TimeoutError:
            logger.warning(f"Request {method} timed out for server {self.config.name}")
            self._pending_requests.pop(request_id, None)
            return None

        except Exception as e:
            logger.error(f"Error sending request to {self.config.name}: {e}")
            self._pending_requests.pop(request_id, None)
            return None

    async def _send_notification(self, method: str, params: Dict[str, Any]):
        """Send a JSON-RPC notification (no response expected)."""
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }

        if self.config.transport == MCPTransport.STDIO:
            if self._process and self._process.stdin:
                message = json.dumps(notification) + "\n"
                self._process.stdin.write(message.encode())
                self._process.stdin.flush()

    async def _fetch_capabilities(self):
        """Fetch tools, resources, and prompts from server."""
        # Fetch tools
        tools_response = await self._send_request("tools/list", {})
        if tools_response and "result" in tools_response:
            for tool_data in tools_response["result"].get("tools", []):
                name = tool_data["name"]

                # Apply tool filtering
                if self.config.allowed_tools and name not in self.config.allowed_tools:
                    continue
                if name in self.config.blocked_tools:
                    continue

                self.tools[name] = MCPTool(
                    name=name,
                    description=tool_data.get("description", ""),
                    input_schema=tool_data.get("inputSchema", {}),
                    server_name=self.config.name,
                )

        # Fetch resources
        resources_response = await self._send_request("resources/list", {})
        if resources_response and "result" in resources_response:
            for res_data in resources_response["result"].get("resources", []):
                self.resources[res_data["uri"]] = MCPResource(
                    uri=res_data["uri"],
                    name=res_data["name"],
                    description=res_data.get("description"),
                    mime_type=res_data.get("mimeType"),
                )

        # Fetch prompts
        prompts_response = await self._send_request("prompts/list", {})
        if prompts_response and "result" in prompts_response:
            for prompt_data in prompts_response["result"].get("prompts", []):
                self.prompts[prompt_data["name"]] = MCPPrompt(
                    name=prompt_data["name"],
                    description=prompt_data.get("description"),
                    arguments=prompt_data.get("arguments", []),
                )

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool on the MCP server."""
        if not self.connected:
            return {"error": f"Not connected to server {self.config.name}"}

        if name not in self.tools:
            return {"error": f"Tool {name} not found on server {self.config.name}"}

        response = await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments,
        })

        if response and "result" in response:
            return response["result"]
        elif response and "error" in response:
            return {"error": response["error"]}
        else:
            return {"error": "No response from server"}

    async def read_resource(self, uri: str) -> Dict[str, Any]:
        """Read a resource from the MCP server."""
        if not self.connected:
            return {"error": f"Not connected to server {self.config.name}"}

        response = await self._send_request("resources/read", {"uri": uri})

        if response and "result" in response:
            return response["result"]
        elif response and "error" in response:
            return {"error": response["error"]}
        else:
            return {"error": "No response from server"}

    async def get_prompt(
        self, name: str, arguments: Dict[str, str]
    ) -> Dict[str, Any]:
        """Get a prompt from the MCP server."""
        if not self.connected:
            return {"error": f"Not connected to server {self.config.name}"}

        response = await self._send_request("prompts/get", {
            "name": name,
            "arguments": arguments,
        })

        if response and "result" in response:
            return response["result"]
        elif response and "error" in response:
            return {"error": response["error"]}
        else:
            return {"error": "No response from server"}

    async def disconnect(self):
        """Disconnect from the MCP server."""
        self.connected = False

        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass

        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()

        if self._ws:
            await self._ws.close()

        if self._session:
            await self._session.close()

        logger.info(f"Disconnected from MCP server {self.config.name}")
