"""ElevenLabs Text-to-Speech Client for Nexus.

This module provides async streaming TTS synthesis using ElevenLabs API.
Uses eleven_turbo_v2 model for low latency, JARVIS-like voice responses.
"""

import logging
from dataclasses import dataclass
from typing import AsyncIterator, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class VoiceSettings:
    """Voice settings for ElevenLabs TTS synthesis."""

    stability: float = 0.75
    similarity_boost: float = 0.85
    style: float = 0.2
    use_speaker_boost: bool = True


class ElevenLabsClient:
    """Async ElevenLabs TTS client with streaming support.

    Provides text-to-speech synthesis using ElevenLabs API with
    support for streaming audio output and customizable voice settings.

    Attributes:
        BASE_URL: ElevenLabs API base URL
        DEFAULT_MODEL: Default model (eleven_turbo_v2 for low latency)
        DEFAULT_VOICE_ID: Default voice ID (Adam - professional, JARVIS-like)
    """

    BASE_URL = "https://api.elevenlabs.io/v1"
    DEFAULT_MODEL = "eleven_turbo_v2"
    # George voice - British, warm, captivating - perfect for JARVIS-like assistant
    DEFAULT_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"

    def __init__(
        self,
        api_key: Optional[str] = None,
        voice_id: Optional[str] = None,
        voice_settings: Optional[VoiceSettings] = None,
    ):
        """Initialize ElevenLabs client.

        Args:
            api_key: ElevenLabs API key. Falls back to settings if not provided.
            voice_id: Voice ID to use. Falls back to settings or default.
            voice_settings: Voice settings for synthesis.
        """
        self.api_key = api_key or settings.elevenlabs_api_key
        self.voice_id = voice_id or settings.elevenlabs_voice_id or self.DEFAULT_VOICE_ID
        self.voice_settings = voice_settings or VoiceSettings()

        if not self.api_key:
            logger.warning(
                "ElevenLabs API key not configured. "
                "TTS will fail until ELEVENLABS_API_KEY is set."
            )

    def _get_headers(self) -> dict[str, str]:
        """Get HTTP headers for API requests."""
        return {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }

    def _build_request_body(
        self,
        text: str,
        model_id: Optional[str] = None,
        voice_settings: Optional[VoiceSettings] = None,
    ) -> dict:
        """Build request body for TTS synthesis.

        Args:
            text: Text to synthesize
            model_id: Model ID to use
            voice_settings: Voice settings override

        Returns:
            Request body dictionary
        """
        settings_to_use = voice_settings or self.voice_settings
        return {
            "text": text,
            "model_id": model_id or self.DEFAULT_MODEL,
            "voice_settings": {
                "stability": settings_to_use.stability,
                "similarity_boost": settings_to_use.similarity_boost,
                "style": settings_to_use.style,
                "use_speaker_boost": settings_to_use.use_speaker_boost,
            },
        }

    async def synthesize_stream(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None,
        voice_settings: Optional[VoiceSettings] = None,
        chunk_size: int = 1024,
    ) -> AsyncIterator[bytes]:
        """Stream audio chunks as they're generated.

        Args:
            text: Text to synthesize
            voice_id: Override voice ID
            model_id: Override model ID
            voice_settings: Override voice settings
            chunk_size: Size of audio chunks to yield

        Yields:
            Audio chunks as bytes (MP3 format)

        Raises:
            httpx.HTTPStatusError: If API request fails
            ValueError: If API key is not configured
        """
        if not self.api_key:
            raise ValueError(
                "ElevenLabs API key not configured. "
                "Set ELEVENLABS_API_KEY environment variable."
            )

        voice = voice_id or self.voice_id
        url = f"{self.BASE_URL}/text-to-speech/{voice}/stream"

        body = self._build_request_body(text, model_id, voice_settings)

        logger.debug(f"Synthesizing speech: '{text[:50]}...' with voice {voice}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                url,
                headers=self._get_headers(),
                json=body,
            ) as response:
                response.raise_for_status()

                async for chunk in response.aiter_bytes(chunk_size):
                    yield chunk

        logger.debug("Speech synthesis completed")

    async def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None,
        voice_settings: Optional[VoiceSettings] = None,
    ) -> bytes:
        """Synthesize speech and return complete audio.

        Args:
            text: Text to synthesize
            voice_id: Override voice ID
            model_id: Override model ID
            voice_settings: Override voice settings

        Returns:
            Complete audio data as bytes (MP3 format)

        Raises:
            httpx.HTTPStatusError: If API request fails
            ValueError: If API key is not configured
        """
        chunks = []
        async for chunk in self.synthesize_stream(
            text=text,
            voice_id=voice_id,
            model_id=model_id,
            voice_settings=voice_settings,
        ):
            chunks.append(chunk)

        return b"".join(chunks)

    async def get_voices(self) -> List[dict]:
        """Get available voices from ElevenLabs.

        Returns:
            List of voice dictionaries with id, name, etc.

        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        if not self.api_key:
            raise ValueError("ElevenLabs API key not configured.")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.BASE_URL}/voices",
                headers={"xi-api-key": self.api_key},
            )
            response.raise_for_status()
            data = response.json()

        return data.get("voices", [])

    async def get_user_info(self) -> dict:
        """Get user subscription info (quota, characters remaining, etc.).

        Returns:
            User info dictionary

        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        if not self.api_key:
            raise ValueError("ElevenLabs API key not configured.")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.BASE_URL}/user/subscription",
                headers={"xi-api-key": self.api_key},
            )
            response.raise_for_status()

        return response.json()


# Singleton instance for dependency injection
_elevenlabs_client: Optional[ElevenLabsClient] = None


def get_elevenlabs_client() -> ElevenLabsClient:
    """Get or create ElevenLabs client singleton.

    Returns:
        ElevenLabsClient instance
    """
    global _elevenlabs_client
    if _elevenlabs_client is None:
        _elevenlabs_client = ElevenLabsClient()
    return _elevenlabs_client
