"""Agent orchestrator for complex multi-agent workflows.

This module provides the main orchestrator that coordinates agents
to achieve complex goals that require collaboration.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from ..message_bus import AgentMessage, MessageBus, MessageType, MessagePriority
from ..registry import AgentRegistry
from .session import CollaborationManager, CollaborationMode, CollaborationSession
from .protocols import DebateProtocol, DelegationProtocol, ParallelExecutionProtocol

logger = logging.getLogger(__name__)


@dataclass
class ExecutionPlan:
    """Represents a plan for executing a complex goal."""

    id: UUID = field(default_factory=uuid4)
    goal: str = ""
    steps: List[Dict[str, Any]] = field(default_factory=list)
    assigned_agents: Dict[str, str] = field(default_factory=dict)  # step_id -> agent_id
    current_step: int = 0
    status: str = "pending"  # pending, executing, completed, failed
    results: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AgentOrchestrator:
    """Orchestrates complex multi-agent workflows.

    The orchestrator analyzes goals, determines which agents should be
    involved, creates execution plans, and coordinates the work.
    """

    # Keywords that suggest certain agents or collaboration modes
    JARVIS_KEYWORDS = [
        "explain", "help", "show", "display", "confirm", "ask",
        "clarify", "present", "summarize", "user",
    ]

    ULTRON_KEYWORDS = [
        "optimize", "automate", "monitor", "analyze", "scan",
        "background", "autonomous", "proactive", "efficiency",
    ]

    COLLABORATION_KEYWORDS = [
        "research and implement", "analyze and present", "both",
        "compare", "debate", "discuss", "together",
    ]

    def __init__(
        self,
        registry: AgentRegistry,
        message_bus: MessageBus,
        collaboration_manager: CollaborationManager,
    ):
        """Initialize the orchestrator.

        Args:
            registry: The agent registry
            message_bus: The message bus for communication
            collaboration_manager: Manager for collaboration sessions
        """
        self.registry = registry
        self.message_bus = message_bus
        self.collab_manager = collaboration_manager

        # Initialize protocols
        self.debate_protocol = DebateProtocol(message_bus, registry)
        self.delegation_protocol = DelegationProtocol(message_bus, registry)
        self.parallel_protocol = ParallelExecutionProtocol(message_bus, registry)

        # Active plans
        self.active_plans: Dict[UUID, ExecutionPlan] = {}

        logger.info("AgentOrchestrator initialized")

    async def execute_complex_goal(
        self,
        goal: str,
        user_id: UUID,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Break down a complex goal and orchestrate agents to achieve it.

        This method:
        1. Analyzes the goal
        2. Determines which agents should be involved
        3. Creates an execution plan
        4. Coordinates agents
        5. Aggregates results

        Args:
            goal: The goal to achieve
            user_id: The user requesting the goal
            context: Optional additional context

        Returns:
            Dictionary with execution results
        """
        logger.info(f"Executing complex goal: '{goal}' for user {user_id}")

        # Step 1: Analyze the goal
        analysis = await self._analyze_goal(goal, context)

        # Step 2: Determine involved agents
        agents = await self._determine_agents(analysis)

        # Step 3: Create execution plan
        plan = await self._create_plan(goal, analysis, agents)
        self.active_plans[plan.id] = plan

        # Step 4: Determine collaboration mode
        mode = self._determine_collaboration_mode(analysis)

        # Step 5: Start collaboration session
        session = await self.collab_manager.start_collaboration(
            goal=goal,
            agents=agents,
            mode=mode,
            metadata={
                "user_id": str(user_id),
                "plan_id": str(plan.id),
                "analysis": analysis,
            },
        )

        # Step 6: Execute based on mode
        try:
            if mode == CollaborationMode.PARALLEL:
                result = await self._execute_parallel(plan, session, context)
            elif mode == CollaborationMode.SEQUENTIAL:
                result = await self._execute_sequential(plan, session, context)
            elif mode == CollaborationMode.DEBATE:
                result = await self._execute_debate(plan, session, context)
            else:  # DELEGATION
                result = await self._execute_delegation(plan, session, context)

            plan.status = "completed"
            plan.results = result

            # End collaboration
            await self.collab_manager.end_collaboration(
                session_id=session.id,
                result=result,
            )

        except Exception as e:
            logger.error(f"Failed to execute goal '{goal}': {e}")
            plan.status = "failed"
            plan.results = {"error": str(e)}
            raise

        finally:
            # Clean up
            del self.active_plans[plan.id]

        return {
            "goal": goal,
            "plan_id": str(plan.id),
            "session_id": str(session.id),
            "mode": mode.value,
            "agents": agents,
            "result": result,
        }

    async def _analyze_goal(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Analyze a goal to understand its requirements.

        Args:
            goal: The goal to analyze
            context: Optional context

        Returns:
            Analysis dictionary
        """
        goal_lower = goal.lower()

        analysis = {
            "goal": goal,
            "requires_user_interaction": any(
                kw in goal_lower for kw in ["confirm", "ask", "show", "present"]
            ),
            "requires_background_work": any(
                kw in goal_lower for kw in ["analyze", "scan", "monitor", "optimize"]
            ),
            "requires_research": any(
                kw in goal_lower for kw in ["research", "find", "search", "compare"]
            ),
            "requires_implementation": any(
                kw in goal_lower for kw in ["implement", "create", "build", "write"]
            ),
            "is_multi_step": "and" in goal_lower or "then" in goal_lower,
            "suggests_debate": any(
                kw in goal_lower for kw in ["should i", "compare", "versus", "vs", "or"]
            ),
            "jarvis_relevance": sum(
                1 for kw in self.JARVIS_KEYWORDS if kw in goal_lower
            ),
            "ultron_relevance": sum(
                1 for kw in self.ULTRON_KEYWORDS if kw in goal_lower
            ),
            "collaboration_suggested": any(
                kw in goal_lower for kw in self.COLLABORATION_KEYWORDS
            ),
        }

        logger.debug(f"Goal analysis: {analysis}")

        return analysis

    async def _determine_agents(
        self,
        analysis: Dict[str, Any],
    ) -> List[str]:
        """Determine which agents should be involved.

        Args:
            analysis: The goal analysis

        Returns:
            List of agent names to involve
        """
        agents = []

        # Check if both agents needed
        if analysis.get("collaboration_suggested") or analysis.get("is_multi_step"):
            agents = ["jarvis", "ultron"]
        elif analysis.get("suggests_debate"):
            agents = ["jarvis", "ultron"]
        elif analysis.get("jarvis_relevance", 0) > analysis.get("ultron_relevance", 0):
            agents = ["jarvis"]
        elif analysis.get("ultron_relevance", 0) > analysis.get("jarvis_relevance", 0):
            agents = ["ultron"]
        else:
            # Default to Jarvis for user-facing requests
            agents = ["jarvis"]

        # For research + implementation, always use both
        if analysis.get("requires_research") and analysis.get("requires_implementation"):
            agents = ["jarvis", "ultron"]

        logger.info(f"Determined agents for goal: {agents}")

        return agents

    async def _create_plan(
        self,
        goal: str,
        analysis: Dict[str, Any],
        agents: List[str],
    ) -> ExecutionPlan:
        """Create an execution plan for the goal.

        Args:
            goal: The goal
            analysis: The goal analysis
            agents: The agents to involve

        Returns:
            The execution plan
        """
        steps = []

        # Research phase
        if analysis.get("requires_research"):
            steps.append({
                "id": str(uuid4()),
                "type": "research",
                "description": "Research and gather information",
                "agent": "ultron" if "ultron" in agents else agents[0],
            })

        # Analysis phase
        if analysis.get("requires_background_work"):
            steps.append({
                "id": str(uuid4()),
                "type": "analysis",
                "description": "Analyze and process data",
                "agent": "ultron" if "ultron" in agents else agents[0],
            })

        # Implementation phase
        if analysis.get("requires_implementation"):
            steps.append({
                "id": str(uuid4()),
                "type": "implementation",
                "description": "Implement the solution",
                "agent": "jarvis" if "jarvis" in agents else agents[0],
            })

        # User interaction phase
        if analysis.get("requires_user_interaction"):
            steps.append({
                "id": str(uuid4()),
                "type": "user_interaction",
                "description": "Present findings and get confirmation",
                "agent": "jarvis",
            })

        # If no specific steps, create a general execution step
        if not steps:
            steps.append({
                "id": str(uuid4()),
                "type": "execute",
                "description": "Execute the goal",
                "agent": agents[0],
            })

        plan = ExecutionPlan(
            goal=goal,
            steps=steps,
            assigned_agents={step["id"]: step["agent"] for step in steps},
        )

        logger.info(f"Created execution plan with {len(steps)} steps")

        return plan

    def _determine_collaboration_mode(
        self,
        analysis: Dict[str, Any],
    ) -> CollaborationMode:
        """Determine the best collaboration mode.

        Args:
            analysis: The goal analysis

        Returns:
            The collaboration mode
        """
        if analysis.get("suggests_debate"):
            return CollaborationMode.DEBATE
        elif analysis.get("is_multi_step") and not analysis.get("collaboration_suggested"):
            return CollaborationMode.SEQUENTIAL
        elif analysis.get("collaboration_suggested") or (
            analysis.get("requires_research") and analysis.get("requires_implementation")
        ):
            return CollaborationMode.PARALLEL
        else:
            return CollaborationMode.DELEGATION

    async def _execute_parallel(
        self,
        plan: ExecutionPlan,
        session: CollaborationSession,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute plan steps in parallel.

        Args:
            plan: The execution plan
            session: The collaboration session
            context: Optional context

        Returns:
            Execution results
        """
        logger.info(f"Executing plan {plan.id} in parallel mode")

        # Group steps by agent
        agent_tasks: Dict[str, List[Dict]] = {}
        for step in plan.steps:
            agent = step["agent"]
            if agent not in agent_tasks:
                agent_tasks[agent] = []
            agent_tasks[agent].append(step)

        # Execute via parallel protocol
        task = {
            "type": "multi_step",
            "payload": {
                "goal": plan.goal,
                "agent_tasks": agent_tasks,
                "context": context,
            },
        }

        result = await self.parallel_protocol.execute_parallel(
            task=task,
            agents=list(agent_tasks.keys()),
            timeout=120.0,
        )

        return result

    async def _execute_sequential(
        self,
        plan: ExecutionPlan,
        session: CollaborationSession,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute plan steps sequentially.

        Args:
            plan: The execution plan
            session: The collaboration session
            context: Optional context

        Returns:
            Execution results
        """
        logger.info(f"Executing plan {plan.id} in sequential mode")

        results = {}
        current_context = context or {}

        for i, step in enumerate(plan.steps):
            plan.current_step = i
            agent = step["agent"]

            # Delegate step to agent
            delegated = await self.delegation_protocol.delegate_task(
                from_agent="orchestrator",
                to_agent=agent,
                task={
                    "type": step["type"],
                    "payload": {
                        "description": step["description"],
                        "goal": plan.goal,
                        "context": current_context,
                        "previous_results": results,
                    },
                },
                callback_on_complete=True,
            )

            # Wait for completion (in real implementation, would use async waiting)
            # For now, store the delegation ID
            results[step["id"]] = {
                "agent": agent,
                "delegation_id": str(delegated.id),
                "status": "delegated",
            }

            # Update context with results for next step
            current_context["previous_step"] = step
            current_context["previous_result"] = results.get(step["id"])

        return {
            "steps_executed": len(plan.steps),
            "results": results,
        }

    async def _execute_debate(
        self,
        plan: ExecutionPlan,
        session: CollaborationSession,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute plan as a debate between agents.

        Args:
            plan: The execution plan
            session: The collaboration session
            context: Optional context

        Returns:
            Debate results
        """
        logger.info(f"Executing plan {plan.id} in debate mode")

        # Start debate
        debate = await self.debate_protocol.initiate_debate(
            topic=plan.goal,
            agents=session.participating_agents,
            max_rounds=5,
        )

        # In a real implementation, agents would submit arguments
        # and the debate would progress. For now, return the debate state.
        return {
            "debate_id": str(debate.session_id),
            "topic": debate.topic,
            "participants": debate.agents,
            "status": "initiated",
        }

    async def _execute_delegation(
        self,
        plan: ExecutionPlan,
        session: CollaborationSession,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute plan by delegating to primary agent.

        Args:
            plan: The execution plan
            session: The collaboration session
            context: Optional context

        Returns:
            Delegation results
        """
        logger.info(f"Executing plan {plan.id} in delegation mode")

        primary_agent = session.participating_agents[0]

        # Delegate entire goal to primary agent
        delegated = await self.delegation_protocol.delegate_task(
            from_agent="orchestrator",
            to_agent=primary_agent,
            task={
                "type": "goal_execution",
                "payload": {
                    "goal": plan.goal,
                    "context": context,
                    "plan": {
                        "id": str(plan.id),
                        "steps": plan.steps,
                    },
                },
            },
            callback_on_complete=True,
        )

        return {
            "delegation_id": str(delegated.id),
            "primary_agent": primary_agent,
            "status": "delegated",
        }

    async def route_message(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str]:
        """Route a message to the most appropriate agent.

        Args:
            message: The message to route
            context: Optional context

        Returns:
            Tuple of (agent_name, reasoning)
        """
        analysis = await self._analyze_goal(message, context)

        jarvis_score = analysis.get("jarvis_relevance", 0)
        ultron_score = analysis.get("ultron_relevance", 0)

        # Add weights based on analysis
        if analysis.get("requires_user_interaction"):
            jarvis_score += 2
        if analysis.get("requires_background_work"):
            ultron_score += 2

        if jarvis_score > ultron_score:
            return ("jarvis", "Message requires user interaction or careful handling")
        elif ultron_score > jarvis_score:
            return ("ultron", "Message suggests autonomous or background work")
        else:
            # Default to Jarvis for ambiguous cases
            return ("jarvis", "Default routing for general requests")

    async def handle_agent_request(
        self,
        from_agent: str,
        request: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle a request from one agent.

        Args:
            from_agent: ID of the requesting agent
            request: The request details

        Returns:
            Response to the request
        """
        request_type = request.get("type")

        logger.info(f"Handling request from {from_agent}: type={request_type}")

        if request_type == "delegate":
            # Agent wants to delegate to another agent
            to_agent = request.get("to_agent")
            task = request.get("task")

            delegated = await self.delegation_protocol.delegate_task(
                from_agent=from_agent,
                to_agent=to_agent,
                task=task,
            )

            return {
                "status": "delegated",
                "delegation_id": str(delegated.id),
            }

        elif request_type == "start_debate":
            # Agent wants to start a debate
            topic = request.get("topic")
            agents = request.get("agents", [from_agent])

            if from_agent not in agents:
                agents.append(from_agent)

            debate = await self.debate_protocol.initiate_debate(
                topic=topic,
                agents=agents,
            )

            return {
                "status": "debate_started",
                "debate_id": str(debate.session_id),
            }

        elif request_type == "get_capable_agents":
            # Agent wants to know who can handle a task
            task_type = request.get("task_type")
            agents = self.registry.find_capable(task_type)

            return {
                "status": "success",
                "capable_agents": [a.name for a in agents],
            }

        else:
            return {
                "status": "error",
                "error": f"Unknown request type: {request_type}",
            }

    async def summarize_collaboration(
        self,
        session_id: UUID,
    ) -> str:
        """Generate a summary of a collaboration for the user.

        Args:
            session_id: The session ID

        Returns:
            Human-readable summary
        """
        session = await self.collab_manager.get_session(session_id)
        if not session:
            return f"No collaboration session found with ID {session_id}"

        summary = f"Collaboration Summary\n"
        summary += f"{'=' * 40}\n\n"
        summary += f"Goal: {session.goal}\n"
        summary += f"Mode: {session.mode.value.title()}\n"
        summary += f"Participants: {', '.join(session.participating_agents)}\n"
        summary += f"Status: {session.status.value.title()}\n"
        summary += f"Duration: {session.updated_at - session.created_at}\n\n"

        if session.messages:
            summary += f"Messages Exchanged: {len(session.messages)}\n"
            summary += "Key Exchanges:\n"
            for msg in session.messages[-5:]:  # Last 5 messages
                summary += f"  - [{msg['from_agent']}] ({msg['intent']}): {msg['content'][:100]}...\n"
            summary += "\n"

        if session.results:
            summary += "Results:\n"
            final = session.results.get("final", {})
            if final:
                summary += f"  Final: {final.get('data', 'No data')}\n"

        return summary
