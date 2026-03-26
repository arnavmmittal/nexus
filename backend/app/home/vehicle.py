"""Vehicle integration manager — driving state, commute briefings, and arrival automation."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.home.presence import PresenceState, get_presence_manager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass
class VehicleState:
    """Current driving / vehicle state reported by the mobile app."""

    is_driving: bool = False
    location: tuple[float, float] | None = None  # (lat, lon)
    destination: str | None = None
    eta_minutes: int | None = None
    speed_mph: float | None = None
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class CommuteBriefing:
    """Natural-language commute briefing assembled from multiple sources."""

    summary: str
    weather: str | None = None
    calendar_events: list[str] = field(default_factory=list)
    reminders: list[str] = field(default_factory=list)
    traffic_notes: str | None = None
    estimated_arrival: str | None = None


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class VehicleManager:
    """Manages vehicle / driving state with JSON file persistence and
    integrates with the presence system for arrival automations."""

    def __init__(self, data_path: Path | None = None) -> None:
        self._data_path = data_path or Path("data/vehicle_state.json")
        self._state = VehicleState()
        self._arrival_hooks: list = []
        self._load()

    # -- persistence --------------------------------------------------------

    def _load(self) -> None:
        if self._data_path.exists():
            try:
                raw = json.loads(self._data_path.read_text())
                # Convert location list back to tuple if present
                loc = raw.get("location")
                if isinstance(loc, list) and len(loc) == 2:
                    raw["location"] = tuple(loc)
                elif loc is not None:
                    raw["location"] = None
                self._state = VehicleState(**{
                    k: v for k, v in raw.items() if k in VehicleState.__dataclass_fields__
                })
            except Exception:
                logger.exception("Failed to load vehicle state from %s", self._data_path)
                self._state = VehicleState()

    def _save(self) -> None:
        self._data_path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(self._state)
        # Convert tuple to list for JSON serialisation
        if payload.get("location") is not None:
            payload["location"] = list(payload["location"])
        self._data_path.write_text(json.dumps(payload, indent=2, default=str))

    # -- core ---------------------------------------------------------------

    async def update_state(self, state: VehicleState) -> VehicleState:
        """Update the current driving / vehicle state."""
        previous_driving = self._state.is_driving
        self._state = state
        self._state.updated_at = datetime.now().isoformat()
        self._save()

        logger.info(
            "Vehicle state updated: driving=%s dest=%s eta=%s speed=%s",
            state.is_driving, state.destination, state.eta_minutes, state.speed_mph,
        )

        # If we just started driving, log it
        if state.is_driving and not previous_driving:
            logger.info("Driving session started")

        # If we just stopped driving, log it
        if not state.is_driving and previous_driving:
            logger.info("Driving session ended")

        return self._state

    async def generate_commute_briefing(
        self, destination: str | None = None
    ) -> CommuteBriefing:
        """Pull calendar, weather, reminders and assemble a natural-language
        commute briefing.  Uses locally available data and builds a summary."""

        dest = destination or self._state.destination or "your destination"
        now = datetime.now()
        hour = now.hour

        # -- Time-of-day greeting -----------------------------------------
        if hour < 12:
            period = "Good morning"
        elif hour < 17:
            period = "Good afternoon"
        else:
            period = "Good evening"

        # -- Build weather blurb (placeholder — hook into real weather) ----
        weather = "Weather data unavailable — connect a weather integration for live updates."

        # -- Calendar events (placeholder — hook into calendar service) ----
        calendar_events: list[str] = []
        # In production, pull from app.integrations.calendar or similar:
        # calendar_events = await calendar_service.get_upcoming(hours=4)

        # -- Reminders (placeholder — hook into reminder service) ----------
        reminders: list[str] = []

        # -- Traffic (placeholder) -----------------------------------------
        traffic_notes: str | None = None

        # -- ETA -----------------------------------------------------------
        eta_str: str | None = None
        if self._state.eta_minutes is not None:
            eta_str = f"~{self._state.eta_minutes} minutes"
        elif destination:
            eta_str = "ETA unknown — no route data yet"

        # -- Summary -------------------------------------------------------
        parts: list[str] = [f"{period}. You're heading to {dest}."]

        if eta_str:
            parts.append(f"Estimated arrival: {eta_str}.")

        if calendar_events:
            parts.append(
                f"Upcoming: {', '.join(calendar_events[:3])}."
            )
        else:
            parts.append("No upcoming calendar events.")

        if reminders:
            parts.append(
                f"Reminders: {', '.join(reminders[:3])}."
            )

        if traffic_notes:
            parts.append(f"Traffic: {traffic_notes}.")

        summary = " ".join(parts)

        return CommuteBriefing(
            summary=summary,
            weather=weather,
            calendar_events=calendar_events,
            reminders=reminders,
            traffic_notes=traffic_notes,
            estimated_arrival=eta_str,
        )

    async def trigger_on_my_way_home(self, member_id: str = "primary") -> dict:
        """Fire the 'on my way home' automation sequence:
        1. Set presence to *arriving*
        2. Run registered arrival hooks (lights, thermostat, etc.)
        3. Return a confirmation dict.
        """

        # Update presence via the shared presence manager
        presence_mgr = get_presence_manager()
        await presence_mgr.update_presence(
            member_id=member_id,
            state=PresenceState.arriving,
            source="vehicle",
            device_name="vehicle_integration",
        )

        # Mark driving toward home
        self._state.destination = "Home"
        self._state.is_driving = True
        self._state.updated_at = datetime.now().isoformat()
        self._save()

        logger.info("On-my-way-home triggered for member=%s", member_id)

        # Fire any registered home-preparation hooks
        results: list[str] = []
        for hook in self._arrival_hooks:
            try:
                result = await hook(member_id)
                results.append(str(result))
            except Exception:
                logger.exception("Arrival hook failed")

        return {
            "status": "triggered",
            "presence": "arriving",
            "destination": "Home",
            "hooks_fired": len(self._arrival_hooks),
            "hook_results": results,
        }

    async def get_driving_summary(self) -> dict:
        """Return the current driving state as a plain dict."""
        data = asdict(self._state)
        if data.get("location") is not None:
            data["location"] = list(data["location"])
        return data

    # -- hooks --------------------------------------------------------------

    def register_arrival_hook(self, hook) -> None:
        """Register an async callable to run when 'on my way home' fires."""
        self._arrival_hooks.append(hook)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_vehicle_manager: VehicleManager | None = None


def get_vehicle_manager() -> VehicleManager:
    global _vehicle_manager
    if _vehicle_manager is None:
        _vehicle_manager = VehicleManager()
    return _vehicle_manager
