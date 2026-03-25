"""
Nexus Backend - FastAPI Application Entry Point.

This is the main entry point for the Nexus backend API.
Run with: uvicorn app.main:app --reload
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.core.config import settings
from app.core.database import close_db, init_db
from app.core.scheduler import start_scheduler, stop_scheduler

# MCP server initialization
try:
    from app.mcp import start_mcp_registry, stop_mcp_registry
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    start_mcp_registry = None
    stop_mcp_registry = None

# Background daemon initialization
try:
    from app.daemon import (
        start_background_monitor,
        stop_background_monitor,
        get_background_monitor,
        get_auto_apply_pipeline,
    )
    DAEMON_AVAILABLE = True
except ImportError:
    DAEMON_AVAILABLE = False
    start_background_monitor = None
    stop_background_monitor = None
    get_background_monitor = None
    get_auto_apply_pipeline = None

# Notification system initialization
try:
    from app.notifications import (
        get_notification_manager,
        setup_monitor_notifications,
    )
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False
    get_notification_manager = None
    setup_monitor_notifications = None

# Agent collaboration hub initialization
try:
    from app.agents import (
        get_collaboration_hub,
        start_collaboration_hub,
        initialize_agents,
        INTEGRATION_AVAILABLE,
        AGENTS_AVAILABLE,
    )
    COLLABORATION_AVAILABLE = INTEGRATION_AVAILABLE and AGENTS_AVAILABLE
except ImportError:
    COLLABORATION_AVAILABLE = False
    get_collaboration_hub = None
    start_collaboration_hub = None
    initialize_agents = None

# Proactive engine initialization
try:
    from app.agents.proactive import (
        get_proactive_engine,
        start_proactive_engine,
        stop_proactive_engine,
    )
    PROACTIVE_AVAILABLE = True
except ImportError:
    PROACTIVE_AVAILABLE = False
    get_proactive_engine = None
    start_proactive_engine = None
    stop_proactive_engine = None

# Event-driven architecture initialization
try:
    from app.events import (
        initialize_events,
        shutdown_events,
        get_event_bus,
        get_workflow_engine,
        emit,
        EventType,
    )
    EVENTS_AVAILABLE = True
except ImportError:
    EVENTS_AVAILABLE = False
    initialize_events = None
    shutdown_events = None
    get_event_bus = None
    get_workflow_engine = None
    emit = None
    EventType = None

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting Nexus backend...")

    # Initialize database (create tables if they don't exist)
    # Note: In production, use Alembic migrations instead
    if settings.debug:
        try:
            await init_db()
            logger.info("Database initialized")
        except Exception as e:
            logger.warning(f"Database initialization skipped: {e}")

    # Start background scheduler
    try:
        await start_scheduler()
        logger.info("Background scheduler started")
    except Exception as e:
        logger.warning(f"Background scheduler initialization failed: {e}")

    # Initialize MCP servers
    if MCP_AVAILABLE:
        try:
            registry = await start_mcp_registry()
            status = registry.get_server_status()
            logger.info(f"MCP servers initialized: {len(status)} servers connected")
            for name, info in status.items():
                logger.info(f"  - {name}: {info['tools_count']} tools available")
        except Exception as e:
            logger.warning(f"MCP initialization failed: {e}")

    # Initialize background monitor daemon (Ultron's always-on system)
    if DAEMON_AVAILABLE:
        try:
            from app.core.user_profile import get_user_profile
            profile = get_user_profile()

            if profile.autonomy.background_monitoring_enabled:
                # Start monitor in background task
                monitor = get_background_monitor()
                asyncio.create_task(monitor.start())
                logger.info("Background monitor daemon started")

                # Set up notification integration
                if NOTIFICATIONS_AVAILABLE and setup_monitor_notifications:
                    setup_monitor_notifications()
                    logger.info("Monitor notifications configured")
            else:
                logger.info("Background monitoring disabled in user settings")

            # Start auto-apply pipeline if enabled
            if profile.autonomy.auto_apply_jobs_enabled and get_auto_apply_pipeline:
                pipeline = get_auto_apply_pipeline()
                asyncio.create_task(pipeline.start())
                logger.info("Auto-apply pipeline started")

        except Exception as e:
            logger.warning(f"Background daemon initialization failed: {e}")

    # Initialize agent collaboration hub with Jarvis and Ultron agents
    if COLLABORATION_AVAILABLE and initialize_agents:
        try:
            jarvis, ultron, hub = initialize_agents()
            if jarvis and ultron:
                logger.info("Jarvis and Ultron agents initialized and connected")
                logger.info(f"  - Jarvis: User-facing assistant (autonomy: 0.3)")
                logger.info(f"  - Ultron: Autonomous executor (autonomy: 0.7)")
            else:
                logger.warning("Agents not fully initialized - falling back to collaboration hub only")
                hub = start_collaboration_hub()
        except Exception as e:
            logger.warning(f"Agent initialization failed: {e}")
            # Fallback to basic hub
            try:
                hub = start_collaboration_hub()
                logger.info("Agent collaboration hub started (basic mode)")
            except Exception as e2:
                logger.warning(f"Collaboration hub initialization also failed: {e2}")

    # Initialize proactive suggestion engine
    if PROACTIVE_AVAILABLE and start_proactive_engine:
        try:
            asyncio.create_task(start_proactive_engine())
            logger.info("Proactive suggestion engine started")
        except Exception as e:
            logger.warning(f"Proactive engine initialization failed: {e}")

    # Initialize event-driven architecture (event bus + workflows)
    if EVENTS_AVAILABLE and initialize_events:
        try:
            await initialize_events()
            bus = get_event_bus()
            engine = get_workflow_engine()
            stats = bus.get_statistics()
            logger.info(
                f"Event system initialized: {stats['subscription_count']} subscriptions, "
                f"{len(engine._workflows)} workflows registered"
            )

            # Emit system startup event
            await emit(
                EventType.SYSTEM_STARTUP,
                data={
                    "version": "0.1.0",
                    "debug": settings.debug,
                    "host": settings.host,
                    "port": settings.port,
                },
                source="main",
            )
        except Exception as e:
            logger.warning(f"Event system initialization failed: {e}")

    logger.info(f"Server running at http://{settings.host}:{settings.port}")

    yield

    # Shutdown
    logger.info("Shutting down Nexus backend...")

    # Shutdown event system first (workflows may depend on other services)
    if EVENTS_AVAILABLE and shutdown_events:
        try:
            # Emit shutdown event before closing
            if emit and EventType:
                await emit(EventType.SYSTEM_SHUTDOWN, source="main")
            await shutdown_events()
            logger.info("Event system shutdown complete")
        except Exception as e:
            logger.warning(f"Event system shutdown error: {e}")

    # Stop background monitor daemon
    if DAEMON_AVAILABLE and stop_background_monitor:
        try:
            await stop_background_monitor()
            logger.info("Background monitor daemon stopped")
        except Exception as e:
            logger.warning(f"Background monitor shutdown error: {e}")

    # Stop MCP servers
    if MCP_AVAILABLE and stop_mcp_registry:
        try:
            await stop_mcp_registry()
            logger.info("MCP servers disconnected")
        except Exception as e:
            logger.warning(f"MCP shutdown error: {e}")

    await stop_scheduler()
    logger.info("Background scheduler stopped")
    await close_db()
    logger.info("Database connections closed")


# Create FastAPI application
app = FastAPI(
    title="Nexus API",
    description="""
    Nexus - Your Personal AI Life Operating System

    A JARVIS-like assistant that helps you optimize your life across all domains:
    - Skills tracking with XP and levels
    - Goal management and progress tracking
    - AI-powered chat with context awareness
    - Memory system with semantic search
    - Integration with external services
    """,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoints at root level for easy access
from datetime import datetime


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/ready", tags=["health"])
async def readiness_check() -> dict:
    """Readiness probe - checks if service can handle requests."""
    return {
        "ready": True,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/live", tags=["health"])
async def liveness_check() -> dict:
    """Liveness probe - checks if service process is running."""
    return {
        "alive": True,
        "timestamp": datetime.utcnow().isoformat(),
    }


# Root endpoint
@app.get("/", tags=["root"])
async def root() -> dict:
    """Root endpoint with API information."""
    return {
        "name": "Nexus API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


# Include API routes
app.include_router(api_router, prefix="/api")


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle uncaught exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
