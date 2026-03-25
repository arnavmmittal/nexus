"""Tools integration for Jarvis agent.

This module provides a unified interface to all existing tools
from the app/agent/ modules, mapping them to the new agent system.
"""

import logging
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class JarvisToolRegistry:
    """Registry that integrates all existing tools with the Jarvis agent.

    This class provides a unified interface to load and execute tools
    from various modules (coder, researcher, system_control, finance).
    """

    def __init__(self, db=None, user_id: Optional[UUID] = None):
        """Initialize the tool registry.

        Args:
            db: Database session for tools that need it
            user_id: User ID for user-specific operations
        """
        self.db = db
        self.user_id = user_id
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._executors: Dict[str, Any] = {}
        self._loaded = False

    def _load_all_tools(self) -> None:
        """Load all tools from existing modules."""
        if self._loaded:
            return

        self._load_coder_tools()
        self._load_researcher_tools()
        self._load_system_tools()
        self._load_finance_tools()
        self._loaded = True

    def _load_coder_tools(self) -> None:
        """Load tools from the coder module."""
        try:
            from app.agent.coder import CODER_TOOLS, CoderToolExecutor

            executor = CoderToolExecutor(self.db, self.user_id)
            self._executors["coder"] = executor

            for tool in CODER_TOOLS:
                tool_name = tool["name"]
                self._tools[tool_name] = {
                    "definition": tool,
                    "executor": "coder",
                    "handler": getattr(executor, f"_tool_{tool_name}", None),
                    "category": "coder",
                    "requires_confirmation": tool.get("requires_confirmation", True),
                }
            logger.info(f"Loaded {len(CODER_TOOLS)} coder tools")
        except ImportError as e:
            logger.warning(f"Could not load coder tools: {e}")
        except Exception as e:
            logger.error(f"Error loading coder tools: {e}")

    def _load_researcher_tools(self) -> None:
        """Load tools from the researcher module."""
        try:
            from app.agent.researcher import RESEARCHER_TOOLS, ResearcherExecutor

            executor = ResearcherExecutor(self.db, self.user_id)
            self._executors["researcher"] = executor

            for tool in RESEARCHER_TOOLS:
                tool_name = tool["name"]
                self._tools[tool_name] = {
                    "definition": tool,
                    "executor": "researcher",
                    "handler": getattr(executor, f"_tool_{tool_name}", None),
                    "category": "researcher",
                    "requires_confirmation": tool.get("requires_confirmation", False),
                }
            logger.info(f"Loaded {len(RESEARCHER_TOOLS)} researcher tools")
        except ImportError as e:
            logger.warning(f"Could not load researcher tools: {e}")
        except Exception as e:
            logger.error(f"Error loading researcher tools: {e}")

    def _load_system_tools(self) -> None:
        """Load tools from the system_control module."""
        try:
            from app.agent.system_control import (
                SYSTEM_CONTROL_TOOLS,
                SystemControlExecutor,
            )

            executor = SystemControlExecutor(self.db, self.user_id)
            self._executors["system_control"] = executor

            for tool in SYSTEM_CONTROL_TOOLS:
                tool_name = tool["name"]
                self._tools[tool_name] = {
                    "definition": tool,
                    "executor": "system_control",
                    "handler": getattr(executor, f"_tool_{tool_name}", None),
                    "category": "system_control",
                    "requires_confirmation": tool.get("requires_confirmation", True),
                }
            logger.info(f"Loaded {len(SYSTEM_CONTROL_TOOLS)} system control tools")
        except ImportError as e:
            logger.warning(f"Could not load system control tools: {e}")
        except Exception as e:
            logger.error(f"Error loading system control tools: {e}")

    def _load_finance_tools(self) -> None:
        """Load tools from the finance module."""
        try:
            from app.agent.finance import FINANCE_TOOLS, FinanceToolExecutor

            executor = FinanceToolExecutor(self.db, self.user_id)
            self._executors["finance"] = executor

            for tool in FINANCE_TOOLS:
                tool_name = tool["name"]
                self._tools[tool_name] = {
                    "definition": tool,
                    "executor": "finance",
                    "handler": getattr(executor, f"_tool_{tool_name}", None),
                    "category": "finance",
                    "requires_confirmation": tool.get("requires_confirmation", False),
                }
            logger.info(f"Loaded {len(FINANCE_TOOLS)} finance tools")
        except ImportError as e:
            logger.warning(f"Could not load finance tools: {e}")
        except Exception as e:
            logger.error(f"Error loading finance tools: {e}")

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """Get all available tool definitions.

        Returns:
            List of tool definitions for Claude API
        """
        self._load_all_tools()
        return [tool_info["definition"] for tool_info in self._tools.values()]

    def get_tools_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get tools for a specific category.

        Args:
            category: One of 'coder', 'researcher', 'system_control', 'finance'

        Returns:
            List of tool definitions in that category
        """
        self._load_all_tools()
        return [
            tool_info["definition"]
            for tool_info in self._tools.values()
            if tool_info["category"] == category
        ]

    def get_tool_names(self) -> List[str]:
        """Get list of all available tool names.

        Returns:
            List of tool names
        """
        self._load_all_tools()
        return list(self._tools.keys())

    def has_tool(self, name: str) -> bool:
        """Check if a tool exists.

        Args:
            name: Tool name

        Returns:
            True if the tool exists
        """
        self._load_all_tools()
        return name in self._tools

    def tool_requires_confirmation(self, name: str) -> bool:
        """Check if a tool requires user confirmation.

        Args:
            name: Tool name

        Returns:
            True if confirmation is required
        """
        self._load_all_tools()
        if name not in self._tools:
            return True  # Default to requiring confirmation for unknown tools
        return self._tools[name].get("requires_confirmation", True)

    async def execute_tool(
        self,
        name: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a tool by name.

        Args:
            name: Name of the tool to execute
            params: Parameters to pass to the tool

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool not found or handler not available
        """
        self._load_all_tools()

        if name not in self._tools:
            raise ValueError(f"Unknown tool: {name}")

        tool_info = self._tools[name]
        handler = tool_info.get("handler")

        if handler is None:
            raise ValueError(f"No handler available for tool: {name}")

        try:
            result = await handler(**params)
            logger.info(f"Tool {name} executed successfully")
            return result
        except Exception as e:
            logger.error(f"Tool {name} execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Tool execution failed: {e}",
            }

    def get_executor(self, category: str) -> Optional[Any]:
        """Get the executor instance for a category.

        Args:
            category: Executor category

        Returns:
            Executor instance or None
        """
        self._load_all_tools()
        return self._executors.get(category)


# Singleton instance for convenience
_global_registry: Optional[JarvisToolRegistry] = None


def get_tool_registry(
    db=None,
    user_id: Optional[UUID] = None,
) -> JarvisToolRegistry:
    """Get or create the global tool registry.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        JarvisToolRegistry instance
    """
    global _global_registry

    # Create new instance if needed or if credentials changed
    if (
        _global_registry is None
        or _global_registry.db != db
        or _global_registry.user_id != user_id
    ):
        _global_registry = JarvisToolRegistry(db, user_id)

    return _global_registry
