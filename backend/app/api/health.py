"""Health check endpoint for Nexus backend."""

from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint.

    Returns basic status information to verify the backend is running.
    Used by frontend to detect if Jarvis is available.
    """
    return {
        "status": "healthy",
        "service": "nexus-backend",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }


@router.get("/health/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """
    Detailed health check with component status.

    Checks database, vector store, and other dependencies.
    """
    components = {
        "api": "healthy",
        "database": "unknown",
        "vector_store": "unknown",
        "elevenlabs": "unknown",
    }

    # Check database
    try:
        from app.core.database import engine
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        components["database"] = "healthy"
    except Exception as e:
        components["database"] = f"unhealthy: {str(e)}"

    # Check vector store
    try:
        from app.memory.vector_store import get_vector_store
        vs = get_vector_store()
        if vs:
            components["vector_store"] = "healthy"
        else:
            components["vector_store"] = "not configured"
    except Exception as e:
        components["vector_store"] = f"unhealthy: {str(e)}"

    # Check ElevenLabs
    try:
        from app.voice.elevenlabs import get_elevenlabs_client
        client = get_elevenlabs_client()
        if client:
            components["elevenlabs"] = "healthy"
        else:
            components["elevenlabs"] = "not configured"
    except Exception as e:
        components["elevenlabs"] = f"unavailable: {str(e)}"

    # Overall status
    all_healthy = all(
        status in ("healthy", "not configured")
        for status in components.values()
    )

    return {
        "status": "healthy" if all_healthy else "degraded",
        "service": "nexus-backend",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "components": components,
    }


@router.get("/ready")
async def readiness_check() -> Dict[str, Any]:
    """
    Readiness probe for service orchestration.

    Returns 200 if the service is ready to handle requests.
    Used by LaunchAgent/Kubernetes to determine if traffic should be routed.
    """
    try:
        from app.core.database import engine
        from sqlalchemy import text

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

        return {
            "ready": True,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {
            "ready": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


@router.get("/live")
async def liveness_check() -> Dict[str, Any]:
    """
    Liveness probe for service orchestration.

    Always returns 200 if the service process is running.
    Used by LaunchAgent/Kubernetes to determine if the service needs restart.
    """
    return {
        "alive": True,
        "timestamp": datetime.utcnow().isoformat(),
    }
