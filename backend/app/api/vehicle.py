"""FastAPI routes for vehicle integration — driving state, commute briefings, and arrival automation."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.home.vehicle import (
    CommuteBriefing,
    VehicleState,
    get_vehicle_manager,
)

router = APIRouter(tags=["vehicle"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class VehicleStateRequest(BaseModel):
    is_driving: bool = False
    location: list[float] | None = None  # [lat, lon]
    destination: str | None = None
    eta_minutes: int | None = None
    speed_mph: float | None = None


class VehicleStateResponse(BaseModel):
    is_driving: bool
    location: list[float] | None = None
    destination: str | None = None
    eta_minutes: int | None = None
    speed_mph: float | None = None
    updated_at: str


class CommuteBriefingResponse(BaseModel):
    summary: str
    weather: str | None = None
    calendar_events: list[str] = []
    reminders: list[str] = []
    traffic_notes: str | None = None
    estimated_arrival: str | None = None


class BriefingQuery(BaseModel):
    destination: str | None = None


class OnMyWayHomeRequest(BaseModel):
    member_id: str = "primary"


class OnMyWayHomeResponse(BaseModel):
    status: str
    presence: str
    destination: str
    hooks_fired: int
    hook_results: list[str] = []


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/state", response_model=VehicleStateResponse)
async def get_vehicle_state():
    """Return the current vehicle / driving state."""
    mgr = get_vehicle_manager()
    summary = await mgr.get_driving_summary()
    return VehicleStateResponse(**summary)


@router.post("/state", response_model=VehicleStateResponse)
async def update_vehicle_state(data: VehicleStateRequest):
    """Update driving state (called from the iOS app during location tracking)."""
    mgr = get_vehicle_manager()

    location_tuple = tuple(data.location) if data.location and len(data.location) == 2 else None

    state = VehicleState(
        is_driving=data.is_driving,
        location=location_tuple,
        destination=data.destination,
        eta_minutes=data.eta_minutes,
        speed_mph=data.speed_mph,
    )
    updated = await mgr.update_state(state)

    loc = list(updated.location) if updated.location else None
    return VehicleStateResponse(
        is_driving=updated.is_driving,
        location=loc,
        destination=updated.destination,
        eta_minutes=updated.eta_minutes,
        speed_mph=updated.speed_mph,
        updated_at=updated.updated_at,
    )


@router.get("/briefing", response_model=CommuteBriefingResponse)
async def get_commute_briefing(destination: str | None = None):
    """Generate a commute briefing with calendar, weather, and reminders."""
    mgr = get_vehicle_manager()
    briefing: CommuteBriefing = await mgr.generate_commute_briefing(destination=destination)
    return CommuteBriefingResponse(
        summary=briefing.summary,
        weather=briefing.weather,
        calendar_events=briefing.calendar_events,
        reminders=briefing.reminders,
        traffic_notes=briefing.traffic_notes,
        estimated_arrival=briefing.estimated_arrival,
    )


@router.post("/on-my-way-home", response_model=OnMyWayHomeResponse)
async def on_my_way_home(data: OnMyWayHomeRequest | None = None):
    """Trigger the 'heading home' automation — sets presence to arriving and fires hooks."""
    mgr = get_vehicle_manager()
    member_id = data.member_id if data else "primary"
    result = await mgr.trigger_on_my_way_home(member_id=member_id)
    return OnMyWayHomeResponse(**result)


@router.get("/driving-summary", response_model=VehicleStateResponse)
async def get_driving_summary():
    """Quick status — alias for GET /state for convenience."""
    mgr = get_vehicle_manager()
    summary = await mgr.get_driving_summary()
    return VehicleStateResponse(**summary)
