"""Web Push Notification Support - Send push notifications to browsers.

This module handles Web Push notifications using the VAPID protocol.
Allows Jarvis to send notifications even when the browser is closed.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import pywebpush
try:
    from pywebpush import webpush, WebPushException
    WEBPUSH_AVAILABLE = True
except ImportError:
    WEBPUSH_AVAILABLE = False
    logger.warning("pywebpush not installed. Web push notifications disabled.")


@dataclass
class PushSubscription:
    """Browser push subscription."""
    endpoint: str
    keys: Dict[str, str]  # Contains 'p256dh' and 'auth' keys
    user_id: str = "default"
    created_at: str = None
    user_agent: str = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "keys": self.keys,
        }


class WebPushManager:
    """Manages web push notifications via VAPID protocol.

    Handles:
    - VAPID key generation and storage
    - Subscription management
    - Sending push notifications to browsers
    """

    def __init__(self):
        self._subscriptions: Dict[str, PushSubscription] = {}
        self._vapid_private_key: Optional[str] = None
        self._vapid_public_key: Optional[str] = None
        self._vapid_claims: Dict[str, str] = {}
        self._storage_path = Path("data/push_subscriptions.json")

        # Load VAPID keys from environment or generate
        self._load_vapid_keys()

        # Load saved subscriptions
        self._load_subscriptions()

    def _load_vapid_keys(self):
        """Load VAPID keys from environment variables or config file."""
        # Try environment variables first
        self._vapid_private_key = os.getenv("VAPID_PRIVATE_KEY")
        self._vapid_public_key = os.getenv("VAPID_PUBLIC_KEY")
        vapid_email = os.getenv("VAPID_EMAIL", "admin@nexus.local")

        # Try config file if not in environment
        if not self._vapid_private_key or not self._vapid_public_key:
            key_file = Path("data/vapid_keys.json")
            if key_file.exists():
                try:
                    with open(key_file) as f:
                        keys = json.load(f)
                        self._vapid_private_key = keys.get("private_key")
                        self._vapid_public_key = keys.get("public_key")
                except Exception as e:
                    logger.error(f"Failed to load VAPID keys: {e}")

        # Generate keys if still missing
        if not self._vapid_private_key or not self._vapid_public_key:
            if WEBPUSH_AVAILABLE:
                self._generate_vapid_keys()
            else:
                logger.warning("Cannot generate VAPID keys - pywebpush not installed")

        # Set up VAPID claims
        if self._vapid_private_key:
            self._vapid_claims = {
                "sub": f"mailto:{vapid_email}"
            }

    def _generate_vapid_keys(self):
        """Generate new VAPID key pair."""
        try:
            from py_vapid import Vapid

            vapid = Vapid()
            vapid.generate_keys()

            # Get keys in the format needed
            self._vapid_private_key = vapid.private_key.private_bytes(
                encoding=vapid.private_key_encoding,
                format=vapid.private_key_format,
                encryption_algorithm=vapid.private_key_encryption
            ).decode('utf-8')

            self._vapid_public_key = vapid.public_key_urlsafe_base64

            # Save keys for persistence
            key_file = Path("data/vapid_keys.json")
            key_file.parent.mkdir(parents=True, exist_ok=True)

            with open(key_file, 'w') as f:
                json.dump({
                    "private_key": self._vapid_private_key,
                    "public_key": self._vapid_public_key,
                }, f)

            logger.info("Generated new VAPID keys")

        except ImportError:
            # Try alternative method with cryptography
            try:
                from cryptography.hazmat.primitives.asymmetric import ec
                from cryptography.hazmat.backends import default_backend
                from cryptography.hazmat.primitives import serialization
                import base64

                # Generate EC key pair
                private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())

                # Get private key in PEM format
                self._vapid_private_key = private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ).decode('utf-8')

                # Get public key in uncompressed format and base64url encode
                public_key = private_key.public_key()
                public_bytes = public_key.public_bytes(
                    encoding=serialization.Encoding.X962,
                    format=serialization.PublicFormat.UncompressedPoint
                )
                self._vapid_public_key = base64.urlsafe_b64encode(public_bytes).decode('utf-8').rstrip('=')

                # Save keys
                key_file = Path("data/vapid_keys.json")
                key_file.parent.mkdir(parents=True, exist_ok=True)

                with open(key_file, 'w') as f:
                    json.dump({
                        "private_key": self._vapid_private_key,
                        "public_key": self._vapid_public_key,
                    }, f)

                logger.info("Generated new VAPID keys using cryptography")

            except Exception as e:
                logger.error(f"Failed to generate VAPID keys: {e}")

    def _load_subscriptions(self):
        """Load saved subscriptions from file."""
        if self._storage_path.exists():
            try:
                with open(self._storage_path) as f:
                    data = json.load(f)
                    for sub_data in data:
                        sub = PushSubscription(**sub_data)
                        self._subscriptions[sub.endpoint] = sub
                logger.info(f"Loaded {len(self._subscriptions)} push subscriptions")
            except Exception as e:
                logger.error(f"Failed to load subscriptions: {e}")

    def _save_subscriptions(self):
        """Save subscriptions to file."""
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._storage_path, 'w') as f:
                data = [asdict(sub) for sub in self._subscriptions.values()]
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Failed to save subscriptions: {e}")

    @property
    def public_key(self) -> Optional[str]:
        """Get the VAPID public key for client-side subscription."""
        return self._vapid_public_key

    @property
    def is_configured(self) -> bool:
        """Check if web push is properly configured."""
        return bool(
            WEBPUSH_AVAILABLE and
            self._vapid_private_key and
            self._vapid_public_key
        )

    def add_subscription(
        self,
        endpoint: str,
        keys: Dict[str, str],
        user_id: str = "default",
        user_agent: str = None,
    ) -> PushSubscription:
        """Add or update a push subscription."""
        subscription = PushSubscription(
            endpoint=endpoint,
            keys=keys,
            user_id=user_id,
            user_agent=user_agent,
        )
        self._subscriptions[endpoint] = subscription
        self._save_subscriptions()
        logger.info(f"Added push subscription for user {user_id}")
        return subscription

    def remove_subscription(self, endpoint: str) -> bool:
        """Remove a push subscription."""
        if endpoint in self._subscriptions:
            del self._subscriptions[endpoint]
            self._save_subscriptions()
            logger.info(f"Removed push subscription")
            return True
        return False

    def get_subscriptions(self, user_id: str = None) -> List[PushSubscription]:
        """Get all subscriptions, optionally filtered by user."""
        subs = list(self._subscriptions.values())
        if user_id:
            subs = [s for s in subs if s.user_id == user_id]
        return subs

    async def send_notification(
        self,
        title: str,
        body: str,
        icon: str = "/icons/icon-192.png",
        badge: str = "/icons/badge-72.png",
        tag: str = "nexus-notification",
        data: Dict[str, Any] = None,
        actions: List[Dict[str, str]] = None,
        priority: str = "normal",
        user_id: str = None,
    ) -> Dict[str, Any]:
        """Send a push notification to subscribed browsers.

        Args:
            title: Notification title
            body: Notification body text
            icon: URL to notification icon
            badge: URL to badge icon (shown in status bar)
            tag: Tag for notification grouping
            data: Additional data to send with notification
            actions: List of action buttons [{action, title, icon}]
            priority: 'critical', 'high', 'normal', or 'low'
            user_id: Send to specific user only (None = all)

        Returns:
            Dict with success count and any errors
        """
        if not self.is_configured:
            return {"success": 0, "failed": 0, "error": "Web push not configured"}

        subscriptions = self.get_subscriptions(user_id)
        if not subscriptions:
            return {"success": 0, "failed": 0, "error": "No subscriptions"}

        payload = json.dumps({
            "title": title,
            "body": body,
            "icon": icon,
            "badge": badge,
            "tag": tag,
            "data": data or {},
            "actions": actions or [],
            "priority": priority,
            "timestamp": datetime.utcnow().isoformat(),
        })

        success_count = 0
        failed_count = 0
        errors = []
        expired_endpoints = []

        for subscription in subscriptions:
            try:
                webpush(
                    subscription_info=subscription.to_dict(),
                    data=payload,
                    vapid_private_key=self._vapid_private_key,
                    vapid_claims=self._vapid_claims,
                    timeout=10,
                )
                success_count += 1

            except WebPushException as e:
                failed_count += 1

                # Check if subscription expired
                if e.response and e.response.status_code in [404, 410]:
                    expired_endpoints.append(subscription.endpoint)
                    logger.info(f"Push subscription expired, removing")
                else:
                    errors.append(str(e))
                    logger.error(f"Push notification failed: {e}")

            except Exception as e:
                failed_count += 1
                errors.append(str(e))
                logger.error(f"Push notification error: {e}")

        # Remove expired subscriptions
        for endpoint in expired_endpoints:
            self.remove_subscription(endpoint)

        return {
            "success": success_count,
            "failed": failed_count,
            "errors": errors[:5] if errors else None,  # Limit error list
        }

    async def send_test(self, user_id: str = None) -> Dict[str, Any]:
        """Send a test notification."""
        return await self.send_notification(
            title="Test Notification",
            body="If you see this, push notifications are working!",
            icon="/icons/icon-192.png",
            tag="nexus-test",
            data={"type": "test"},
            user_id=user_id,
        )


# Global web push manager
_web_push_manager: Optional[WebPushManager] = None


def get_web_push_manager() -> WebPushManager:
    """Get the global web push manager."""
    global _web_push_manager
    if _web_push_manager is None:
        _web_push_manager = WebPushManager()
    return _web_push_manager
