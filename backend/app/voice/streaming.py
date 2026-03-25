"""Streaming TTS Processor for Nexus.

This module provides low-latency streaming TTS by sending text to ElevenLabs
as sentences are completed, rather than waiting for the full AI response.

Key features:
- Buffers text until sentence boundaries (. ! ? or newline)
- Sends complete sentences to ElevenLabs for synthesis
- Yields audio chunks as they arrive
- Significantly reduces perceived latency
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional, List, Callable, Awaitable

import httpx

from app.core.config import settings
from app.voice.elevenlabs import VoiceSettings

logger = logging.getLogger(__name__)


@dataclass
class StreamingTTSConfig:
    """Configuration for streaming TTS."""

    # Sentence boundary patterns
    sentence_endings: tuple = (".", "!", "?")
    # Also treat double newlines as sentence boundaries
    paragraph_break: str = "\n\n"
    # Minimum characters before sending (avoid sending tiny fragments)
    min_chunk_size: int = 10
    # Maximum characters to buffer before forcing a send
    max_buffer_size: int = 500
    # Timeout for waiting for more text (seconds)
    flush_timeout: float = 0.5
    # ElevenLabs API settings
    model_id: str = "eleven_turbo_v2"
    chunk_size: int = 1024


@dataclass
class SentenceBuffer:
    """Buffer for accumulating text until sentence boundaries."""

    text: str = ""
    sentences: List[str] = field(default_factory=list)

    def add_text(self, text: str, config: StreamingTTSConfig) -> List[str]:
        """Add text to buffer and return any complete sentences.

        Args:
            text: Text chunk to add
            config: Streaming configuration

        Returns:
            List of complete sentences ready for TTS
        """
        self.text += text
        ready_sentences = []

        # Check for paragraph breaks first
        while config.paragraph_break in self.text:
            parts = self.text.split(config.paragraph_break, 1)
            if parts[0].strip():
                ready_sentences.append(parts[0].strip())
            self.text = parts[1] if len(parts) > 1 else ""

        # Check for sentence endings
        # Use regex to find sentence boundaries while preserving the punctuation
        pattern = r'([^.!?\n]+[.!?]+\s*)'

        while True:
            match = re.match(pattern, self.text)
            if match:
                sentence = match.group(1).strip()
                if len(sentence) >= config.min_chunk_size:
                    ready_sentences.append(sentence)
                    self.text = self.text[match.end():]
                else:
                    # Sentence too short, keep buffering
                    break
            else:
                break

        # Force flush if buffer is too large
        if len(self.text) >= config.max_buffer_size:
            # Find the last space to avoid cutting words
            last_space = self.text.rfind(" ", 0, config.max_buffer_size)
            if last_space > config.min_chunk_size:
                ready_sentences.append(self.text[:last_space].strip())
                self.text = self.text[last_space:].strip()
            else:
                # No good break point, send the whole buffer
                ready_sentences.append(self.text.strip())
                self.text = ""

        return ready_sentences

    def flush(self) -> Optional[str]:
        """Flush any remaining text in the buffer.

        Returns:
            Remaining text or None if empty
        """
        remaining = self.text.strip()
        self.text = ""
        return remaining if remaining else None


class StreamingTTSProcessor:
    """Process streaming text from Claude and convert to streaming audio.

    This class buffers incoming text until sentence boundaries, then sends
    complete sentences to ElevenLabs for synthesis, yielding audio chunks
    as they arrive.

    Usage:
        processor = StreamingTTSProcessor(voice_id="JBFqnCBsd6RMkjVDRZzb")

        async def text_generator():
            yield "Hello, "
            yield "how are you today? "
            yield "I hope you're doing well."

        async for audio_chunk in processor.process_stream(text_generator()):
            # Handle audio chunk
            pass
    """

    BASE_URL = "https://api.elevenlabs.io/v1"

    def __init__(
        self,
        voice_id: str,
        voice_settings: Optional[VoiceSettings] = None,
        config: Optional[StreamingTTSConfig] = None,
        api_key: Optional[str] = None,
    ):
        """Initialize streaming TTS processor.

        Args:
            voice_id: ElevenLabs voice ID
            voice_settings: Voice settings for synthesis
            config: Streaming configuration
            api_key: ElevenLabs API key (falls back to settings)
        """
        self.voice_id = voice_id
        self.voice_settings = voice_settings or VoiceSettings()
        self.config = config or StreamingTTSConfig()
        self.api_key = api_key or settings.elevenlabs_api_key

        if not self.api_key:
            raise ValueError(
                "ElevenLabs API key not configured. "
                "Set ELEVENLABS_API_KEY environment variable."
            )

        # Statistics for debugging
        self.stats = {
            "sentences_processed": 0,
            "total_text_length": 0,
            "audio_chunks_yielded": 0,
        }

    def _get_headers(self) -> dict[str, str]:
        """Get HTTP headers for API requests."""
        return {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }

    def _build_request_body(self, text: str) -> dict:
        """Build request body for TTS synthesis."""
        return {
            "text": text,
            "model_id": self.config.model_id,
            "voice_settings": {
                "stability": self.voice_settings.stability,
                "similarity_boost": self.voice_settings.similarity_boost,
                "style": self.voice_settings.style,
                "use_speaker_boost": self.voice_settings.use_speaker_boost,
            },
        }

    async def _synthesize_sentence(
        self,
        text: str,
        client: httpx.AsyncClient,
    ) -> AsyncGenerator[bytes, None]:
        """Synthesize a single sentence and yield audio chunks.

        Args:
            text: Text to synthesize
            client: HTTP client to use

        Yields:
            Audio chunks as bytes
        """
        url = f"{self.BASE_URL}/text-to-speech/{self.voice_id}/stream"
        body = self._build_request_body(text)

        logger.debug(f"Synthesizing sentence: '{text[:50]}...'")
        self.stats["sentences_processed"] += 1
        self.stats["total_text_length"] += len(text)

        try:
            async with client.stream(
                "POST",
                url,
                headers=self._get_headers(),
                json=body,
            ) as response:
                response.raise_for_status()

                async for chunk in response.aiter_bytes(self.config.chunk_size):
                    self.stats["audio_chunks_yielded"] += 1
                    yield chunk

        except httpx.HTTPStatusError as e:
            logger.error(f"ElevenLabs API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error synthesizing sentence: {e}")
            raise

    async def process_stream(
        self,
        text_generator: AsyncGenerator[str, None],
    ) -> AsyncGenerator[bytes, None]:
        """Process a stream of text chunks and yield audio as it's generated.

        This method:
        1. Receives text chunks from the generator
        2. Buffers them until sentence boundaries
        3. Sends complete sentences to ElevenLabs
        4. Yields audio chunks as they arrive

        Args:
            text_generator: Async generator yielding text chunks

        Yields:
            Audio chunks as bytes (MP3 format)
        """
        buffer = SentenceBuffer()

        # Queue for sentences ready to be synthesized
        sentence_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()

        # Track if text generation is complete
        text_complete = asyncio.Event()

        # Error handling
        synthesis_error: Optional[Exception] = None

        async def collect_text():
            """Collect text chunks and queue complete sentences."""
            nonlocal synthesis_error
            try:
                async for text_chunk in text_generator:
                    sentences = buffer.add_text(text_chunk, self.config)
                    for sentence in sentences:
                        await sentence_queue.put(sentence)

                # Flush any remaining text
                remaining = buffer.flush()
                if remaining:
                    await sentence_queue.put(remaining)

            except Exception as e:
                logger.error(f"Error collecting text: {e}")
                synthesis_error = e
            finally:
                # Signal that text collection is complete
                text_complete.set()
                await sentence_queue.put(None)  # Sentinel to end processing

        async def synthesize_sentences(client: httpx.AsyncClient):
            """Synthesize sentences from the queue and yield audio."""
            nonlocal synthesis_error

            while True:
                # Wait for a sentence or timeout
                try:
                    sentence = await asyncio.wait_for(
                        sentence_queue.get(),
                        timeout=self.config.flush_timeout if text_complete.is_set() else 10.0
                    )
                except asyncio.TimeoutError:
                    # Check if we should flush the buffer
                    if text_complete.is_set():
                        break
                    continue

                if sentence is None:
                    # End of stream
                    break

                try:
                    async for audio_chunk in self._synthesize_sentence(sentence, client):
                        yield audio_chunk
                except Exception as e:
                    logger.error(f"Synthesis error for sentence: {e}")
                    synthesis_error = e
                    break

        # Run text collection and synthesis concurrently
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Start text collection in background
            collect_task = asyncio.create_task(collect_text())

            try:
                # Yield audio as it's synthesized
                async for audio_chunk in synthesize_sentences(client):
                    yield audio_chunk
            finally:
                # Ensure collection task completes
                await collect_task

        # Log statistics
        logger.debug(
            f"Streaming TTS complete: {self.stats['sentences_processed']} sentences, "
            f"{self.stats['total_text_length']} chars, "
            f"{self.stats['audio_chunks_yielded']} audio chunks"
        )

        if synthesis_error:
            raise synthesis_error

    async def process_text(self, text: str) -> AsyncGenerator[bytes, None]:
        """Process a complete text string as a stream.

        Convenience method that wraps a string in an async generator.

        Args:
            text: Complete text to process

        Yields:
            Audio chunks as bytes
        """
        async def text_gen():
            yield text

        async for chunk in self.process_stream(text_gen()):
            yield chunk


class StreamingTTSManager:
    """Manager for creating and managing streaming TTS processors.

    This provides a higher-level interface for integrating streaming TTS
    with the AI engine's streaming chat responses.
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the manager.

        Args:
            api_key: ElevenLabs API key (falls back to settings)
        """
        self.api_key = api_key or settings.elevenlabs_api_key

    def create_processor(
        self,
        voice_id: str,
        voice_settings: Optional[VoiceSettings] = None,
        config: Optional[StreamingTTSConfig] = None,
    ) -> StreamingTTSProcessor:
        """Create a new streaming TTS processor.

        Args:
            voice_id: ElevenLabs voice ID
            voice_settings: Voice settings for synthesis
            config: Streaming configuration

        Returns:
            StreamingTTSProcessor instance
        """
        return StreamingTTSProcessor(
            voice_id=voice_id,
            voice_settings=voice_settings,
            config=config,
            api_key=self.api_key,
        )

    async def stream_ai_response_to_audio(
        self,
        text_generator: AsyncGenerator[str, None],
        voice_id: str,
        voice_settings: Optional[VoiceSettings] = None,
        config: Optional[StreamingTTSConfig] = None,
        on_text_chunk: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> AsyncGenerator[bytes, None]:
        """Stream AI text response directly to audio output.

        This is the main integration point with AIEngine.stream_chat().
        It captures text chunks, optionally processes them, and yields audio.

        Args:
            text_generator: Async generator from AIEngine.stream_chat()
            voice_id: ElevenLabs voice ID
            voice_settings: Voice settings
            config: Streaming configuration
            on_text_chunk: Optional callback for each text chunk (for logging/display)

        Yields:
            Audio chunks as bytes
        """
        accumulated_text = []

        async def wrapped_generator():
            async for chunk in text_generator:
                accumulated_text.append(chunk)
                if on_text_chunk:
                    await on_text_chunk(chunk)
                yield chunk

        processor = self.create_processor(
            voice_id=voice_id,
            voice_settings=voice_settings,
            config=config,
        )

        async for audio_chunk in processor.process_stream(wrapped_generator()):
            yield audio_chunk

        # Return the full text via the accumulated_text list
        # (accessible after generator completes)

    def get_full_text(self, accumulated_text: List[str]) -> str:
        """Get the full accumulated text from streaming.

        Args:
            accumulated_text: List of text chunks accumulated during streaming

        Returns:
            Complete text string
        """
        return "".join(accumulated_text)


# Singleton instance
_streaming_manager: Optional[StreamingTTSManager] = None


def get_streaming_tts_manager() -> StreamingTTSManager:
    """Get or create the streaming TTS manager singleton.

    Returns:
        StreamingTTSManager instance
    """
    global _streaming_manager
    if _streaming_manager is None:
        _streaming_manager = StreamingTTSManager()
    return _streaming_manager
