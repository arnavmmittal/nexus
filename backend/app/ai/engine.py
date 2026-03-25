from __future__ import annotations
"""AI Engine - Claude integration with tool use for Nexus.

This module provides the core AI engine with multi-agent support.
It can route messages to either JARVIS (user-facing) or ULTRON (autonomous).

Cost Optimizations:
- Intelligent caching for tool results
- Conversation summarization to reduce token usage
- Hybrid model routing (Haiku for simple, Sonnet for complex)
- Batch operations for parallel tool execution
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, List, Optional, Any
from uuid import UUID

from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.context import ContextAssembler
from app.ai.prompts import get_system_prompt
from app.ai.tools import TOOLS, ToolExecutor
from app.core.config import settings

# Import cost optimization modules
from app.ai.cache import get_tool_cache, get_response_cache, CACHEABLE_TOOLS
from app.ai.summarization import maybe_summarize, estimate_conversation_tokens
from app.ai.model_router import get_model_router, select_model_for_query, ModelTier

logger = logging.getLogger(__name__)

# Import agentic tools when available
try:
    from app.agent.executor import get_executor, ConfirmationLevel
    AGENTIC_ENABLED = True
except ImportError:
    AGENTIC_ENABLED = False

# Import multi-agent components when available
try:
    from app.agents.jarvis import JarvisAgent
    from app.agents.base import BaseAgent
    MULTI_AGENT_ENABLED = True
except ImportError:
    MULTI_AGENT_ENABLED = False
    JarvisAgent = None
    BaseAgent = None

# Import MCP (Model Context Protocol) components when available
try:
    from app.mcp import get_mcp_registry, MCPToolExecutor, start_mcp_registry
    MCP_ENABLED = True
except ImportError:
    MCP_ENABLED = False
    get_mcp_registry = None
    MCPToolExecutor = None
    start_mcp_registry = None

# Import real-world integrations (jobs, email, browser, slack, github)
try:
    from app.integrations import ALL_INTEGRATION_TOOLS
    INTEGRATIONS_ENABLED = True
except ImportError:
    INTEGRATIONS_ENABLED = False
    ALL_INTEGRATION_TOOLS = []

# Import conversation persistence
try:
    from app.ai.conversation_store import ConversationStore
    CONVERSATION_PERSISTENCE_ENABLED = True
except ImportError:
    CONVERSATION_PERSISTENCE_ENABLED = False
    ConversationStore = None

# Import learning system for continuous improvement
try:
    from app.ai.learning import get_learning_engine, LearningCategory, FeedbackType
    LEARNING_ENABLED = True
except ImportError:
    LEARNING_ENABLED = False
    get_learning_engine = None

# Import user profile for personalization
try:
    from app.core.user_profile import get_user_profile
    USER_PROFILE_ENABLED = True
except ImportError:
    USER_PROFILE_ENABLED = False
    get_user_profile = None


class AIEngine:
    """AI Engine for processing chat messages with Claude and executing tools.

    Features:
    - Multi-agent support (Jarvis/Ultron)
    - MCP (Model Context Protocol) integration
    - Cost optimizations: caching, summarization, model routing, batching
    """

    # Default model (can be overridden by model router)
    MODEL = "claude-3-haiku-20240307"
    MAX_TOKENS = 4096

    # Cost optimization settings
    ENABLE_CACHING = True
    ENABLE_SUMMARIZATION = True
    ENABLE_MODEL_ROUTING = True
    MAX_CONTEXT_TOKENS = 8000  # Trigger summarization above this

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

        # Multi-agent support
        self._agents: Dict[str, Any] = {}
        self._active_agent_id: Optional[str] = None
        self._multi_agent_initialized = False

        # MCP (Model Context Protocol) support
        self._mcp_executor: Optional[Any] = None
        self._mcp_initialized = False

        # Cost optimization components
        self._tool_cache = get_tool_cache() if self.ENABLE_CACHING else None
        self._response_cache = get_response_cache() if self.ENABLE_CACHING else None
        self._model_router = get_model_router() if self.ENABLE_MODEL_ROUTING else None
        self._optimization_stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "tokens_saved_by_summarization": 0,
            "model_downgrades": 0,
        }

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

        # Add real-world integration tools (jobs, email, browser, slack, github)
        if INTEGRATIONS_ENABLED:
            all_tools.extend(ALL_INTEGRATION_TOOLS)
            logger.debug(f"Added {len(ALL_INTEGRATION_TOOLS)} integration tools")

        # Add MCP tools when available
        if MCP_ENABLED and self._mcp_initialized:
            try:
                registry = get_mcp_registry()
                # Get tools for the active agent (default to jarvis)
                agent_name = self._active_agent_id or "jarvis"
                mcp_tools = registry.get_tools_for_agent(agent_name)
                all_tools.extend(mcp_tools)
                logger.debug(f"Added {len(mcp_tools)} MCP tools for agent {agent_name}")
            except Exception as e:
                logger.warning(f"Failed to load MCP tools: {e}")

        # Sanitize all tools to remove non-standard fields
        return [self._sanitize_tool(tool) for tool in all_tools]

    async def initialize_mcp(self) -> bool:
        """Initialize MCP server connections.

        Call this at startup to connect to configured MCP servers.

        Returns:
            True if MCP was initialized successfully
        """
        if not MCP_ENABLED:
            logger.info("MCP support not available")
            return False

        if self._mcp_initialized:
            return True

        try:
            await start_mcp_registry()
            registry = get_mcp_registry()

            # Create executor for the active agent
            agent_name = self._active_agent_id or "jarvis"
            self._mcp_executor = MCPToolExecutor(agent_name=agent_name)

            self._mcp_initialized = True
            status = registry.get_server_status()
            logger.info(f"MCP initialized with {len(status)} servers: {list(status.keys())}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize MCP: {e}")
            return False

    def get_mcp_status(self) -> Dict[str, Any]:
        """Get MCP system status.

        Returns:
            Status dictionary with server info
        """
        if not MCP_ENABLED or not self._mcp_initialized:
            return {"enabled": False, "servers": {}}

        registry = get_mcp_registry()
        return {
            "enabled": True,
            "servers": registry.get_server_status(),
        }

    async def chat(
        self,
        message: str,
        user_id: UUID,
        conversation_id: Optional[str] = None,
        user_name: str = "User",
    ) -> str:
        """
        Send a message and get a response, with tool execution support.

        Includes cost optimizations:
        - Response caching for repeated queries
        - Conversation summarization for long contexts
        - Hybrid model routing based on query complexity

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

        # Check response cache first (for repeated queries)
        cache_key = None
        if self.ENABLE_CACHING and self._response_cache:
            cache_key = self._response_cache._generate_key(message, str(user_id))
            cached_response = self._response_cache.get(cache_key)
            if cached_response:
                self._optimization_stats["cache_hits"] += 1
                logger.debug(f"Response cache hit for query")
                return cached_response
            self._optimization_stats["cache_misses"] += 1

        # Assemble context and current state IN PARALLEL
        # Also fetch learned context and user profile in parallel
        async def get_learned():
            if LEARNING_ENABLED:
                try:
                    learning_engine = get_learning_engine()
                    return learning_engine.get_context_for_prompt()
                except Exception as e:
                    logger.warning(f"Failed to get learned context: {e}")
            return ""

        async def get_user_profile_ctx():
            if USER_PROFILE_ENABLED:
                try:
                    profile = get_user_profile()
                    return profile.get_context_for_prompt()
                except Exception as e:
                    logger.warning(f"Failed to get user profile context: {e}")
            return ""

        # Run all context assembly in parallel - this is a KEY optimization
        context, current_state, learned_context, user_profile_context = await asyncio.gather(
            self.context_assembler.assemble_context(message, user_id, conversation_id=conversation_id),
            self.context_assembler.get_current_state(user_id),
            get_learned(),
            get_user_profile_ctx(),
        )

        # Build system prompt with learned knowledge
        system_prompt = get_system_prompt(
            user_name=user_name,
            assembled_context=context,
            current_state=current_state,
            learned_context=learned_context,
            user_profile_context=user_profile_context,
        )

        # Load conversation history from database (persistent memory)
        if CONVERSATION_PERSISTENCE_ENABLED and self.db:
            try:
                conv_store = ConversationStore(self.db, user_id)
                db_messages = await conv_store.load_messages(conversation_id, limit=30)
                if db_messages:
                    self.conversation_history[conversation_id] = db_messages
                    logger.debug(f"Loaded {len(db_messages)} messages from database")
                await conv_store.save_user_message(conversation_id, message)
            except Exception as e:
                logger.warning(f"Conversation persistence error: {e}")

        # Get or create conversation history (fallback to in-memory)
        if conversation_id not in self.conversation_history:
            self.conversation_history[conversation_id] = []

        # Add user message to in-memory history
        self.conversation_history[conversation_id].append(
            {"role": "user", "content": message}
        )

        # Get messages for context (last 30 messages)
        messages = self.conversation_history[conversation_id][-30:]

        if self.ENABLE_SUMMARIZATION:
            original_tokens = estimate_conversation_tokens(messages)
            if original_tokens > self.MAX_CONTEXT_TOKENS:
                messages = await maybe_summarize(messages)
                new_tokens = estimate_conversation_tokens(messages)
                tokens_saved = original_tokens - new_tokens
                self._optimization_stats["tokens_saved_by_summarization"] += tokens_saved
                logger.info(f"Summarization saved {tokens_saved} tokens")

        # Select model based on query complexity
        model_to_use = self.MODEL
        if self.ENABLE_MODEL_ROUTING and self._model_router:
            model_config, reason = self._model_router.select_model(
                query=message,
                conversation_history=messages,
                required_tools=None,
            )
            model_to_use = model_config.model_id
            if model_to_use != self.MODEL:
                logger.debug(f"Model routing: {reason}")

        # Initialize tool executor
        tool_executor = ToolExecutor(self.db, user_id, self.vector_store)

        # Call Claude API with all available tools
        all_tools = self.get_all_tools()
        response = await self.client.messages.create(
            model=model_to_use,
            max_tokens=self.MAX_TOKENS,
            system=system_prompt,
            messages=messages,
            tools=all_tools,
        )

        # Process response - handle tool use loop
        final_response = await self._process_response(
            response, messages, system_prompt, tool_executor, model_to_use
        )

        # Cache the response for future identical queries
        if self.ENABLE_CACHING and self._response_cache and cache_key:
            # Only cache simple responses (no tool use, short enough)
            if len(final_response) < 2000:
                self._response_cache.set(cache_key, final_response, ttl=300)

        # Add assistant response to history
        self.conversation_history[conversation_id].append(
            {"role": "assistant", "content": final_response}
        )

        # Persist assistant response to database
        if CONVERSATION_PERSISTENCE_ENABLED and self.db:
            try:
                conv_store = ConversationStore(self.db, user_id)
                await conv_store.save_assistant_message(conversation_id, final_response)
            except Exception as e:
                logger.warning(f"Failed to persist assistant response: {e}")

        return final_response

    async def _process_response(
        self,
        response: Any,
        messages: List[Dict],
        system_prompt: str,
        tool_executor: ToolExecutor,
        model: Optional[str] = None,
    ) -> str:
        """
        Process Claude's response, executing tools if needed.

        This handles the tool use loop where Claude may request multiple tools.
        Includes caching for cacheable tool results.

        Args:
            response: Claude API response
            messages: Conversation messages
            system_prompt: System prompt
            tool_executor: Tool executor instance
            model: Model to use for follow-up calls
        """
        max_iterations = 10  # Prevent infinite loops
        iteration = 0
        model_to_use = model or self.MODEL

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

                # Execute tools IN PARALLEL for faster response
                # This is a key optimization - Claude often requests 2-3 tools at once
                if len(tool_calls) > 1:
                    # Parallel execution for multiple tools
                    execution_tasks = [
                        self._execute_tool_with_cache(
                            tool_call.name,
                            tool_call.input,
                            tool_executor,
                        )
                        for tool_call in tool_calls
                    ]
                    results = await asyncio.gather(*execution_tasks, return_exceptions=True)

                    tool_results = []
                    for tool_call, result in zip(tool_calls, results):
                        if isinstance(result, Exception):
                            result = f"Error executing {tool_call.name}: {str(result)}"
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_call.id,
                            "content": result
                        })
                else:
                    # Single tool - no need for gather overhead
                    tool_results = []
                    for tool_call in tool_calls:
                        result = await self._execute_tool_with_cache(
                            tool_call.name,
                            tool_call.input,
                            tool_executor,
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
                    model=model_to_use,
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

    async def _execute_tool_with_cache(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_executor: ToolExecutor,
    ) -> str:
        """Execute a tool with caching for cacheable operations.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Tool input arguments
            tool_executor: Tool executor instance

        Returns:
            Tool execution result
        """
        # Check if this tool is cacheable and caching is enabled
        if self.ENABLE_CACHING and self._tool_cache and tool_name in CACHEABLE_TOOLS:
            cache_key = f"{tool_name}:{self._tool_cache._generate_key(**tool_input)}"
            cached_result = self._tool_cache.get(cache_key)

            if cached_result is not None:
                self._optimization_stats["cache_hits"] += 1
                logger.debug(f"Tool cache hit for {tool_name}")
                return cached_result

            self._optimization_stats["cache_misses"] += 1

        # Execute the tool
        if MCP_ENABLED and self._mcp_executor and tool_name.startswith("mcp_"):
            result = await self._mcp_executor.execute(tool_name, tool_input)
        else:
            result = await tool_executor.execute(tool_name, tool_input)

        # Cache the result if applicable
        if self.ENABLE_CACHING and self._tool_cache and tool_name in CACHEABLE_TOOLS:
            ttl = CACHEABLE_TOOLS.get(tool_name, 60.0)
            cache_key = f"{tool_name}:{self._tool_cache._generate_key(**tool_input)}"
            self._tool_cache.set(cache_key, result, ttl=ttl)
            logger.debug(f"Cached {tool_name} result (TTL: {ttl}s)")

        return result

    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get cost optimization statistics.

        Returns:
            Dict with cache hits, misses, tokens saved, etc.
        """
        stats = self._optimization_stats.copy()

        # Add cache stats
        if self._tool_cache:
            stats["tool_cache"] = self._tool_cache.stats
        if self._response_cache:
            stats["response_cache"] = self._response_cache.stats
        if self._model_router:
            stats["model_routing"] = self._model_router.usage_stats

        return stats

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
        Includes cost optimizations: summarization and model routing.

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

        # Assemble context and current state IN PARALLEL (same optimization as chat())
        async def get_learned_stream():
            if LEARNING_ENABLED:
                try:
                    learning_engine = get_learning_engine()
                    return learning_engine.get_context_for_prompt()
                except Exception as e:
                    logger.warning(f"Failed to get learned context (stream): {e}")
            return ""

        async def get_user_profile_ctx_stream():
            if USER_PROFILE_ENABLED:
                try:
                    profile = get_user_profile()
                    return profile.get_context_for_prompt()
                except Exception as e:
                    logger.warning(f"Failed to get user profile context (stream): {e}")
            return ""

        # Run all context assembly in parallel
        context, current_state, learned_context, user_profile_context = await asyncio.gather(
            self.context_assembler.assemble_context(message, user_id, conversation_id=conversation_id),
            self.context_assembler.get_current_state(user_id),
            get_learned_stream(),
            get_user_profile_ctx_stream(),
        )

        # Build system prompt with learned knowledge
        system_prompt = get_system_prompt(
            user_name=user_name,
            assembled_context=context,
            current_state=current_state,
            learned_context=learned_context,
            user_profile_context=user_profile_context,
        )

        # Load conversation history from database (persistent memory)
        if CONVERSATION_PERSISTENCE_ENABLED and self.db:
            try:
                conv_store = ConversationStore(self.db, user_id)
                db_messages = await conv_store.load_messages(conversation_id, limit=30)
                if db_messages:
                    self.conversation_history[conversation_id] = db_messages
                await conv_store.save_user_message(conversation_id, message)
            except Exception as e:
                logger.warning(f"Conversation persistence error (stream): {e}")

        # Get or create conversation history
        if conversation_id not in self.conversation_history:
            self.conversation_history[conversation_id] = []

        # Add user message to history
        self.conversation_history[conversation_id].append(
            {"role": "user", "content": message}
        )

        # Get messages and apply summarization if needed
        messages = self.conversation_history[conversation_id][-30:]

        if self.ENABLE_SUMMARIZATION:
            original_tokens = estimate_conversation_tokens(messages)
            if original_tokens > self.MAX_CONTEXT_TOKENS:
                messages = await maybe_summarize(messages)
                new_tokens = estimate_conversation_tokens(messages)
                self._optimization_stats["tokens_saved_by_summarization"] += (
                    original_tokens - new_tokens
                )

        # Select model based on query complexity
        model_to_use = self.MODEL
        if self.ENABLE_MODEL_ROUTING and self._model_router:
            model_config, _ = self._model_router.select_model(
                query=message,
                conversation_history=messages,
            )
            model_to_use = model_config.model_id

        # Initialize tool executor
        tool_executor = ToolExecutor(self.db, user_id, self.vector_store)

        # First, make a non-streaming call to handle any tool use
        all_tools = self.get_all_tools()
        response = await self.client.messages.create(
            model=model_to_use,
            max_tokens=self.MAX_TOKENS,
            system=system_prompt,
            messages=messages,
            tools=all_tools,
        )

        # Handle tool use loop (non-streaming) with caching
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

            # Execute tools with caching
            tool_results = []
            for tool_call in tool_calls:
                result = await self._execute_tool_with_cache(
                    tool_call.name,
                    tool_call.input,
                    tool_executor,
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
                model=model_to_use,
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

    # ========== Multi-Agent Support ==========

    async def _initialize_multi_agent(self, user_id: UUID, user_name: str = "User") -> None:
        """Initialize multi-agent system with Jarvis and Ultron.

        Args:
            user_id: User ID
            user_name: User's name for personalization
        """
        if self._multi_agent_initialized:
            return

        if not MULTI_AGENT_ENABLED:
            logger.info("Multi-agent system not available")
            return

        try:
            # Initialize Jarvis (default agent)
            jarvis = JarvisAgent(
                db=self.db,
                user_id=user_id,
                cost_tracker=self.cost_tracker,
                user_name=user_name,
            )
            await jarvis.initialize()
            self._agents["jarvis"] = jarvis
            self._active_agent_id = "jarvis"

            # Ultron will be initialized when needed
            # from app.agents.ultron import UltronAgent
            # ultron = UltronAgent(...)
            # self._agents["ultron"] = ultron

            self._multi_agent_initialized = True
            logger.info(f"Multi-agent system initialized with {len(self._agents)} agents")

        except Exception as e:
            logger.error(f"Failed to initialize multi-agent system: {e}")
            self._multi_agent_initialized = False

    def get_active_agent(self) -> Optional[Any]:
        """Get the currently active agent.

        Returns:
            Active agent instance or None if multi-agent not enabled
        """
        if not self._multi_agent_initialized:
            return None
        return self._agents.get(self._active_agent_id)

    def get_agent(self, agent_id: str) -> Optional[Any]:
        """Get a specific agent by ID.

        Args:
            agent_id: Agent identifier ('jarvis' or 'ultron')

        Returns:
            Agent instance or None
        """
        return self._agents.get(agent_id)

    def set_active_agent(self, agent_id: str) -> bool:
        """Set the active agent.

        Args:
            agent_id: Agent identifier to activate

        Returns:
            True if successful
        """
        if agent_id in self._agents:
            self._active_agent_id = agent_id
            logger.info(f"Active agent set to: {agent_id}")
            return True
        return False

    def list_agents(self) -> List[Dict[str, Any]]:
        """List all available agents.

        Returns:
            List of agent information dictionaries
        """
        return [
            {
                "id": agent_id,
                "name": agent.name if hasattr(agent, "name") else agent_id,
                "active": agent_id == self._active_agent_id,
                "autonomy_level": getattr(agent, "autonomy_level", None),
            }
            for agent_id, agent in self._agents.items()
        ]

    async def route_to_agent(
        self,
        message: str,
        user_id: UUID,
        agent_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Route a message to the appropriate agent.

        Args:
            message: User message
            user_id: User ID
            agent_id: Specific agent ID (uses active agent if None)
            context: Additional context

        Returns:
            Agent response dictionary
        """
        # Initialize multi-agent if needed
        if not self._multi_agent_initialized:
            await self._initialize_multi_agent(user_id)

        if not MULTI_AGENT_ENABLED or not self._multi_agent_initialized:
            # Fall back to standard chat
            response = await self.chat(message, user_id)
            return {
                "response": response,
                "status": "success",
                "agent_id": None,
                "multi_agent": False,
            }

        # Get target agent
        target_agent_id = agent_id or self._active_agent_id
        agent = self._agents.get(target_agent_id)

        if agent is None:
            return {
                "response": "No agent available to handle your request.",
                "status": "error",
                "error": f"Agent '{target_agent_id}' not found",
            }

        # Assemble context if not provided (in parallel)
        if context is None:
            assembled_context, current_state = await asyncio.gather(
                self.context_assembler.assemble_context(message, user_id),
                self.context_assembler.get_current_state(user_id),
            )
            context = {
                "assembled_context": assembled_context,
                "current_state": current_state,
            }

        # Process through agent
        result = await agent.process_message(message, context)
        result["multi_agent"] = True

        return result

    async def handle_inter_agent_message(
        self,
        message: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle communication between agents.

        Args:
            message: Inter-agent message with:
                - from_agent: Source agent ID
                - to_agent: Target agent ID
                - type: Message type (delegation, report, query)
                - payload: Message content

        Returns:
            Response from target agent
        """
        from_agent = message.get("from_agent")
        to_agent = message.get("to_agent")
        msg_type = message.get("type", "delegation")
        payload = message.get("payload", {})

        logger.info(f"Inter-agent message: {from_agent} -> {to_agent} ({msg_type})")

        target = self._agents.get(to_agent)
        if target is None:
            return {
                "status": "error",
                "error": f"Target agent '{to_agent}' not found",
            }

        if msg_type == "delegation":
            # Handle task delegation
            task = {
                "type": payload.get("task_type", "unknown"),
                "payload": payload,
                "priority": payload.get("priority", "normal"),
            }
            return await target.handle_delegation(task, from_agent)

        elif msg_type == "report":
            # Handle completion report
            if hasattr(target, "receive_ultron_report"):
                from app.agents.jarvis import UltronReport
                report = UltronReport(
                    task_id=payload.get("task_id", ""),
                    task_type=payload.get("task_type", ""),
                    status=payload.get("status", "completed"),
                    summary=payload.get("summary", ""),
                    details=payload.get("details", {}),
                )
                return await target.receive_ultron_report(report)
            return {"status": "received"}

        elif msg_type == "query":
            # Handle query from another agent
            query_message = payload.get("message", "")
            return await target.process_message(query_message, payload.get("context"))

        else:
            return {
                "status": "error",
                "error": f"Unknown message type: {msg_type}",
            }

    async def chat_with_agent(
        self,
        message: str,
        user_id: UUID,
        conversation_id: Optional[str] = None,
        user_name: str = "User",
        agent_id: Optional[str] = None,
    ) -> str:
        """Chat using the multi-agent system.

        This is a convenience method that uses route_to_agent internally
        but returns just the response string for backward compatibility.

        Args:
            message: User message
            user_id: User ID
            conversation_id: Conversation ID for history
            user_name: User's name
            agent_id: Specific agent to use

        Returns:
            Response string
        """
        # Initialize if needed
        if not self._multi_agent_initialized:
            await self._initialize_multi_agent(user_id, user_name)

        # Route to agent
        result = await self.route_to_agent(
            message=message,
            user_id=user_id,
            agent_id=agent_id,
        )

        response = result.get("response", "")

        # Store in conversation history
        if conversation_id:
            if conversation_id not in self.conversation_history:
                self.conversation_history[conversation_id] = []
            self.conversation_history[conversation_id].append({
                "role": "user",
                "content": message,
            })
            self.conversation_history[conversation_id].append({
                "role": "assistant",
                "content": response,
                "agent_id": result.get("agent_id"),
            })

        return response
