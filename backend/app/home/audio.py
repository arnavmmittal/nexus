"""Multi-room audio manager with TTS announcements and speaker control."""
from __future__ import annotations

import asyncio
import json
import logging
import platform
import tempfile
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import httpx

from app.core.config import settings
from app.voice.elevenlabs import get_elevenlabs_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

@dataclass
class RoomSpeaker:
    """A speaker/audio endpoint in a specific room."""

    room_id: str
    name: str
    type: str  # "sonos" | "chromecast" | "local" | "airplay"
    ip_address: str = ""
    volume: int = 50  # 0-100
    is_playing: bool = False
    zone: Optional[str] = None


@dataclass
class AudioZone:
    """A logical grouping of rooms for synchronized playback."""

    zone_id: str
    name: str
    rooms: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class AudioManager:
    """Manages multi-room audio with TTS announcements and speaker control."""

    def __init__(self, data_path: Path | None = None) -> None:
        self._data_path = data_path or Path("data/audio_rooms.json")
        self._rooms: dict[str, RoomSpeaker] = {}
        self._zones: dict[str, AudioZone] = {}
        self._load()

    # -- persistence --------------------------------------------------------

    def _load(self) -> None:
        if not self._data_path.exists():
            return
        try:
            raw = json.loads(self._data_path.read_text())
            for entry in raw.get("rooms", []):
                speaker = RoomSpeaker(**entry)
                self._rooms[speaker.room_id] = speaker
            for entry in raw.get("zones", []):
                zone = AudioZone(**entry)
                self._zones[zone.zone_id] = zone
        except Exception as e:
            logger.error(f"Failed to load audio config: {e}")

    def _save(self) -> None:
        self._data_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "rooms": [asdict(r) for r in self._rooms.values()],
            "zones": [asdict(z) for z in self._zones.values()],
        }
        self._data_path.write_text(json.dumps(payload, indent=2))

    # -- room CRUD ----------------------------------------------------------

    async def register_room(
        self,
        name: str,
        speaker_type: str,
        ip_address: str = "",
        volume: int = 50,
        zone: str | None = None,
    ) -> RoomSpeaker:
        """Register a new room/speaker."""
        room_id = uuid.uuid4().hex[:12]
        speaker = RoomSpeaker(
            room_id=room_id,
            name=name,
            type=speaker_type,
            ip_address=ip_address,
            volume=volume,
            zone=zone,
        )
        self._rooms[room_id] = speaker
        self._save()
        logger.info(f"Registered room '{name}' ({speaker_type}) as {room_id}")
        return speaker

    async def remove_room(self, room_id: str) -> bool:
        """Remove a room/speaker."""
        if room_id not in self._rooms:
            return False
        del self._rooms[room_id]
        # Remove from any zones
        for zone in self._zones.values():
            if room_id in zone.rooms:
                zone.rooms.remove(room_id)
        self._save()
        return True

    async def get_room(self, room_id: str) -> RoomSpeaker | None:
        return self._rooms.get(room_id)

    async def get_room_status(self) -> list[dict]:
        """Return status of all rooms."""
        return [asdict(r) for r in self._rooms.values()]

    # -- volume -------------------------------------------------------------

    async def set_volume(self, room_id: str, volume: int) -> RoomSpeaker | None:
        """Set volume for a specific room (0-100)."""
        speaker = self._rooms.get(room_id)
        if not speaker:
            return None
        speaker.volume = max(0, min(100, volume))
        self._save()

        # Push volume to the actual speaker
        try:
            await self._set_speaker_volume(speaker)
        except Exception as e:
            logger.warning(f"Failed to set hardware volume for {room_id}: {e}")

        return speaker

    # -- zones --------------------------------------------------------------

    async def create_zone(self, name: str, room_ids: list[str]) -> AudioZone:
        """Create a zone grouping multiple rooms."""
        zone_id = uuid.uuid4().hex[:8]
        # Validate room IDs
        valid_ids = [rid for rid in room_ids if rid in self._rooms]
        zone = AudioZone(zone_id=zone_id, name=name, rooms=valid_ids)
        self._zones[zone_id] = zone

        # Tag rooms with zone
        for rid in valid_ids:
            self._rooms[rid].zone = zone_id

        self._save()
        logger.info(f"Created zone '{name}' with {len(valid_ids)} rooms")
        return zone

    async def list_zones(self) -> list[dict]:
        return [asdict(z) for z in self._zones.values()]

    async def get_zone(self, zone_id: str) -> AudioZone | None:
        return self._zones.get(zone_id)

    # -- TTS & announcements ------------------------------------------------

    async def play_tts(self, text: str, room_id: str) -> bool:
        """Generate TTS via ElevenLabs and play on a specific room's speaker."""
        speaker = self._rooms.get(room_id)
        if not speaker:
            logger.error(f"Room {room_id} not found")
            return False

        try:
            client = get_elevenlabs_client()
            audio_data = await client.synthesize(text)
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            return False

        return await self._play_audio(speaker, audio_data)

    async def announce(
        self, message: str, rooms: list[str] | None = None
    ) -> dict[str, bool]:
        """Send TTS announcement to specific rooms or all rooms.

        Returns:
            Dict mapping room_id -> success boolean.
        """
        target_ids = rooms if rooms else list(self._rooms.keys())
        if not target_ids:
            logger.warning("No rooms to announce to")
            return {}

        # Generate TTS once
        try:
            client = get_elevenlabs_client()
            audio_data = await client.synthesize(message)
        except Exception as e:
            logger.error(f"TTS synthesis failed for announcement: {e}")
            return {rid: False for rid in target_ids}

        # Play on all target rooms concurrently
        results: dict[str, bool] = {}
        tasks = []
        for rid in target_ids:
            speaker = self._rooms.get(rid)
            if speaker:
                tasks.append((rid, self._play_audio(speaker, audio_data)))
            else:
                results[rid] = False

        if tasks:
            outcomes = await asyncio.gather(
                *(t[1] for t in tasks), return_exceptions=True
            )
            for (rid, _), outcome in zip(tasks, outcomes):
                results[rid] = outcome is True

        return results

    async def announce_to_zone(self, message: str, zone_id: str) -> dict[str, bool]:
        """Announce to all rooms in a zone."""
        zone = self._zones.get(zone_id)
        if not zone:
            logger.error(f"Zone {zone_id} not found")
            return {}
        return await self.announce(message, rooms=zone.rooms)

    # -- speaker backends ---------------------------------------------------

    async def _play_audio(self, speaker: RoomSpeaker, audio_data: bytes) -> bool:
        """Route audio to the correct speaker backend."""
        speaker.is_playing = True
        try:
            if speaker.type == "sonos":
                return await self._play_sonos(speaker, audio_data)
            elif speaker.type == "chromecast":
                return await self._play_chromecast(speaker, audio_data)
            elif speaker.type == "airplay":
                return await self._play_airplay(speaker, audio_data)
            elif speaker.type == "local":
                return await self._play_local(audio_data)
            else:
                logger.error(f"Unknown speaker type: {speaker.type}")
                return False
        except Exception as e:
            logger.error(f"Playback failed on {speaker.name}: {e}")
            return False
        finally:
            speaker.is_playing = False

    async def _play_local(self, audio_data: bytes) -> bool:
        """Play audio on the local machine using afplay (macOS) or aplay (Linux)."""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(audio_data)
            tmp_path = f.name

        cmd = "afplay" if platform.system() == "Darwin" else "aplay"
        proc = await asyncio.create_subprocess_exec(
            cmd, tmp_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        Path(tmp_path).unlink(missing_ok=True)

        if proc.returncode != 0:
            logger.error(f"Local playback failed: {stderr.decode()}")
            return False
        return True

    async def _play_sonos(self, speaker: RoomSpeaker, audio_data: bytes) -> bool:
        """Play audio on a Sonos speaker via its HTTP API (node-sonos-http-api)."""
        # Requires node-sonos-http-api running (https://github.com/jishi/node-sonos-http-api)
        # Write audio to temp file and serve, or use clip endpoint
        base_url = f"http://{speaker.ip_address}:5005"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Set volume first
                await client.get(f"{base_url}/{speaker.name}/volume/{speaker.volume}")
                # Use say endpoint as fallback (uses built-in TTS)
                # For pre-generated audio, you'd host it and use /clip endpoint
                resp = await client.get(
                    f"{base_url}/{speaker.name}/clip/announcement.mp3",
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"Sonos playback error ({speaker.name}): {e}")
            return False

    async def _play_chromecast(self, speaker: RoomSpeaker, audio_data: bytes) -> bool:
        """Play audio on a Chromecast device via its REST endpoint."""
        # Requires a Chromecast media bridge or catt-based service
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio_data)
                tmp_path = f.name

            # Use catt CLI to cast audio
            proc = await asyncio.create_subprocess_exec(
                "catt", "-d", speaker.ip_address, "cast", tmp_path,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            Path(tmp_path).unlink(missing_ok=True)

            if proc.returncode != 0:
                logger.error(f"Chromecast cast failed: {stderr.decode()}")
                return False
            return True
        except FileNotFoundError:
            logger.error("catt not installed. Install with: pip install catt")
            return False

    async def _play_airplay(self, speaker: RoomSpeaker, audio_data: bytes) -> bool:
        """Play audio on an AirPlay speaker via shairport-sync or raop."""
        # Simple approach: write to temp file and stream via ffmpeg + raop
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio_data)
                tmp_path = f.name

            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-i", tmp_path,
                "-f", "raop",
                f"raop://{speaker.ip_address}/stream",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            Path(tmp_path).unlink(missing_ok=True)

            if proc.returncode != 0:
                logger.error(f"AirPlay playback failed: {stderr.decode()}")
                return False
            return True
        except FileNotFoundError:
            logger.error("ffmpeg not installed for AirPlay streaming")
            return False

    async def _set_speaker_volume(self, speaker: RoomSpeaker) -> None:
        """Push volume change to the hardware speaker."""
        if speaker.type == "sonos" and speaker.ip_address:
            base_url = f"http://{speaker.ip_address}:5005"
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.get(f"{base_url}/{speaker.name}/volume/{speaker.volume}")
        # Other types: volume is applied at playback time


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_audio_manager: AudioManager | None = None


def get_audio_manager() -> AudioManager:
    global _audio_manager
    if _audio_manager is None:
        _audio_manager = AudioManager()
    return _audio_manager
