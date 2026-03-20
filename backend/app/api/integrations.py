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

    # Plaid status
    plaid_items_result = await db.execute(
        select(PlaidItem).where(
            PlaidItem.user_id == DEFAULT_USER_ID, PlaidItem.status == "active"
        )
    )
    plaid_items = plaid_items_result.scalars().all()
    plaid_connected = len(plaid_items) > 0
    integrations.append(
        IntegrationStatus(
            name="plaid",
            connected=plaid_connected,
            last_sync=plaid_items[0].last_accounts_sync if plaid_items else None,
            error=None,
        )
    )

    return {
        "integrations": [i.model_dump() for i in integrations],
        "total_connected": sum(1 for i in integrations if i.connected),
    }


# ============================================================================
# Plaid Schemas
# ============================================================================


class PlaidLinkTokenResponse(BaseModel):
    """Response for link token creation."""

    link_token: str
    expiration: str


class PlaidExchangeRequest(BaseModel):
    """Request to exchange public token."""

    public_token: str = Field(..., description="The public token from Plaid Link")
    institution_id: str | None = Field(None, description="Institution ID")
    institution_name: str | None = Field(None, description="Institution name")


class PlaidExchangeResponse(BaseModel):
    """Response after exchanging public token."""

    item_id: str
    accounts_count: int
    institution_name: str | None = None


class PlaidAccountResponse(BaseModel):
    """Account information response."""

    id: str
    name: str
    official_name: str | None = None
    type: str
    subtype: str | None = None
    mask: str | None = None
    current_balance: float | None = None
    available_balance: float | None = None
    currency: str = "USD"
    include_in_net_worth: bool = True


class PlaidBalancesResponse(BaseModel):
    """Balances response with net worth calculation."""

    accounts: list[PlaidAccountResponse]
    total_assets: float
    total_liabilities: float
    net_worth: float
    last_updated: str


class PlaidTransactionResponse(BaseModel):
    """Transaction response."""

    id: str
    date: str | None
    name: str
    merchant_name: str | None = None
    amount: float
    category: str
    pending: bool = False


class PlaidTransactionsResponse(BaseModel):
    """Transactions list response."""

    transactions: list[PlaidTransactionResponse]
    total_count: int
    period: dict[str, Any]
    summary: dict[str, Any]


class PlaidConnectionStatus(BaseModel):
    """Connection status for Plaid."""

    connected: bool
    items_count: int
    accounts_count: int
    institutions: list[str]


# ============================================================================
# Plaid Endpoints
# ============================================================================


@router.post("/plaid/link-token", response_model=PlaidLinkTokenResponse)
async def create_plaid_link_token(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Create a Plaid Link token.

    This token is used to initialize Plaid Link in the frontend.
    The Link flow allows users to securely connect their bank accounts.
    """
    plaid = get_plaid_integration()

    if not plaid.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Plaid is not configured. Please set PLAID_CLIENT_ID and PLAID_SECRET.",
        )

    try:
        result = await plaid.create_link_token(str(DEFAULT_USER_ID))
        return result
    except Exception as e:
        logger.error(f"Failed to create Plaid link token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create link token: {str(e)}",
        )


@router.post("/plaid/exchange", response_model=PlaidExchangeResponse)
async def exchange_plaid_public_token(
    request: PlaidExchangeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Exchange a public token for an access token.

    After a user completes Plaid Link, call this endpoint with the
    public_token to store the access token and fetch initial accounts.
    """
    plaid = get_plaid_integration()

    if not plaid.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Plaid is not configured.",
        )

    try:
        # Exchange the token
        result = await plaid.exchange_public_token(request.public_token)

        # Create PlaidItem record
        plaid_item = PlaidItem(
            user_id=DEFAULT_USER_ID,
            item_id=result["item_id"],
            access_token=result["access_token"],  # TODO: Encrypt in production
            institution_id=request.institution_id,
            institution_name=request.institution_name,
            status="active",
        )
        db.add(plaid_item)
        await db.flush()

        # Fetch and store accounts
        accounts = await plaid.get_accounts(result["access_token"])
        accounts_count = 0

        for acc in accounts:
            plaid_account = PlaidAccount(
                item_id=plaid_item.id,
                user_id=DEFAULT_USER_ID,
                account_id=acc["id"],
                name=acc["name"],
                official_name=acc.get("official_name"),
                mask=acc.get("mask"),
                type=str(acc["type"]),
                subtype=acc.get("subtype"),
            )
            db.add(plaid_account)
            accounts_count += 1

        plaid_item.last_accounts_sync = datetime.utcnow()
        await db.commit()

        return {
            "item_id": result["item_id"],
            "accounts_count": accounts_count,
            "institution_name": request.institution_name,
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to exchange Plaid token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to exchange token: {str(e)}",
        )


@router.get("/plaid/status", response_model=PlaidConnectionStatus)
async def get_plaid_connection_status(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Get Plaid connection status.

    Returns information about connected accounts and institutions.
    """
    # Get all items for user
    items_result = await db.execute(
        select(PlaidItem).where(
            PlaidItem.user_id == DEFAULT_USER_ID, PlaidItem.status == "active"
        )
    )
    items = items_result.scalars().all()

    # Get all accounts
    accounts_result = await db.execute(
        select(PlaidAccount).where(PlaidAccount.user_id == DEFAULT_USER_ID)
    )
    accounts = accounts_result.scalars().all()

    return {
        "connected": len(items) > 0,
        "items_count": len(items),
        "accounts_count": len(accounts),
        "institutions": [item.institution_name for item in items if item.institution_name],
    }


@router.get("/plaid/accounts")
async def get_plaid_accounts(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, Any]]:
    """
    Get all connected Plaid accounts.

    Returns a list of all bank and investment accounts.
    """
    # Get accounts from database
    result = await db.execute(
        select(PlaidAccount).where(PlaidAccount.user_id == DEFAULT_USER_ID)
    )
    accounts = result.scalars().all()

    return [
        {
            "id": str(acc.id),
            "account_id": acc.account_id,
            "name": acc.custom_name or acc.name,
            "official_name": acc.official_name,
            "type": acc.type,
            "subtype": acc.subtype,
            "mask": acc.mask,
            "current_balance": acc.current_balance,
            "available_balance": acc.available_balance,
            "currency": acc.currency,
            "include_in_net_worth": acc.include_in_net_worth,
            "balance_updated_at": (
                acc.balance_updated_at.isoformat() if acc.balance_updated_at else None
            ),
        }
        for acc in accounts
    ]


@router.get("/plaid/balances", response_model=PlaidBalancesResponse)
async def get_plaid_balances(
    db: Annotated[AsyncSession, Depends(get_db)],
    refresh: bool = Query(False, description="Fetch fresh data from Plaid"),
) -> dict[str, Any]:
    """
    Get account balances and calculate net worth.

    Args:
        refresh: If True, fetch fresh data from Plaid
    """
    plaid = get_plaid_integration()

    # Get all active items
    items_result = await db.execute(
        select(PlaidItem).where(
            PlaidItem.user_id == DEFAULT_USER_ID, PlaidItem.status == "active"
        )
    )
    items = items_result.scalars().all()

    if not items:
        return {
            "accounts": [],
            "total_assets": 0.0,
            "total_liabilities": 0.0,
            "net_worth": 0.0,
            "last_updated": datetime.utcnow().isoformat(),
        }

    all_accounts = []
    total_assets = 0.0
    total_liabilities = 0.0

    for item in items:
        if refresh and plaid.is_configured:
            try:
                # Fetch fresh balances from Plaid
                balances = await plaid.get_balances(item.access_token)

                # Update cached accounts
                for acc_data in balances["accounts"]:
                    acc_result = await db.execute(
                        select(PlaidAccount).where(
                            PlaidAccount.account_id == acc_data["id"]
                        )
                    )
                    account = acc_result.scalar_one_or_none()
                    if account:
                        account.current_balance = acc_data["current_balance"]
                        account.available_balance = acc_data["available_balance"]
                        account.balance_updated_at = datetime.utcnow()

                await db.commit()
            except Exception as e:
                logger.warning(f"Failed to refresh Plaid balances: {e}")
                # Continue with cached data

        # Get accounts from database
        accounts_result = await db.execute(
            select(PlaidAccount).where(
                PlaidAccount.item_id == item.id,
                PlaidAccount.include_in_net_worth == True,
            )
        )
        accounts = accounts_result.scalars().all()

        for acc in accounts:
            balance = acc.current_balance or 0.0
            all_accounts.append(
                {
                    "id": str(acc.id),
                    "name": acc.custom_name or acc.name,
                    "official_name": acc.official_name,
                    "type": acc.type,
                    "subtype": acc.subtype,
                    "mask": acc.mask,
                    "current_balance": balance,
                    "available_balance": acc.available_balance,
                    "currency": acc.currency,
                    "include_in_net_worth": acc.include_in_net_worth,
                }
            )

            # Calculate totals
            if acc.type in ["depository", "investment", "brokerage", "other"]:
                total_assets += balance
            elif acc.type in ["credit", "loan"]:
                total_liabilities += balance

    return {
        "accounts": all_accounts,
        "total_assets": round(total_assets, 2),
        "total_liabilities": round(total_liabilities, 2),
        "net_worth": round(total_assets - total_liabilities, 2),
        "last_updated": datetime.utcnow().isoformat(),
    }


@router.get("/plaid/transactions", response_model=PlaidTransactionsResponse)
async def get_plaid_transactions(
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(30, ge=1, le=90, description="Number of days of history"),
) -> dict[str, Any]:
    """
    Get recent transactions.

    Args:
        days: Number of days of history (default 30, max 90)
    """
    plaid = get_plaid_integration()

    # Get all active items
    items_result = await db.execute(
        select(PlaidItem).where(
            PlaidItem.user_id == DEFAULT_USER_ID, PlaidItem.status == "active"
        )
    )
    items = items_result.scalars().all()

    if not items:
        return {
            "transactions": [],
            "total_count": 0,
            "period": {"start_date": "", "end_date": "", "days": days},
            "summary": {
                "total_spending": 0,
                "total_income": 0,
                "net": 0,
                "top_categories": [],
            },
        }

    all_transactions = []
    total_spending = 0.0
    total_income = 0.0
    by_category: dict[str, float] = {}

    for item in items:
        if plaid.is_configured:
            try:
                result = await plaid.get_transactions(item.access_token, days)
                all_transactions.extend(result["transactions"])
                total_spending += result["summary"]["total_spending"]
                total_income += result["summary"]["total_income"]

                # Merge categories
                for cat in result["summary"]["top_categories"]:
                    by_category[cat["category"]] = (
                        by_category.get(cat["category"], 0) + cat["amount"]
                    )
            except Exception as e:
                logger.warning(f"Failed to fetch Plaid transactions: {e}")
                # Continue with other items

    # Sort transactions by date
    all_transactions.sort(key=lambda x: x.get("date", ""), reverse=True)

    # Get top categories
    top_categories = sorted(by_category.items(), key=lambda x: x[1], reverse=True)[:5]

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)

    return {
        "transactions": [
            {
                "id": t["id"],
                "date": t.get("date"),
                "name": t["name"],
                "merchant_name": t.get("merchant_name"),
                "amount": t["amount"],
                "category": t.get("category", "Uncategorized"),
                "pending": t.get("pending", False),
            }
            for t in all_transactions[:100]  # Limit to 100 transactions
        ],
        "total_count": len(all_transactions),
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days": days,
        },
        "summary": {
            "total_spending": round(total_spending, 2),
            "total_income": round(total_income, 2),
            "net": round(total_income - total_spending, 2),
            "top_categories": [
                {"category": cat, "amount": round(amt, 2)}
                for cat, amt in top_categories
            ],
        },
    }


@router.get("/plaid/investments")
async def get_plaid_investments(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Get investment holdings.

    Returns investment accounts, holdings, and portfolio allocation.
    """
    plaid = get_plaid_integration()

    # Get all active items
    items_result = await db.execute(
        select(PlaidItem).where(
            PlaidItem.user_id == DEFAULT_USER_ID, PlaidItem.status == "active"
        )
    )
    items = items_result.scalars().all()

    if not items:
        return {
            "accounts": [],
            "holdings": [],
            "total_value": 0.0,
            "allocation": {},
            "last_updated": datetime.utcnow().isoformat(),
        }

    all_holdings = []
    all_accounts = []
    total_value = 0.0
    by_type: dict[str, float] = {}

    for item in items:
        if plaid.is_configured:
            try:
                result = await plaid.get_investments(item.access_token)

                if "error" not in result:
                    all_holdings.extend(result.get("holdings", []))
                    all_accounts.extend(result.get("accounts", []))
                    total_value += result.get("total_value", 0)

                    # Merge allocation
                    for asset_type, data in result.get("allocation", {}).items():
                        by_type[asset_type] = by_type.get(asset_type, 0) + data["value"]
            except Exception as e:
                logger.warning(f"Failed to fetch Plaid investments: {e}")

    # Recalculate percentages
    allocation = {}
    for asset_type, value in by_type.items():
        allocation[asset_type] = {
            "value": round(value, 2),
            "percentage": round(value / total_value * 100, 2) if total_value > 0 else 0,
        }

    return {
        "accounts": all_accounts,
        "holdings": all_holdings,
        "total_value": round(total_value, 2),
        "allocation": allocation,
        "last_updated": datetime.utcnow().isoformat(),
    }


@router.delete("/plaid/items/{item_id}")
async def disconnect_plaid_item(
    item_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """
    Disconnect a Plaid item (bank connection).

    This removes the connection but preserves historical data.
    """
    result = await db.execute(
        select(PlaidItem).where(
            PlaidItem.item_id == item_id, PlaidItem.user_id == DEFAULT_USER_ID
        )
    )
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    # Soft delete by marking as disconnected
    item.status = "disconnected"
    await db.commit()

    return {"message": "Successfully disconnected"}
