"""Notifications Module - Real-time alert delivery.

This module handles sending notifications through multiple channels:
- WebSocket: Real-time in-app notifications
- Web Push: Browser push notifications (even when app is closed)
- Email: Important alerts and digests (future)
- SMS: Critical alerts (future)

Integrates with the background monitor to surface alerts to users.
"""

from app.notifications.push import (
    Notification,
    NotificationChannel,
    NotificationPriority,
    NotificationManager,
    get_notification_manager,
    notify,
    setup_monitor_notifications,
)

__all__ = [
    "Notification",
    "NotificationChannel",
    "NotificationPriority",
    "NotificationManager",
    "get_notification_manager",
    "notify",
    "setup_monitor_notifications",
]
