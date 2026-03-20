from __future__ import annotations
"""Google Calendar integration using OAuth2."""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import settings

logger = logging.getLogger(__name__)

# OAuth2 scopes for Google Calendar
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]


class GoogleCalendarIntegration:
    """Google Calendar API integration with OAuth2 authentication."""

    def __init__(self, credentials: Optional[Credentials] = None):
        """
        Initialize Google Calendar integration.

        Args:
            credentials: Google OAuth2 credentials (optional for auth flow)
        """
        self._credentials = credentials
        self._service = None

    @property
    def service(self):
        """Get or create the Google Calendar service."""
        if self._service is None and self._credentials:
            self._service = build("calendar", "v3", credentials=self._credentials)
        return self._service

    @classmethod
    def create_oauth_flow(cls, redirect_uri: Optional[str] = None) -> Flow:
        """
        Create OAuth2 flow for Google Calendar authorization.

        Args:
            redirect_uri: OAuth redirect URI (uses settings default if not provided)

        Returns:
            Google OAuth2 Flow object
        """
        client_config = {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri or settings.google_redirect_uri],
            }
        }

        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=redirect_uri or settings.google_redirect_uri,
        )
        return flow

    @classmethod
    def get_auth_url(cls, redirect_uri: Optional[str] = None) -> tuple[str, str]:
        """
        Get the OAuth2 authorization URL.

        Args:
            redirect_uri: OAuth redirect URI

        Returns:
            Tuple of (authorization_url, state)
        """
        flow = cls.create_oauth_flow(redirect_uri)
        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",  # Force consent to get refresh token
        )
        return authorization_url, state

    @classmethod
    def exchange_code(cls, code: str, redirect_uri: Optional[str] = None) -> dict[str, Any]:
        """
        Exchange authorization code for credentials.

        Args:
            code: Authorization code from OAuth callback
            redirect_uri: OAuth redirect URI

        Returns:
            Token data including access_token, refresh_token, etc.
        """
        flow = cls.create_oauth_flow(redirect_uri)
        flow.fetch_token(code=code)
        credentials = flow.credentials

        return {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": list(credentials.scopes) if credentials.scopes else SCOPES,
            "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
        }

    @classmethod
    def from_token_data(cls, token_data: dict[str, Any]) -> "GoogleCalendarIntegration":
        """
        Create integration instance from stored token data.

        Args:
            token_data: Token data dict from database

        Returns:
            GoogleCalendarIntegration instance
        """
        credentials = Credentials(
            token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=token_data.get("client_id", settings.google_client_id),
            client_secret=token_data.get("client_secret", settings.google_client_secret),
            scopes=token_data.get("scopes", SCOPES),
        )
        return cls(credentials=credentials)

    def get_updated_token_data(self) -> Optional[dict[str, Any]]:
        """
        Get updated token data after potential refresh.

        Returns:
            Updated token data if refresh occurred, None otherwise
        """
        if self._credentials and self._credentials.expired and self._credentials.refresh_token:
            # Token was refreshed, return new token data
            return {
                "access_token": self._credentials.token,
                "refresh_token": self._credentials.refresh_token,
                "token_uri": self._credentials.token_uri,
                "client_id": self._credentials.client_id,
                "client_secret": self._credentials.client_secret,
                "scopes": list(self._credentials.scopes) if self._credentials.scopes else SCOPES,
                "expiry": self._credentials.expiry.isoformat() if self._credentials.expiry else None,
            }
        return None

    async def get_todays_events(self, calendar_id: str = "primary") -> list[dict[str, Any]]:
        """
        Get events for today.

        Args:
            calendar_id: Calendar ID (default: primary)

        Returns:
            List of event dictionaries
        """
        now = datetime.utcnow()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        return await self._get_events(
            calendar_id=calendar_id,
            time_min=start_of_day,
            time_max=end_of_day,
        )

    async def get_upcoming_events(
        self, days: int = 7, calendar_id: str = "primary"
    ) -> list[dict[str, Any]]:
        """
        Get upcoming events for the specified number of days.

        Args:
            days: Number of days to look ahead (default: 7)
            calendar_id: Calendar ID (default: primary)

        Returns:
            List of event dictionaries
        """
        now = datetime.utcnow()
        end_time = now + timedelta(days=days)

        return await self._get_events(
            calendar_id=calendar_id,
            time_min=now,
            time_max=end_time,
        )

    async def _get_events(
        self,
        calendar_id: str,
        time_min: datetime,
        time_max: datetime,
        max_results: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Internal method to fetch events from Google Calendar.

        Args:
            calendar_id: Calendar ID
            time_min: Start time for events
            time_max: End time for events
            max_results: Maximum number of events to return

        Returns:
            List of event dictionaries
        """
        if not self.service:
            raise ValueError("Calendar service not initialized. Credentials required.")

        try:
            events_result = (
                self.service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=time_min.isoformat() + "Z",
                    timeMax=time_max.isoformat() + "Z",
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            events = events_result.get("items", [])
            return [self._format_event(event) for event in events]

        except HttpError as e:
            logger.error(f"Error fetching calendar events: {e}")
            raise

    async def get_free_busy(
        self,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        calendar_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Get free/busy information for calendars.

        Args:
            time_min: Start time (default: now)
            time_max: End time (default: 7 days from now)
            calendar_ids: List of calendar IDs (default: ["primary"])

        Returns:
            Free/busy information
        """
        if not self.service:
            raise ValueError("Calendar service not initialized. Credentials required.")

        time_min = time_min or datetime.utcnow()
        time_max = time_max or (datetime.utcnow() + timedelta(days=7))
        calendar_ids = calendar_ids or ["primary"]

        try:
            body = {
                "timeMin": time_min.isoformat() + "Z",
                "timeMax": time_max.isoformat() + "Z",
                "items": [{"id": cal_id} for cal_id in calendar_ids],
            }

            freebusy_result = self.service.freebusy().query(body=body).execute()

            calendars = freebusy_result.get("calendars", {})
            result = {}

            for cal_id, cal_data in calendars.items():
                busy_blocks = cal_data.get("busy", [])
                result[cal_id] = {
                    "busy": [
                        {
                            "start": block.get("start"),
                            "end": block.get("end"),
                        }
                        for block in busy_blocks
                    ],
                    "errors": cal_data.get("errors", []),
                }

            return result

        except HttpError as e:
            logger.error(f"Error fetching free/busy information: {e}")
            raise

    async def create_event(
        self,
        summary: str,
        start_time: datetime,
        end_time: datetime,
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[list[str]] = None,
        calendar_id: str = "primary",
        timezone: str = "UTC",
    ) -> dict[str, Any]:
        """
        Create a new calendar event.

        Args:
            summary: Event title
            start_time: Event start time
            end_time: Event end time
            description: Event description (optional)
            location: Event location (optional)
            attendees: List of attendee email addresses (optional)
            calendar_id: Calendar ID (default: primary)
            timezone: Timezone for the event (default: UTC)

        Returns:
            Created event data
        """
        if not self.service:
            raise ValueError("Calendar service not initialized. Credentials required.")

        event_body = {
            "summary": summary,
            "start": {
                "dateTime": start_time.isoformat(),
                "timeZone": timezone,
            },
            "end": {
                "dateTime": end_time.isoformat(),
                "timeZone": timezone,
            },
        }

        if description:
            event_body["description"] = description

        if location:
            event_body["location"] = location

        if attendees:
            event_body["attendees"] = [{"email": email} for email in attendees]

        try:
            event = (
                self.service.events()
                .insert(
                    calendarId=calendar_id,
                    body=event_body,
                    sendUpdates="all" if attendees else "none",
                )
                .execute()
            )

            return self._format_event(event)

        except HttpError as e:
            logger.error(f"Error creating calendar event: {e}")
            raise

    def _format_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """
        Format a Google Calendar event into a standardized structure.

        Args:
            event: Raw Google Calendar event

        Returns:
            Formatted event dictionary
        """
        start = event.get("start", {})
        end = event.get("end", {})

        # Handle all-day events vs timed events
        start_time = start.get("dateTime") or start.get("date")
        end_time = end.get("dateTime") or end.get("date")
        is_all_day = "date" in start and "dateTime" not in start

        return {
            "id": event.get("id"),
            "summary": event.get("summary", "(No title)"),
            "description": event.get("description"),
            "location": event.get("location"),
            "start": start_time,
            "end": end_time,
            "is_all_day": is_all_day,
            "timezone": start.get("timeZone"),
            "status": event.get("status"),
            "html_link": event.get("htmlLink"),
            "attendees": [
                {
                    "email": attendee.get("email"),
                    "response_status": attendee.get("responseStatus"),
                    "organizer": attendee.get("organizer", False),
                }
                for attendee in event.get("attendees", [])
            ],
            "organizer": event.get("organizer", {}).get("email"),
            "created": event.get("created"),
            "updated": event.get("updated"),
        }


def get_google_calendar_integration(token_data: dict[str, Any]) -> GoogleCalendarIntegration:
    """
    Factory function to create a GoogleCalendarIntegration instance.

    Args:
        token_data: Stored OAuth token data

    Returns:
        GoogleCalendarIntegration instance
    """
    return GoogleCalendarIntegration.from_token_data(token_data)
