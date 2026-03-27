"""Hybrid model routing for cost-efficient AI operations.

This module provides intelligent model selection based on query complexity,
routing simple queries to cheaper models and complex reasoning to more
capable (and expensive) models.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class QueryComplexity(str, Enum):
    """Query complexity levels."""
    SIMPLE = "simple"      # Factual lookups, basic queries
    MODERATE = "moderate"  # Multi-step tasks, some reasoning
    COMPLEX = "complex"    # Deep reasoning, creative tasks, long context


class ModelTier(str, Enum):
    """Model tiers by capability/cost."""
    FAST = "fast"          # Haiku - cheapest, fastest
    BALANCED = "balanced"  # Sonnet - good balance
    POWERFUL = "powerful"  # Opus - most capable, expensive


@dataclass
class ModelConfig:
    """Configuration for a specific model."""
    name: str
    model_id: str
    tier: ModelTier
    cost_per_1k_input: float
    cost_per_1k_output: float
    max_context: int
    best_for: List[str]


# Available models with their configurations
AVAILABLE_MODELS: Dict[ModelTier, ModelConfig] = {
    ModelTier.FAST: ModelConfig(
        name="Claude 3 Haiku",
        model_id="claude-haiku-4-5-20251001",
        tier=ModelTier.FAST,
        cost_per_1k_input=0.00025,
        cost_per_1k_output=0.00125,
        max_context=200000,
        best_for=[
            "simple_questions",
            "data_extraction",
            "classification",
            "tool_routing",
            "status_checks",
        ],
    ),
    ModelTier.BALANCED: ModelConfig(
        name="Claude 3.5 Sonnet",
        model_id="claude-sonnet-4-20250514",
        tier=ModelTier.BALANCED,
        cost_per_1k_input=0.003,
        cost_per_1k_output=0.015,
        max_context=200000,
        best_for=[
            "code_generation",
            "analysis",
            "multi_step_reasoning",
            "document_processing",
        ],
    ),
    ModelTier.POWERFUL: ModelConfig(
        name="Claude 3 Opus",
        model_id="claude-opus-4-5-20251101",
        tier=ModelTier.POWERFUL,
        cost_per_1k_input=0.015,
        cost_per_1k_output=0.075,
        max_context=200000,
        best_for=[
            "complex_reasoning",
            "creative_writing",
            "research",
            "nuanced_analysis",
        ],
    ),
}


# Complexity indicators in queries
SIMPLE_INDICATORS = [
    r"\bwhat is\b",
    r"\bwho is\b",
    r"\bwhen did\b",
    r"\bwhere is\b",
    r"\bhow many\b",
    r"\blist\b",
    r"\bshow me\b",
    r"\bget\b",
    r"\bcheck\b",
    r"\bstatus\b",
    r"\bweather\b",
    r"\btime\b",
    r"\bdate\b",
    r"\bprice\b",
]

COMPLEX_INDICATORS = [
    r"\bexplain\b.*\bwhy\b",
    r"\banalyze\b",
    r"\bcompare\b.*\band\b",
    r"\bcreate\b.*\bplan\b",
    r"\bdesign\b",
    r"\barchitect\b",
    r"\boptimize\b",
    r"\brefactor\b",
    r"\bdebug\b.*\bcomplex\b",
    r"\bresearch\b",
    r"\bwrite\b.*\b(essay|article|report)\b",
    r"\bstrategy\b",
    r"\btrade-?offs?\b",
]

MODERATE_INDICATORS = [
    r"\bhow to\b",
    r"\bhelp me\b",
    r"\bcan you\b",
    r"\bwrite\b.*\bcode\b",
    r"\bfix\b",
    r"\bupdate\b",
    r"\bmodify\b",
    r"\bsummarize\b",
]


def _count_pattern_matches(text: str, patterns: List[str]) -> int:
    """Count how many patterns match in the text."""
    text_lower = text.lower()
    return sum(1 for p in patterns if re.search(p, text_lower))


def analyze_query_complexity(
    query: str,
    conversation_length: int = 0,
    tool_count: int = 0,
) -> Tuple[QueryComplexity, float]:
    """Analyze the complexity of a query.

    Args:
        query: The user's query
        conversation_length: Number of messages in conversation
        tool_count: Number of tools likely to be used

    Returns:
        Tuple of (complexity level, confidence score 0-1)
    """
    # Count pattern matches
    simple_matches = _count_pattern_matches(query, SIMPLE_INDICATORS)
    moderate_matches = _count_pattern_matches(query, MODERATE_INDICATORS)
    complex_matches = _count_pattern_matches(query, COMPLEX_INDICATORS)

    # Base scoring
    simple_score = simple_matches * 2
    moderate_score = moderate_matches * 1.5
    complex_score = complex_matches * 3

    # Adjust for query length (longer queries tend to be more complex)
    query_len = len(query)
    if query_len > 500:
        complex_score += 2
    elif query_len > 200:
        moderate_score += 1

    # Adjust for conversation length
    if conversation_length > 20:
        complex_score += 1
    elif conversation_length > 10:
        moderate_score += 0.5

    # Adjust for tool usage
    if tool_count > 3:
        moderate_score += 1
    if tool_count > 5:
        complex_score += 1

    # Determine complexity
    scores = {
        QueryComplexity.SIMPLE: simple_score,
        QueryComplexity.MODERATE: moderate_score,
        QueryComplexity.COMPLEX: complex_score,
    }

    max_score = max(scores.values())
    total_score = sum(scores.values())

    if max_score == 0:
        # Default to simple if no indicators found
        return QueryComplexity.SIMPLE, 0.5

    # Find winner and calculate confidence
    complexity = max(scores, key=scores.get)
    confidence = max_score / (total_score + 1)  # +1 to avoid division issues

    return complexity, min(confidence, 1.0)


class ModelRouter:
    """Routes queries to the most appropriate model based on complexity.

    Strategy:
    - SIMPLE queries -> Haiku (cheapest)
    - MODERATE queries -> Haiku with option to escalate
    - COMPLEX queries -> Sonnet (balanced cost/capability)
    - User can override with explicit model preference
    """

    def __init__(
        self,
        default_tier: ModelTier = ModelTier.FAST,
        allow_escalation: bool = True,
        cost_conscious: bool = True,
    ):
        """Initialize model router.

        Args:
            default_tier: Default model tier to use
            allow_escalation: Allow automatic escalation to better models
            cost_conscious: Prioritize cheaper models when possible
        """
        self.default_tier = default_tier
        self.allow_escalation = allow_escalation
        self.cost_conscious = cost_conscious
        self._usage_stats: Dict[str, int] = {tier.value: 0 for tier in ModelTier}

    def select_model(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        required_tools: Optional[List[str]] = None,
        user_preference: Optional[ModelTier] = None,
    ) -> Tuple[ModelConfig, str]:
        """Select the best model for a query.

        Args:
            query: The user's query
            conversation_history: Previous conversation messages
            required_tools: Tools that will likely be used
            user_preference: User's explicit model preference

        Returns:
            Tuple of (ModelConfig, reason for selection)
        """
        # User preference overrides
        if user_preference is not None:
            model = AVAILABLE_MODELS[user_preference]
            self._usage_stats[user_preference.value] += 1
            return model, f"User requested {model.name}"

        # Analyze complexity
        conv_len = len(conversation_history) if conversation_history else 0
        tool_count = len(required_tools) if required_tools else 0

        complexity, confidence = analyze_query_complexity(
            query, conv_len, tool_count
        )

        # Map complexity to tier
        if complexity == QueryComplexity.SIMPLE:
            tier = ModelTier.FAST
            reason = "Simple query - using fast/cheap model"

        elif complexity == QueryComplexity.MODERATE:
            if self.cost_conscious:
                tier = ModelTier.FAST
                reason = "Moderate query - using fast model (cost-conscious mode)"
            else:
                tier = ModelTier.BALANCED
                reason = "Moderate query - using balanced model"

        else:  # COMPLEX
            if self.allow_escalation:
                tier = ModelTier.BALANCED
                reason = "Complex query - escalating to capable model"
            else:
                tier = ModelTier.FAST
                reason = "Complex query - staying with fast model (escalation disabled)"

        model = AVAILABLE_MODELS[tier]
        self._usage_stats[tier.value] += 1

        logger.debug(
            f"Query routed to {model.name}: complexity={complexity.value}, "
            f"confidence={confidence:.2f}, reason={reason}"
        )

        return model, reason

    def get_model_for_task(self, task_type: str) -> ModelConfig:
        """Get the recommended model for a specific task type.

        Args:
            task_type: Type of task (e.g., "code_generation", "classification")

        Returns:
            Recommended ModelConfig
        """
        # Check which models are best for this task
        for tier, model in AVAILABLE_MODELS.items():
            if task_type in model.best_for:
                if self.cost_conscious and tier == ModelTier.POWERFUL:
                    # Downgrade to balanced if cost-conscious
                    return AVAILABLE_MODELS[ModelTier.BALANCED]
                return model

        # Default to fast tier
        return AVAILABLE_MODELS[self.default_tier]

    def estimate_cost(
        self,
        model: ModelConfig,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimate the cost of a request.

        Args:
            model: Model configuration
            input_tokens: Estimated input tokens
            output_tokens: Estimated output tokens

        Returns:
            Estimated cost in dollars
        """
        input_cost = (input_tokens / 1000) * model.cost_per_1k_input
        output_cost = (output_tokens / 1000) * model.cost_per_1k_output
        return input_cost + output_cost

    @property
    def usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        total = sum(self._usage_stats.values())
        return {
            "total_requests": total,
            "by_tier": self._usage_stats.copy(),
            "tier_percentages": {
                tier: (count / total * 100) if total > 0 else 0
                for tier, count in self._usage_stats.items()
            },
        }


# Global router instance
_router: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    """Get the global model router."""
    global _router
    if _router is None:
        _router = ModelRouter(
            default_tier=ModelTier.FAST,
            allow_escalation=True,
            cost_conscious=True,  # Prioritize cost efficiency
        )
    return _router


def select_model_for_query(
    query: str,
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    required_tools: Optional[List[str]] = None,
) -> str:
    """Select the best model ID for a query.

    Convenience function that returns just the model ID string.

    Args:
        query: User's query
        conversation_history: Previous messages
        required_tools: Tools to be used

    Returns:
        Model ID string (e.g., "claude-haiku-4-5-20251001")
    """
    router = get_model_router()
    model, _ = router.select_model(query, conversation_history, required_tools)
    return model.model_id
