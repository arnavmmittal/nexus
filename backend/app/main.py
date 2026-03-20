"""
Nexus Backend - FastAPI Application Entry Point.

This is the main entry point for the Nexus backend API.
Run with: uvicorn app.main:app --reload
"""

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

    logger.info(f"Server running at http://{settings.host}:{settings.port}")

    yield

    # Shutdown
    logger.info("Shutting down Nexus backend...")
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
