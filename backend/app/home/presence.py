"""Presence detection and tracking for family members."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class PresenceState(str, Enum):
    home = "home"
    away = "away"
    arriving = "arriving"
    leaving = "leaving"


@dataclass
class DevicePresence:
    """Tracks a single device associated with a family member."""

    member_id: str
    device_name: str
    ip_address: Optional[str] = None
    last_seen: datetime = field(default_factory=datetime.now)
    state: PresenceState = PresenceState.away


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class PresenceManager:
    """Tracks family member presence via device pings or manual check-in."""

    # After this many minutes without a ping the member is considered away.
    AWAY_TIMEOUT_MINUTES: int = 15

    def __init__(self) -> None:
        # member_id -> latest DevicePresence
        self._presence: dict[str, DevicePresence] = {}
        # callbacks
        self._arrival_hooks: list = []
        self._departure_hooks: list = []

    # -- core ---------------------------------------------------------------

    async def update_presence(
        self,
        member_id: str,
        state: PresenceState,
        source: str = "manual",
        device_name: str = "unknown",
        ip_address: Optional[str] = None,
    ) -> DevicePresence:
        previous = self._presence.get(member_id)
        previous_state = previous.state if previous else PresenceState.away

        device = DevicePresence(
            member_id=member_id,
            device_name=device_name,
            ip_address=ip_address,
            last_seen=datetime.now(),
            state=state,
        )
        self._presence[member_id] = device

        logger.info(
            "Presence updated: member=%s state=%s source=%s",
            member_id, state.value, source,
        )

        # Trigger hooks on transitions
        if state in (PresenceState.home, PresenceState.arriving) and previous_state == PresenceState.away:
            await self.on_arrival(member_id)
        elif state in (PresenceState.away, PresenceState.leaving) and previous_state == PresenceState.home:
            await self.on_departure(member_id)

        return device

    async def get_presence(self, member_id: str) -> PresenceState:
        device = self._presence.get(member_id)
        if not device:
            return PresenceState.away

        # Auto-expire stale entries
        if (
            device.state == PresenceState.home
            and datetime.now() - device.last_seen > timedelta(minutes=self.AWAY_TIMEOUT_MINUTES)
        ):
            device.state = PresenceState.away
            return PresenceState.away

        return device.state

    async def get_all_presence(self) -> dict[str, PresenceState]:
        result: dict[str, PresenceState] = {}
        for member_id in self._presence:
            result[member_id] = await self.get_presence(member_id)
        return result

    # -- automation hooks ---------------------------------------------------

    async def on_arrival(self, member_id: str) -> None:
        """Triggered when a member transitions to home/arriving."""
        logger.info("Arrival detected: member=%s", member_id)
        for hook in self._arrival_hooks:
            try:
                await hook(member_id)
            except Exception:
                logger.exception("Arrival hook failed for member=%s", member_id)

    async def on_departure(self, member_id: str) -> None:
        """Triggered when a member transitions to away/leaving."""
        logger.info("Departure detected: member=%s", member_id)
        for hook in self._departure_hooks:
            try:
                await hook(member_id)
            except Exception:
                logger.exception("Departure hook failed for member=%s", member_id)

    def register_arrival_hook(self, hook) -> None:
        self._arrival_hooks.append(hook)

    def register_departure_hook(self, hook) -> None:
        self._departure_hooks.append(hook)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_presence_manager: PresenceManager | None = None


def get_presence_manager() -> PresenceManager:
    global _presence_manager
    if _presence_manager is None:
        _presence_manager = PresenceManager()
    return _presence_manager
