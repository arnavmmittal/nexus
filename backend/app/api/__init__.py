"""API routes for Nexus backend."""

from fastapi import APIRouter

from app.api import chat, widgets, skills, goals, memory
from app.voice.router import router as voice_router

# Create main API router
api_router = APIRouter()

# Include all route modules
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(widgets.router, prefix="/widgets", tags=["widgets"])
api_router.include_router(skills.router, prefix="/skills", tags=["skills"])
api_router.include_router(goals.router, prefix="/goals", tags=["goals"])
api_router.include_router(memory.router, prefix="/memory", tags=["memory"])
api_router.include_router(voice_router, prefix="/voice", tags=["voice"])
