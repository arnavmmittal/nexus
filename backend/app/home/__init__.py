"""Home integration module - family profiles, presence, and terminal support."""
from app.home.family import (
    FamilyMember,
    FamilyProfile,
    FamilyManager,
    get_family_manager,
)
from app.home.presence import (
    PresenceState,
    PresenceManager,
    get_presence_manager,
)
