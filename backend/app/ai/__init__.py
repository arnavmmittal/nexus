from __future__ import annotations
"""AI engine for Nexus - Claude integration and context assembly."""

from app.ai.engine import AIEngine
from app.ai.context import ContextAssembler
from app.ai.prompts import SYSTEM_PROMPT, get_system_prompt

# Import intelligent routing system
try:
    from app.ai.routing import (
        ModelTier,
        QueryCategory,
        OverrideReason,
        ModelConfig,
        ClassificationResult,
        RoutingDecision,
        UsageRecord,
        QueryClassifier,
        ModelRouter,
        RouterMiddleware,
        get_router,
        get_middleware,
        configure_router,
        route_query,
        classify_query,
        get_model_for_tier,
        set_user_model_preference,
        configure_ultron_override,
        AVAILABLE_MODELS,
    )
    ROUTING_AVAILABLE = True
except ImportError:
    ROUTING_AVAILABLE = False
    ModelTier = None
    QueryCategory = None
    OverrideReason = None
    ModelConfig = None
    ClassificationResult = None
    RoutingDecision = None
    UsageRecord = None
    QueryClassifier = None
    ModelRouter = None
    RouterMiddleware = None
    get_router = None
    get_middleware = None
    configure_router = None
    route_query = None
    classify_query = None
    get_model_for_tier = None
    set_user_model_preference = None
    configure_ultron_override = None
    AVAILABLE_MODELS = {}

# Import explanation system for transparency
try:
    from app.ai.explanations import (
        ExplanationEngine,
        DecisionLog,
        DecisionOutcome,
        ReasoningFormatter,
        get_explanation_engine,
        log_decision,
        EXPLANATION_TOOLS,
    )
    EXPLANATIONS_AVAILABLE = True
except ImportError:
    EXPLANATIONS_AVAILABLE = False
    ExplanationEngine = None
    DecisionLog = None
    DecisionOutcome = None
    ReasoningFormatter = None
    get_explanation_engine = None
    log_decision = None
    EXPLANATION_TOOLS = []

# Import document analysis system
try:
    from app.ai.documents import (
        DocumentAnalyzer,
        DocumentStore,
        DocumentAnalysis,
        DocumentMetadata,
        DocumentType,
        ExtractedTable,
        get_document_analyzer,
        get_document_store,
        analyze_document,
        summarize_document,
        extract_from_document,
        search_in_document,
        compare_documents,
        DOCUMENT_TOOLS,
    )
    DOCUMENTS_AVAILABLE = True
except ImportError:
    DOCUMENTS_AVAILABLE = False
    DocumentAnalyzer = None
    DocumentStore = None
    DocumentAnalysis = None
    DocumentMetadata = None
    DocumentType = None
    ExtractedTable = None
    get_document_analyzer = None
    get_document_store = None
    analyze_document = None
    summarize_document = None
    extract_from_document = None
    search_in_document = None
    compare_documents = None
    DOCUMENT_TOOLS = []

# Import predictive alerts system
try:
    from app.ai.predictions import (
        PredictionType,
        PredictionUrgency,
        PredictionStatus,
        Prediction,
        SuggestedAction,
        BaseAnalyzer,
        CalendarAnalyzer,
        BehaviorAnalyzer,
        GoalAnalyzer,
        CommunicationAnalyzer,
        FinancialAnalyzer,
        PredictiveEngine,
        PREDICTION_TOOLS,
        PredictionToolExecutor,
        JarvisPredictionBehavior,
        UltronPredictionBehavior,
    )
    PREDICTIONS_AVAILABLE = True
except ImportError:
    PREDICTIONS_AVAILABLE = False
    PredictionType = None
    PredictionUrgency = None
    PredictionStatus = None
    Prediction = None
    SuggestedAction = None
    BaseAnalyzer = None
    CalendarAnalyzer = None
    BehaviorAnalyzer = None
    GoalAnalyzer = None
    CommunicationAnalyzer = None
    FinancialAnalyzer = None
    PredictiveEngine = None
    PREDICTION_TOOLS = []
    PredictionToolExecutor = None
    JarvisPredictionBehavior = None
    UltronPredictionBehavior = None

__all__ = [
    "AIEngine",
    "ContextAssembler",
    "SYSTEM_PROMPT",
    "get_system_prompt",
    # Intelligent Routing
    "ModelTier",
    "QueryCategory",
    "OverrideReason",
    "ModelConfig",
    "ClassificationResult",
    "RoutingDecision",
    "UsageRecord",
    "QueryClassifier",
    "ModelRouter",
    "RouterMiddleware",
    "get_router",
    "get_middleware",
    "configure_router",
    "route_query",
    "classify_query",
    "get_model_for_tier",
    "set_user_model_preference",
    "configure_ultron_override",
    "AVAILABLE_MODELS",
    "ROUTING_AVAILABLE",
    # Explanations
    "ExplanationEngine",
    "DecisionLog",
    "DecisionOutcome",
    "ReasoningFormatter",
    "get_explanation_engine",
    "log_decision",
    "EXPLANATION_TOOLS",
    "EXPLANATIONS_AVAILABLE",
    # Document Analysis
    "DocumentAnalyzer",
    "DocumentStore",
    "DocumentAnalysis",
    "DocumentMetadata",
    "DocumentType",
    "ExtractedTable",
    "get_document_analyzer",
    "get_document_store",
    "analyze_document",
    "summarize_document",
    "extract_from_document",
    "search_in_document",
    "compare_documents",
    "DOCUMENT_TOOLS",
    "DOCUMENTS_AVAILABLE",
    # Predictive Alerts
    "PredictionType",
    "PredictionUrgency",
    "PredictionStatus",
    "Prediction",
    "SuggestedAction",
    "BaseAnalyzer",
    "CalendarAnalyzer",
    "BehaviorAnalyzer",
    "GoalAnalyzer",
    "CommunicationAnalyzer",
    "FinancialAnalyzer",
    "PredictiveEngine",
    "PREDICTION_TOOLS",
    "PredictionToolExecutor",
    "JarvisPredictionBehavior",
    "UltronPredictionBehavior",
    "PREDICTIONS_AVAILABLE",
]
