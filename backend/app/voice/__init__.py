"""Voice module for Nexus - ElevenLabs TTS and speech-to-text integration."""

from app.voice.elevenlabs import ElevenLabsClient
from app.voice.router import router as voice_router
from app.voice.streaming import (
    StreamingTTSProcessor,
    StreamingTTSConfig,
    StreamingTTSManager,
    get_streaming_tts_manager,
)

__all__ = [
    "ElevenLabsClient",
    "voice_router",
    "StreamingTTSProcessor",
    "StreamingTTSConfig",
    "StreamingTTSManager",
    "get_streaming_tts_manager",
]
