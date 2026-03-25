"""Event-driven architecture for the Nexus AI system.

This module provides the infrastructure for event-driven communication
across the entire system. Events enable decoupled, reactive behaviors
that make the AI feel alive and responsive.

Core Components:
- EventBus: Central pub/sub message broker
- Event: The event data structure
- Handlers: Reusable event processing utilities
- WorkflowEngine: Complex multi-step automation

Event Types:
- User events: user_message, voice_command
- Agent events: agent_response, agent_thinking, agent_error
- Tool events: tool_executed, tool_failed
- Memory events: memory_updated, memory_recalled
- Proactive events: proactive_suggestion, proactive_action
- Schedule events: schedule_triggered, schedule_created
- Environment events: smart_home_changed, location_changed
- Workflow events: workflow_started, workflow_completed

Usage:
    from app.events import (
        Event, EventType, EventPriority,
        get_event_bus, emit, subscribe,
        WorkflowEngine, Workflow,
    )

    # Publish an event
    await emit(EventType.USER_MESSAGE, data={"message": "Hello"})

    # Subscribe to events
    async def on_message(event: Event):
        print(f"Received: {event.data}")

    subscribe("user_*", on_message)

    # Create a workflow
    workflow = Workflow(name="my_workflow")
    workflow.add_step("step1", my_action)
    engine.register(workflow)
"""

from .bus import (
    Event,
    EventBus,
    EventPriority,
    EventType,
    Subscription,
    emit,
    get_event_bus,
    publish,
    subscribe,
    unsubscribe,
)

from .handlers import (
    AggregatingHandler,
    BaseHandler,
    ChainHandler,
    ConditionalHandler,
    LoggingHandler,
    MetricsHandler,
    ThrottledHandler,
)

from .workflows import (
    StepStatus,
    Workflow,
    WorkflowEngine,
    WorkflowMode,
    WorkflowStatus,
    WorkflowStep,
    create_leaving_home_workflow,
    create_meeting_prep_workflow,
    create_morning_routine_workflow,
    get_workflow_engine,
    register_default_workflows,
    start_workflow_engine,
    stop_workflow_engine,
)


# Module-level initialization functions
async def initialize_events() -> None:
    """Initialize the event system.

    Sets up:
    1. Global event bus
    2. Default handlers (logging, metrics)
    3. Workflow engine with default workflows
    """
    bus = get_event_bus()

    # Set up default logging handler
    logging_handler = LoggingHandler(
        name="SystemLogger",
        log_level=10,  # DEBUG
        include_data=True,
    )
    logging_handler.register(bus, patterns=["*"])

    # Set up metrics handler
    metrics_handler = MetricsHandler(
        name="SystemMetrics",
        window_minutes=60,
    )
    metrics_handler.register(bus, patterns=["*"])

    # Set up chain handler for common event chains
    chain_handler = ChainHandler(
        name="EventChains",
        chains={
            EventType.TOOL_EXECUTED.value: EventType.MEMORY_UPDATED.value,
        },
    )
    chain_handler.register(bus, patterns=["tool_*"])

    # Initialize workflow engine
    await start_workflow_engine()


async def shutdown_events() -> None:
    """Shutdown the event system cleanly."""
    # Stop workflow engine
    await stop_workflow_engine()

    # Shutdown event bus
    bus = get_event_bus()
    await bus.shutdown()


__all__ = [
    # Event bus
    "Event",
    "EventBus",
    "EventPriority",
    "EventType",
    "Subscription",
    "emit",
    "get_event_bus",
    "publish",
    "subscribe",
    "unsubscribe",
    # Handlers
    "AggregatingHandler",
    "BaseHandler",
    "ChainHandler",
    "ConditionalHandler",
    "LoggingHandler",
    "MetricsHandler",
    "ThrottledHandler",
    # Workflows
    "StepStatus",
    "Workflow",
    "WorkflowEngine",
    "WorkflowMode",
    "WorkflowStatus",
    "WorkflowStep",
    "create_leaving_home_workflow",
    "create_meeting_prep_workflow",
    "create_morning_routine_workflow",
    "get_workflow_engine",
    "register_default_workflows",
    "start_workflow_engine",
    "stop_workflow_engine",
    # Initialization
    "initialize_events",
    "shutdown_events",
]
