"""API endpoints for external integrations."""

import logging
from datetime import datetime, timedelta
from typing import Annotated, Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.integrations.github import GitHubIntegration, get_github_integration
from app.integrations.google_calendar import (
    GoogleCalendarIntegration,
    get_google_calendar_integration,
)
from app.integrations.plaid import get_plaid_integration
from app.models.user import User
from app.models.plaid import PlaidItem, PlaidAccount

logger = logging.getLogger(__name__)

# Placeholder user ID (will be replaced with auth later)
DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")

# In-memory state storage for OAuth (should use Redis in production)
_oauth_states: dict[str, dict[str, Any]] = {}

router = APIRouter()


# --- Pydantic Schemas ---


class GitHubConnectRequest(BaseModel):
    """Request to connect GitHub integration."""

    token: str = Field(
        ...,
        min_length=1,
        description="GitHub personal access token",
    )


class GitHubConnectResponse(BaseModel):
    """Response after connecting GitHub."""

    status: str
    user: str | None = None
    message: str


class GitHubActivityResponse(BaseModel):
    """Response containing GitHub activity."""

    user: str | None = None
    commits: list[dict[str, Any]] = []
    pull_requests: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    repos_analyzed: int = 0
    error: str | None = None


class GitHubStatsResponse(BaseModel):
    """Response containing GitHub statistics."""

    commit_stats: dict[str, Any] = {}
    language_stats: dict[str, Any] = {}
    error: str | None = None


class GitHubSyncRequest(BaseModel):
    """Request to sync GitHub activity."""

    days: int = Field(default=7, ge=1, le=90, description="Days to sync")


class GitHubSyncResponse(BaseModel):
    """Response after syncing GitHub activity."""

    status: str
    commits_processed: int = 0
    prs_processed: int = 0
    xp_awarded: dict[str, int] = {}
    total_xp: int = 0
    error: str | None = None


# --- Helper to get integration ---


def get_github(token: str | None = None) -> GitHubIntegration:
    """Get GitHub integration instance."""
    return get_github_integration(token)


# --- Endpoints ---


@router.post("/github/connect", response_model=GitHubConnectResponse)
async def connect_github(
    request: GitHubConnectRequest,
) -> GitHubConnectResponse:
    """
    Connect GitHub integration with a personal access token.

    The token is validated by making a test API call.
    For now, the token is stored in memory. In production,
    this would be encrypted and stored in the database.

    Args:
        request: GitHub connection request with token

    Returns:
        Connection status and user info
    """
    try:
        # Create integration with the provided token
        github = get_github(request.token)

        # Validate by getting user info
        if not github.is_configured():
            return GitHubConnectResponse(
                status="error",
                message="Token is empty or invalid",
            )

        # Test the token
        try:
            user = github.client.get_user()
            username = user.login
        except Exception as e:
            logger.error(f"GitHub token validation failed: {e}")
            return GitHubConnectResponse(
                status="error",
                message=f"Token validation failed: {str(e)}",
            )

        return GitHubConnectResponse(
            status="connected",
            user=username,
            message=f"Successfully connected as {username}",
        )

    except Exception as e:
        logger.error(f"GitHub connection error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Connection failed: {str(e)}",
        )


@router.get("/github/activity", response_model=GitHubActivityResponse)
async def get_github_activity(
    days: int = 30,
) -> GitHubActivityResponse:
    """
    Get recent GitHub activity for the connected user.

    Args:
        days: Number of days to look back (default 30)

    Returns:
        Recent commits, PRs, and issues
    """
    github = get_github()

    if not github.is_configured():
        return GitHubActivityResponse(
            error="GitHub not connected. Use POST /api/integrations/github/connect first.",
        )

    try:
        activity = github.get_user_activity(days=days)

        if "error" in activity:
            return GitHubActivityResponse(error=activity["error"])

        return GitHubActivityResponse(
            user=activity.get("user"),
            commits=activity.get("commits", []),
            pull_requests=activity.get("pull_requests", []),
            issues=activity.get("issues", []),
            repos_analyzed=activity.get("repos_analyzed", 0),
        )

    except Exception as e:
        logger.error(f"Error fetching GitHub activity: {e}")
        return GitHubActivityResponse(error=str(e))


@router.get("/github/stats", response_model=GitHubStatsResponse)
async def get_github_stats() -> GitHubStatsResponse:
    """
    Get GitHub coding statistics.

    Returns commit stats and language usage.

    Returns:
        Commit and language statistics
    """
    github = get_github()

    if not github.is_configured():
        return GitHubStatsResponse(
            error="GitHub not connected. Use POST /api/integrations/github/connect first.",
        )

    try:
        commit_stats = github.get_commit_stats()
        language_stats = github.get_language_stats()

        # Check for errors
        if "error" in commit_stats:
            return GitHubStatsResponse(error=commit_stats["error"])
        if "error" in language_stats:
            return GitHubStatsResponse(error=language_stats["error"])

        return GitHubStatsResponse(
            commit_stats=commit_stats,
            language_stats=language_stats,
        )

    except Exception as e:
        logger.error(f"Error fetching GitHub stats: {e}")
        return GitHubStatsResponse(error=str(e))


@router.post("/github/sync", response_model=GitHubSyncResponse)
async def sync_github_activity(
    request: GitHubSyncRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GitHubSyncResponse:
    """
    Sync GitHub activity and award XP to skills.

    Analyzes recent commits and PRs, detects programming languages,
    and awards XP to the corresponding skills.

    Args:
        request: Sync request with days parameter
        db: Database session

    Returns:
        Sync results including XP awarded
    """
    github = get_github()

    if not github.is_configured():
        return GitHubSyncResponse(
            status="error",
            error="GitHub not connected. Use POST /api/integrations/github/connect first.",
        )

    try:
        result = await github.sync_activity(db, days=request.days)

        if "error" in result:
            return GitHubSyncResponse(
                status="error",
                error=result["error"],
            )

        return GitHubSyncResponse(
            status=result.get("status", "success"),
            commits_processed=result.get("commits_processed", 0),
            prs_processed=result.get("prs_processed", 0),
            xp_awarded=result.get("xp_awarded", {}),
            total_xp=result.get("total_xp", 0),
        )

    except Exception as e:
        logger.error(f"Error syncing GitHub activity: {e}")
        return GitHubSyncResponse(
            status="error",
            error=str(e),
        )


@router.get("/github/status")
async def get_github_status() -> dict[str, Any]:
    """
    Get the current status of the GitHub integration.

    Returns:
        Connection status and basic info
    """
    github = get_github()

    if not github.is_configured():
        return {
            "connected": False,
            "message": "GitHub not connected",
        }

    try:
        user = github.client.get_user()
        return {
            "connected": True,
            "user": user.login,
            "name": user.name,
            "public_repos": user.public_repos,
            "followers": user.followers,
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
        }


# ============================================================================
# Google Calendar Schemas
# ============================================================================


class CreateEventRequest(BaseModel):
    """Request body for creating a calendar event."""

    summary: str = Field(..., description="Event title")
    start_time: datetime = Field(..., description="Event start time (ISO format)")
    end_time: datetime = Field(..., description="Event end time (ISO format)")
    description: Optional[str] = Field(None, description="Event description")
    location: Optional[str] = Field(None, description="Event location")
    attendees: Optional[list[str]] = Field(None, description="List of attendee emails")
    timezone: str = Field("UTC", description="Timezone for the event")


class IntegrationStatus(BaseModel):
    """Status of an integration."""

    name: str
    connected: bool
    last_sync: Optional[datetime] = None
    error: Optional[str] = None


# ============================================================================
# Google Calendar OAuth Endpoints
# ============================================================================


@router.get("/google/auth")
async def get_google_auth_url(
    redirect_uri: Optional[str] = Query(None, description="Custom redirect URI"),
) -> dict[str, str]:
    """
    Get the Google OAuth2 authorization URL.

    Returns:
        Authorization URL to redirect the user for Google login
    """
    try:
        auth_url, state = GoogleCalendarIntegration.get_auth_url(redirect_uri)

        # Store state for validation
        _oauth_states[state] = {
            "created_at": datetime.utcnow().isoformat(),
            "redirect_uri": redirect_uri,
        }

        return {
            "auth_url": auth_url,
            "state": state,
        }
    except Exception as e:
        logger.error(f"Error generating Google auth URL: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate authorization URL. Check Google OAuth configuration.",
        )


@router.get("/google/callback")
async def google_oauth_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="OAuth state for CSRF protection"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Handle Google OAuth2 callback.

    Exchanges the authorization code for tokens and stores them.

    Returns:
        Success message with connection status
    """
    # Validate state
    if state not in _oauth_states:
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state. Please try the authorization flow again.",
        )

    state_data = _oauth_states.pop(state)
    redirect_uri = state_data.get("redirect_uri")

    try:
        # Exchange code for tokens
        token_data = GoogleCalendarIntegration.exchange_code(code, redirect_uri)

        # Get or create user
        result = await db.execute(select(User).where(User.id == DEFAULT_USER_ID))
        user = result.scalar_one_or_none()

        if not user:
            user = User(id=DEFAULT_USER_ID, name="Default User")
            db.add(user)

        # Store token in user settings (encrypted in production)
        settings = user.settings or {}
        settings["google_calendar_tokens"] = token_data
        user.settings = settings

        await db.commit()

        return {
            "status": "success",
            "message": "Google Calendar connected successfully",
            "scopes": token_data.get("scopes", []),
        }

    except Exception as e:
        logger.error(f"Error in Google OAuth callback: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to complete authorization: {str(e)}",
        )


@router.delete("/google/disconnect")
async def disconnect_google(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """
    Disconnect Google Calendar integration.

    Removes stored OAuth tokens.
    """
    result = await db.execute(select(User).where(User.id == DEFAULT_USER_ID))
    user = result.scalar_one_or_none()

    if user and user.settings:
        settings = user.settings.copy()
        if "google_calendar_tokens" in settings:
            del settings["google_calendar_tokens"]
            user.settings = settings
            await db.commit()

    return {"status": "success", "message": "Google Calendar disconnected"}


# ============================================================================
# Google Calendar API Endpoints
# ============================================================================


async def _get_calendar_integration(
    db: AsyncSession,
) -> GoogleCalendarIntegration:
    """Get Google Calendar integration for current user."""
    result = await db.execute(select(User).where(User.id == DEFAULT_USER_ID))
    user = result.scalar_one_or_none()

    if not user or not user.settings or "google_calendar_tokens" not in user.settings:
        raise HTTPException(
            status_code=401,
            detail="Google Calendar not connected. Please authorize first.",
        )

    token_data = user.settings["google_calendar_tokens"]
    return get_google_calendar_integration(token_data)


@router.get("/google/calendar/today")
async def get_todays_calendar_events(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Get today's calendar events.

    Returns:
        List of events for today
    """
    integration = await _get_calendar_integration(db)

    try:
        events = await integration.get_todays_events()
        return {
            "date": datetime.now().date().isoformat(),
            "events": events,
            "count": len(events),
        }
    except Exception as e:
        logger.error(f"Error fetching today's events: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch events: {str(e)}",
        )


@router.get("/google/calendar/upcoming")
async def get_upcoming_calendar_events(
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(7, ge=1, le=30, description="Number of days to look ahead"),
) -> dict[str, Any]:
    """
    Get upcoming calendar events.

    Args:
        days: Number of days to look ahead (default: 7, max: 30)

    Returns:
        List of upcoming events
    """
    integration = await _get_calendar_integration(db)

    try:
        events = await integration.get_upcoming_events(days=days)
        return {
            "days": days,
            "events": events,
            "count": len(events),
        }
    except Exception as e:
        logger.error(f"Error fetching upcoming events: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch events: {str(e)}",
        )


@router.get("/google/calendar/freebusy")
async def get_calendar_free_busy(
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(7, ge=1, le=30, description="Number of days to check"),
) -> dict[str, Any]:
    """
    Get free/busy information for the calendar.

    Args:
        days: Number of days to check (default: 7)

    Returns:
        Free/busy blocks for the specified period
    """
    integration = await _get_calendar_integration(db)

    try:
        freebusy = await integration.get_free_busy()
        return {
            "days": days,
            "calendars": freebusy,
        }
    except Exception as e:
        logger.error(f"Error fetching free/busy: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch free/busy: {str(e)}",
        )


@router.post("/google/calendar/events")
async def create_calendar_event(
    request: CreateEventRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Create a new calendar event.

    Returns:
        Created event data
    """
    integration = await _get_calendar_integration(db)

    try:
        event = await integration.create_event(
            summary=request.summary,
            start_time=request.start_time,
            end_time=request.end_time,
            description=request.description,
            location=request.location,
            attendees=request.attendees,
            timezone=request.timezone,
        )
        return {
            "status": "created",
            "event": event,
        }
    except Exception as e:
        logger.error(f"Error creating event: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create event: {str(e)}",
        )


@router.get("/google/status")
async def get_google_calendar_status(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Get Google Calendar integration status.

    Returns:
        Connection status and details
    """
    result = await db.execute(select(User).where(User.id == DEFAULT_USER_ID))
    user = result.scalar_one_or_none()

    if not user or not user.settings or "google_calendar_tokens" not in user.settings:
        return {
            "connected": False,
            "message": "Google Calendar not connected",
        }

    token_data = user.settings["google_calendar_tokens"]

    return {
        "connected": True,
        "scopes": token_data.get("scopes", []),
        "has_refresh_token": bool(token_data.get("refresh_token")),
    }


# ============================================================================
# All Integrations Status
# ============================================================================


@router.get("/status")
async def get_all_integration_statuses(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Get status of all integrations.

    Returns:
        Status of each integration (connected, last sync, errors)
    """
    result = await db.execute(select(User).where(User.id == DEFAULT_USER_ID))
    user = result.scalar_one_or_none()

    user_settings = user.settings if user else {}

    integrations = []

    # GitHub status
    github = get_github()
    github_connected = github.is_configured()
    integrations.append(
        IntegrationStatus(
            name="github",
            connected=github_connected,
            last_sync=None,
            error=None,
        )
    )

    # Google Calendar status
    google_connected = "google_calendar_tokens" in user_settings
    integrations.append(
        IntegrationStatus(
            name="google_calendar",
            connected=google_connected,
            last_sync=None,
            error=None,
        )
    )

    return {
        "integrations": [i.model_dump() for i in integrations],
        "total_connected": sum(1 for i in integrations if i.connected),
    }
