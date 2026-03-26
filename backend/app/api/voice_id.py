"""FastAPI routes for voice identification — enroll and identify family members by voice."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel

from app.home.voice_id import (
    VoiceIdentifier,
    VoiceProfile,
    MIN_SAMPLES_FOR_ID,
    get_voice_identifier,
)
from app.home.family import get_family_manager

router = APIRouter(tags=["voice-id"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class EnrollResponse(BaseModel):
    member_id: str
    sample_count: int
    samples_needed: int
    ready: bool
    message: str


class IdentifyResponse(BaseModel):
    member_id: str | None
    member_name: str | None = None
    confidence: float
    identified: bool


class ProfileStatusResponse(BaseModel):
    member_id: str
    sample_count: int
    samples_needed: int
    ready: bool
    created_at: str


class ProfileSummaryResponse(BaseModel):
    member_id: str
    sample_count: int
    ready: bool


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/enroll/{member_id}", response_model=EnrollResponse)
async def enroll_voice(
    member_id: str,
    audio: UploadFile = File(...),
    sample_rate: int = Query(16000, description="Audio sample rate in Hz"),
):
    """Upload an audio sample to enroll a family member's voice.

    Accepts WAV or raw 16-bit PCM audio.  At least 3 samples are needed for
    reliable identification.
    """
    # Verify the family member exists
    fmgr = get_family_manager()
    profile = await fmgr.get_member(member_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Family member not found")

    audio_data = await audio.read()
    if not audio_data:
        raise HTTPException(status_code=400, detail="Empty audio file")

    vid = get_voice_identifier()

    try:
        vp = vid.enroll(member_id, audio_data, sample_rate)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to process audio: {e}")

    ready = vp.sample_count >= MIN_SAMPLES_FOR_ID
    remaining = max(0, MIN_SAMPLES_FOR_ID - vp.sample_count)

    # Update the family member's voice_profile_ready flag
    if ready and not profile.member.voice_profile_ready:
        from app.home.family import FamilyMemberUpdate
        await fmgr.update_member(member_id, FamilyMemberUpdate(voice_profile_ready=True))

    return EnrollResponse(
        member_id=member_id,
        sample_count=vp.sample_count,
        samples_needed=remaining,
        ready=ready,
        message=(
            "Voice profile ready for identification."
            if ready
            else f"Need {remaining} more sample(s) for reliable identification."
        ),
    )


@router.post("/identify", response_model=IdentifyResponse)
async def identify_voice(
    audio: UploadFile = File(...),
    sample_rate: int = Query(16000, description="Audio sample rate in Hz"),
):
    """Upload audio to identify which family member is speaking.

    Returns the matched member and confidence score.  If no match exceeds
    the threshold, ``identified`` is false.
    """
    audio_data = await audio.read()
    if not audio_data:
        raise HTTPException(status_code=400, detail="Empty audio file")

    vid = get_voice_identifier()

    try:
        member_id, confidence = vid.identify(audio_data, sample_rate)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to process audio: {e}")

    member_name: str | None = None
    if member_id:
        fmgr = get_family_manager()
        profile = await fmgr.get_member(member_id)
        if profile:
            member_name = profile.member.name

    return IdentifyResponse(
        member_id=member_id,
        member_name=member_name,
        confidence=round(confidence, 4),
        identified=member_id is not None,
    )


@router.get("/profiles", response_model=list[ProfileSummaryResponse])
async def list_profiles():
    """List all enrolled voice profiles with sample counts."""
    vid = get_voice_identifier()
    return [
        ProfileSummaryResponse(
            member_id=p.member_id,
            sample_count=p.sample_count,
            ready=p.sample_count >= MIN_SAMPLES_FOR_ID,
        )
        for p in vid.list_profiles()
    ]


@router.get("/profiles/{member_id}/status", response_model=ProfileStatusResponse)
async def get_profile_status(member_id: str):
    """Get enrollment status for a specific family member's voice profile."""
    vid = get_voice_identifier()
    vp = vid.get_profile(member_id)
    if not vp:
        raise HTTPException(status_code=404, detail="Voice profile not found")

    return ProfileStatusResponse(
        member_id=vp.member_id,
        sample_count=vp.sample_count,
        samples_needed=max(0, MIN_SAMPLES_FOR_ID - vp.sample_count),
        ready=vp.sample_count >= MIN_SAMPLES_FOR_ID,
        created_at=vp.created_at,
    )


@router.delete("/profiles/{member_id}", status_code=204)
async def delete_profile(member_id: str):
    """Remove a family member's voice profile."""
    vid = get_voice_identifier()
    removed = vid.remove_profile(member_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Voice profile not found")

    # Reset the family member's voice_profile_ready flag
    fmgr = get_family_manager()
    profile = await fmgr.get_member(member_id)
    if profile and profile.member.voice_profile_ready:
        from app.home.family import FamilyMemberUpdate
        await fmgr.update_member(member_id, FamilyMemberUpdate(voice_profile_ready=False))
