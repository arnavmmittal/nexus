"""Push Notification API Endpoints.

Handles browser push notification subscriptions and sending test notifications.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.notifications import get_web_push_manager

logger = logging.getLogger(__name__)
router = APIRouter()


# ============ Request/Response Models ============

class PushSubscriptionKeys(BaseModel):
    """Keys required for push subscription."""
    p256dh: str = Field(..., description="Public key for encryption")
    auth: str = Field(..., description="Authentication secret")


class PushSubscribeRequest(BaseModel):
    """Request to subscribe to push notifications."""
    endpoint: str = Field(..., description="Push service endpoint URL")
    keys: PushSubscriptionKeys = Field(..., description="Encryption keys")
    expirationTime: Optional[int] = Field(None, description="Subscription expiration time")


class PushUnsubscribeRequest(BaseModel):
    """Request to unsubscribe from push notifications."""
    endpoint: str = Field(..., description="Push service endpoint URL to remove")


class PushNotificationRequest(BaseModel):
    """Request to send a push notification."""
    title: str = Field(..., description="Notification title")
    body: str = Field(..., description="Notification body text")
    icon: str = Field("/icons/icon-192.png", description="Icon URL")
    tag: str = Field("nexus-notification", description="Notification tag")
    data: Dict[str, Any] = Field(default_factory=dict, description="Additional data")
    actions: List[Dict[str, str]] = Field(default_factory=list, description="Action buttons")
    priority: str = Field("normal", description="Priority level")


class VAPIDPublicKeyResponse(BaseModel):
    """Response containing VAPID public key."""
    publicKey: Optional[str] = Field(None, description="VAPID public key for subscription")
    configured: bool = Field(..., description="Whether push is configured")


class PushStatusResponse(BaseModel):
    """Response for push notification status."""
    configured: bool = Field(..., description="Whether push is configured")
    subscriptionCount: int = Field(..., description="Number of active subscriptions")


class PushResultResponse(BaseModel):
    """Response for push notification result."""
    success: int = Field(..., description="Number of successful sends")
    failed: int = Field(..., description="Number of failed sends")
    error: Optional[str] = Field(None, description="Error message if any")


# ============ Endpoints ============

@router.get("/vapid-public-key", response_model=VAPIDPublicKeyResponse)
async def get_vapid_public_key():
    """Get the VAPID public key for client-side push subscription.

    The client needs this key to subscribe to push notifications.
    """
    manager = get_web_push_manager()

    return VAPIDPublicKeyResponse(
        publicKey=manager.public_key,
        configured=manager.is_configured,
    )


@router.get("/status", response_model=PushStatusResponse)
async def get_push_status():
    """Get push notification service status."""
    manager = get_web_push_manager()

    return PushStatusResponse(
        configured=manager.is_configured,
        subscriptionCount=len(manager.get_subscriptions()),
    )


@router.post("/subscribe")
async def subscribe_push(request: PushSubscribeRequest):
    """Register a browser for push notifications.

    Called when user enables push notifications in the browser.
    """
    manager = get_web_push_manager()

    if not manager.is_configured:
        raise HTTPException(
            status_code=503,
            detail="Push notifications are not configured on the server"
        )

    try:
        subscription = manager.add_subscription(
            endpoint=request.endpoint,
            keys={
                "p256dh": request.keys.p256dh,
                "auth": request.keys.auth,
            },
            user_id="default",  # TODO: Get from auth
        )

        return {
            "status": "subscribed",
            "endpoint": subscription.endpoint[:50] + "...",
        }

    except Exception as e:
        logger.error(f"Failed to add push subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/unsubscribe")
async def unsubscribe_push(request: PushUnsubscribeRequest):
    """Remove a push notification subscription.

    Called when user disables push notifications.
    """
    manager = get_web_push_manager()

    removed = manager.remove_subscription(request.endpoint)

    if removed:
        return {"status": "unsubscribed"}
    else:
        return {"status": "not_found"}


@router.post("/test", response_model=PushResultResponse)
async def send_test_notification():
    """Send a test push notification to all subscribed browsers.

    Useful for testing that push notifications are working.
    """
    manager = get_web_push_manager()

    if not manager.is_configured:
        raise HTTPException(
            status_code=503,
            detail="Push notifications are not configured"
        )

    result = await manager.send_test()

    return PushResultResponse(
        success=result.get("success", 0),
        failed=result.get("failed", 0),
        error=result.get("error"),
    )


@router.post("/send", response_model=PushResultResponse)
async def send_notification(request: PushNotificationRequest):
    """Send a custom push notification.

    Sends to all subscribed browsers.
    """
    manager = get_web_push_manager()

    if not manager.is_configured:
        raise HTTPException(
            status_code=503,
            detail="Push notifications are not configured"
        )

    result = await manager.send_notification(
        title=request.title,
        body=request.body,
        icon=request.icon,
        tag=request.tag,
        data=request.data,
        actions=request.actions,
        priority=request.priority,
    )

    return PushResultResponse(
        success=result.get("success", 0),
        failed=result.get("failed", 0),
        error=result.get("error"),
    )


@router.get("/subscriptions")
async def list_subscriptions():
    """List all active push subscriptions (admin endpoint)."""
    manager = get_web_push_manager()

    subscriptions = manager.get_subscriptions()

    return {
        "count": len(subscriptions),
        "subscriptions": [
            {
                "endpoint_prefix": s.endpoint[:60] + "..." if len(s.endpoint) > 60 else s.endpoint,
                "user_id": s.user_id,
                "created_at": s.created_at,
            }
            for s in subscriptions
        ],
    }
