from __future__ import annotations
"""Integrations module for external service connections."""

from app.integrations.github import GitHubIntegration, get_github_integration
from app.integrations.google_calendar import (
    GoogleCalendarIntegration,
    get_google_calendar_integration,
)
from app.integrations.plaid import PlaidIntegration, get_plaid_integration

__all__ = [
    "GitHubIntegration",
    "get_github_integration",
    "GoogleCalendarIntegration",
    "get_google_calendar_integration",
    "PlaidIntegration",
    "get_plaid_integration",
]
