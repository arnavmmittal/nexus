"""Voice API endpoints for Nexus.

Provides text-to-speech synthesis and voice-to-voice chat capabilities
using ElevenLabs for TTS and Claude for AI processing.
"""

import logging
from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.engine import AIEngine
from app.core.database import get_db
from app.memory.vector_store import get_vector_store
from app.voice.elevenlabs import (
    ElevenLabsClient,
    VoiceSettings,
    get_elevenlabs_client,
)
from app.voice.transcription import get_whisper_client

router = APIRouter()
logger = logging.getLogger(__name__)

# Placeholder user ID (will be replaced with auth later)
DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_USER_NAME = "User"


# Request/Response schemas
class SynthesizeRequest(BaseModel):
    """Request body for text-to-speech synthesis."""

    text: str = Field(..., min_length=1, max_length=5000, description="Text to synthesize")
    voice_id: Optional[str] = Field(None, description="Override voice ID")
    stability: Optional[float] = Field(None, ge=0.0, le=1.0, description="Voice stability")
    similarity_boost: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Voice similarity boost"
    )
    style: Optional[float] = Field(None, ge=0.0, le=1.0, description="Voice style")


class VoiceChatRequest(BaseModel):
    """Request body for voice-to-voice chat."""

    text: str = Field(..., min_length=1, max_length=10000, description="User message text")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for continuity")
    voice_id: Optional[str] = Field(None, description="Override voice ID for response")


class VoiceChatResponse(BaseModel):
    """Metadata response for voice chat (audio streamed separately)."""

    conversation_id: str
    text_response: str


class TranscriptionResponse(BaseModel):
    """Response body for transcription."""

    text: str
    language: Optional[str] = None


@router.post("/synthesize")
async def synthesize_speech(
    request: SynthesizeRequest,
    client: Annotated[ElevenLabsClient, Depends(get_elevenlabs_client)],
) -> StreamingResponse:
    """
    Synthesize text to speech using ElevenLabs.

    Returns an audio stream (MP3 format) that can be played directly
    in the browser or saved to a file.

    Args:
        request: Synthesis request with text and optional voice settings
        client: ElevenLabs client

    Returns:
        StreamingResponse with audio/mpeg content type
    """
    try:
        # Build voice settings if any overrides provided
        voice_settings = None
        if any([request.stability, request.similarity_boost, request.style]):
            voice_settings = VoiceSettings(
                stability=request.stability or 0.75,
                similarity_boost=request.similarity_boost or 0.85,
                style=request.style or 0.2,
            )

        logger.info(f"Synthesizing speech: '{request.text[:50]}...'")

        # Stream audio response
        async def generate():
            async for chunk in client.synthesize_stream(
                text=request.text,
                voice_id=request.voice_id,
                voice_settings=voice_settings,
            ):
                yield chunk

        return StreamingResponse(
            generate(),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "inline",
                "Cache-Control": "no-cache",
            },
        )

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise HTTPException(
            status_code=503,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Synthesis error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to synthesize speech: {str(e)}",
        )


@router.post("/chat")
async def voice_chat(
    request: VoiceChatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    tts_client: Annotated[ElevenLabsClient, Depends(get_elevenlabs_client)],
) -> StreamingResponse:
    """
    Voice-to-voice chat: receive text, process with Claude, return audio.

    This endpoint:
    1. Receives text input (transcribed on frontend or via /transcribe)
    2. Processes through Claude with full context assembly
    3. Streams the response to ElevenLabs for synthesis
    4. Returns audio stream

    Args:
        request: Voice chat request with message text
        db: Database session
        tts_client: ElevenLabs client

    Returns:
        StreamingResponse with audio/mpeg content type
    """
    try:
        # Initialize AI engine
        vector_store = get_vector_store()
        engine = AIEngine(db, vector_store)

        # Get AI response
        logger.info(f"Voice chat request: '{request.text[:50]}...'")

        response_text = await engine.chat(
            message=request.text,
            user_id=DEFAULT_USER_ID,
            conversation_id=request.conversation_id,
            user_name=DEFAULT_USER_NAME,
        )

        logger.info(f"AI response: '{response_text[:50]}...'")

        # Stream audio response
        async def generate():
            async for chunk in tts_client.synthesize_stream(
                text=response_text,
                voice_id=request.voice_id,
            ):
                yield chunk

        return StreamingResponse(
            generate(),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "inline",
                "Cache-Control": "no-cache",
                # Include text response in header for frontend to display
                "X-Text-Response": response_text[:500].replace("\n", " "),
                "X-Conversation-Id": request.conversation_id or "new",
            },
        )

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise HTTPException(
            status_code=503,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Voice chat error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process voice chat: {str(e)}",
        )


@router.post("/chat/text", response_model=VoiceChatResponse)
async def voice_chat_text_response(
    request: VoiceChatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VoiceChatResponse:
    """
    Voice chat with text response only (no audio synthesis).

    Useful when you want to get the AI response text separately
    and handle TTS on the frontend or skip it entirely.

    Args:
        request: Voice chat request with message text
        db: Database session

    Returns:
        VoiceChatResponse with text response
    """
    try:
        # Initialize AI engine
        vector_store = get_vector_store()
        engine = AIEngine(db, vector_store)

        # Get AI response
        response_text = await engine.chat(
            message=request.text,
            user_id=DEFAULT_USER_ID,
            conversation_id=request.conversation_id,
            user_name=DEFAULT_USER_NAME,
        )

        return VoiceChatResponse(
            conversation_id=request.conversation_id or "new",
            text_response=response_text,
        )

    except Exception as e:
        logger.error(f"Voice chat error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process chat: {str(e)}",
        )


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    audio: UploadFile = File(..., description="Audio file to transcribe"),
    language: Optional[str] = None,
):
    """
    Transcribe audio to text using Whisper API.

    Note: For most use cases, consider using the browser's Web Speech API
    (free, lower latency). Use this endpoint for better accuracy or
    when browser API is unavailable.

    Supported formats: mp3, mp4, mpeg, mpga, m4a, wav, webm

    Args:
        audio: Audio file upload
        language: Optional ISO 639-1 language code (e.g., 'en')

    Returns:
        TranscriptionResponse with transcribed text
    """
    try:
        client = get_whisper_client()

        # Read audio data
        audio_data = await audio.read()

        # Get filename for format detection
        filename = audio.filename or "audio.webm"

        logger.info(f"Transcribing audio: {filename} ({len(audio_data)} bytes)")

        # Transcribe
        text = await client.transcribe(
            audio_data=audio_data,
            filename=filename,
            language=language,
        )

        return TranscriptionResponse(
            text=text,
            language=language,
        )

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise HTTPException(
            status_code=503,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to transcribe audio: {str(e)}",
        )


@router.get("/voices")
async def list_voices(
    client: Annotated[ElevenLabsClient, Depends(get_elevenlabs_client)],
):
    """
    List available ElevenLabs voices.

    Returns all voices available to your account, including
    premade voices and any custom voice clones.

    Args:
        client: ElevenLabs client

    Returns:
        List of voice objects with id, name, and metadata
    """
    try:
        voices = await client.get_voices()
        return {"voices": voices}

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise HTTPException(
            status_code=503,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error fetching voices: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch voices: {str(e)}",
        )


@router.get("/status")
async def voice_status(
    tts_client: Annotated[ElevenLabsClient, Depends(get_elevenlabs_client)],
):
    """
    Get voice service status and quota information.

    Returns ElevenLabs subscription info including
    character quota and usage.

    Args:
        tts_client: ElevenLabs client

    Returns:
        Status information and quota details
    """
    try:
        user_info = await tts_client.get_user_info()

        return {
            "status": "operational",
            "tts_provider": "elevenlabs",
            "model": tts_client.DEFAULT_MODEL,
            "default_voice": tts_client.voice_id,
            "subscription": {
                "tier": user_info.get("tier", "unknown"),
                "character_count": user_info.get("character_count", 0),
                "character_limit": user_info.get("character_limit", 0),
            },
        }

    except ValueError as e:
        return {
            "status": "not_configured",
            "error": str(e),
        }
    except Exception as e:
        logger.error(f"Error fetching status: {e}")
        return {
            "status": "error",
            "error": str(e),
        }
