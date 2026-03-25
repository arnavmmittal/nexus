"""Bridge between old Jarvis implementation and new multi-agent system.

This module provides backward compatibility by wrapping existing tool
executors and integrating with the new agent architecture.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.agents.jarvis.tools_integration import JarvisToolRegistry, get_tool_registry

logger = logging.getLogger(__name__)


class JarvisBridge:
    """Bridge class connecting old Jarvis implementation to new multi-agent system.

    This bridge:
    - Wraps existing tool executors from app/agent/
    - Provides unified tool execution interface
    - Maintains backward compatibility with existing AI engine
    - Supports gradual migration to the new agent architecture
    """

    def __init__(
        self,
        db=None,
        user_id: Optional[UUID] = None,
        cost_tracker=None,
    ):
        """Initialize the bridge.

        Args:
            db: Database session
            user_id: User ID for user-specific operations
            cost_tracker: Optional cost tracker for budget management
        """
        self.db = db
        self.user_id = user_id
        self.cost_tracker = cost_tracker
        self._tool_registry = JarvisToolRegistry(db, user_id)
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize all tool executors.

        This should be called before using the bridge to ensure
        all tools are loaded and ready.
        """
        if self._initialized:
            return

        # Load all tools through the registry
        self._tool_registry._load_all_tools()
        self._initialized = True
        logger.info("JarvisBridge initialized with all tool executors")

    async def execute_tool(
        self,
        tool_name: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a tool using the existing executors.

        Args:
            tool_name: Name of the tool to execute
            params: Parameters for the tool

        Returns:
            Tool execution result
        """
        await self.initialize()

        # Check budget if cost tracker is available
        if self.cost_tracker:
            # Estimate cost for the operation
            estimated_cost = self._estimate_tool_cost(tool_name)
            if estimated_cost > 0:
                is_within_budget = await self.cost_tracker.is_within_budget(
                    estimated_cost
                )
                if not is_within_budget:
                    return {
                        "success": False,
                        "error": "Daily budget exceeded",
                        "message": "Cannot execute tool - daily budget limit reached",
                    }

        # Execute the tool
        result = await self._tool_registry.execute_tool(tool_name, params)

        # Track actual cost if applicable
        if self.cost_tracker and result.get("success"):
            actual_cost = result.get("cost", 0) or self._estimate_tool_cost(tool_name)
            if actual_cost > 0:
                await self.cost_tracker.track_cost(
                    operation=tool_name,
                    actual_cost=actual_cost,
                )

        return result

    def _estimate_tool_cost(self, tool_name: str) -> float:
        """Estimate the cost of executing a tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Estimated cost in dollars
        """
        # Tools that involve API calls typically have costs
        cost_map = {
            # Research tools (may use APIs)
            "search_web_ddg": 0.0,  # Free
            "fetch_webpage": 0.0,   # Free
            "explain_concept": 0.01,  # Claude API
            "research_topic": 0.05,   # Multiple Claude calls
            "summarize_article": 0.01,
            "compare_options": 0.02,

            # Coder tools
            "run_shell_command": 0.0,
            "write_file": 0.0,
            "read_file": 0.0,
            "create_github_repo": 0.0,
            "git_commit_push": 0.0,
            "create_pull_request": 0.0,
            "install_package": 0.0,

            # System tools
            "launch_application": 0.0,
            "take_screenshot": 0.0,
            "list_directory": 0.0,
            "open_file": 0.0,
            "copy_file": 0.0,
            "move_file": 0.0,
            "delete_file": 0.0,
            "create_directory": 0.0,

            # Finance tools
            "get_stock_price": 0.0,  # yfinance is free
            "get_stock_history": 0.0,
            "analyze_portfolio": 0.0,
            "get_spending_summary": 0.0,
        }
        return cost_map.get(tool_name, 0.0)

    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get all available tool definitions.

        Returns:
            List of tool definitions compatible with Claude API
        """
        await self.initialize()
        return self._tool_registry.get_all_tools()

    def get_tool_names(self) -> List[str]:
        """Get list of available tool names.

        Returns:
            List of tool names
        """
        return self._tool_registry.get_tool_names()

    def has_tool(self, name: str) -> bool:
        """Check if a tool is available.

        Args:
            name: Tool name

        Returns:
            True if tool exists
        """
        return self._tool_registry.has_tool(name)

    def tool_requires_confirmation(self, name: str) -> bool:
        """Check if tool requires user confirmation.

        Args:
            name: Tool name

        Returns:
            True if confirmation required
        """
        return self._tool_registry.tool_requires_confirmation(name)

    async def batch_execute_tools(
        self,
        tools: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Execute multiple tools in sequence.

        Args:
            tools: List of dicts with 'name' and 'params' keys

        Returns:
            List of execution results
        """
        results = []
        for tool_spec in tools:
            name = tool_spec.get("name")
            params = tool_spec.get("params", {})

            if not name:
                results.append({
                    "success": False,
                    "error": "Missing tool name",
                })
                continue

            result = await self.execute_tool(name, params)
            results.append(result)

            # Stop on failure if requested
            if tool_spec.get("stop_on_failure", False) and not result.get("success"):
                break

        return results

    def get_tool_categories(self) -> Dict[str, List[str]]:
        """Get tools organized by category.

        Returns:
            Dict mapping category names to lists of tool names
        """
        categories = {
            "coder": [],
            "researcher": [],
            "system_control": [],
            "finance": [],
        }

        for tool_name, tool_info in self._tool_registry._tools.items():
            category = tool_info.get("category", "other")
            if category in categories:
                categories[category].append(tool_name)
            else:
                categories.setdefault("other", []).append(tool_name)

        return categories


# Factory function for creating bridge instances
async def create_jarvis_bridge(
    db=None,
    user_id: Optional[UUID] = None,
    cost_tracker=None,
) -> JarvisBridge:
    """Create and initialize a JarvisBridge instance.

    Args:
        db: Database session
        user_id: User ID
        cost_tracker: Optional cost tracker

    Returns:
        Initialized JarvisBridge instance
    """
    bridge = JarvisBridge(db, user_id, cost_tracker)
    await bridge.initialize()
    return bridge
