"""Speech-to-Text transcription support for Nexus.

This module provides transcription capabilities using:
1. OpenAI Whisper API (more accurate, paid)
2. Web Speech API guidance (free, browser-based)

The Web Speech API is typically handled on the frontend, so this module
primarily supports Whisper API for server-side transcription.
"""

import logging
from io import BytesIO
from typing import BinaryIO, Optional, Union

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class WhisperTranscriptionClient:
    """OpenAI Whisper API client for speech-to-text transcription.

    Provides server-side transcription using OpenAI's Whisper model.
    Cost: ~$0.006 per minute of audio.

    Note: For most use cases, consider using the browser's Web Speech API
    (free, lower latency) and only fall back to Whisper for better accuracy.
    """

    BASE_URL = "https://api.openai.com/v1/audio/transcriptions"
    DEFAULT_MODEL = "whisper-1"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Whisper client.

        Args:
            api_key: OpenAI API key. Falls back to settings if not provided.
        """
        self.api_key = api_key or settings.openai_api_key

        if not self.api_key:
            logger.warning(
                "OpenAI API key not configured. "
                "Whisper transcription will fail until OPENAI_API_KEY is set."
            )

    async def transcribe(
        self,
        audio_data: Union[bytes, BinaryIO],
        filename: str = "audio.webm",
        language: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> str:
        """Transcribe audio to text using Whisper.

        Args:
            audio_data: Audio data as bytes or file-like object
            filename: Filename with extension (helps with format detection)
            language: ISO 639-1 language code (e.g., 'en', 'es')
            prompt: Optional prompt to guide transcription style

        Returns:
            Transcribed text

        Raises:
            httpx.HTTPStatusError: If API request fails
            ValueError: If API key is not configured
        """
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not configured. "
                "Set OPENAI_API_KEY environment variable."
            )

        # Prepare file data
        if isinstance(audio_data, bytes):
            file_data = BytesIO(audio_data)
        else:
            file_data = audio_data

        # Build multipart form data
        files = {
            "file": (filename, file_data),
        }

        data = {
            "model": self.DEFAULT_MODEL,
        }

        if language:
            data["language"] = language

        if prompt:
            data["prompt"] = prompt

        logger.debug(f"Transcribing audio: {filename}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                self.BASE_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                files=files,
                data=data,
            )
            response.raise_for_status()
            result = response.json()

        transcript = result.get("text", "")
        logger.debug(f"Transcription complete: '{transcript[:50]}...'")

        return transcript


# Guidance for frontend Web Speech API usage
WEB_SPEECH_API_GUIDE = """
# Web Speech API Usage (Frontend)

The Web Speech API provides free, browser-based speech recognition.
Implement this on the frontend for low-latency transcription:

```typescript
// Initialize speech recognition
const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
recognition.continuous = false;
recognition.interimResults = true;
recognition.lang = 'en-US';

// Event handlers
recognition.onresult = (event) => {
  const transcript = Array.from(event.results)
    .map(result => result[0].transcript)
    .join('');

  if (event.results[0].isFinal) {
    // Final result - send to backend
    sendToBackend(transcript);
  } else {
    // Interim result - update UI
    updateUI(transcript);
  }
};

recognition.onerror = (event) => {
  console.error('Speech recognition error:', event.error);
};

// Start listening
recognition.start();

// Stop listening (on user action or timeout)
recognition.stop();
```

Pros:
- Free (no API costs)
- Low latency (runs locally)
- Good for most use cases

Cons:
- Less accurate in noisy environments
- May not work in all browsers
- Accents/languages may vary in quality

For better accuracy, use Whisper API (server-side) as a fallback.
"""


# Singleton instance
_whisper_client: Optional[WhisperTranscriptionClient] = None


def get_whisper_client() -> WhisperTranscriptionClient:
    """Get or create Whisper client singleton.

    Returns:
        WhisperTranscriptionClient instance
    """
    global _whisper_client
    if _whisper_client is None:
        _whisper_client = WhisperTranscriptionClient()
    return _whisper_client
