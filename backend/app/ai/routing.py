"""Multi-model intelligent routing system for Nexus AI.

This module provides intelligent routing of queries to the most appropriate AI model
based on task complexity, query characteristics, and user preferences.

Architecture:
- ModelTier: Enum defining model capability tiers (FAST, BALANCED, POWERFUL)
- QueryClassifier: Analyzes queries to determine recommended tier
- ModelRouter: Routes queries and manages model selection

Cost Optimization:
- Routes simple queries to cheaper, faster models (Haiku)
- Routes complex reasoning to more capable models (Opus)
- Tracks usage and costs per tier
- Supports user/agent overrides

Integration:
- Works with both Jarvis and Ultron agents
- Ultron can override to POWERFUL tier for autonomous decisions
- User preferences respected ("always use the best model")
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================


class ModelTier(str, Enum):
    """Model capability tiers.

    FAST: Claude Haiku - Simple queries, quick responses, low cost
        - Best for: greetings, simple questions, status checks, time/weather
        - Cost: $0.25/M input, $1.25/M output

    BALANCED: Claude Sonnet - Most tasks, good balance of cost/capability
        - Best for: conversations, tool usage, moderate complexity
        - Cost: $3/M input, $15/M output

    POWERFUL: Claude Opus - Complex reasoning, creative tasks, critical decisions
        - Best for: coding, complex analysis, creative writing, multi-agent coordination
        - Cost: $15/M input, $75/M output
    """
    FAST = "fast"
    BALANCED = "balanced"
    POWERFUL = "powerful"


class QueryCategory(str, Enum):
    """Categories of queries for classification."""
    GREETING = "greeting"
    SIMPLE_QUESTION = "simple_question"
    STATUS_CHECK = "status_check"
    TIME_WEATHER = "time_weather"
    CONVERSATION = "conversation"
    TOOL_USAGE = "tool_usage"
    CODING = "coding"
    ANALYSIS = "analysis"
    CREATIVE = "creative"
    MULTI_STEP = "multi_step"
    CRITICAL_DECISION = "critical_decision"
    UNKNOWN = "unknown"


class OverrideReason(str, Enum):
    """Reasons for tier override."""
    USER_PREFERENCE = "user_preference"
    AGENT_OVERRIDE = "agent_override"
    CRITICAL_TASK = "critical_task"
    TESTING = "testing"
    FALLBACK = "fallback"
    COST_LIMIT = "cost_limit"


@dataclass
class ModelConfig:
    """Configuration for a specific model."""
    name: str
    model_id: str
    tier: ModelTier
    cost_per_1m_input: float  # Per million tokens
    cost_per_1m_output: float
    max_context: int
    max_output: int
    best_for: List[QueryCategory]
    latency_class: str  # "fast", "medium", "slow"

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for a request in dollars."""
        input_cost = (input_tokens / 1_000_000) * self.cost_per_1m_input
        output_cost = (output_tokens / 1_000_000) * self.cost_per_1m_output
        return input_cost + output_cost


@dataclass
class ClassificationResult:
    """Result of query classification."""
    recommended_tier: ModelTier
    category: QueryCategory
    confidence: float  # 0.0 to 1.0
    reasoning: str
    signals: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommended_tier": self.recommended_tier.value,
            "category": self.category.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "signals": self.signals,
        }


@dataclass
class RoutingDecision:
    """Final routing decision with model selection."""
    model: ModelConfig
    tier: ModelTier
    classification: ClassificationResult
    was_overridden: bool = False
    override_reason: Optional[OverrideReason] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model.model_id,
            "model_name": self.model.name,
            "tier": self.tier.value,
            "classification": self.classification.to_dict(),
            "was_overridden": self.was_overridden,
            "override_reason": self.override_reason.value if self.override_reason else None,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class UsageRecord:
    """Record of a single model usage."""
    tier: ModelTier
    model_id: str
    category: QueryCategory
    input_tokens: int
    output_tokens: int
    cost: float
    latency_ms: float
    timestamp: datetime
    was_accurate: Optional[bool] = None  # Set after user feedback


# =============================================================================
# MODEL CONFIGURATIONS
# =============================================================================


AVAILABLE_MODELS: Dict[ModelTier, ModelConfig] = {
    ModelTier.FAST: ModelConfig(
        name="Claude 3.5 Haiku",
        model_id="claude-3-5-haiku-20241022",
        tier=ModelTier.FAST,
        cost_per_1m_input=1.0,
        cost_per_1m_output=5.0,
        max_context=200000,
        max_output=8192,
        best_for=[
            QueryCategory.GREETING,
            QueryCategory.SIMPLE_QUESTION,
            QueryCategory.STATUS_CHECK,
            QueryCategory.TIME_WEATHER,
        ],
        latency_class="fast",
    ),
    ModelTier.BALANCED: ModelConfig(
        name="Claude 4 Sonnet",
        model_id="claude-sonnet-4-20250514",
        tier=ModelTier.BALANCED,
        cost_per_1m_input=3.0,
        cost_per_1m_output=15.0,
        max_context=200000,
        max_output=16384,
        best_for=[
            QueryCategory.CONVERSATION,
            QueryCategory.TOOL_USAGE,
            QueryCategory.ANALYSIS,
        ],
        latency_class="medium",
    ),
    ModelTier.POWERFUL: ModelConfig(
        name="Claude Opus 4.5",
        model_id="claude-opus-4-5-20251101",
        tier=ModelTier.POWERFUL,
        cost_per_1m_input=15.0,
        cost_per_1m_output=75.0,
        max_context=200000,
        max_output=32768,
        best_for=[
            QueryCategory.CODING,
            QueryCategory.CREATIVE,
            QueryCategory.MULTI_STEP,
            QueryCategory.CRITICAL_DECISION,
        ],
        latency_class="slow",
    ),
}


# =============================================================================
# CLASSIFICATION PATTERNS
# =============================================================================


# Pattern sets for classification
GREETING_PATTERNS = [
    r"^(hi|hello|hey|good\s*(morning|afternoon|evening)|greetings)\b",
    r"^(how are you|what'?s up|howdy)\b",
    r"^(thanks|thank you|bye|goodbye|see you)\b",
]

SIMPLE_QUESTION_PATTERNS = [
    r"\b(what is|what'?s|who is|who'?s)\s+\w+\b",
    r"\b(define|meaning of)\s+\w+\b",
    r"\bhow many\b",
    r"\bwhen (is|was|did)\b",
    r"\bwhere (is|was)\b",
]

STATUS_CHECK_PATTERNS = [
    r"\b(status|state|check|progress)\b",
    r"\bhow(?: is| are)? (?:my|the)\b",
    r"\b(show|list|get)\s+(?:my|the)?\s*\w+\s*(?:status|state)\b",
]

TIME_WEATHER_PATTERNS = [
    r"\b(what time|current time|what'?s the time)\b",
    r"\b(what'?s the date|today'?s date|current date)\b",
    r"\b(weather|temperature|forecast)\b",
    r"\b(sunrise|sunset)\b",
]

CODING_PATTERNS = [
    r"\b(code|coding|program|programming)\b",
    r"\b(function|class|method|variable)\b",
    r"\b(debug|fix|bug|error|exception)\b",
    r"\b(refactor|optimize|improve)\s+(?:the|this)?\s*code\b",
    r"\b(write|create|implement)\s+(?:a|an)?\s*(?:function|class|script|program)\b",
    r"```[\w]*\n",  # Code blocks
    r"\b(python|javascript|typescript|java|c\+\+|rust|go)\b",
    r"\b(api|endpoint|database|query)\b",
]

ANALYSIS_PATTERNS = [
    r"\b(analyze|analysis|analyse)\b",
    r"\b(compare|comparison|versus|vs\.?)\b",
    r"\b(evaluate|assessment|review)\b",
    r"\b(explain\s+(?:why|how))\b",
    r"\b(pros?\s+(?:and|&)\s+cons?)\b",
    r"\b(trade-?offs?|advantages?|disadvantages?)\b",
]

CREATIVE_PATTERNS = [
    r"\b(write|create|compose)\s+(?:a|an)?\s*(story|poem|essay|article|blog)\b",
    r"\b(creative|imagine|invent)\b",
    r"\b(brainstorm|ideas?\s+for)\b",
    r"\b(design|concept|vision)\b",
]

MULTI_STEP_PATTERNS = [
    r"\b(step[\s-]by[\s-]step|steps?)\b",
    r"\b(plan|planning|roadmap|strategy)\b",
    r"\b(first|then|next|finally|after that)\b.*\b(then|next|finally)\b",
    r"\b(process|workflow|procedure)\b",
    r"\b(\d+\.\s+\w+.*){2,}",  # Numbered lists
    r"\b(business|startup|company)\s+plan\b",  # Business planning
    r"\b(comprehensive|detailed)\s+(plan|analysis|review)\b",
]

CRITICAL_DECISION_PATTERNS = [
    r"\b(critical|important|crucial|urgent)\b",
    r"\b(decision|decide|choose|select)\b.*\b(best|right|correct)\b",
    r"\b(production|deploy|release|launch)\b",
    r"\b(security|secure|safe|protect)\b",
    r"\b(financial|money|cost|budget)\s+decision\b",
]

# Technical complexity indicators
TECHNICAL_TERMS = [
    "algorithm", "architecture", "asynchronous", "authentication",
    "authorization", "backend", "caching", "concurrency", "cryptography",
    "database", "debugging", "deployment", "distributed", "docker",
    "elasticsearch", "encryption", "frontend", "graphql", "kubernetes",
    "latency", "microservices", "middleware", "optimization", "parallel",
    "postgresql", "queue", "redis", "scalability", "schema", "serverless",
    "sharding", "socket", "sql", "synchronization", "threading", "transaction",
    "vector", "webhook", "websocket",
]


# =============================================================================
# QUERY CLASSIFIER
# =============================================================================


class QueryClassifier:
    """Analyzes queries and determines the recommended model tier.

    Classification signals:
    - Query length and complexity
    - Presence of technical terms, code, math
    - Multi-step reasoning indicators
    - Creative/analytical markers
    - Urgency/time-sensitivity
    - Conversation context
    """

    def __init__(
        self,
        default_tier: ModelTier = ModelTier.BALANCED,
        confidence_threshold: float = 0.6,
    ):
        """Initialize the classifier.

        Args:
            default_tier: Default tier when classification is uncertain
            confidence_threshold: Minimum confidence to use classification
        """
        self.default_tier = default_tier
        self.confidence_threshold = confidence_threshold

        # Compile patterns for efficiency
        self._patterns = {
            QueryCategory.GREETING: [re.compile(p, re.IGNORECASE) for p in GREETING_PATTERNS],
            QueryCategory.SIMPLE_QUESTION: [re.compile(p, re.IGNORECASE) for p in SIMPLE_QUESTION_PATTERNS],
            QueryCategory.STATUS_CHECK: [re.compile(p, re.IGNORECASE) for p in STATUS_CHECK_PATTERNS],
            QueryCategory.TIME_WEATHER: [re.compile(p, re.IGNORECASE) for p in TIME_WEATHER_PATTERNS],
            QueryCategory.CODING: [re.compile(p, re.IGNORECASE) for p in CODING_PATTERNS],
            QueryCategory.ANALYSIS: [re.compile(p, re.IGNORECASE) for p in ANALYSIS_PATTERNS],
            QueryCategory.CREATIVE: [re.compile(p, re.IGNORECASE) for p in CREATIVE_PATTERNS],
            QueryCategory.MULTI_STEP: [re.compile(p, re.IGNORECASE) for p in MULTI_STEP_PATTERNS],
            QueryCategory.CRITICAL_DECISION: [re.compile(p, re.IGNORECASE) for p in CRITICAL_DECISION_PATTERNS],
        }

        # Technical terms set for fast lookup
        self._technical_terms = set(t.lower() for t in TECHNICAL_TERMS)

    def classify(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ClassificationResult:
        """Analyze a query and return the recommended tier.

        Args:
            query: The user's query text
            conversation_history: Previous messages in the conversation
            context: Additional context (e.g., active tools, user profile)

        Returns:
            ClassificationResult with recommended tier and reasoning
        """
        signals = self._extract_signals(query, conversation_history, context)
        category, category_confidence = self._determine_category(query, signals)
        tier = self._category_to_tier(category, signals)
        confidence = self._calculate_confidence(signals, category_confidence)
        reasoning = self._generate_reasoning(category, signals)

        # Apply confidence threshold
        if confidence < self.confidence_threshold:
            tier = self.default_tier
            reasoning = f"Low confidence ({confidence:.2f}), using default tier. {reasoning}"

        return ClassificationResult(
            recommended_tier=tier,
            category=category,
            confidence=confidence,
            reasoning=reasoning,
            signals=signals,
        )

    def _extract_signals(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, Any]]],
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Extract classification signals from query and context."""
        signals = {
            "query_length": len(query),
            "word_count": len(query.split()),
            "has_code_block": "```" in query,
            "has_question_mark": "?" in query,
            "technical_term_count": 0,
            "conversation_length": 0,
            "pattern_matches": {},
        }

        # Count technical terms
        query_lower = query.lower()
        for term in self._technical_terms:
            if term in query_lower:
                signals["technical_term_count"] += 1

        # Conversation context
        if conversation_history:
            signals["conversation_length"] = len(conversation_history)
            # Check if we're in a coding or complex conversation
            recent_messages = conversation_history[-5:] if len(conversation_history) > 5 else conversation_history
            code_in_history = any("```" in str(m.get("content", "")) for m in recent_messages)
            signals["code_in_conversation"] = code_in_history

        # Additional context signals
        if context:
            signals["active_tools"] = context.get("active_tools", [])
            signals["user_tier_preference"] = context.get("user_tier_preference")
            signals["agent_type"] = context.get("agent_type")

        # Pattern matches
        for category, patterns in self._patterns.items():
            matches = sum(1 for p in patterns if p.search(query))
            if matches > 0:
                signals["pattern_matches"][category.value] = matches

        return signals

    def _determine_category(
        self,
        query: str,
        signals: Dict[str, Any],
    ) -> Tuple[QueryCategory, float]:
        """Determine the query category with confidence."""
        pattern_matches = signals.get("pattern_matches", {})

        # Score each category
        category_scores = {
            QueryCategory.GREETING: 0.0,
            QueryCategory.SIMPLE_QUESTION: 0.0,
            QueryCategory.STATUS_CHECK: 0.0,
            QueryCategory.TIME_WEATHER: 0.0,
            QueryCategory.CONVERSATION: 0.3,  # Base score for default
            QueryCategory.TOOL_USAGE: 0.0,
            QueryCategory.CODING: 0.0,
            QueryCategory.ANALYSIS: 0.0,
            QueryCategory.CREATIVE: 0.0,
            QueryCategory.MULTI_STEP: 0.0,
            QueryCategory.CRITICAL_DECISION: 0.0,
        }

        # Add pattern match scores
        for category_str, matches in pattern_matches.items():
            try:
                category = QueryCategory(category_str)
                category_scores[category] += matches * 0.3
            except ValueError:
                pass

        # Adjust scores based on signals
        word_count = signals.get("word_count", 0)

        # Short queries are likely simpler
        if word_count < 5:
            category_scores[QueryCategory.GREETING] += 0.2
            category_scores[QueryCategory.SIMPLE_QUESTION] += 0.2

        # Technical content boosts coding/analysis
        tech_count = signals.get("technical_term_count", 0)
        if tech_count > 0:
            category_scores[QueryCategory.CODING] += tech_count * 0.15
            category_scores[QueryCategory.ANALYSIS] += tech_count * 0.1

        # Code blocks strongly indicate coding
        if signals.get("has_code_block"):
            category_scores[QueryCategory.CODING] += 0.5

        # Long queries with many words are likely complex
        if word_count > 50:
            category_scores[QueryCategory.MULTI_STEP] += 0.2
            category_scores[QueryCategory.ANALYSIS] += 0.15

        # Find best category
        best_category = max(category_scores, key=category_scores.get)
        best_score = category_scores[best_category]

        # Calculate confidence based on score margin
        sorted_scores = sorted(category_scores.values(), reverse=True)
        if len(sorted_scores) > 1 and sorted_scores[0] > 0:
            margin = sorted_scores[0] - sorted_scores[1]
            confidence = min(0.5 + margin, 0.95)
        else:
            confidence = 0.5

        return best_category, confidence

    def _category_to_tier(
        self,
        category: QueryCategory,
        signals: Dict[str, Any],
    ) -> ModelTier:
        """Map category to model tier."""
        # FAST tier categories
        fast_categories = {
            QueryCategory.GREETING,
            QueryCategory.SIMPLE_QUESTION,
            QueryCategory.STATUS_CHECK,
            QueryCategory.TIME_WEATHER,
        }

        # POWERFUL tier categories (always use best model)
        powerful_categories = {
            QueryCategory.CODING,
            QueryCategory.CREATIVE,
            QueryCategory.MULTI_STEP,
            QueryCategory.CRITICAL_DECISION,
        }

        # Categories that upgrade to POWERFUL with complexity signals
        upgradeable_categories = {
            QueryCategory.ANALYSIS,
        }

        # Determine base tier from category
        if category in fast_categories:
            base_tier = ModelTier.FAST
        elif category in powerful_categories:
            base_tier = ModelTier.POWERFUL
        else:
            base_tier = ModelTier.BALANCED

        # Adjust based on complexity signals
        tech_count = signals.get("technical_term_count", 0)
        word_count = signals.get("word_count", 0)

        # Upgrade if query is complex despite simple category
        if base_tier == ModelTier.FAST:
            if tech_count > 2 or word_count > 30:
                base_tier = ModelTier.BALANCED

        # Upgrade analysis tasks to POWERFUL if they have complexity indicators
        if category in upgradeable_categories:
            # Check for deep analysis indicators
            if tech_count >= 2 or word_count > 40:
                base_tier = ModelTier.POWERFUL
            # Check for specific complex analysis keywords
            pattern_matches = signals.get("pattern_matches", {})
            if "analysis" in pattern_matches and pattern_matches["analysis"] >= 2:
                base_tier = ModelTier.POWERFUL

        # Downgrade if query is simple despite complex category
        # But keep POWERFUL for multi-step planning tasks
        if base_tier == ModelTier.POWERFUL:
            # Don't downgrade multi-step/planning tasks - they need POWERFUL
            if category != QueryCategory.MULTI_STEP:
                if tech_count == 0 and word_count < 10:
                    base_tier = ModelTier.BALANCED

        return base_tier

    def _calculate_confidence(
        self,
        signals: Dict[str, Any],
        category_confidence: float,
    ) -> float:
        """Calculate overall classification confidence."""
        # Start with category confidence
        confidence = category_confidence

        # Adjust based on signal clarity
        pattern_matches = signals.get("pattern_matches", {})
        if len(pattern_matches) == 1:
            # Clear single category match
            confidence += 0.1
        elif len(pattern_matches) > 2:
            # Ambiguous with multiple matches
            confidence -= 0.1

        # Very short queries are harder to classify
        if signals.get("word_count", 0) < 3:
            confidence -= 0.1

        return max(0.1, min(0.95, confidence))

    def _generate_reasoning(
        self,
        category: QueryCategory,
        signals: Dict[str, Any],
    ) -> str:
        """Generate human-readable reasoning for classification."""
        reasons = []

        if category == QueryCategory.GREETING:
            reasons.append("Detected greeting pattern")
        elif category == QueryCategory.CODING:
            if signals.get("has_code_block"):
                reasons.append("Contains code block")
            if signals.get("technical_term_count", 0) > 0:
                reasons.append(f"Contains {signals['technical_term_count']} technical terms")
            reasons.append("Coding-related query")
        elif category == QueryCategory.ANALYSIS:
            reasons.append("Requires analytical reasoning")
        elif category == QueryCategory.CREATIVE:
            reasons.append("Creative task requested")
        elif category == QueryCategory.MULTI_STEP:
            reasons.append("Multi-step planning required")
        elif category == QueryCategory.CRITICAL_DECISION:
            reasons.append("Critical decision-making context")

        # Add complexity notes
        if signals.get("word_count", 0) > 50:
            reasons.append(f"Long query ({signals['word_count']} words)")

        if signals.get("conversation_length", 0) > 10:
            reasons.append("Extended conversation context")

        return "; ".join(reasons) if reasons else f"Category: {category.value}"


# =============================================================================
# MODEL ROUTER
# =============================================================================


class ModelRouter:
    """Routes queries to the appropriate model based on classification.

    Features:
    - Intelligent tier selection via QueryClassifier
    - Override support for agents and users
    - Cost tracking per tier
    - Fallback logic for model availability
    - Usage analytics
    """

    def __init__(
        self,
        classifier: Optional[QueryClassifier] = None,
        models: Optional[Dict[ModelTier, ModelConfig]] = None,
        enable_tracking: bool = True,
        cost_limit_per_hour: Optional[float] = None,
    ):
        """Initialize the router.

        Args:
            classifier: QueryClassifier instance (creates default if None)
            models: Model configurations (uses defaults if None)
            enable_tracking: Whether to track usage
            cost_limit_per_hour: Optional hourly cost limit
        """
        self.classifier = classifier or QueryClassifier()
        self.models = models or AVAILABLE_MODELS.copy()
        self.enable_tracking = enable_tracking
        self.cost_limit_per_hour = cost_limit_per_hour

        # Tracking state
        self._usage_history: List[UsageRecord] = []
        self._tier_counts: Dict[ModelTier, int] = {tier: 0 for tier in ModelTier}
        self._tier_costs: Dict[ModelTier, float] = {tier: 0.0 for tier in ModelTier}
        self._classification_accuracy: List[Tuple[bool, ModelTier]] = []

        # Override state
        self._forced_tier: Optional[ModelTier] = None
        self._user_preferences: Dict[str, ModelTier] = {}
        self._agent_overrides: Dict[str, ModelTier] = {}

        logger.info("ModelRouter initialized with tiers: " + ", ".join(t.value for t in self.models.keys()))

    def route(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> RoutingDecision:
        """Route a query to the appropriate model.

        Args:
            query: The user's query
            conversation_history: Previous conversation messages
            context: Additional context
            user_id: User ID for preference lookup
            agent_id: Agent ID for override lookup

        Returns:
            RoutingDecision with selected model
        """
        # Classify the query
        classification = self.classifier.classify(
            query,
            conversation_history,
            context,
        )

        # Check for overrides in order of priority
        override_tier = None
        override_reason = None

        # 1. Forced tier (testing)
        if self._forced_tier is not None:
            override_tier = self._forced_tier
            override_reason = OverrideReason.TESTING

        # 2. Agent override (e.g., Ultron for critical decisions)
        elif agent_id and agent_id in self._agent_overrides:
            override_tier = self._agent_overrides[agent_id]
            override_reason = OverrideReason.AGENT_OVERRIDE

        # 3. User preference
        elif user_id and user_id in self._user_preferences:
            override_tier = self._user_preferences[user_id]
            override_reason = OverrideReason.USER_PREFERENCE

        # 4. Cost limit check
        elif self.cost_limit_per_hour and self._check_cost_limit():
            # Downgrade to cheapest tier
            override_tier = ModelTier.FAST
            override_reason = OverrideReason.COST_LIMIT

        # 5. Critical task in context
        elif context and context.get("is_critical"):
            override_tier = ModelTier.POWERFUL
            override_reason = OverrideReason.CRITICAL_TASK

        # Determine final tier
        if override_tier is not None:
            final_tier = override_tier
            was_overridden = True
        else:
            final_tier = classification.recommended_tier
            was_overridden = False

        # Get model for tier (with fallback)
        model = self.get_model_for_tier(final_tier)

        # Create decision
        decision = RoutingDecision(
            model=model,
            tier=final_tier,
            classification=classification,
            was_overridden=was_overridden,
            override_reason=override_reason,
        )

        # Track usage
        if self.enable_tracking:
            self._tier_counts[final_tier] += 1

        logger.debug(
            f"Routed query to {model.name}: "
            f"tier={final_tier.value}, "
            f"category={classification.category.value}, "
            f"confidence={classification.confidence:.2f}"
        )

        return decision

    def get_model_for_tier(
        self,
        tier: ModelTier,
        fallback: bool = True,
    ) -> ModelConfig:
        """Get the model configuration for a tier.

        Args:
            tier: The model tier
            fallback: Whether to fallback if tier unavailable

        Returns:
            ModelConfig for the tier
        """
        if tier in self.models:
            return self.models[tier]

        if fallback:
            # Fallback order: BALANCED -> FAST -> POWERFUL
            fallback_order = [ModelTier.BALANCED, ModelTier.FAST, ModelTier.POWERFUL]
            for fallback_tier in fallback_order:
                if fallback_tier in self.models and fallback_tier != tier:
                    logger.warning(f"Tier {tier.value} unavailable, falling back to {fallback_tier.value}")
                    return self.models[fallback_tier]

        raise ValueError(f"No model available for tier {tier.value}")

    def override_tier(
        self,
        tier: Optional[ModelTier],
        reason: str = "testing",
    ) -> None:
        """Force a specific tier for all queries (for testing).

        Args:
            tier: Tier to force, or None to clear
            reason: Reason for the override
        """
        self._forced_tier = tier
        if tier:
            logger.info(f"Forcing tier override to {tier.value}: {reason}")
        else:
            logger.info("Cleared tier override")

    def set_user_preference(
        self,
        user_id: str,
        preference: Optional[ModelTier],
    ) -> None:
        """Set a user's model preference.

        Args:
            user_id: User identifier
            preference: Preferred tier, or None to clear
        """
        if preference is None:
            self._user_preferences.pop(user_id, None)
        else:
            self._user_preferences[user_id] = preference
            logger.info(f"Set user {user_id} preference to {preference.value}")

    def set_agent_override(
        self,
        agent_id: str,
        tier: Optional[ModelTier],
    ) -> None:
        """Set an agent-specific tier override.

        Args:
            agent_id: Agent identifier (e.g., "ultron")
            tier: Override tier, or None to clear
        """
        if tier is None:
            self._agent_overrides.pop(agent_id, None)
        else:
            self._agent_overrides[agent_id] = tier
            logger.info(f"Set agent {agent_id} override to {tier.value}")

    def record_usage(
        self,
        decision: RoutingDecision,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
    ) -> UsageRecord:
        """Record usage after a request completes.

        Args:
            decision: The routing decision that was used
            input_tokens: Actual input tokens
            output_tokens: Actual output tokens
            latency_ms: Request latency in milliseconds

        Returns:
            UsageRecord for the request
        """
        cost = decision.model.estimate_cost(input_tokens, output_tokens)

        record = UsageRecord(
            tier=decision.tier,
            model_id=decision.model.model_id,
            category=decision.classification.category,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            latency_ms=latency_ms,
            timestamp=datetime.utcnow(),
        )

        if self.enable_tracking:
            self._usage_history.append(record)
            self._tier_costs[decision.tier] += cost

            # Keep only last 1000 records
            if len(self._usage_history) > 1000:
                self._usage_history = self._usage_history[-1000:]

        return record

    def record_classification_accuracy(
        self,
        was_accurate: bool,
        tier_used: ModelTier,
    ) -> None:
        """Record whether a classification was accurate (user feedback).

        Args:
            was_accurate: Whether the tier selection was appropriate
            tier_used: The tier that was used
        """
        self._classification_accuracy.append((was_accurate, tier_used))

        # Keep only last 500 accuracy records
        if len(self._classification_accuracy) > 500:
            self._classification_accuracy = self._classification_accuracy[-500:]

    def _check_cost_limit(self) -> bool:
        """Check if hourly cost limit has been reached."""
        if not self.cost_limit_per_hour:
            return False

        # Calculate cost in last hour
        cutoff = datetime.utcnow() - timedelta(hours=1)
        recent_cost = sum(
            r.cost for r in self._usage_history
            if r.timestamp > cutoff
        )

        return recent_cost >= self.cost_limit_per_hour

    @property
    def usage_stats(self) -> Dict[str, Any]:
        """Get comprehensive usage statistics."""
        total_requests = sum(self._tier_counts.values())
        total_cost = sum(self._tier_costs.values())

        # Calculate accuracy
        accuracy = None
        if self._classification_accuracy:
            accurate_count = sum(1 for acc, _ in self._classification_accuracy if acc)
            accuracy = accurate_count / len(self._classification_accuracy)

        # Calculate tier percentages
        tier_percentages = {}
        for tier, count in self._tier_counts.items():
            tier_percentages[tier.value] = (count / total_requests * 100) if total_requests > 0 else 0

        # Recent latency stats
        recent_records = self._usage_history[-100:] if self._usage_history else []
        avg_latency = sum(r.latency_ms for r in recent_records) / len(recent_records) if recent_records else 0

        return {
            "total_requests": total_requests,
            "total_cost": total_cost,
            "by_tier": {
                tier.value: {
                    "count": self._tier_counts[tier],
                    "cost": self._tier_costs[tier],
                    "percentage": tier_percentages[tier.value],
                }
                for tier in ModelTier
            },
            "classification_accuracy": accuracy,
            "accuracy_sample_size": len(self._classification_accuracy),
            "average_latency_ms": avg_latency,
            "cost_limit_per_hour": self.cost_limit_per_hour,
            "cost_limit_active": self._check_cost_limit() if self.cost_limit_per_hour else False,
        }

    def get_cost_by_category(self) -> Dict[str, float]:
        """Get cost breakdown by query category."""
        costs = {cat.value: 0.0 for cat in QueryCategory}

        for record in self._usage_history:
            costs[record.category.value] += record.cost

        return costs

    def reset_stats(self) -> None:
        """Reset all tracking statistics."""
        self._usage_history.clear()
        self._tier_counts = {tier: 0 for tier in ModelTier}
        self._tier_costs = {tier: 0.0 for tier in ModelTier}
        self._classification_accuracy.clear()
        logger.info("Router statistics reset")


# =============================================================================
# ROUTER MIDDLEWARE
# =============================================================================


class RouterMiddleware:
    """Middleware that intercepts requests and applies routing.

    Integrates with the AI engine to automatically route requests
    to the appropriate model based on query classification.
    """

    def __init__(
        self,
        router: ModelRouter,
        on_route: Optional[Callable[[RoutingDecision], None]] = None,
    ):
        """Initialize middleware.

        Args:
            router: ModelRouter instance
            on_route: Optional callback when routing decision is made
        """
        self.router = router
        self.on_route = on_route

    async def process_request(
        self,
        query: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, RoutingDecision]:
        """Process a request and return the model ID to use.

        Args:
            query: User query
            user_id: User identifier
            agent_id: Agent identifier
            conversation_history: Conversation history
            context: Additional context

        Returns:
            Tuple of (model_id, RoutingDecision)
        """
        decision = self.router.route(
            query=query,
            conversation_history=conversation_history,
            context=context,
            user_id=user_id,
            agent_id=agent_id,
        )

        if self.on_route:
            self.on_route(decision)

        return decision.model.model_id, decision

    def record_completion(
        self,
        decision: RoutingDecision,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
    ) -> None:
        """Record completion of a routed request.

        Args:
            decision: The routing decision used
            input_tokens: Actual input tokens
            output_tokens: Actual output tokens
            latency_ms: Request latency
        """
        self.router.record_usage(decision, input_tokens, output_tokens, latency_ms)


# =============================================================================
# GLOBAL INSTANCES
# =============================================================================


_router: Optional[ModelRouter] = None
_middleware: Optional[RouterMiddleware] = None


def get_router() -> ModelRouter:
    """Get the global ModelRouter instance."""
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router


def get_middleware() -> RouterMiddleware:
    """Get the global RouterMiddleware instance."""
    global _middleware
    if _middleware is None:
        _middleware = RouterMiddleware(get_router())
    return _middleware


def configure_router(
    cost_limit_per_hour: Optional[float] = None,
    default_tier: ModelTier = ModelTier.BALANCED,
    enable_tracking: bool = True,
) -> ModelRouter:
    """Configure and return the global router.

    Args:
        cost_limit_per_hour: Optional hourly cost limit
        default_tier: Default tier for uncertain classifications
        enable_tracking: Whether to track usage

    Returns:
        Configured ModelRouter instance
    """
    global _router, _middleware

    classifier = QueryClassifier(default_tier=default_tier)
    _router = ModelRouter(
        classifier=classifier,
        enable_tracking=enable_tracking,
        cost_limit_per_hour=cost_limit_per_hour,
    )
    _middleware = RouterMiddleware(_router)

    logger.info(f"Router configured: default_tier={default_tier.value}, cost_limit={cost_limit_per_hour}")
    return _router


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def route_query(
    query: str,
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Tuple[str, RoutingDecision]:
    """Route a query and return the model ID.

    Convenience function for simple routing.

    Args:
        query: User query
        user_id: Optional user ID
        agent_id: Optional agent ID
        conversation_history: Optional conversation history
        context: Optional additional context

    Returns:
        Tuple of (model_id, RoutingDecision)
    """
    router = get_router()
    decision = router.route(
        query=query,
        user_id=user_id,
        agent_id=agent_id,
        conversation_history=conversation_history,
        context=context,
    )
    return decision.model.model_id, decision


def classify_query(
    query: str,
    conversation_history: Optional[List[Dict[str, Any]]] = None,
) -> ClassificationResult:
    """Classify a query without routing.

    Args:
        query: User query
        conversation_history: Optional conversation history

    Returns:
        ClassificationResult
    """
    router = get_router()
    return router.classifier.classify(query, conversation_history)


def get_model_for_tier(tier: ModelTier) -> ModelConfig:
    """Get model configuration for a tier.

    Args:
        tier: Model tier

    Returns:
        ModelConfig
    """
    return get_router().get_model_for_tier(tier)


def set_user_model_preference(user_id: str, tier: ModelTier) -> None:
    """Set a user's model preference.

    Args:
        user_id: User ID
        tier: Preferred tier
    """
    get_router().set_user_preference(user_id, tier)


def configure_ultron_override(enabled: bool = True) -> None:
    """Configure Ultron to use POWERFUL tier for autonomous decisions.

    Args:
        enabled: Whether to enable the override
    """
    router = get_router()
    if enabled:
        router.set_agent_override("ultron", ModelTier.POWERFUL)
    else:
        router.set_agent_override("ultron", None)
