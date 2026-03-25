"""Collaboration protocols for multi-agent coordination.

This module defines structured protocols for different types of
agent collaboration: debates, delegation, and parallel execution.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID, uuid4

from ..message_bus import AgentMessage, MessageBus, MessageType, MessagePriority

logger = logging.getLogger(__name__)


@dataclass
class Argument:
    """Represents an argument in a debate."""

    id: str = field(default_factory=lambda: str(uuid4()))
    agent_id: str = ""
    position: str = ""  # "for" or "against"
    content: str = ""
    supporting_evidence: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    round_number: int = 0


@dataclass
class DebateState:
    """State of a debate between agents."""

    session_id: UUID = field(default_factory=uuid4)
    topic: str = ""
    agents: List[str] = field(default_factory=list)
    arguments: List[Argument] = field(default_factory=list)
    current_round: int = 0
    max_rounds: int = 5
    consensus_reached: bool = False
    consensus_position: Optional[str] = None
    final_recommendation: Optional[str] = None


class DebateProtocol:
    """Protocol for agents to debate and discuss topics.

    This protocol facilitates structured debates where agents can
    present arguments, respond to each other, and reach consensus.
    """

    def __init__(self, message_bus: MessageBus, agent_registry: Any):
        """Initialize the debate protocol.

        Args:
            message_bus: The message bus for communication
            agent_registry: The agent registry for looking up agents
        """
        self.message_bus = message_bus
        self.agent_registry = agent_registry
        self.active_debates: Dict[UUID, DebateState] = {}

        logger.info("DebateProtocol initialized")

    async def initiate_debate(
        self,
        topic: str,
        agents: List[str],
        max_rounds: int = 5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DebateState:
        """Start a debate between agents.

        Args:
            topic: The topic to debate
            agents: List of agent IDs to participate
            max_rounds: Maximum number of debate rounds
            metadata: Optional additional metadata

        Returns:
            The created debate state
        """
        if len(agents) < 2:
            raise ValueError("At least 2 agents required for a debate")

        debate = DebateState(
            topic=topic,
            agents=agents,
            max_rounds=max_rounds,
        )

        self.active_debates[debate.session_id] = debate

        logger.info(
            f"Initiated debate {debate.session_id}: "
            f"topic='{topic}', agents={agents}, max_rounds={max_rounds}"
        )

        # Notify agents to start debate
        for i, agent_id in enumerate(agents):
            position = "for" if i % 2 == 0 else "against"
            message = AgentMessage(
                from_agent="debate_protocol",
                to_agent=agent_id,
                type=MessageType.DEBATE,
                content={
                    "event": "debate_initiated",
                    "session_id": str(debate.session_id),
                    "topic": topic,
                    "your_position": position,
                    "max_rounds": max_rounds,
                    "participants": agents,
                },
                priority=MessagePriority.HIGH,
            )
            await self.message_bus.publish(message)

        return debate

    async def process_argument(
        self,
        session_id: UUID,
        agent_id: str,
        argument: str,
        position: str = "neutral",
        evidence: Optional[List[str]] = None,
    ) -> Argument:
        """Process an argument from an agent.

        Args:
            session_id: The debate session ID
            agent_id: ID of the agent making the argument
            argument: The argument content
            position: The agent's position (for, against, neutral)
            evidence: Optional supporting evidence

        Returns:
            The created argument

        Raises:
            ValueError: If debate not found or agent not participating
        """
        debate = self.active_debates.get(session_id)
        if not debate:
            raise ValueError(f"Debate {session_id} not found")

        if agent_id not in debate.agents:
            raise ValueError(f"Agent {agent_id} is not participating in this debate")

        # Create argument
        arg = Argument(
            agent_id=agent_id,
            position=position,
            content=argument,
            supporting_evidence=evidence or [],
            round_number=debate.current_round,
        )

        debate.arguments.append(arg)

        logger.debug(
            f"Processed argument in debate {session_id} from {agent_id}: "
            f"position={position}"
        )

        # Check if round is complete (all agents have argued)
        round_args = [a for a in debate.arguments if a.round_number == debate.current_round]
        if len(round_args) >= len(debate.agents):
            debate.current_round += 1

            if debate.current_round >= debate.max_rounds:
                # Max rounds reached, try to reach consensus
                await self._try_consensus(session_id)

        # Notify other agents
        for other_agent in debate.agents:
            if other_agent != agent_id:
                message = AgentMessage(
                    from_agent=agent_id,
                    to_agent=other_agent,
                    type=MessageType.DEBATE,
                    content={
                        "event": "argument_made",
                        "session_id": str(session_id),
                        "argument": argument,
                        "position": position,
                        "evidence": evidence or [],
                        "round": debate.current_round,
                    },
                    priority=MessagePriority.NORMAL,
                )
                await self.message_bus.publish(message)

        return arg

    async def _try_consensus(self, session_id: UUID) -> None:
        """Attempt to reach consensus in a debate.

        Args:
            session_id: The debate session ID
        """
        debate = self.active_debates.get(session_id)
        if not debate:
            return

        # Analyze arguments to find consensus
        # This is a simplified implementation - in practice, you'd use
        # more sophisticated NLP or have agents vote
        for_count = sum(1 for a in debate.arguments if a.position == "for")
        against_count = sum(1 for a in debate.arguments if a.position == "against")

        if for_count > against_count * 1.5:
            debate.consensus_reached = True
            debate.consensus_position = "for"
        elif against_count > for_count * 1.5:
            debate.consensus_reached = True
            debate.consensus_position = "against"

        logger.info(
            f"Debate {session_id} consensus: "
            f"reached={debate.consensus_reached}, position={debate.consensus_position}"
        )

    async def reach_consensus(self, session_id: UUID) -> Dict[str, Any]:
        """Finalize and get the consensus from a debate.

        Args:
            session_id: The debate session ID

        Returns:
            Dictionary with consensus information

        Raises:
            ValueError: If debate not found
        """
        debate = self.active_debates.get(session_id)
        if not debate:
            raise ValueError(f"Debate {session_id} not found")

        await self._try_consensus(session_id)

        result = {
            "session_id": str(session_id),
            "topic": debate.topic,
            "consensus_reached": debate.consensus_reached,
            "consensus_position": debate.consensus_position,
            "total_arguments": len(debate.arguments),
            "rounds_completed": debate.current_round,
            "summary": self._generate_debate_summary(debate),
        }

        # Clean up
        del self.active_debates[session_id]

        return result

    def _generate_debate_summary(self, debate: DebateState) -> str:
        """Generate a summary of the debate.

        Args:
            debate: The debate state

        Returns:
            A summary string
        """
        for_args = [a for a in debate.arguments if a.position == "for"]
        against_args = [a for a in debate.arguments if a.position == "against"]

        summary = f"Debate on '{debate.topic}':\n"
        summary += f"- {len(for_args)} arguments FOR\n"
        summary += f"- {len(against_args)} arguments AGAINST\n"

        if debate.consensus_reached:
            summary += f"- Consensus: {debate.consensus_position.upper()}"
        else:
            summary += "- No clear consensus reached"

        return summary


@dataclass
class DelegatedTask:
    """Represents a task delegated between agents."""

    id: UUID = field(default_factory=uuid4)
    from_agent: str = ""
    to_agent: str = ""
    task_type: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    callback_on_complete: bool = True
    status: str = "pending"  # pending, in_progress, completed, failed
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class DelegationProtocol:
    """Protocol for task delegation between agents.

    This protocol handles delegating tasks from one agent to another,
    tracking progress, and reporting completion.
    """

    def __init__(self, message_bus: MessageBus, agent_registry: Any):
        """Initialize the delegation protocol.

        Args:
            message_bus: The message bus for communication
            agent_registry: The agent registry for looking up agents
        """
        self.message_bus = message_bus
        self.agent_registry = agent_registry
        self.active_tasks: Dict[UUID, DelegatedTask] = {}
        self._completion_callbacks: Dict[UUID, Callable] = {}

        logger.info("DelegationProtocol initialized")

    async def delegate_task(
        self,
        from_agent: str,
        to_agent: str,
        task: Dict[str, Any],
        callback_on_complete: bool = True,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> DelegatedTask:
        """Delegate a task from one agent to another.

        Args:
            from_agent: ID of the delegating agent
            to_agent: ID of the agent to delegate to
            task: Task details including type and payload
            callback_on_complete: Whether to notify on completion
            priority: Priority of the task

        Returns:
            The created delegated task
        """
        delegated = DelegatedTask(
            from_agent=from_agent,
            to_agent=to_agent,
            task_type=task.get("type", "general"),
            payload=task.get("payload", {}),
            callback_on_complete=callback_on_complete,
        )

        self.active_tasks[delegated.id] = delegated

        logger.info(
            f"Delegating task {delegated.id}: "
            f"{from_agent} -> {to_agent}, type={delegated.task_type}"
        )

        # Send delegation message
        message = AgentMessage(
            from_agent=from_agent,
            to_agent=to_agent,
            type=MessageType.DELEGATE,
            content={
                "task_id": str(delegated.id),
                "task_type": delegated.task_type,
                "payload": delegated.payload,
                "callback_requested": callback_on_complete,
            },
            priority=priority,
            requires_response=callback_on_complete,
        )

        await self.message_bus.publish(message)

        return delegated

    async def accept_task(self, task_id: UUID, agent_id: str) -> DelegatedTask:
        """Mark a task as accepted and in progress.

        Args:
            task_id: The task ID
            agent_id: ID of the agent accepting

        Returns:
            The updated task

        Raises:
            ValueError: If task not found or wrong agent
        """
        task = self.active_tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        if task.to_agent != agent_id:
            raise ValueError(f"Task {task_id} is not assigned to {agent_id}")

        task.status = "in_progress"

        logger.debug(f"Task {task_id} accepted by {agent_id}")

        # Notify delegating agent
        if task.callback_on_complete:
            message = AgentMessage(
                from_agent=agent_id,
                to_agent=task.from_agent,
                type=MessageType.INFORM,
                content={
                    "event": "task_accepted",
                    "task_id": str(task_id),
                },
                priority=MessagePriority.LOW,
            )
            await self.message_bus.publish(message)

        return task

    async def report_completion(
        self,
        task_id: UUID,
        result: Dict[str, Any],
        success: bool = True,
        error: Optional[str] = None,
    ) -> DelegatedTask:
        """Report task completion back to delegating agent.

        Args:
            task_id: The task ID
            result: The result of the task
            success: Whether the task succeeded
            error: Optional error message if failed

        Returns:
            The updated task

        Raises:
            ValueError: If task not found
        """
        task = self.active_tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        task.status = "completed" if success else "failed"
        task.completed_at = datetime.now(timezone.utc)
        task.result = result
        task.error = error

        logger.info(
            f"Task {task_id} completed: "
            f"success={success}, error={error}"
        )

        # Notify delegating agent
        if task.callback_on_complete:
            message = AgentMessage(
                from_agent=task.to_agent,
                to_agent=task.from_agent,
                type=MessageType.RESPONSE,
                content={
                    "event": "task_completed",
                    "task_id": str(task_id),
                    "success": success,
                    "result": result,
                    "error": error,
                },
                priority=MessagePriority.HIGH,
            )
            await self.message_bus.publish(message)

        # Move to history
        del self.active_tasks[task_id]

        return task

    def get_pending_tasks(self, agent_id: str) -> List[DelegatedTask]:
        """Get pending tasks for an agent.

        Args:
            agent_id: The agent ID

        Returns:
            List of pending tasks for the agent
        """
        return [
            task for task in self.active_tasks.values()
            if task.to_agent == agent_id and task.status in ["pending", "in_progress"]
        ]

    def get_delegated_tasks(self, agent_id: str) -> List[DelegatedTask]:
        """Get tasks delegated by an agent.

        Args:
            agent_id: The agent ID

        Returns:
            List of tasks delegated by the agent
        """
        return [
            task for task in self.active_tasks.values()
            if task.from_agent == agent_id
        ]


@dataclass
class ParallelTask:
    """Represents a task split for parallel execution."""

    id: UUID = field(default_factory=uuid4)
    parent_task_id: UUID = field(default_factory=uuid4)
    agent_id: str = ""
    subtask: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    result: Optional[Any] = None
    error: Optional[str] = None


class ParallelExecutionProtocol:
    """Protocol for parallel task execution across agents.

    This protocol handles splitting tasks among multiple agents,
    executing in parallel, and merging results.
    """

    def __init__(self, message_bus: MessageBus, agent_registry: Any):
        """Initialize the parallel execution protocol.

        Args:
            message_bus: The message bus for communication
            agent_registry: The agent registry for looking up agents
        """
        self.message_bus = message_bus
        self.agent_registry = agent_registry
        self.active_parallel_tasks: Dict[UUID, List[ParallelTask]] = {}

        logger.info("ParallelExecutionProtocol initialized")

    async def split_task(
        self,
        task: Dict[str, Any],
        agents: List[str],
        split_strategy: str = "equal",
    ) -> Dict[str, Dict[str, Any]]:
        """Split a task among multiple agents.

        Args:
            task: The task to split
            agents: List of agent IDs to distribute to
            split_strategy: How to split the task (equal, capability_based)

        Returns:
            Dictionary mapping agent IDs to their subtasks
        """
        parent_id = uuid4()
        subtasks: Dict[str, Dict[str, Any]] = {}
        parallel_tasks: List[ParallelTask] = []

        task_type = task.get("type", "general")
        payload = task.get("payload", {})
        items = payload.get("items", [])

        if split_strategy == "equal" and items:
            # Equally distribute items among agents
            chunk_size = max(1, len(items) // len(agents))
            for i, agent_id in enumerate(agents):
                start = i * chunk_size
                end = start + chunk_size if i < len(agents) - 1 else len(items)

                subtask = {
                    "type": task_type,
                    "payload": {
                        **payload,
                        "items": items[start:end],
                    },
                    "parent_task_id": str(parent_id),
                    "subtask_index": i,
                }
                subtasks[agent_id] = subtask

                parallel_tasks.append(ParallelTask(
                    parent_task_id=parent_id,
                    agent_id=agent_id,
                    subtask=subtask,
                ))
        else:
            # Each agent gets the full task (for different perspectives)
            for i, agent_id in enumerate(agents):
                subtask = {
                    "type": task_type,
                    "payload": payload,
                    "parent_task_id": str(parent_id),
                    "subtask_index": i,
                }
                subtasks[agent_id] = subtask

                parallel_tasks.append(ParallelTask(
                    parent_task_id=parent_id,
                    agent_id=agent_id,
                    subtask=subtask,
                ))

        self.active_parallel_tasks[parent_id] = parallel_tasks

        logger.info(
            f"Split task {parent_id} into {len(subtasks)} subtasks "
            f"for agents {agents}"
        )

        return subtasks

    async def execute_parallel(
        self,
        task: Dict[str, Any],
        agents: List[str],
        timeout: float = 60.0,
    ) -> Dict[str, Any]:
        """Execute a task in parallel across multiple agents.

        Args:
            task: The task to execute
            agents: List of agent IDs to use
            timeout: Maximum time to wait for results

        Returns:
            Merged results from all agents
        """
        subtasks = await self.split_task(task, agents)

        # Send tasks to all agents
        tasks = []
        for agent_id, subtask in subtasks.items():
            message = AgentMessage(
                from_agent="parallel_protocol",
                to_agent=agent_id,
                type=MessageType.DELEGATE,
                content={
                    "event": "parallel_task",
                    "subtask": subtask,
                },
                priority=MessagePriority.HIGH,
                requires_response=True,
            )
            tasks.append(self.message_bus.send_and_wait(message, timeout=timeout))

        # Wait for all responses
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect results
        results: Dict[str, Any] = {}
        for agent_id, response in zip(agents, responses):
            if isinstance(response, Exception):
                results[agent_id] = {"error": str(response)}
            elif response:
                results[agent_id] = response.content
            else:
                results[agent_id] = {"error": "timeout"}

        # Merge results
        return await self.merge_results(results)

    async def report_subtask_result(
        self,
        parent_task_id: UUID,
        agent_id: str,
        result: Any,
        success: bool = True,
        error: Optional[str] = None,
    ) -> bool:
        """Report result of a subtask.

        Args:
            parent_task_id: The parent task ID
            agent_id: The agent reporting
            result: The result
            success: Whether successful
            error: Optional error message

        Returns:
            True if all subtasks are complete
        """
        parallel_tasks = self.active_parallel_tasks.get(parent_task_id)
        if not parallel_tasks:
            raise ValueError(f"Parent task {parent_task_id} not found")

        # Find and update the subtask
        for task in parallel_tasks:
            if task.agent_id == agent_id:
                task.status = "completed" if success else "failed"
                task.result = result
                task.error = error
                break

        # Check if all complete
        all_complete = all(t.status in ["completed", "failed"] for t in parallel_tasks)

        logger.debug(
            f"Subtask result for {parent_task_id} from {agent_id}: "
            f"success={success}, all_complete={all_complete}"
        )

        return all_complete

    async def merge_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Merge results from multiple agents.

        Args:
            results: Dictionary of agent results

        Returns:
            Merged result dictionary
        """
        merged = {
            "agents": list(results.keys()),
            "individual_results": results,
            "success_count": sum(1 for r in results.values() if "error" not in r),
            "error_count": sum(1 for r in results.values() if "error" in r),
        }

        # Combine non-error results
        combined_data = []
        for agent_id, result in results.items():
            if "error" not in result:
                if "data" in result:
                    combined_data.extend(result["data"] if isinstance(result["data"], list) else [result["data"]])
                elif "result" in result:
                    combined_data.append(result["result"])

        merged["combined_data"] = combined_data

        logger.info(
            f"Merged results from {len(results)} agents: "
            f"{merged['success_count']} success, {merged['error_count']} errors"
        )

        return merged
