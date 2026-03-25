from __future__ import annotations
"""API routes for Nexus backend."""

from fastapi import APIRouter

from app.api import chat, widgets, skills, goals, memory, integrations, costs, health, agents, ultron, mcp, autonomy, shortcut, telegram, push, family
from app.api.websocket_agents import router as websocket_agents_router
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
api_router.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
api_router.include_router(costs.router, prefix="/costs", tags=["costs"])
api_router.include_router(health.router, tags=["health"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(ultron.router, prefix="/ultron", tags=["ultron"])
api_router.include_router(mcp.router, tags=["mcp"])
api_router.include_router(autonomy.router, prefix="/autonomy", tags=["autonomy"])
api_router.include_router(shortcut.router, prefix="/shortcut", tags=["shortcut"])
api_router.include_router(telegram.router, prefix="/v1/telegram", tags=["telegram"])
api_router.include_router(websocket_agents_router, tags=["websocket"])
api_router.include_router(push.router, prefix="/push", tags=["push"])
api_router.include_router(family.router, prefix="/family", tags=["family"])
