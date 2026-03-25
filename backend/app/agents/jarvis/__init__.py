"""Jarvis Agent module.

JARVIS (Just A Rather Very Intelligent System) is the user-facing AI assistant.
It's polite, helpful, and careful - always confirming before taking significant actions.

This module exports all Jarvis agent components:
- JarvisAgent: The main agent implementation
- JarvisBridge: Bridge to existing tool infrastructure
- JarvisToolRegistry: Registry of all available tools
- Persona components: System prompt and personality traits
"""

from app.agents.jarvis.agent import (
    JarvisAgent,
    UltronDelegation,
    UltronReport,
)
from app.agents.jarvis.bridge import (
    JarvisBridge,
    create_jarvis_bridge,
)
from app.agents.jarvis.tools_integration import (
    JarvisToolRegistry,
    get_tool_registry,
)
from app.agents.jarvis.persona import (
    JARVIS_SYSTEM_PROMPT,
    JARVIS_TRAITS,
    JARVIS_PHRASES,
    CONFIRMATION_REQUIRED_ACTIONS,
    ULTRON_DELEGATABLE_TASKS,
    get_jarvis_prompt_with_context,
    should_delegate_to_ultron,
    requires_confirmation,
)

__all__ = [
    # Agent
    "JarvisAgent",
    "UltronDelegation",
    "UltronReport",
    # Bridge
    "JarvisBridge",
    "create_jarvis_bridge",
    # Tools
    "JarvisToolRegistry",
    "get_tool_registry",
    # Persona
    "JARVIS_SYSTEM_PROMPT",
    "JARVIS_TRAITS",
    "JARVIS_PHRASES",
    "CONFIRMATION_REQUIRED_ACTIONS",
    "ULTRON_DELEGATABLE_TASKS",
    "get_jarvis_prompt_with_context",
    "should_delegate_to_ultron",
    "requires_confirmation",
]
