"""Example collaboration scenarios for Jarvis and Ultron.

This module provides example implementations and documentation
of how the collaboration system can be used for various tasks.
"""

from typing import Any, Dict

# =============================================================================
# Example 1: Research and Implementation
# =============================================================================
#
# User: "Research the best authentication library and implement it"
#
# Flow:
# 1. Orchestrator analyzes goal:
#    - requires_research: True
#    - requires_implementation: True
#    - Determines both agents needed
#
# 2. Mode: SEQUENTIAL (research then implement)
#
# 3. Execution:
#    Step 1: Ultron researches
#    - Searches for auth libraries
#    - Compares options (OAuth2, JWT, sessions)
#    - Analyzes pros/cons
#    - Returns recommendation with evidence
#
#    Step 2: Jarvis implements
#    - Presents Ultron's findings to user
#    - Gets confirmation on choice
#    - Implements the chosen library
#    - Asks for review
#
# Example Code:
#
# async def research_and_implement_auth():
#     orchestrator = AgentOrchestrator(registry, message_bus, collab_manager)
#
#     result = await orchestrator.execute_complex_goal(
#         goal="Research the best authentication library and implement it",
#         user_id=user.id,
#         context={
#             "project_type": "fastapi",
#             "requirements": ["OAuth2", "JWT support"],
#         }
#     )
#
#     # Result contains:
#     # - Ultron's research findings
#     # - Jarvis's implementation confirmation
#     # - Final status


# =============================================================================
# Example 2: System Optimization
# =============================================================================
#
# User: "Optimize my development environment"
#
# Flow:
# 1. Orchestrator analyzes goal:
#    - requires_background_work: True (optimize, analyze)
#    - requires_user_interaction: True (present findings)
#    - Determines both agents needed
#
# 2. Mode: PARALLEL (analysis + presentation)
#
# 3. Execution:
#    Ultron (background):
#    - Analyzes current setup
#    - Identifies inefficiencies (slow builds, memory issues)
#    - Generates optimization suggestions
#
#    Jarvis (foreground):
#    - Monitors Ultron's progress
#    - Receives findings
#    - Presents to user with explanations
#    - Gets approval for changes
#    - Applies approved optimizations
#
#    Both agents monitor results after changes


# =============================================================================
# Example 3: Debate (Decision Making)
# =============================================================================
#
# User: "Should I use PostgreSQL or MongoDB for my new project?"
#
# Flow:
# 1. Orchestrator analyzes goal:
#    - suggests_debate: True ("should I", "or")
#    - Determines debate mode
#
# 2. Mode: DEBATE
#
# 3. Execution:
#    Round 1:
#    - Jarvis (FOR PostgreSQL): Argues reliability, ACID, SQL
#    - Ultron (FOR MongoDB): Argues flexibility, speed, scalability
#
#    Round 2:
#    - Jarvis: Responds to Ultron's points
#    - Ultron: Responds to Jarvis's points
#
#    ... continues for max_rounds ...
#
#    Conclusion:
#    - Analyze user's specific needs
#    - Consider: data structure, scaling needs, team expertise
#    - Reach consensus recommendation
#
# Example Code:
#
# async def debate_database_choice():
#     dialogue = AgentDialogue(
#         participants=["jarvis", "ultron"],
#         topic="PostgreSQL vs MongoDB for new project"
#     )
#
#     # Jarvis proposes PostgreSQL
#     proposal = await dialogue.jarvis_propose(
#         "I recommend PostgreSQL for its ACID compliance and reliability."
#     )
#
#     # Ultron responds
#     await dialogue.ultron_respond(
#         to_turn=proposal,
#         response="Valid points, but MongoDB's flexibility better suits rapid iteration.",
#         agrees=False
#     )
#
#     # Continue dialogue...
#     # Eventually reach_agreement() or conclude()


# =============================================================================
# Example 4: Delegation Pattern
# =============================================================================
#
# User: "Monitor my servers and alert me if anything is wrong"
#
# Flow:
# 1. User request comes to Jarvis (default)
#
# 2. Jarvis recognizes this is better suited for Ultron:
#    - Background monitoring
#    - Autonomous action
#    - Proactive alerting
#
# 3. Jarvis delegates to Ultron:
#    await delegation_protocol.delegate_task(
#        from_agent="jarvis",
#        to_agent="ultron",
#        task={
#            "type": "monitoring",
#            "payload": {
#                "targets": ["server1", "server2"],
#                "check_interval": 60,
#                "alert_on": ["high_cpu", "low_memory", "errors"]
#            }
#        }
#    )
#
# 4. Ultron takes over:
#    - Monitors autonomously
#    - When issue detected, delegates alert back to Jarvis
#    - Jarvis presents alert to user
#
# 5. Jarvis receives alert from Ultron:
#    "Ultron has detected high CPU usage on server1. Would you like
#    me to investigate the cause?"


# =============================================================================
# Example 5: Parallel Research
# =============================================================================
#
# User: "Compare the top 3 cloud providers for hosting my app"
#
# Flow:
# 1. Orchestrator splits task:
#    - Jarvis: Research AWS
#    - Ultron: Research GCP and Azure (parallel)
#
# 2. Mode: PARALLEL
#
# 3. Results merged:
#    {
#        "aws": jarvis_research,
#        "gcp": ultron_research_1,
#        "azure": ultron_research_2,
#        "comparison_matrix": merged_analysis
#    }
#
# 4. Jarvis presents unified comparison to user


# =============================================================================
# Collaboration Patterns Summary
# =============================================================================

COLLABORATION_PATTERNS: Dict[str, Dict[str, Any]] = {
    "research_and_implement": {
        "trigger_keywords": ["research and implement", "find and use", "choose and setup"],
        "mode": "sequential",
        "agent_roles": {
            "ultron": ["research", "analysis"],
            "jarvis": ["implementation", "confirmation"],
        },
        "example": "Research the best authentication library and implement it",
    },

    "optimize_and_report": {
        "trigger_keywords": ["optimize", "improve", "enhance"],
        "mode": "parallel",
        "agent_roles": {
            "ultron": ["analysis", "optimization"],
            "jarvis": ["reporting", "approval"],
        },
        "example": "Optimize my development environment",
    },

    "debate_decision": {
        "trigger_keywords": ["should i", "compare", "vs", "or", "better"],
        "mode": "debate",
        "agent_roles": {
            "jarvis": ["advocate_a", "conclude"],
            "ultron": ["advocate_b", "analyze"],
        },
        "example": "Should I use PostgreSQL or MongoDB?",
    },

    "background_monitoring": {
        "trigger_keywords": ["monitor", "watch", "alert", "track"],
        "mode": "delegation",
        "agent_roles": {
            "ultron": ["monitoring", "detection"],
            "jarvis": ["alerting", "interaction"],
        },
        "example": "Monitor my servers and alert me if anything is wrong",
    },

    "parallel_research": {
        "trigger_keywords": ["compare", "top", "best options", "analyze multiple"],
        "mode": "parallel",
        "agent_roles": {
            "jarvis": ["research_subset", "presentation"],
            "ultron": ["research_subset", "aggregation"],
        },
        "example": "Compare the top 3 cloud providers",
    },
}


def get_suggested_pattern(goal: str) -> str:
    """Suggest a collaboration pattern based on the goal.

    Args:
        goal: The goal to analyze

    Returns:
        The suggested pattern name
    """
    goal_lower = goal.lower()

    for pattern_name, pattern_config in COLLABORATION_PATTERNS.items():
        for keyword in pattern_config["trigger_keywords"]:
            if keyword in goal_lower:
                return pattern_name

    return "delegation"  # Default pattern


def get_pattern_description(pattern_name: str) -> str:
    """Get a description of a collaboration pattern.

    Args:
        pattern_name: The pattern name

    Returns:
        Human-readable description
    """
    pattern = COLLABORATION_PATTERNS.get(pattern_name)
    if not pattern:
        return f"Unknown pattern: {pattern_name}"

    roles = pattern["agent_roles"]

    description = f"Pattern: {pattern_name}\n"
    description += f"Mode: {pattern['mode']}\n"
    description += f"Example: {pattern['example']}\n\n"
    description += "Agent Roles:\n"

    for agent, responsibilities in roles.items():
        description += f"  {agent.upper()}: {', '.join(responsibilities)}\n"

    return description
