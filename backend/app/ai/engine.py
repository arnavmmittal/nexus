from __future__ import annotations
"""AI Engine - Claude integration with tool use for Nexus."""

import json
from typing import AsyncGenerator, Dict, List, Optional, Any
from uuid import UUID

from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.context import ContextAssembler
from app.ai.prompts import get_system_prompt
from app.ai.tools import TOOLS, ToolExecutor
from app.core.config import settings

# Import agentic tools when available
try:
    from app.agent.executor import get_executor, ConfirmationLevel
    AGENTIC_ENABLED = True
except ImportError:
    AGENTIC_ENABLED = False


class AIEngine:
    """AI Engine for processing chat messages with Claude and executing tools."""

    # Using Haiku for cost efficiency
    MODEL = "claude-3-haiku-20240307"
    MAX_TOKENS = 4096

    def __init__(self, db: AsyncSession, vector_store=None, cost_tracker=None):
        """
        Initialize AI Engine.

        Args:
            db: Database session
            vector_store: Optional vector store for memory search
            cost_tracker: Optional cost tracker for budget management
        """
        self.db = db
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.context_assembler = ContextAssembler(db, vector_store)
        self.vector_store = vector_store
        self.cost_tracker = cost_tracker
        self.conversation_history: Dict[str, List[Dict]] = {}
        self.pending_plans: Dict[str, Any] = {}  # For agentic confirmation flow
        self._agentic_executor = None

    async def get_agentic_executor(self, user_id: UUID):
        """Get the agentic executor for this user."""
        if not AGENTIC_ENABLED:
            return None
        if self._agentic_executor is None:
            self._agentic_executor = await get_executor(
                self.db, user_id, self.cost_tracker
            )
        return self._agentic_executor

    def _sanitize_tool(self, tool: Dict) -> Dict:
        """Remove non-standard fields from tool definition for Claude API."""
        # Claude API only accepts: name, description, input_schema
        sanitized = {
            "name": tool.get("name"),
            "description": tool.get("description"),
        }
        if "input_schema" in tool:
            # Recursively clean input_schema of any non-standard fields
            sanitized["input_schema"] = self._clean_schema(tool["input_schema"])
        return sanitized

    def _clean_schema(self, schema: Dict) -> Dict:
        """Clean a JSON schema of non-standard fields."""
        if not isinstance(schema, dict):
            return schema

        # Standard JSON Schema fields
        allowed_keys = {
            "type", "properties", "required", "items", "enum", "const",
            "default", "description", "minimum", "maximum", "minLength",
            "maxLength", "pattern", "format", "additionalProperties",
            "oneOf", "anyOf", "allOf", "$ref", "$defs", "definitions"
        }

        cleaned = {}
        for key, value in schema.items():
            if key in allowed_keys:
                if key == "properties" and isinstance(value, dict):
                    # Recursively clean each property
                    cleaned[key] = {
                        k: self._clean_schema(v) for k, v in value.items()
                    }
                elif key == "items" and isinstance(value, dict):
                    cleaned[key] = self._clean_schema(value)
                elif key in ("oneOf", "anyOf", "allOf") and isinstance(value, list):
                    cleaned[key] = [self._clean_schema(item) for item in value]
                else:
                    cleaned[key] = value
        return cleaned

    def get_all_tools(self) -> List[Dict]:
        """Get all available tools including agentic ones."""
        all_tools = list(TOOLS)

        # Add agentic tools when available
        if AGENTIC_ENABLED:
            try:
                from app.agent.coder import CODER_TOOLS
                all_tools.extend(CODER_TOOLS)
            except ImportError:
                pass

            try:
                from app.agent.researcher import RESEARCHER_TOOLS
                all_tools.extend(RESEARCHER_TOOLS)
            except ImportError:
                pass

            try:
                from app.agent.system_control import SYSTEM_CONTROL_TOOLS
                all_tools.extend(SYSTEM_CONTROL_TOOLS)
            except ImportError:
                pass

            try:
                from app.agent.finance import FINANCE_TOOLS
                all_tools.extend(FINANCE_TOOLS)
            except ImportError:
                pass

        # Sanitize all tools to remove non-standard fields
        return [self._sanitize_tool(tool) for tool in all_tools]

    async def chat(
        self,
        message: str,
        user_id: UUID,
        conversation_id: Optional[str] = None,
        user_name: str = "User",
    ) -> str:
        """
        Send a message and get a response, with tool execution support.

        Args:
            message: User message
            user_id: User ID for context
            conversation_id: Optional conversation ID for continuity
            user_name: User's name

        Returns:
            Assistant response string
        """
        # Generate conversation ID if not provided
        if not conversation_id:
            import uuid
            conversation_id = str(uuid.uuid4())

        # Assemble context
        context = await self.context_assembler.assemble_context(message, user_id)
        current_state = await self.context_assembler.get_current_state(user_id)

        # Build system prompt
        system_prompt = get_system_prompt(
            user_name=user_name,
            assembled_context=context,
            current_state=current_state,
        )

        # Get or create conversation history
        if conversation_id not in self.conversation_history:
            self.conversation_history[conversation_id] = []

        # Add user message to history
        self.conversation_history[conversation_id].append(
            {"role": "user", "content": message}
        )

        # Keep conversation history manageable (last 20 messages)
        messages = self.conversation_history[conversation_id][-20:]

        # Initialize tool executor
        tool_executor = ToolExecutor(self.db, user_id, self.vector_store)

        # Call Claude API with all available tools
        all_tools = self.get_all_tools()
        response = await self.client.messages.create(
            model=self.MODEL,
            max_tokens=self.MAX_TOKENS,
            system=system_prompt,
            messages=messages,
            tools=all_tools,
        )

        # Process response - handle tool use loop
        final_response = await self._process_response(
            response, messages, system_prompt, tool_executor
        )

        # Add assistant response to history
        self.conversation_history[conversation_id].append(
            {"role": "assistant", "content": final_response}
        )

        return final_response

    async def _process_response(
        self,
        response: Any,
        messages: List[Dict],
        system_prompt: str,
        tool_executor: ToolExecutor,
    ) -> str:
        """
        Process Claude's response, executing tools if needed.

        This handles the tool use loop where Claude may request multiple tools.
        """
        max_iterations = 10  # Prevent infinite loops
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # Check if response has tool use
            if response.stop_reason == "tool_use":
                # Extract tool calls from response
                tool_calls = []
                text_parts = []

                for block in response.content:
                    if block.type == "tool_use":
                        tool_calls.append(block)
                    elif block.type == "text":
                        text_parts.append(block.text)

                # Add assistant message with tool use to history
                messages.append({
                    "role": "assistant",
                    "content": response.content
                })

                # Execute each tool and collect results
                tool_results = []
                for tool_call in tool_calls:
                    result = await tool_executor.execute(
                        tool_call.name,
                        tool_call.input
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_call.id,
                        "content": result
                    })

                # Add tool results to messages
                messages.append({
                    "role": "user",
                    "content": tool_results
                })

                # Call Claude again with tool results
                all_tools = self.get_all_tools()
                response = await self.client.messages.create(
                    model=self.MODEL,
                    max_tokens=self.MAX_TOKENS,
                    system=system_prompt,
                    messages=messages,
                    tools=all_tools,
                )
            else:
                # No more tool use - extract final text response
                final_text = ""
                for block in response.content:
                    if block.type == "text":
                        final_text += block.text

                return final_text

        # If we hit max iterations, return what we have
        return "I apologize, but I encountered an issue processing your request. Please try again."

    async def stream_chat(
        self,
        message: str,
        user_id: UUID,
        conversation_id: Optional[str] = None,
        user_name: str = "User",
    ) -> AsyncGenerator[str, None]:
        """
        Stream a chat response with tool execution.

        Note: Tool execution happens before streaming the final response.

        Args:
            message: User message
            user_id: User ID for context
            conversation_id: Optional conversation ID
            user_name: User's name

        Yields:
            Response content chunks
        """
        # For streaming with tools, we need to handle tool execution first
        # then stream the final response

        # Generate conversation ID if not provided
        if not conversation_id:
            import uuid
            conversation_id = str(uuid.uuid4())

        # Assemble context
        context = await self.context_assembler.assemble_context(message, user_id)
        current_state = await self.context_assembler.get_current_state(user_id)

        # Build system prompt
        system_prompt = get_system_prompt(
            user_name=user_name,
            assembled_context=context,
            current_state=current_state,
        )

        # Get or create conversation history
        if conversation_id not in self.conversation_history:
            self.conversation_history[conversation_id] = []

        # Add user message to history
        self.conversation_history[conversation_id].append(
            {"role": "user", "content": message}
        )

        # Keep conversation history manageable
        messages = self.conversation_history[conversation_id][-20:]

        # Initialize tool executor
        tool_executor = ToolExecutor(self.db, user_id, self.vector_store)

        # First, make a non-streaming call to handle any tool use
        all_tools = self.get_all_tools()
        response = await self.client.messages.create(
            model=self.MODEL,
            max_tokens=self.MAX_TOKENS,
            system=system_prompt,
            messages=messages,
            tools=all_tools,
        )

        # Handle tool use loop (non-streaming)
        while response.stop_reason == "tool_use":
            tool_calls = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_calls.append(block)

            # Add assistant message with tool use
            messages.append({
                "role": "assistant",
                "content": response.content
            })

            # Execute tools
            tool_results = []
            for tool_call in tool_calls:
                result = await tool_executor.execute(
                    tool_call.name,
                    tool_call.input
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_call.id,
                    "content": result
                })

            # Add tool results
            messages.append({
                "role": "user",
                "content": tool_results
            })

            # Continue conversation
            response = await self.client.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                system=system_prompt,
                messages=messages,
                tools=all_tools,
            )

        # Now stream the final response
        full_response = ""
        for block in response.content:
            if block.type == "text":
                full_response += block.text
                # Yield in chunks for streaming effect
                for char in block.text:
                    yield char

        # Add full response to history
        self.conversation_history[conversation_id].append(
            {"role": "assistant", "content": full_response}
        )

    def clear_conversation(self, conversation_id: str) -> None:
        """Clear conversation history."""
        if conversation_id in self.conversation_history:
            del self.conversation_history[conversation_id]

    def get_conversation_history(self, conversation_id: str) -> List[Dict]:
        """Get conversation history."""
        return self.conversation_history.get(conversation_id, [])
