"""iOS Shortcut API endpoints for Nexus.

Enables "Hey Siri, ask Jarvis..." functionality with optimized
voice responses and quick actions for iOS Shortcuts integration.

Features:
- Optimized voice endpoint with pre-generated audio
- Quick action endpoints for common tasks
- Response formatting for speakable output
- Audio caching with TTL
- Simple API key authentication for Shortcuts
- Latency optimization with fast model tier
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.engine import AIEngine
from app.ai.routing import ModelTier, get_router, AVAILABLE_MODELS
from app.core.config import settings
from app.core.database import get_db
from app.memory.vector_store import get_vector_store
from app.voice.elevenlabs import ElevenLabsClient, VoiceSettings, get_elevenlabs_client

# Import integrations for quick actions
try:
    from app.integrations.smart_home import (
        control_lights,
        activate_scene,
        get_home_status,
        set_thermostat,
    )
    SMART_HOME_AVAILABLE = True
except ImportError:
    SMART_HOME_AVAILABLE = False

try:
    from app.integrations.google_calendar import GoogleCalendarIntegration
    CALENDAR_AVAILABLE = True
except ImportError:
    CALENDAR_AVAILABLE = False

try:
    from app.scheduler.tools import schedule_action
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False

router = APIRouter()
logger = logging.getLogger(__name__)

# Default user ID for shortcuts (will be replaced with proper auth)
DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_USER_NAME = "Arnav Mittal"

# Voice settings for Jarvis (Shortcut default)
JARVIS_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # George - British, warm, JARVIS-like
JARVIS_VOICE_SETTINGS = VoiceSettings(
    stability=0.7,
    similarity_boost=0.8,
    style=0.3,
)

# Audio cache configuration
AUDIO_CACHE_DIR = Path("./data/audio_cache")
AUDIO_CACHE_TTL_SECONDS = 300  # 5 minutes

# Ensure cache directory exists
AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# CONTEXT LEVEL ENUM
# =============================================================================


class ContextLevel(str, Enum):
    """Response context level for voice output."""
    BRIEF = "brief"  # Under 50 words, single sentence when possible
    NORMAL = "normal"  # 50-100 words, natural conversation
    DETAILED = "detailed"  # No limit, full response


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================


class VoiceRequest(BaseModel):
    """Request for voice-optimized AI response."""
    text: str = Field(..., min_length=1, max_length=1000, description="User's voice query")
    user_id: Optional[str] = Field(None, description="User identifier")
    voice_response: bool = Field(True, description="Generate audio response")
    context: ContextLevel = Field(ContextLevel.BRIEF, description="Response detail level")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for context")


class ActionTaken(BaseModel):
    """Record of an action taken by the AI."""
    action_type: str
    description: str
    success: bool
    details: Optional[Dict[str, Any]] = None


class VoiceResponse(BaseModel):
    """Response from voice endpoint."""
    text: str = Field(..., description="Full response text")
    speech: str = Field(..., description="Optimized text for TTS")
    audio_url: Optional[str] = Field(None, description="URL to pre-generated audio")
    actions_taken: List[ActionTaken] = Field(default_factory=list)
    latency_ms: int = Field(..., description="Total processing latency")
    conversation_id: Optional[str] = None


class QuickRemindRequest(BaseModel):
    """Request for quick reminder creation."""
    text: str = Field(..., description="Reminder text")
    when: str = Field(..., description="When to remind (natural language)")


class QuickScheduleRequest(BaseModel):
    """Request for quick event scheduling."""
    title: str = Field(..., description="Event title")
    when: str = Field(..., description="When (natural language)")
    duration_minutes: int = Field(30, description="Event duration")


class QuickStatusResponse(BaseModel):
    """Quick status response."""
    weather: Optional[Dict[str, Any]] = None
    calendar: Optional[Dict[str, Any]] = None
    home: Optional[Dict[str, Any]] = None
    time: str
    greeting: str


class HomeActionRequest(BaseModel):
    """Request for home automation action."""
    room: Optional[str] = Field(None, description="Target room")
    brightness: Optional[int] = Field(None, ge=0, le=100, description="Light brightness")
    temperature: Optional[float] = Field(None, description="Thermostat temperature")


# =============================================================================
# RESPONSE FORMATTER
# =============================================================================


class ShortcutResponseFormatter:
    """Formats AI responses for voice/shortcut output.

    Creates concise, speakable responses optimized for Siri/voice assistants.
    Strips markdown, avoids bullet points, and keeps it conversational.
    """

    # Maximum words for each context level
    WORD_LIMITS = {
        ContextLevel.BRIEF: 50,
        ContextLevel.NORMAL: 100,
        ContextLevel.DETAILED: 500,
    }

    # Patterns to remove for voice output
    MARKDOWN_PATTERNS = [
        (r'\*\*([^*]+)\*\*', r'\1'),  # Bold
        (r'\*([^*]+)\*', r'\1'),  # Italic
        (r'`([^`]+)`', r'\1'),  # Code
        (r'```[\w]*\n?([^`]+)```', r'\1'),  # Code blocks
        (r'\[([^\]]+)\]\([^)]+\)', r'\1'),  # Links
        (r'^#{1,6}\s+', ''),  # Headers
        (r'^\s*[-*+]\s+', ''),  # Bullet points
        (r'^\s*\d+\.\s+', ''),  # Numbered lists
        (r'\n{2,}', '. '),  # Multiple newlines to period
        (r'\n', ' '),  # Single newlines to space
    ]

    # Conversational replacements
    CONVERSATIONAL_REPLACEMENTS = [
        (r'\bYou have (\d+) meetings today', r'You have \1 meetings today'),
        (r'(\d{1,2}):(\d{2})\s*(AM|PM)', lambda m: f"{int(m.group(1))} {m.group(3)}"),
        (r'\bapproximately\b', 'about'),
        (r'\badditionally\b', 'also'),
        (r'\bfurthermore\b', 'also'),
        (r'\bhowever\b', 'but'),
        (r'\btherefore\b', 'so'),
    ]

    @classmethod
    def format_for_speech(
        cls,
        text: str,
        context: ContextLevel = ContextLevel.BRIEF,
    ) -> str:
        """Format text for TTS output.

        Args:
            text: Raw AI response text
            context: Desired context level

        Returns:
            Cleaned, speakable text
        """
        # Strip markdown
        result = text
        for pattern, replacement in cls.MARKDOWN_PATTERNS:
            result = re.sub(pattern, replacement, result, flags=re.MULTILINE)

        # Apply conversational replacements
        for pattern, replacement in cls.CONVERSATIONAL_REPLACEMENTS:
            if callable(replacement):
                result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
            else:
                result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        # Clean up whitespace
        result = re.sub(r'\s+', ' ', result).strip()

        # Remove multiple periods
        result = re.sub(r'\.{2,}', '.', result)

        # Ensure proper sentence endings
        if result and not result[-1] in '.!?':
            result += '.'

        # Apply word limit
        word_limit = cls.WORD_LIMITS.get(context, 100)
        words = result.split()
        if len(words) > word_limit:
            result = ' '.join(words[:word_limit])
            # Find last sentence boundary
            last_period = result.rfind('.')
            last_question = result.rfind('?')
            last_exclaim = result.rfind('!')
            last_boundary = max(last_period, last_question, last_exclaim)
            if last_boundary > len(result) // 2:
                result = result[:last_boundary + 1]
            else:
                result += '...'

        return result

    @classmethod
    def format_calendar_response(
        cls,
        events: List[Dict[str, Any]],
        context: ContextLevel = ContextLevel.BRIEF,
    ) -> str:
        """Format calendar events for speech.

        Example:
            Input: [{"summary": "Team Standup", "start": "09:00"}, ...]
            Output: "You have 3 meetings today. First is Team Standup at 9 AM..."
        """
        if not events:
            return "You have no meetings scheduled for today."

        count = len(events)
        if context == ContextLevel.BRIEF:
            if count == 1:
                event = events[0]
                time_str = cls._format_time(event.get("start", ""))
                return f"You have one meeting today: {event.get('summary', 'an event')} at {time_str}."
            else:
                return f"You have {count} meetings today."

        # Normal/detailed: list events
        parts = [f"You have {count} {'meeting' if count == 1 else 'meetings'} today."]

        ordinals = ["First", "Second", "Third", "Fourth", "Fifth"]
        for i, event in enumerate(events[:5]):
            ordinal = ordinals[i] if i < len(ordinals) else f"Then"
            time_str = cls._format_time(event.get("start", ""))
            name = event.get("summary", "an event")

            if i == 0:
                parts.append(f"{ordinal} is {name} at {time_str}")
            elif i == len(events) - 1 and i < 5:
                parts.append(f"and {name} at {time_str}")
            else:
                parts.append(f"then {name} at {time_str}")

        if count > 5:
            parts.append(f"plus {count - 5} more")

        return ", ".join(parts) + "."

    @classmethod
    def format_home_status(
        cls,
        status: Dict[str, Any],
        context: ContextLevel = ContextLevel.BRIEF,
    ) -> str:
        """Format home status for speech."""
        parts = []

        # Temperature
        climate = status.get("climate", {})
        if climate.get("current_temp"):
            temp = int(climate["current_temp"])
            parts.append(f"It's {temp} degrees inside")

        # Lights
        lighting = status.get("lighting", {})
        if lighting.get("total_lights"):
            on = lighting.get("lights_on", 0)
            total = lighting["total_lights"]
            if on == 0:
                parts.append("all lights are off")
            elif on == total:
                parts.append("all lights are on")
            else:
                parts.append(f"{on} of {total} lights are on")

        # Security
        security = status.get("security", {})
        if security.get("all_locked"):
            parts.append("all doors are locked")
        elif security.get("locks"):
            unlocked = [l["name"] for l in security["locks"] if not l.get("locked")]
            if unlocked:
                parts.append(f"the {unlocked[0]} is unlocked")

        if not parts:
            return "Everything looks good at home."

        return ", ".join(parts) + "."

    @classmethod
    def _format_time(cls, time_str: str) -> str:
        """Format time string for speech (e.g., "9 AM" instead of "09:00")."""
        if not time_str:
            return "sometime today"

        try:
            # Handle ISO format
            if "T" in time_str:
                dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                hour = dt.hour
                minute = dt.minute
            else:
                # Handle HH:MM format
                parts = time_str.split(":")
                hour = int(parts[0])
                minute = int(parts[1]) if len(parts) > 1 else 0

            period = "AM" if hour < 12 else "PM"
            hour_12 = hour if hour <= 12 else hour - 12
            if hour_12 == 0:
                hour_12 = 12

            if minute == 0:
                return f"{hour_12} {period}"
            else:
                return f"{hour_12}:{minute:02d} {period}"
        except (ValueError, IndexError):
            return time_str


# =============================================================================
# AUDIO CACHE
# =============================================================================


class AudioCache:
    """Simple file-based audio cache with TTL."""

    def __init__(self, cache_dir: Path = AUDIO_CACHE_DIR, ttl_seconds: int = AUDIO_CACHE_TTL_SECONDS):
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self._metadata: Dict[str, Dict[str, Any]] = {}

    def _generate_key(self, text: str, voice_id: str) -> str:
        """Generate cache key from text and voice."""
        content = f"{text}:{voice_id}"
        return hashlib.md5(content.encode()).hexdigest()

    def get_path(self, key: str) -> Path:
        """Get file path for cache key."""
        return self.cache_dir / f"{key}.mp3"

    def get(self, text: str, voice_id: str) -> Optional[Path]:
        """Get cached audio file if exists and not expired."""
        key = self._generate_key(text, voice_id)
        path = self.get_path(key)

        if not path.exists():
            return None

        # Check TTL
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        if datetime.now() - mtime > timedelta(seconds=self.ttl_seconds):
            # Expired, delete
            try:
                path.unlink()
            except OSError:
                pass
            return None

        return path

    async def put(self, text: str, voice_id: str, audio_data: bytes) -> Path:
        """Store audio data in cache."""
        key = self._generate_key(text, voice_id)
        path = self.get_path(key)

        # Write audio file
        path.write_bytes(audio_data)

        return path

    def cleanup_expired(self) -> int:
        """Remove expired cache files. Returns count of removed files."""
        removed = 0
        cutoff = datetime.now() - timedelta(seconds=self.ttl_seconds)

        for path in self.cache_dir.glob("*.mp3"):
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime)
                if mtime < cutoff:
                    path.unlink()
                    removed += 1
            except OSError:
                pass

        return removed


# Global audio cache instance
_audio_cache = AudioCache()


# =============================================================================
# AUTHENTICATION
# =============================================================================


async def verify_shortcut_api_key(
    x_api_key: str = Header(None, alias="X-API-Key"),
    authorization: str = Header(None),
) -> str:
    """Verify API key for Shortcut requests.

    Supports both X-API-Key header and Bearer token auth.
    For simplicity, accepts any non-empty key for now.
    In production, validate against stored device tokens.
    """
    api_key = x_api_key

    # Check Bearer token if no X-API-Key
    if not api_key and authorization:
        if authorization.startswith("Bearer "):
            api_key = authorization[7:]

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Use X-API-Key header or Bearer token.",
        )

    # TODO: In production, validate against database of device tokens
    # For now, accept any key that looks valid (32+ chars)
    if len(api_key) < 8:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format",
        )

    return api_key


# =============================================================================
# VOICE ENDPOINT
# =============================================================================


@router.post("/voice", response_model=VoiceResponse)
async def shortcut_voice(
    request: VoiceRequest,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(verify_shortcut_api_key),
) -> VoiceResponse:
    """
    Optimized voice endpoint for iOS Shortcuts.

    Designed for "Hey Siri, ask Jarvis..." functionality:
    - Uses fast model tier for quick responses
    - Generates concise, speakable responses
    - Pre-generates audio with ElevenLabs
    - Returns audio URL for Shortcuts to play

    Target latency: <2 seconds
    """
    start_time = time.time()

    try:
        # Initialize AI engine with fast model preference
        vector_store = get_vector_store()
        engine = AIEngine(db, vector_store)

        # Use Haiku for simple queries, Sonnet for complex ones
        # The routing system will handle this automatically

        # Generate AI response (parallel with audio generation prep)
        response_text = await engine.chat(
            message=request.text,
            user_id=UUID(request.user_id) if request.user_id else DEFAULT_USER_ID,
            conversation_id=request.conversation_id,
            user_name=DEFAULT_USER_NAME,
        )

        # Format for speech
        speech_text = ShortcutResponseFormatter.format_for_speech(
            response_text,
            request.context,
        )

        # Track actions taken (extract from response or tool use)
        actions_taken: List[ActionTaken] = []

        # Generate audio URL if requested
        audio_url = None
        if request.voice_response:
            # Check cache first
            cached = _audio_cache.get(speech_text, JARVIS_VOICE_ID)
            if cached:
                audio_url = f"/api/shortcut/audio/{cached.stem}"
            else:
                # Generate audio
                try:
                    tts_client = get_elevenlabs_client()
                    audio_data = await tts_client.synthesize(
                        text=speech_text,
                        voice_id=JARVIS_VOICE_ID,
                        voice_settings=JARVIS_VOICE_SETTINGS,
                    )

                    # Cache audio
                    audio_path = await _audio_cache.put(
                        speech_text,
                        JARVIS_VOICE_ID,
                        audio_data,
                    )
                    audio_url = f"/api/shortcut/audio/{audio_path.stem}"
                except Exception as e:
                    logger.warning(f"Audio generation failed: {e}")
                    # Continue without audio

        latency_ms = int((time.time() - start_time) * 1000)

        return VoiceResponse(
            text=response_text,
            speech=speech_text,
            audio_url=audio_url,
            actions_taken=actions_taken,
            latency_ms=latency_ms,
            conversation_id=request.conversation_id or str(uuid.uuid4()),
        )

    except Exception as e:
        logger.error(f"Voice endpoint error: {e}")
        latency_ms = int((time.time() - start_time) * 1000)

        # Return error as speakable response
        error_speech = "I'm sorry, I encountered an error processing your request. Please try again."
        return VoiceResponse(
            text=str(e),
            speech=error_speech,
            audio_url=None,
            actions_taken=[],
            latency_ms=latency_ms,
        )


@router.get("/audio/{audio_id}")
async def get_audio(audio_id: str) -> FileResponse:
    """
    Serve cached audio file.

    iOS Shortcuts can play this URL directly.
    """
    audio_path = AUDIO_CACHE_DIR / f"{audio_id}.mp3"

    if not audio_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio not found or expired",
        )

    return FileResponse(
        audio_path,
        media_type="audio/mpeg",
        headers={
            "Cache-Control": f"max-age={AUDIO_CACHE_TTL_SECONDS}",
        },
    )


# =============================================================================
# QUICK ACTION ENDPOINTS
# =============================================================================


@router.post("/home/{action}")
async def home_action(
    action: str,
    request: Optional[HomeActionRequest] = None,
    api_key: str = Depends(verify_shortcut_api_key),
) -> Dict[str, Any]:
    """
    Quick home automation actions.

    Actions:
    - lights_on: Turn on lights (optionally in specific room)
    - lights_off: Turn off lights
    - scene/{scene_name}: Activate a scene
    - status: Get home status
    - thermostat: Set temperature
    """
    if not SMART_HOME_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Smart home integration not available",
        )

    start_time = time.time()

    try:
        if action == "lights_on":
            room = request.room if request else "all"
            brightness = request.brightness if request and request.brightness else 100
            result = await control_lights(room, "on", brightness=brightness)
            result_data = json.loads(result)
            speech = f"Lights are now on in the {room}." if room != "all" else "All lights are on."

        elif action == "lights_off":
            room = request.room if request else "all"
            result = await control_lights(room, "off")
            result_data = json.loads(result)
            speech = f"Lights are now off in the {room}." if room != "all" else "All lights are off."

        elif action.startswith("scene/"):
            scene_name = action[6:]
            result = await activate_scene(scene_name)
            result_data = json.loads(result)
            speech = f"Activated {scene_name} scene."

        elif action == "status":
            result = await get_home_status()
            result_data = json.loads(result)
            speech = ShortcutResponseFormatter.format_home_status(result_data)

        elif action == "thermostat":
            if not request or not request.temperature:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Temperature required for thermostat action",
                )
            result = await set_thermostat(request.temperature)
            result_data = json.loads(result)
            speech = f"Thermostat set to {int(request.temperature)} degrees."

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown action: {action}",
            )

        latency_ms = int((time.time() - start_time) * 1000)

        return {
            "success": True,
            "action": action,
            "speech": speech,
            "data": result_data,
            "latency_ms": latency_ms,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Home action error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/remind")
async def quick_remind(
    request: QuickRemindRequest,
    api_key: str = Depends(verify_shortcut_api_key),
) -> Dict[str, Any]:
    """
    Quick reminder creation.

    Example: "Remind me to call mom in 30 minutes"
    """
    if not SCHEDULER_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduler not available",
        )

    start_time = time.time()

    try:
        result = await schedule_action(
            action_type="reminder",
            scheduled_time=request.when,
            payload={"message": request.text},
            description=request.text,
        )

        result_data = json.loads(result)

        # Format for speech
        if result_data.get("status") == "scheduled":
            scheduled_time = result_data["action"].get("scheduled_time_local", request.when)
            speech = f"Got it. I'll remind you to {request.text} at {scheduled_time}."
        else:
            speech = f"I've set a reminder: {request.text}."

        latency_ms = int((time.time() - start_time) * 1000)

        return {
            "success": True,
            "speech": speech,
            "data": result_data,
            "latency_ms": latency_ms,
        }

    except Exception as e:
        logger.error(f"Reminder creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/schedule")
async def quick_schedule(
    request: QuickScheduleRequest,
    api_key: str = Depends(verify_shortcut_api_key),
) -> Dict[str, Any]:
    """
    Quick event scheduling.

    Note: Requires Google Calendar to be configured.
    """
    start_time = time.time()

    # For now, create as a scheduled action/reminder
    # Full calendar integration would require OAuth
    if SCHEDULER_AVAILABLE:
        try:
            result = await schedule_action(
                action_type="reminder",
                scheduled_time=request.when,
                payload={
                    "type": "event",
                    "title": request.title,
                    "duration_minutes": request.duration_minutes,
                },
                description=f"Event: {request.title}",
            )

            result_data = json.loads(result)
            speech = f"Scheduled {request.title} for {request.when}."

            latency_ms = int((time.time() - start_time) * 1000)

            return {
                "success": True,
                "speech": speech,
                "data": result_data,
                "latency_ms": latency_ms,
            }
        except Exception as e:
            logger.error(f"Schedule creation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduling not available",
        )


@router.get("/status")
async def quick_status(
    api_key: str = Depends(verify_shortcut_api_key),
) -> QuickStatusResponse:
    """
    Quick status check - weather, calendar, home status.

    Aggregates common status information for voice output.
    """
    start_time = time.time()

    # Get current time
    now = datetime.now()
    hour = now.hour

    # Determine greeting
    if hour < 12:
        greeting = "Good morning"
    elif hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    # Get home status if available
    home_status = None
    if SMART_HOME_AVAILABLE:
        try:
            result = await get_home_status()
            home_status = json.loads(result)
        except Exception as e:
            logger.warning(f"Failed to get home status: {e}")

    # Calendar status would require OAuth - placeholder
    calendar_status = None

    # Weather would require external API - placeholder
    weather_status = None

    return QuickStatusResponse(
        weather=weather_status,
        calendar=calendar_status,
        home=home_status,
        time=now.strftime("%I:%M %p"),
        greeting=f"{greeting}. It's {now.strftime('%I:%M %p')}.",
    )


# =============================================================================
# UTILITY ENDPOINTS
# =============================================================================


@router.post("/generate-key")
async def generate_api_key(
    device_name: str = Query(..., description="Name for this device"),
) -> Dict[str, str]:
    """
    Generate a new API key for a device.

    In production, this would store the key in the database.
    For now, generates a random key.
    """
    # Generate a simple API key
    import secrets
    api_key = secrets.token_urlsafe(32)

    # TODO: Store in database with device_name and user association

    return {
        "api_key": api_key,
        "device_name": device_name,
        "message": "Store this key securely. It won't be shown again.",
    }


@router.get("/health")
async def shortcut_health() -> Dict[str, Any]:
    """Health check for shortcut endpoints."""
    return {
        "status": "healthy",
        "features": {
            "voice": True,
            "smart_home": SMART_HOME_AVAILABLE,
            "calendar": CALENDAR_AVAILABLE,
            "scheduler": SCHEDULER_AVAILABLE,
        },
        "cache": {
            "audio_files": len(list(AUDIO_CACHE_DIR.glob("*.mp3"))),
            "ttl_seconds": AUDIO_CACHE_TTL_SECONDS,
        },
    }


@router.post("/cache/cleanup")
async def cleanup_cache(
    api_key: str = Depends(verify_shortcut_api_key),
) -> Dict[str, int]:
    """Cleanup expired audio cache files."""
    removed = _audio_cache.cleanup_expired()
    return {"removed_files": removed}
