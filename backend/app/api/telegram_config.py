"""Telegram Bot Configuration for Nexus AI.

This module provides configuration and bot token management for
the Telegram integration. The bot enables chatting with Jarvis/Ultron
from anywhere via Telegram.

Configuration is loaded from environment variables:
- TELEGRAM_BOT_TOKEN: Bot token from @BotFather
- TELEGRAM_WEBHOOK_URL: URL for receiving webhook updates
- TELEGRAM_WEBHOOK_SECRET: Secret token for webhook verification
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

from pydantic import Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class TelegramSettings(BaseSettings):
    """Telegram bot settings loaded from environment."""

    # Bot token from @BotFather
    telegram_bot_token: str = ""

    # Webhook configuration
    telegram_webhook_url: str = ""
    telegram_webhook_secret: str = ""

    # Rate limiting (requests per minute per user)
    telegram_rate_limit: int = 30

    # Voice response settings
    telegram_voice_enabled: bool = True
    telegram_voice_reply_to_voice: bool = True  # Reply with voice when user sends voice

    # Default AI persona
    telegram_default_persona: str = "jarvis"

    # Allowed user IDs (empty = allow all)
    telegram_allowed_users: str = ""  # Comma-separated user IDs

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def allowed_user_ids(self) -> set:
        """Get set of allowed user IDs."""
        if not self.telegram_allowed_users:
            return set()  # Empty = allow all
        return {int(uid.strip()) for uid in self.telegram_allowed_users.split(",") if uid.strip()}

    @property
    def is_configured(self) -> bool:
        """Check if Telegram bot is configured."""
        return bool(self.telegram_bot_token)


# Singleton settings instance
_telegram_settings: Optional[TelegramSettings] = None


def get_telegram_settings() -> TelegramSettings:
    """Get or create Telegram settings singleton."""
    global _telegram_settings
    if _telegram_settings is None:
        _telegram_settings = TelegramSettings()
    return _telegram_settings


@dataclass
class UserSession:
    """Tracks user session state for Telegram conversations."""

    user_id: int
    telegram_user_id: int
    username: Optional[str] = None
    first_name: str = "User"
    last_name: Optional[str] = None

    # AI mode: "jarvis" or "ultron"
    mode: str = "jarvis"

    # Conversation tracking
    conversation_id: Optional[str] = None
    message_count: int = 0

    # User preferences
    voice_enabled: bool = True
    voice_reply_mode: bool = True  # Reply with voice to voice messages

    # Rate limiting
    request_timestamps: list = field(default_factory=list)

    # Location awareness
    last_location: Optional[Dict] = None

    def get_full_name(self) -> str:
        """Get user's full name."""
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name


# User session storage (in production, use Redis or database)
_user_sessions: Dict[int, UserSession] = {}


def get_user_session(telegram_user_id: int) -> Optional[UserSession]:
    """Get existing user session."""
    return _user_sessions.get(telegram_user_id)


def create_user_session(
    telegram_user_id: int,
    username: Optional[str] = None,
    first_name: str = "User",
    last_name: Optional[str] = None,
) -> UserSession:
    """Create a new user session."""
    import uuid

    session = UserSession(
        user_id=telegram_user_id,  # Use telegram ID as user ID for now
        telegram_user_id=telegram_user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        conversation_id=str(uuid.uuid4()),
    )
    _user_sessions[telegram_user_id] = session
    logger.info(f"Created session for Telegram user {telegram_user_id}")
    return session


def get_or_create_session(
    telegram_user_id: int,
    username: Optional[str] = None,
    first_name: str = "User",
    last_name: Optional[str] = None,
) -> UserSession:
    """Get existing session or create new one."""
    session = get_user_session(telegram_user_id)
    if session is None:
        session = create_user_session(
            telegram_user_id=telegram_user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
    return session


def update_user_mode(telegram_user_id: int, mode: str) -> bool:
    """Update user's AI mode (jarvis/ultron)."""
    session = get_user_session(telegram_user_id)
    if session and mode in ("jarvis", "ultron"):
        session.mode = mode
        logger.info(f"User {telegram_user_id} switched to {mode} mode")
        return True
    return False


# Voice settings per persona
VOICE_IDS = {
    "jarvis": "JBFqnCBsd6RMkjVDRZzb",  # George - British, warm, helpful
    "ultron": "ErXwobaYiN019PkySvjV",   # Antoni - Confident, authoritative
}

VOICE_SETTINGS = {
    "jarvis": {"stability": 0.7, "similarity_boost": 0.8, "style": 0.3},
    "ultron": {"stability": 0.8, "similarity_boost": 0.9, "style": 0.5},
}


# Command descriptions for /help
COMMAND_DESCRIPTIONS = {
    "/start": "Welcome message and initial setup",
    "/jarvis": "Switch to Jarvis mode - helpful assistant that asks permission",
    "/ultron": "Switch to Ultron mode - autonomous, efficient executor",
    "/home": "Smart home control panel with quick actions",
    "/schedule": "View and manage your scheduled actions",
    "/memory": "What does the AI remember about you?",
    "/status": "System status and recent activity",
    "/settings": "Configure your preferences",
    "/help": "Show this help message",
}


# Quick action keyboards
SMART_HOME_KEYBOARD = [
    [
        {"text": "Lights On", "callback_data": "home:lights:on"},
        {"text": "Lights Off", "callback_data": "home:lights:off"},
    ],
    [
        {"text": "Temp Up", "callback_data": "home:temp:up"},
        {"text": "Temp Down", "callback_data": "home:temp:down"},
    ],
    [
        {"text": "Movie Mode", "callback_data": "home:scene:movie"},
        {"text": "Night Mode", "callback_data": "home:scene:night"},
    ],
    [
        {"text": "Home Status", "callback_data": "home:status"},
        {"text": "All Off", "callback_data": "home:all:off"},
    ],
]

QUICK_ACTIONS_KEYBOARD = [
    [
        {"text": "Today's Schedule", "callback_data": "action:schedule:today"},
        {"text": "Set Reminder", "callback_data": "action:reminder:new"},
    ],
    [
        {"text": "Daily Brief", "callback_data": "action:brief:daily"},
        {"text": "Home Status", "callback_data": "action:home:status"},
    ],
]

SETTINGS_KEYBOARD = [
    [
        {"text": "Toggle Voice Replies", "callback_data": "settings:voice:toggle"},
    ],
    [
        {"text": "Clear Conversation", "callback_data": "settings:conversation:clear"},
    ],
    [
        {"text": "Switch Mode", "callback_data": "settings:mode:switch"},
    ],
]
