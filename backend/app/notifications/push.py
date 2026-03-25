"""Push Notification System - Real-time alerts to your devices.

This module handles sending notifications via:
- WebSocket (for real-time in-app notifications)
- Web Push API (for browser notifications even when app is closed)
- Future: Mobile push (APNs, FCM)

This is how Jarvis gets your attention when something important happens.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import uuid4

logger = logging.getLogger(__name__)


class NotificationChannel(str, Enum):
    """Notification delivery channels."""
    WEBSOCKET = "websocket"     # Real-time in-app
    WEB_PUSH = "web_push"       # Browser push notification
    EMAIL = "email"             # Email notification
    SMS = "sms"                 # SMS (future)


class NotificationPriority(str, Enum):
    """Notification priority for filtering."""
    CRITICAL = "critical"   # Always deliver, with sound
    HIGH = "high"           # Deliver immediately
    NORMAL = "normal"       # Deliver, can batch
    LOW = "low"             # Only in digest


@dataclass
class Notification:
    """A notification to be sent to the user."""
    id: str
    title: str
    body: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    channel: NotificationChannel = NotificationChannel.WEBSOCKET

    # Optional fields
    icon: str = "🤖"
    action_url: Optional[str] = None
    actions: List[Dict[str, str]] = None
    data: Dict[str, Any] = None

    # Timestamps
    created_at: str = None
    delivered_at: Optional[str] = None
    read_at: Optional[str] = None

    def __post_init__(self):
        if self.actions is None:
            self.actions = []
        if self.data is None:
            self.data = {}
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "priority": self.priority.value,
            "channel": self.channel.value,
            "icon": self.icon,
            "action_url": self.action_url,
            "actions": self.actions,
            "data": self.data,
            "created_at": self.created_at,
            "delivered_at": self.delivered_at,
            "read_at": self.read_at,
        }

    def to_websocket_message(self) -> str:
        """Format for WebSocket delivery."""
        return json.dumps({
            "type": "notification",
            "payload": self.to_dict(),
        })


class NotificationManager:
    """Manages notification delivery across channels.

    Handles:
    - WebSocket connections for real-time delivery
    - Notification history
    - Delivery preferences
    - Batching for low-priority notifications
    """

    def __init__(self):
        self.websocket_connections: Set[Any] = set()
        self.notification_history: List[Notification] = []
        self.pending_batch: List[Notification] = []
        self._handlers: Dict[NotificationChannel, Callable] = {}

        # Register default handlers
        self._handlers[NotificationChannel.WEBSOCKET] = self._deliver_websocket

    def register_handler(self, channel: NotificationChannel, handler: Callable):
        """Register a delivery handler for a channel."""
        self._handlers[channel] = handler

    def add_websocket(self, ws):
        """Add a WebSocket connection for real-time notifications."""
        self.websocket_connections.add(ws)
        logger.info(f"WebSocket connected. Total: {len(self.websocket_connections)}")

    def remove_websocket(self, ws):
        """Remove a WebSocket connection."""
        self.websocket_connections.discard(ws)
        logger.info(f"WebSocket disconnected. Total: {len(self.websocket_connections)}")

    async def send(
        self,
        title: str,
        body: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        channel: NotificationChannel = NotificationChannel.WEBSOCKET,
        icon: str = "🤖",
        action_url: Optional[str] = None,
        actions: List[Dict[str, str]] = None,
        data: Dict[str, Any] = None,
    ) -> Notification:
        """Send a notification."""
        notification = Notification(
            id=str(uuid4())[:12],
            title=title,
            body=body,
            priority=priority,
            channel=channel,
            icon=icon,
            action_url=action_url,
            actions=actions or [],
            data=data or {},
        )

        # Add to history
        self.notification_history.append(notification)

        # Trim history
        if len(self.notification_history) > 1000:
            self.notification_history = self.notification_history[-500:]

        # Deliver based on priority
        if priority in [NotificationPriority.CRITICAL, NotificationPriority.HIGH]:
            await self._deliver_immediately(notification)
        elif priority == NotificationPriority.NORMAL:
            await self._deliver_immediately(notification)
        else:
            # Batch low priority
            self.pending_batch.append(notification)
            if len(self.pending_batch) >= 5:
                await self._deliver_batch()

        return notification

    async def _deliver_immediately(self, notification: Notification):
        """Deliver a notification immediately."""
        handler = self._handlers.get(notification.channel)
        if handler:
            try:
                await handler(notification)
                notification.delivered_at = datetime.utcnow().isoformat()
            except Exception as e:
                logger.error(f"Notification delivery failed: {e}")

    async def _deliver_batch(self):
        """Deliver batched notifications."""
        if not self.pending_batch:
            return

        # Create summary notification
        count = len(self.pending_batch)
        summary = Notification(
            id=str(uuid4())[:12],
            title=f"{count} new updates",
            body="; ".join(n.title for n in self.pending_batch[:3]) + ("..." if count > 3 else ""),
            priority=NotificationPriority.LOW,
            icon="📋",
            data={"batch": [n.to_dict() for n in self.pending_batch]},
        )

        await self._deliver_immediately(summary)
        self.pending_batch = []

    async def _deliver_websocket(self, notification: Notification):
        """Deliver via WebSocket."""
        if not self.websocket_connections:
            logger.debug("No WebSocket connections for notification")
            return

        message = notification.to_websocket_message()

        # Send to all connections
        disconnected = set()
        for ws in self.websocket_connections:
            try:
                await ws.send_text(message)
            except Exception as e:
                logger.warning(f"WebSocket send failed: {e}")
                disconnected.add(ws)

        # Clean up disconnected
        self.websocket_connections -= disconnected

    def get_unread(self) -> List[Notification]:
        """Get unread notifications."""
        return [n for n in self.notification_history if n.read_at is None]

    def mark_read(self, notification_id: str):
        """Mark a notification as read."""
        for n in self.notification_history:
            if n.id == notification_id:
                n.read_at = datetime.utcnow().isoformat()
                return

    def mark_all_read(self):
        """Mark all notifications as read."""
        now = datetime.utcnow().isoformat()
        for n in self.notification_history:
            if n.read_at is None:
                n.read_at = now


# Global notification manager
_notification_manager: Optional[NotificationManager] = None


def get_notification_manager() -> NotificationManager:
    """Get the global notification manager."""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager


# Convenience function
async def notify(
    title: str,
    body: str,
    priority: NotificationPriority = NotificationPriority.NORMAL,
    **kwargs,
) -> Notification:
    """Send a notification."""
    return await get_notification_manager().send(title, body, priority, **kwargs)


# Integration with background monitor
def setup_monitor_notifications():
    """Set up notifications for background monitor alerts."""
    from app.daemon.monitor import get_background_monitor, Alert, AlertPriority

    monitor = get_background_monitor()

    async def on_alert(alert: Alert):
        """Handle background monitor alerts."""
        # Map alert priority to notification priority
        priority_map = {
            AlertPriority.CRITICAL: NotificationPriority.CRITICAL,
            AlertPriority.HIGH: NotificationPriority.HIGH,
            AlertPriority.MEDIUM: NotificationPriority.NORMAL,
            AlertPriority.LOW: NotificationPriority.LOW,
            AlertPriority.INFO: NotificationPriority.LOW,
        }

        # Send notification
        await notify(
            title=alert.title,
            body=alert.message,
            priority=priority_map.get(alert.priority, NotificationPriority.NORMAL),
            icon="⚡" if alert.action_required else "ℹ️",
            data={"alert_id": alert.id, "category": alert.category.value},
        )

    # Register callback (sync wrapper for async)
    def sync_on_alert(alert: Alert):
        asyncio.create_task(on_alert(alert))

    monitor.on_alert(sync_on_alert)
    logger.info("Monitor notifications configured")
