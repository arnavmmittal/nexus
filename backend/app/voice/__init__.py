"""Voice module for Nexus - ElevenLabs TTS and speech-to-text integration."""

from app.voice.elevenlabs import ElevenLabsClient
from app.voice.router import router as voice_router

__all__ = ["ElevenLabsClient", "voice_router"]
