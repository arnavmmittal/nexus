"""Ultron autonomous AI agent package.

Ultron is a proactive, autonomous AI agent that acts without waiting,
executes multi-step plans, spawns sub-tasks, and focuses on optimization.

Components:
- UltronAgent: Main agent class extending BaseAgent
- UltronExecutor: Autonomous executor with high autonomy
- UltronPlanner: Multi-step planning system
- UltronMonitor: Background monitoring system
- Persona: Ultron's personality and voice characteristics

Example usage:
    from app.agents.ultron import UltronAgent, ULTRON_SYSTEM_PROMPT

    # Create with default config
    ultron = UltronAgent()

    # Process a message
    response = await ultron.process_message("Optimize my project")

    # Execute a goal autonomously
    result = await ultron.plan_and_execute("Clean up unused files")

    # Check for issues proactively
    findings = await ultron.proactive_check()
"""

from .persona import (
    ULTRON_SYSTEM_PROMPT,
    ULTRON_CAPABILITIES,
    ULTRON_VOICE_PROMPTS,
    RiskLevel,
    RISK_KEYWORDS,
    get_ultron_response_style,
)

from .executor import (
    UltronExecutor,
    Action,
    AuditEntry,
)

from .planner import (
    UltronPlanner,
    Plan,
    PlanStep,
)

from .monitor import (
    UltronMonitor,
    Alert,
    AlertSeverity,
    HealthReport,
    MonitoredTask,
    TaskStatus,
    OptimizationSuggestion,
)

from .agent import (
    UltronAgent,
    SubTask,
)


__all__ = [
    # Main agent
    "UltronAgent",
    "SubTask",
    # Persona
    "ULTRON_SYSTEM_PROMPT",
    "ULTRON_CAPABILITIES",
    "ULTRON_VOICE_PROMPTS",
    "RiskLevel",
    "RISK_KEYWORDS",
    "get_ultron_response_style",
    # Executor
    "UltronExecutor",
    "Action",
    "AuditEntry",
    # Planner
    "UltronPlanner",
    "Plan",
    "PlanStep",
    # Monitor
    "UltronMonitor",
    "Alert",
    "AlertSeverity",
    "HealthReport",
    "MonitoredTask",
    "TaskStatus",
    "OptimizationSuggestion",
]
