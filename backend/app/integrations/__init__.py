"""Integrations for Nexus agents.

This module provides integrations with external services:
- Google Calendar (OAuth2)
- Plaid (Banking)
- GitHub (existing OAuth integration)
- Job hunting tools (LinkedIn, Indeed, job tracking)
- Email tools (Gmail, Outlook)
- Browser automation
- Slack
- Smart Home (Apple HomeKit)
"""

# Existing OAuth integrations
from app.integrations.google_calendar import (
    GoogleCalendarIntegration,
    get_google_calendar_integration,
)
from app.integrations.plaid import get_plaid_integration
from app.integrations.github import GitHubIntegration, get_github_integration

# New agent tools
from app.integrations.jobs import JOB_TOOLS
from app.integrations.email_tools import EMAIL_TOOLS
from app.integrations.browser import BROWSER_TOOLS
from app.integrations.slack_tools import SLACK_TOOLS
from app.integrations.github_tools import GITHUB_TOOLS
from app.integrations.job_intelligence import JOB_INTELLIGENCE_TOOLS
from app.integrations.filesystem import FILESYSTEM_TOOLS
from app.integrations.smart_home import SMART_HOME_TOOLS

# All integration tools combined for AI agents
ALL_INTEGRATION_TOOLS = (
    JOB_TOOLS +
    EMAIL_TOOLS +
    BROWSER_TOOLS +
    SLACK_TOOLS +
    GITHUB_TOOLS +
    JOB_INTELLIGENCE_TOOLS +
    FILESYSTEM_TOOLS +
    SMART_HOME_TOOLS
)

__all__ = [
    # Existing integrations
    "GoogleCalendarIntegration",
    "get_google_calendar_integration",
    "get_plaid_integration",
    "GitHubIntegration",
    "get_github_integration",
    # Agent tools
    "ALL_INTEGRATION_TOOLS",
    "JOB_TOOLS",
    "EMAIL_TOOLS",
    "BROWSER_TOOLS",
    "SLACK_TOOLS",
    "GITHUB_TOOLS",
    "FILESYSTEM_TOOLS",
    "SMART_HOME_TOOLS",
]
