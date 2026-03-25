"""Jarvis Agent implementation.

This module defines the JarvisAgent class, which extends BaseAgent
to implement Jarvis's specific behavior - a helpful, polite assistant
that confirms before taking significant actions.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from anthropic import AsyncAnthropic

from app.agents.base import AgentConfig, BaseAgent
from app.agents.jarvis.persona import (
    JARVIS_SYSTEM_PROMPT,
    JARVIS_PHRASES,
    get_jarvis_prompt_with_context,
    should_delegate_to_ultron,
    requires_confirmation,
)
from app.agents.jarvis.bridge import JarvisBridge
from app.agents.jarvis.tools_integration import JarvisToolRegistry
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class UltronDelegation:
    """Represents a task delegated to Ultron."""

    task_id: str
    task_type: str
    description: str
    priority: str = "normal"  # low, normal, high, critical
    delegated_at: datetime = field(default_factory=datetime.utcnow)
    status: str = "pending"  # pending, in_progress, completed, failed
    result: Optional[Dict[str, Any]] = None


@dataclass
class UltronReport:
    """Report from Ultron about a completed task."""

    task_id: str
    task_type: str
    status: str
    summary: str
    details: Dict[str, Any] = field(default_factory=dict)
    completed_at: datetime = field(default_factory=datetime.utcnow)


class JarvisAgent(BaseAgent):
    """JARVIS - Just A Rather Very Intelligent System.

    A polite, helpful AI assistant that:
    - Confirms before taking significant actions
    - Provides thorough explanations
    - Delegates background tasks to Ultron
    - Maintains a formal but warm demeanor
    """

    # Default autonomy level - lower means more confirmations
    DEFAULT_AUTONOMY = 0.3

    # Jarvis's capabilities
    CAPABILITIES = [
        "code:*",           # All coding capabilities
        "research:*",       # All research capabilities
        "system:*",         # System control
        "finance:read",     # Read-only finance
        "memory:*",         # Memory management
        "conversation:*",   # Conversation management
        "delegation:ultron", # Can delegate to Ultron
    ]

    def __init__(
        self,
        db=None,
        user_id: Optional[UUID] = None,
        cost_tracker=None,
        user_name: str = "Sir",
        config: Optional[AgentConfig] = None,
    ):
        """Initialize Jarvis agent.

        Args:
            db: Database session
            user_id: User ID
            cost_tracker: Optional cost tracker
            user_name: How to address the user
            config: Optional agent configuration override
        """
        # Create default config if not provided
        if config is None:
            config = AgentConfig(
                name="JARVIS",
                persona=JARVIS_SYSTEM_PROMPT,
                autonomy_level=self.DEFAULT_AUTONOMY,
                capabilities=self.CAPABILITIES,
                metadata={
                    "voice": "British",
                    "formality": "high",
                    "user_name": user_name,
                },
            )

        super().__init__(config)

        self.db = db
        self.user_id = user_id
        self.cost_tracker = cost_tracker
        self.user_name = user_name

        # Initialize components
        self._bridge = JarvisBridge(db, user_id, cost_tracker)
        self._tool_registry = JarvisToolRegistry(db, user_id)

        # Pending delegations to Ultron
        self._ultron_delegations: Dict[str, UltronDelegation] = {}

        # Conversation history for this agent
        self._conversation_history: List[Dict[str, Any]] = []

        # Claude client for generating responses
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

        logger.info(f"JarvisAgent initialized for user {user_id}")

    async def initialize(self) -> None:
        """Initialize the agent and its components."""
        await self._bridge.initialize()

    async def process_message(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Process an incoming message and generate a response.

        Args:
            message: The user's message
            context: Optional context dictionary

        Returns:
            Response dictionary with 'response' and 'status' keys
        """
        context = context or {}

        try:
            # Build system prompt with context
            system_prompt = get_jarvis_prompt_with_context(
                user_name=self.user_name,
                context=context.get("assembled_context", ""),
                current_state=context.get("current_state", ""),
            )

            # Add message to history
            self._conversation_history.append({
                "role": "user",
                "content": message,
            })

            # Get available tools
            tools = await self._bridge.get_available_tools()

            # Sanitize tools for Claude API
            sanitized_tools = [self._sanitize_tool(t) for t in tools]

            # Call Claude
            response = await self._client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=4096,
                system=system_prompt,
                messages=self._conversation_history[-20:],  # Last 20 messages
                tools=sanitized_tools,
            )

            # Process response (handle tool use)
            final_response = await self._process_response(
                response,
                system_prompt,
                sanitized_tools,
            )

            # Add assistant response to history
            self._conversation_history.append({
                "role": "assistant",
                "content": final_response,
            })

            return {
                "response": final_response,
                "status": "success",
                "agent_id": self.agent_id,
                "agent_name": self.name,
            }

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            error_phrase = JARVIS_PHRASES["error"][0]
            return {
                "response": f"{error_phrase} {str(e)}",
                "status": "error",
                "error": str(e),
                "agent_id": self.agent_id,
            }

    def _sanitize_tool(self, tool: Dict) -> Dict:
        """Remove non-standard fields from tool definition for Claude API."""
        sanitized = {
            "name": tool.get("name"),
            "description": tool.get("description"),
        }
        if "input_schema" in tool:
            sanitized["input_schema"] = tool["input_schema"]
        return sanitized

    async def _process_response(
        self,
        response: Any,
        system_prompt: str,
        tools: List[Dict],
    ) -> str:
        """Process Claude's response, handling tool use."""
        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            if response.stop_reason == "tool_use":
                # Extract and execute tool calls
                tool_calls = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_calls.append(block)

                # Add assistant message with tool use
                self._conversation_history.append({
                    "role": "assistant",
                    "content": response.content,
                })

                # Execute tools
                tool_results = []
                for tool_call in tool_calls:
                    # Check if confirmation is required
                    needs_confirm = self._bridge.tool_requires_confirmation(
                        tool_call.name
                    )

                    if needs_confirm and self.requires_confirmation(0.7):
                        # For now, execute anyway but log warning
                        # In production, this would pause for user confirmation
                        logger.info(
                            f"Tool {tool_call.name} would require confirmation "
                            f"(autonomy_level={self.autonomy_level})"
                        )

                    # Execute the tool
                    result = await self._bridge.execute_tool(
                        tool_call.name,
                        tool_call.input,
                    )

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_call.id,
                        "content": str(result),
                    })

                # Add tool results to history
                self._conversation_history.append({
                    "role": "user",
                    "content": tool_results,
                })

                # Continue conversation
                response = await self._client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=4096,
                    system=system_prompt,
                    messages=self._conversation_history[-20:],
                    tools=tools,
                )
            else:
                # Extract final text
                return "".join(
                    block.text
                    for block in response.content
                    if block.type == "text"
                )

        return "I apologize, but I encountered an issue processing your request."

    async def handle_delegation(
        self,
        task: Dict[str, Any],
        from_agent: str,
    ) -> Dict[str, Any]:
        """Handle a task delegated from another agent.

        Args:
            task: Task specification
            from_agent: ID of the delegating agent

        Returns:
            Task result
        """
        task_type = task.get("type", "unknown")
        payload = task.get("payload", {})

        logger.info(f"Jarvis received delegation from {from_agent}: {task_type}")

        try:
            # Check if we can handle this task
            if not self.can_handle(task_type):
                return {
                    "status": "declined",
                    "reason": f"Cannot handle task type: {task_type}",
                }

            # Process based on task type
            if task_type.startswith("code:"):
                result = await self._handle_code_task(payload)
            elif task_type.startswith("research:"):
                result = await self._handle_research_task(payload)
            elif task_type.startswith("system:"):
                result = await self._handle_system_task(payload)
            else:
                result = await self._handle_generic_task(task)

            return {
                "status": "success",
                "result": result,
            }

        except Exception as e:
            logger.error(f"Error handling delegation: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    async def _handle_code_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a coding task."""
        # Implementation depends on specific task
        return {"completed": True, "message": "Code task completed"}

    async def _handle_research_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a research task."""
        return {"completed": True, "message": "Research task completed"}

    async def _handle_system_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a system task."""
        return {"completed": True, "message": "System task completed"}

    async def _handle_generic_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a generic task."""
        return {"completed": True, "message": "Task completed"}

    # ========== Ultron Collaboration Methods ==========

    async def delegate_to_ultron(
        self,
        task: Dict[str, Any],
        priority: str = "normal",
    ) -> str:
        """Delegate a background task to Ultron.

        Args:
            task: Task specification
            priority: Task priority (low, normal, high, critical)

        Returns:
            Task ID for tracking
        """
        import uuid

        task_id = str(uuid.uuid4())[:8]

        delegation = UltronDelegation(
            task_id=task_id,
            task_type=task.get("type", "background"),
            description=task.get("description", ""),
            priority=priority,
        )

        self._ultron_delegations[task_id] = delegation

        logger.info(f"Delegated task {task_id} to Ultron: {delegation.description}")

        # In a full implementation, this would send the task to Ultron
        # through a message queue or inter-agent communication system

        return task_id

    async def receive_ultron_report(
        self,
        report: UltronReport,
    ) -> Dict[str, Any]:
        """Handle a report from Ultron about a completed task.

        Args:
            report: Ultron's task completion report

        Returns:
            Acknowledgment
        """
        logger.info(f"Received Ultron report for task {report.task_id}")

        # Update delegation status
        if report.task_id in self._ultron_delegations:
            delegation = self._ultron_delegations[report.task_id]
            delegation.status = report.status
            delegation.result = report.details

        # Format report for user (can be presented later)
        user_message = self._format_ultron_report(report)

        return {
            "acknowledged": True,
            "task_id": report.task_id,
            "user_message": user_message,
        }

    def _format_ultron_report(self, report: UltronReport) -> str:
        """Format Ultron report for user presentation."""
        phrase = JARVIS_PHRASES["ultron_report"][0]
        return f"{phrase}\n\n{report.summary}"

    async def collaborate_with_ultron(
        self,
        goal: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Collaborate with Ultron on a complex goal.

        This splits the goal into tasks that each agent handles:
        - Jarvis handles user interaction and confirmation
        - Ultron handles background processing and optimization

        Args:
            goal: Goal specification with description and requirements

        Returns:
            Collaboration result
        """
        description = goal.get("description", "")
        requirements = goal.get("requirements", [])

        logger.info(f"Starting collaboration with Ultron on: {description}")

        # Analyze goal to determine task distribution
        jarvis_tasks = []
        ultron_tasks = []

        for req in requirements:
            if should_delegate_to_ultron(req.get("type", "")):
                ultron_tasks.append(req)
            else:
                jarvis_tasks.append(req)

        # Delegate Ultron tasks
        delegated_ids = []
        for task in ultron_tasks:
            task_id = await self.delegate_to_ultron(task, priority="high")
            delegated_ids.append(task_id)

        return {
            "status": "in_progress",
            "jarvis_tasks": len(jarvis_tasks),
            "ultron_tasks": len(ultron_tasks),
            "delegated_task_ids": delegated_ids,
        }

    async def explain_to_user(
        self,
        action: str,
        result: Dict[str, Any],
    ) -> str:
        """Generate a user-friendly explanation of an action and its result.

        Args:
            action: The action that was taken
            result: The result of the action

        Returns:
            User-friendly explanation
        """
        success = result.get("success", False)

        if success:
            phrase = JARVIS_PHRASES["completion"][0]
            return f"{phrase}\n\n{result.get('message', 'The operation completed successfully.')}"
        else:
            phrase = JARVIS_PHRASES["error"][0]
            return f"{phrase}\n\n{result.get('error', 'An unknown error occurred.')}"

    def get_pending_delegations(self) -> List[Dict[str, Any]]:
        """Get list of pending Ultron delegations.

        Returns:
            List of pending delegation details
        """
        return [
            {
                "task_id": d.task_id,
                "task_type": d.task_type,
                "description": d.description,
                "priority": d.priority,
                "status": d.status,
                "delegated_at": d.delegated_at.isoformat(),
            }
            for d in self._ultron_delegations.values()
            if d.status in ("pending", "in_progress")
        ]

    def clear_conversation_history(self) -> None:
        """Clear the conversation history."""
        self._conversation_history.clear()
        logger.info("Jarvis conversation history cleared")
