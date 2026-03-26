"""Family member management with file-based JSON storage."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

@dataclass
class FamilyMember:
    """Core identity and permissions for a household member."""

    id: str
    name: str
    voice_id: Optional[str] = None
    preferences: dict = field(default_factory=dict)
    autonomy_level: float = 0.5  # 0-1, higher = more autonomous actions allowed
    allowed_actions: list[str] = field(default_factory=list)
    avatar_url: Optional[str] = None
    telegram_user_id: Optional[int] = None
    voice_profile_ready: bool = False


@dataclass
class FamilyProfile:
    """Extended profile wrapping a FamilyMember with UX preferences."""

    member: FamilyMember
    greeting_preferences: dict = field(default_factory=lambda: {
        "use_name": True,
        "time_aware": True,
        "formal": False,
    })
    default_mode: str = "jarvis"  # "jarvis" or "ultron"
    voice_enabled: bool = True


# ---------------------------------------------------------------------------
# Pydantic schemas (request / response)
# ---------------------------------------------------------------------------

class FamilyMemberCreate(BaseModel):
    name: str
    voice_id: Optional[str] = None
    preferences: dict = {}
    autonomy_level: float = 0.5
    allowed_actions: list[str] = []
    avatar_url: Optional[str] = None
    telegram_user_id: Optional[int] = None
    voice_profile_ready: bool = False
    greeting_preferences: dict = {
        "use_name": True,
        "time_aware": True,
        "formal": False,
    }
    default_mode: str = "jarvis"
    voice_enabled: bool = True


class FamilyMemberUpdate(BaseModel):
    name: Optional[str] = None
    voice_id: Optional[str] = None
    preferences: Optional[dict] = None
    autonomy_level: Optional[float] = None
    allowed_actions: Optional[list[str]] = None
    avatar_url: Optional[str] = None
    telegram_user_id: Optional[int] = None
    voice_profile_ready: Optional[bool] = None
    greeting_preferences: Optional[dict] = None
    default_mode: Optional[str] = None
    voice_enabled: Optional[bool] = None


class FamilyMemberResponse(BaseModel):
    id: str
    name: str
    voice_id: Optional[str] = None
    preferences: dict = {}
    autonomy_level: float = 0.5
    allowed_actions: list[str] = []
    avatar_url: Optional[str] = None
    telegram_user_id: Optional[int] = None
    voice_profile_ready: bool = False
    greeting_preferences: dict = {}
    default_mode: str = "jarvis"
    voice_enabled: bool = True


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class FamilyManager:
    """Manages family profiles with JSON file persistence."""

    def __init__(self, data_path: Path | None = None) -> None:
        self._data_path = data_path or Path("data/family.json")
        self._profiles: dict[str, FamilyProfile] = {}
        self._load()

    # -- persistence --------------------------------------------------------

    def _load(self) -> None:
        if self._data_path.exists():
            raw = json.loads(self._data_path.read_text())
            for entry in raw:
                member = FamilyMember(**entry["member"])
                profile = FamilyProfile(
                    member=member,
                    greeting_preferences=entry.get("greeting_preferences", {}),
                    default_mode=entry.get("default_mode", "jarvis"),
                    voice_enabled=entry.get("voice_enabled", True),
                )
                self._profiles[member.id] = profile

    def _save(self) -> None:
        self._data_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "member": asdict(p.member),
                "greeting_preferences": p.greeting_preferences,
                "default_mode": p.default_mode,
                "voice_enabled": p.voice_enabled,
            }
            for p in self._profiles.values()
        ]
        self._data_path.write_text(json.dumps(payload, indent=2, default=str))

    # -- CRUD ---------------------------------------------------------------

    async def add_member(self, data: FamilyMemberCreate) -> FamilyProfile:
        member_id = uuid.uuid4().hex[:12]
        member = FamilyMember(
            id=member_id,
            name=data.name,
            voice_id=data.voice_id,
            preferences=data.preferences,
            autonomy_level=data.autonomy_level,
            allowed_actions=data.allowed_actions,
            avatar_url=data.avatar_url,
            telegram_user_id=data.telegram_user_id,
            voice_profile_ready=data.voice_profile_ready,
        )
        profile = FamilyProfile(
            member=member,
            greeting_preferences=data.greeting_preferences,
            default_mode=data.default_mode,
            voice_enabled=data.voice_enabled,
        )
        self._profiles[member_id] = profile
        self._save()
        return profile

    async def remove_member(self, member_id: str) -> bool:
        if member_id in self._profiles:
            del self._profiles[member_id]
            self._save()
            return True
        return False

    async def update_member(
        self, member_id: str, data: FamilyMemberUpdate
    ) -> FamilyProfile | None:
        profile = self._profiles.get(member_id)
        if not profile:
            return None

        updates = data.model_dump(exclude_none=True)
        member = profile.member

        # Member-level fields
        for key in (
            "name", "voice_id", "preferences", "autonomy_level",
            "allowed_actions", "avatar_url", "telegram_user_id",
            "voice_profile_ready",
        ):
            if key in updates:
                setattr(member, key, updates[key])

        # Profile-level fields
        if "greeting_preferences" in updates:
            profile.greeting_preferences = updates["greeting_preferences"]
        if "default_mode" in updates:
            profile.default_mode = updates["default_mode"]
        if "voice_enabled" in updates:
            profile.voice_enabled = updates["voice_enabled"]

        self._save()
        return profile

    async def get_member(self, member_id: str) -> FamilyProfile | None:
        return self._profiles.get(member_id)

    async def list_members(self) -> list[FamilyProfile]:
        return list(self._profiles.values())

    # -- lookups ------------------------------------------------------------

    async def get_member_by_voice_id(self, voice_id: str) -> FamilyProfile | None:
        for profile in self._profiles.values():
            if profile.member.voice_id == voice_id:
                return profile
        return None

    async def get_member_by_telegram_id(self, telegram_id: int) -> FamilyProfile | None:
        for profile in self._profiles.values():
            if profile.member.telegram_user_id == telegram_id:
                return profile
        return None

    # -- voice identification -----------------------------------------------

    async def identify_by_voice(
        self, audio_data: bytes, sample_rate: int = 16000
    ) -> tuple[FamilyProfile | None, float]:
        """Identify a family member by their voice.

        Returns (FamilyProfile | None, confidence).  Uses the VoiceIdentifier
        service under the hood.
        """
        from app.home.voice_id import get_voice_identifier

        vid = get_voice_identifier()
        member_id, confidence = vid.identify(audio_data, sample_rate)
        if member_id:
            profile = self._profiles.get(member_id)
            return profile, confidence
        return None, confidence

    # -- greeting -----------------------------------------------------------

    async def get_greeting(self, member_id: str) -> str:
        profile = self._profiles.get(member_id)
        if not profile:
            return "Hello."

        prefs = profile.greeting_preferences
        name = profile.member.name if prefs.get("use_name", True) else ""
        formal = prefs.get("formal", False)

        if prefs.get("time_aware", True):
            hour = datetime.now().hour
            if hour < 12:
                period = "Good morning"
            elif hour < 17:
                period = "Good afternoon"
            elif hour < 21:
                period = "Good evening"
            else:
                period = "Good night"
        else:
            period = "Hello" if not formal else "Greetings"

        if formal:
            return f"{period}, Mr./Ms. {name}." if name else f"{period}."
        return f"{period}, {name}." if name else f"{period}."


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_family_manager: FamilyManager | None = None


def get_family_manager() -> FamilyManager:
    global _family_manager
    if _family_manager is None:
        _family_manager = FamilyManager()
    return _family_manager
