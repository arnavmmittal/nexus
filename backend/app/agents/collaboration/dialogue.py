"""Inter-agent dialogue system for structured conversations.

This module provides a structured dialogue system for agents to
communicate, propose ideas, reach agreements, and collaborate.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class DialogueIntent(Enum):
    """Intents for dialogue turns."""

    PROPOSE = "propose"      # Making a proposal or suggestion
    AGREE = "agree"          # Agreeing with a proposal
    DISAGREE = "disagree"    # Disagreeing with a proposal
    CLARIFY = "clarify"      # Asking for or providing clarification
    CONCLUDE = "conclude"    # Concluding or summarizing
    QUESTION = "question"    # Asking a question
    INFORM = "inform"        # Sharing information
    DELEGATE = "delegate"    # Requesting delegation


@dataclass
class DialogueTurn:
    """Represents a single turn in a dialogue between agents."""

    id: str = field(default_factory=lambda: str(uuid4()))
    agent_id: str = ""
    content: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    intent: DialogueIntent = DialogueIntent.INFORM
    references: List[str] = field(default_factory=list)  # IDs of turns being responded to
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert turn to dictionary representation."""
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "intent": self.intent.value,
            "references": self.references,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DialogueTurn":
        """Create turn from dictionary representation."""
        return cls(
            id=data["id"],
            agent_id=data["agent_id"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            intent=DialogueIntent(data["intent"]),
            references=data.get("references", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class AgreementState:
    """Tracks the state of agreement between agents."""

    proposal_id: str = ""
    proposer: str = ""
    proposal_content: str = ""
    supporters: List[str] = field(default_factory=list)
    opposers: List[str] = field(default_factory=list)
    pending: List[str] = field(default_factory=list)
    is_resolved: bool = False
    resolution: Optional[str] = None  # "agreed", "rejected", "modified"
    final_content: Optional[str] = None


class AgentDialogue:
    """Manages structured dialogue between agents.

    This class facilitates multi-turn conversations between Jarvis
    and Ultron, tracking proposals, agreements, and disagreements.
    """

    def __init__(
        self,
        participants: Optional[List[str]] = None,
        topic: str = "",
    ):
        """Initialize a dialogue.

        Args:
            participants: List of participating agent IDs
            topic: The topic of discussion
        """
        self.id: UUID = uuid4()
        self.participants: List[str] = participants or ["jarvis", "ultron"]
        self.topic: str = topic
        self.turns: List[DialogueTurn] = []
        self.agreements: Dict[str, AgreementState] = {}
        self.created_at: datetime = datetime.now(timezone.utc)
        self.status: str = "active"  # active, concluded, abandoned

        logger.info(
            f"AgentDialogue {self.id} created: "
            f"participants={self.participants}, topic='{topic}'"
        )

    async def add_turn(
        self,
        agent_id: str,
        content: str,
        intent: DialogueIntent = DialogueIntent.INFORM,
        references: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DialogueTurn:
        """Add a turn to the dialogue.

        Args:
            agent_id: ID of the speaking agent
            content: The content of the turn
            intent: The intent of the turn
            references: IDs of turns being responded to
            metadata: Optional additional metadata

        Returns:
            The created dialogue turn
        """
        if agent_id not in self.participants:
            raise ValueError(f"Agent {agent_id} is not a participant")

        turn = DialogueTurn(
            agent_id=agent_id,
            content=content,
            intent=intent,
            references=references or [],
            metadata=metadata or {},
        )

        self.turns.append(turn)

        logger.debug(
            f"Dialogue {self.id}: {agent_id} added turn with intent {intent.value}"
        )

        # Track proposals and responses
        if intent == DialogueIntent.PROPOSE:
            self._track_proposal(turn)
        elif intent in [DialogueIntent.AGREE, DialogueIntent.DISAGREE]:
            self._track_response(turn)

        return turn

    def _track_proposal(self, turn: DialogueTurn) -> None:
        """Track a new proposal.

        Args:
            turn: The proposal turn
        """
        state = AgreementState(
            proposal_id=turn.id,
            proposer=turn.agent_id,
            proposal_content=turn.content,
            pending=[p for p in self.participants if p != turn.agent_id],
        )
        self.agreements[turn.id] = state

        logger.debug(f"Tracking proposal {turn.id} from {turn.agent_id}")

    def _track_response(self, turn: DialogueTurn) -> None:
        """Track a response to a proposal.

        Args:
            turn: The response turn
        """
        for ref_id in turn.references:
            if ref_id in self.agreements:
                state = self.agreements[ref_id]

                if turn.agent_id in state.pending:
                    state.pending.remove(turn.agent_id)

                if turn.intent == DialogueIntent.AGREE:
                    state.supporters.append(turn.agent_id)
                else:
                    state.opposers.append(turn.agent_id)

                # Check if all have responded
                if not state.pending:
                    state.is_resolved = True
                    if not state.opposers:
                        state.resolution = "agreed"
                        state.final_content = state.proposal_content
                    elif not state.supporters:
                        state.resolution = "rejected"
                    else:
                        state.resolution = "modified"

                logger.debug(
                    f"Proposal {ref_id} response from {turn.agent_id}: "
                    f"intent={turn.intent.value}, resolved={state.is_resolved}"
                )

    async def jarvis_propose(
        self,
        proposal: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DialogueTurn:
        """Jarvis makes a proposal.

        Args:
            proposal: The proposal content
            metadata: Optional metadata

        Returns:
            The proposal turn
        """
        return await self.add_turn(
            agent_id="jarvis",
            content=proposal,
            intent=DialogueIntent.PROPOSE,
            metadata=metadata,
        )

    async def ultron_propose(
        self,
        proposal: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DialogueTurn:
        """Ultron makes a proposal.

        Args:
            proposal: The proposal content
            metadata: Optional metadata

        Returns:
            The proposal turn
        """
        return await self.add_turn(
            agent_id="ultron",
            content=proposal,
            intent=DialogueIntent.PROPOSE,
            metadata=metadata,
        )

    async def jarvis_respond(
        self,
        to_turn: DialogueTurn,
        response: str,
        agrees: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DialogueTurn:
        """Jarvis responds to a turn.

        Args:
            to_turn: The turn being responded to
            response: The response content
            agrees: Whether Jarvis agrees
            metadata: Optional metadata

        Returns:
            The response turn
        """
        intent = DialogueIntent.AGREE if agrees else DialogueIntent.DISAGREE

        return await self.add_turn(
            agent_id="jarvis",
            content=response,
            intent=intent,
            references=[to_turn.id],
            metadata=metadata,
        )

    async def ultron_respond(
        self,
        to_turn: DialogueTurn,
        response: str,
        agrees: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DialogueTurn:
        """Ultron responds to a turn.

        Args:
            to_turn: The turn being responded to
            response: The response content
            agrees: Whether Ultron agrees
            metadata: Optional metadata

        Returns:
            The response turn
        """
        intent = DialogueIntent.AGREE if agrees else DialogueIntent.DISAGREE

        return await self.add_turn(
            agent_id="ultron",
            content=response,
            intent=intent,
            references=[to_turn.id],
            metadata=metadata,
        )

    async def reach_agreement(self) -> Optional[Dict[str, Any]]:
        """Check if agents have reached agreement.

        Returns:
            Agreement details if reached, None otherwise
        """
        resolved_agreements = [
            state for state in self.agreements.values()
            if state.is_resolved and state.resolution == "agreed"
        ]

        if not resolved_agreements:
            return None

        # Return the most recent agreement
        latest = resolved_agreements[-1]

        logger.info(f"Dialogue {self.id}: Agreement reached on proposal {latest.proposal_id}")

        return {
            "proposal_id": latest.proposal_id,
            "proposer": latest.proposer,
            "content": latest.final_content,
            "supporters": latest.supporters,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def conclude(
        self,
        conclusion: str,
        concluding_agent: str = "jarvis",
    ) -> DialogueTurn:
        """Conclude the dialogue.

        Args:
            conclusion: The concluding statement
            concluding_agent: The agent providing the conclusion

        Returns:
            The conclusion turn
        """
        turn = await self.add_turn(
            agent_id=concluding_agent,
            content=conclusion,
            intent=DialogueIntent.CONCLUDE,
        )

        self.status = "concluded"

        logger.info(f"Dialogue {self.id} concluded by {concluding_agent}")

        return turn

    def get_dialogue_history(self) -> List[DialogueTurn]:
        """Get the full dialogue history.

        Returns:
            List of all dialogue turns
        """
        return self.turns.copy()

    def get_recent_turns(self, count: int = 5) -> List[DialogueTurn]:
        """Get recent dialogue turns.

        Args:
            count: Number of recent turns to return

        Returns:
            List of recent turns
        """
        return self.turns[-count:]

    def get_proposals(self) -> List[DialogueTurn]:
        """Get all proposals made in the dialogue.

        Returns:
            List of proposal turns
        """
        return [t for t in self.turns if t.intent == DialogueIntent.PROPOSE]

    def get_agreement_status(self) -> Dict[str, Any]:
        """Get the current status of all agreements.

        Returns:
            Dictionary with agreement statuses
        """
        return {
            "total_proposals": len(self.agreements),
            "agreed": sum(
                1 for s in self.agreements.values()
                if s.resolution == "agreed"
            ),
            "rejected": sum(
                1 for s in self.agreements.values()
                if s.resolution == "rejected"
            ),
            "pending": sum(
                1 for s in self.agreements.values()
                if not s.is_resolved
            ),
            "details": {
                pid: {
                    "proposer": state.proposer,
                    "resolved": state.is_resolved,
                    "resolution": state.resolution,
                    "supporters": state.supporters,
                    "opposers": state.opposers,
                }
                for pid, state in self.agreements.items()
            },
        }

    def get_turn_by_agent(self, agent_id: str) -> List[DialogueTurn]:
        """Get all turns by a specific agent.

        Args:
            agent_id: The agent ID

        Returns:
            List of turns by that agent
        """
        return [t for t in self.turns if t.agent_id == agent_id]

    def to_dict(self) -> Dict[str, Any]:
        """Convert dialogue to dictionary representation.

        Returns:
            Dictionary representation
        """
        return {
            "id": str(self.id),
            "participants": self.participants,
            "topic": self.topic,
            "turns": [t.to_dict() for t in self.turns],
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "agreement_status": self.get_agreement_status(),
        }

    def format_transcript(self) -> str:
        """Format the dialogue as a human-readable transcript.

        Returns:
            Formatted transcript string
        """
        lines = [
            f"Dialogue: {self.topic}",
            f"Participants: {', '.join(self.participants)}",
            f"Status: {self.status}",
            "-" * 50,
        ]

        for turn in self.turns:
            agent = turn.agent_id.upper()
            intent = f"[{turn.intent.value}]"
            time = turn.timestamp.strftime("%H:%M:%S")
            lines.append(f"{time} {agent} {intent}: {turn.content}")

        lines.append("-" * 50)

        agreement = self.get_agreement_status()
        lines.append(
            f"Agreements: {agreement['agreed']} agreed, "
            f"{agreement['rejected']} rejected, "
            f"{agreement['pending']} pending"
        )

        return "\n".join(lines)
