"""FastAPI routes for family member management and presence tracking."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.home.family import (
    FamilyManager,
    FamilyMemberCreate,
    FamilyMemberResponse,
    FamilyMemberUpdate,
    get_family_manager,
)
from app.home.presence import (
    PresenceManager,
    PresenceState,
    get_presence_manager,
)

router = APIRouter(tags=["family"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _profile_to_response(profile) -> FamilyMemberResponse:
    m = profile.member
    return FamilyMemberResponse(
        id=m.id,
        name=m.name,
        voice_id=m.voice_id,
        preferences=m.preferences,
        autonomy_level=m.autonomy_level,
        allowed_actions=m.allowed_actions,
        avatar_url=m.avatar_url,
        telegram_user_id=m.telegram_user_id,
        greeting_preferences=profile.greeting_preferences,
        default_mode=profile.default_mode,
        voice_enabled=profile.voice_enabled,
    )


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class PresenceUpdate(BaseModel):
    state: PresenceState
    source: str = "manual"
    device_name: str = "unknown"
    ip_address: str | None = None


class PresenceResponse(BaseModel):
    member_id: str
    state: PresenceState


class GreetingResponse(BaseModel):
    greeting: str


# ---------------------------------------------------------------------------
# Family CRUD
# ---------------------------------------------------------------------------

@router.get("/family", response_model=list[FamilyMemberResponse])
async def list_family_members():
    """List all family members."""
    mgr: FamilyManager = get_family_manager()
    profiles = await mgr.list_members()
    return [_profile_to_response(p) for p in profiles]


@router.post("/family", response_model=FamilyMemberResponse, status_code=201)
async def add_family_member(data: FamilyMemberCreate):
    """Add a new family member."""
    mgr: FamilyManager = get_family_manager()
    profile = await mgr.add_member(data)
    return _profile_to_response(profile)


@router.get("/family/{member_id}", response_model=FamilyMemberResponse)
async def get_family_member(member_id: str):
    """Get a family member by ID."""
    mgr: FamilyManager = get_family_manager()
    profile = await mgr.get_member(member_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Family member not found")
    return _profile_to_response(profile)


@router.put("/family/{member_id}", response_model=FamilyMemberResponse)
async def update_family_member(member_id: str, data: FamilyMemberUpdate):
    """Update a family member."""
    mgr: FamilyManager = get_family_manager()
    profile = await mgr.update_member(member_id, data)
    if not profile:
        raise HTTPException(status_code=404, detail="Family member not found")
    return _profile_to_response(profile)


@router.delete("/family/{member_id}", status_code=204)
async def delete_family_member(member_id: str):
    """Remove a family member."""
    mgr: FamilyManager = get_family_manager()
    removed = await mgr.remove_member(member_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Family member not found")


# ---------------------------------------------------------------------------
# Greeting
# ---------------------------------------------------------------------------

@router.get("/family/{member_id}/greeting", response_model=GreetingResponse)
async def get_greeting(member_id: str):
    """Get a personalized time-based greeting for a family member."""
    mgr: FamilyManager = get_family_manager()
    profile = await mgr.get_member(member_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Family member not found")
    greeting = await mgr.get_greeting(member_id)
    return GreetingResponse(greeting=greeting)


# ---------------------------------------------------------------------------
# Presence
# ---------------------------------------------------------------------------

@router.post("/family/{member_id}/presence", response_model=PresenceResponse)
async def update_member_presence(member_id: str, data: PresenceUpdate):
    """Update presence state for a family member."""
    # Verify member exists
    fmgr: FamilyManager = get_family_manager()
    profile = await fmgr.get_member(member_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Family member not found")

    pmgr: PresenceManager = get_presence_manager()
    await pmgr.update_presence(
        member_id=member_id,
        state=data.state,
        source=data.source,
        device_name=data.device_name,
        ip_address=data.ip_address,
    )
    return PresenceResponse(member_id=member_id, state=data.state)


@router.get("/presence", response_model=list[PresenceResponse])
async def get_all_presence():
    """Get presence states for all tracked family members."""
    pmgr: PresenceManager = get_presence_manager()
    states = await pmgr.get_all_presence()
    return [
        PresenceResponse(member_id=mid, state=state)
        for mid, state in states.items()
    ]
