"""FastAPI routes for multi-room audio management and TTS announcements."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.home.audio import AudioManager, get_audio_manager

router = APIRouter(tags=["audio"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class AnnounceRequest(BaseModel):
    message: str
    rooms: Optional[list[str]] = None  # None = all rooms


class AnnounceResponse(BaseModel):
    results: dict[str, bool]  # room_id -> success


class TTSRequest(BaseModel):
    text: str
    room_id: str


class TTSResponse(BaseModel):
    success: bool
    room_id: str


class RoomCreate(BaseModel):
    name: str
    type: str = Field(description="Speaker type: sonos, chromecast, local, airplay")
    ip_address: str = ""
    volume: int = Field(default=50, ge=0, le=100)
    zone: Optional[str] = None


class RoomResponse(BaseModel):
    room_id: str
    name: str
    type: str
    ip_address: str
    volume: int
    is_playing: bool
    zone: Optional[str]


class VolumeRequest(BaseModel):
    volume: int = Field(ge=0, le=100)


class ZoneCreate(BaseModel):
    name: str
    room_ids: list[str]


class ZoneResponse(BaseModel):
    zone_id: str
    name: str
    rooms: list[str]


class ZoneAnnounceRequest(BaseModel):
    message: str
    zone_id: str


# ---------------------------------------------------------------------------
# Announcement endpoints
# ---------------------------------------------------------------------------

@router.post("/announce", response_model=AnnounceResponse)
async def announce(data: AnnounceRequest):
    """Send a TTS announcement to specific rooms or all rooms."""
    mgr: AudioManager = get_audio_manager()
    results = await mgr.announce(data.message, rooms=data.rooms)
    return AnnounceResponse(results=results)


@router.post("/tts", response_model=TTSResponse)
async def play_tts(data: TTSRequest):
    """Play TTS on a specific room's speaker."""
    mgr: AudioManager = get_audio_manager()
    room = await mgr.get_room(data.room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    success = await mgr.play_tts(data.text, data.room_id)
    return TTSResponse(success=success, room_id=data.room_id)


# ---------------------------------------------------------------------------
# Room CRUD
# ---------------------------------------------------------------------------

@router.get("/rooms", response_model=list[RoomResponse])
async def list_rooms():
    """List all registered rooms and their status."""
    mgr: AudioManager = get_audio_manager()
    rooms = await mgr.get_room_status()
    return rooms


@router.post("/rooms", response_model=RoomResponse, status_code=201)
async def register_room(data: RoomCreate):
    """Register a new room/speaker."""
    if data.type not in ("sonos", "chromecast", "local", "airplay"):
        raise HTTPException(
            status_code=400,
            detail="Invalid speaker type. Must be: sonos, chromecast, local, airplay",
        )
    mgr: AudioManager = get_audio_manager()
    speaker = await mgr.register_room(
        name=data.name,
        speaker_type=data.type,
        ip_address=data.ip_address,
        volume=data.volume,
        zone=data.zone,
    )
    return RoomResponse(
        room_id=speaker.room_id,
        name=speaker.name,
        type=speaker.type,
        ip_address=speaker.ip_address,
        volume=speaker.volume,
        is_playing=speaker.is_playing,
        zone=speaker.zone,
    )


@router.delete("/rooms/{room_id}", status_code=204)
async def remove_room(room_id: str):
    """Remove a registered room/speaker."""
    mgr: AudioManager = get_audio_manager()
    removed = await mgr.remove_room(room_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Room not found")


@router.put("/rooms/{room_id}/volume", response_model=RoomResponse)
async def set_volume(room_id: str, data: VolumeRequest):
    """Set volume for a specific room."""
    mgr: AudioManager = get_audio_manager()
    speaker = await mgr.set_volume(room_id, data.volume)
    if not speaker:
        raise HTTPException(status_code=404, detail="Room not found")
    return RoomResponse(
        room_id=speaker.room_id,
        name=speaker.name,
        type=speaker.type,
        ip_address=speaker.ip_address,
        volume=speaker.volume,
        is_playing=speaker.is_playing,
        zone=speaker.zone,
    )


# ---------------------------------------------------------------------------
# Zone endpoints
# ---------------------------------------------------------------------------

@router.post("/zones", response_model=ZoneResponse, status_code=201)
async def create_zone(data: ZoneCreate):
    """Create a zone grouping multiple rooms."""
    mgr: AudioManager = get_audio_manager()
    zone = await mgr.create_zone(data.name, data.room_ids)
    return ZoneResponse(zone_id=zone.zone_id, name=zone.name, rooms=zone.rooms)


@router.get("/zones", response_model=list[ZoneResponse])
async def list_zones():
    """List all audio zones."""
    mgr: AudioManager = get_audio_manager()
    zones = await mgr.list_zones()
    return zones


@router.post("/zones/announce", response_model=AnnounceResponse)
async def announce_to_zone(data: ZoneAnnounceRequest):
    """Announce to all rooms in a zone."""
    mgr: AudioManager = get_audio_manager()
    zone = await mgr.get_zone(data.zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    results = await mgr.announce_to_zone(data.message, data.zone_id)
    return AnnounceResponse(results=results)
