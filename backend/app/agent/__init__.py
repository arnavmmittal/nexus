"""Agent module for Nexus/Jarvis agentic capabilities.

This module provides specialized agent tools for different domains:
- system_control: macOS system automation and file operations
- coder: Code generation, file manipulation, git operations, GitHub integration
- researcher: Web search, content fetching, AI-powered research and analysis
- finance: Financial tracking and budgeting tools
- cost_tracker: API cost tracking and budget management
"""

from .system_control import (
    SYSTEM_CONTROL_TOOLS,
    SystemControlExecutor,
    is_path_safe,
    SAFE_DIRECTORIES,
)
from .cost_tracker import (
    CostTracker,
    BudgetExceededError,
    track_cost,
    track_cost_with_actual,
)
from .finance import (
    FINANCE_TOOLS,
    FinanceToolExecutor,
)
from .coder import (
    # Tool functions
    run_shell_command,
    write_file,
    read_file,
    create_github_repo,
    git_commit_push,
    create_pull_request,
    install_package,
    # Tool definitions
    CODER_TOOLS,
    # Executor class
    CoderToolExecutor,
    # Configuration
    DEFAULT_TIMEOUT,
)
from .conversation_manager import (
    ConversationManager,
    get_conversation_manager,
)
from .researcher import (
    RESEARCHER_TOOLS,
    ResearcherTools,
    ResearcherExecutor,
    ResearchResult,
)

__all__ = [
    # System control tools
    "SYSTEM_CONTROL_TOOLS",
    "SystemControlExecutor",
    "is_path_safe",
    "SAFE_DIRECTORIES",
    # Cost tracking
    "CostTracker",
    "BudgetExceededError",
    "track_cost",
    "track_cost_with_actual",
    # Finance tools
    "FINANCE_TOOLS",
    "FinanceToolExecutor",
    # Coder tools
    "CODER_TOOLS",
    "CoderToolExecutor",
    "run_shell_command",
    "write_file",
    "read_file",
    "create_github_repo",
    "git_commit_push",
    "create_pull_request",
    "install_package",
    "DEFAULT_TIMEOUT",
    # Conversation management
    "ConversationManager",
    "get_conversation_manager",
    # Research tools
    "RESEARCHER_TOOLS",
    "ResearcherTools",
    "ResearcherExecutor",
    "ResearchResult",
]
