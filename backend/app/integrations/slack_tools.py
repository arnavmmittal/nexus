"""Slack integration tools.

Provides tools for:
- Sending messages
- Reading channels
- Managing notifications
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")


async def send_slack_message(
    channel: str,
    message: str,
    thread_ts: str = "",
) -> str:
    """Send a message to a Slack channel."""
    logger.info(f"Sending to Slack #{channel}: {message[:50]}...")
    
    if not SLACK_BOT_TOKEN:
        return json.dumps({
            "status": "not_configured",
            "message": "Slack integration not configured.",
            "instructions": [
                "1. Create a Slack app at https://api.slack.com/apps",
                "2. Add bot scopes: chat:write, channels:read, channels:history",
                "3. Install to workspace",
                "4. Set SLACK_BOT_TOKEN in .env",
            ],
            "draft": {
                "channel": channel,
                "message": message,
            }
        }, indent=2)
    
    import aiohttp
    
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://slack.com/api/chat.postMessage"
            headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}
            data = {
                "channel": channel,
                "text": message,
            }
            if thread_ts:
                data["thread_ts"] = thread_ts
                
            async with session.post(url, headers=headers, json=data) as resp:
                result = await resp.json()
                return json.dumps({
                    "status": "sent" if result.get("ok") else "error",
                    "result": result,
                }, indent=2)
                
    except Exception as e:
        return json.dumps({"error": str(e)})


async def list_slack_channels() -> str:
    """List available Slack channels."""
    
    if not SLACK_BOT_TOKEN:
        return json.dumps({
            "status": "not_configured",
            "message": "Slack integration not configured.",
        }, indent=2)
    
    import aiohttp
    
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://slack.com/api/conversations.list"
            headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}
            
            async with session.get(url, headers=headers) as resp:
                result = await resp.json()
                if result.get("ok"):
                    channels = [
                        {"name": c["name"], "id": c["id"]}
                        for c in result.get("channels", [])
                    ]
                    return json.dumps({
                        "channels": channels,
                        "total": len(channels),
                    }, indent=2)
                return json.dumps({"error": result.get("error")})
                
    except Exception as e:
        return json.dumps({"error": str(e)})


async def read_slack_channel(
    channel: str,
    limit: int = 10,
) -> str:
    """Read recent messages from a Slack channel."""
    
    if not SLACK_BOT_TOKEN:
        return json.dumps({
            "status": "not_configured",
            "message": "Slack integration not configured.",
        }, indent=2)
    
    import aiohttp
    
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://slack.com/api/conversations.history"
            headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}
            params = {"channel": channel, "limit": limit}
            
            async with session.get(url, headers=headers, params=params) as resp:
                result = await resp.json()
                if result.get("ok"):
                    messages = [
                        {
                            "text": m.get("text", ""),
                            "user": m.get("user", ""),
                            "ts": m.get("ts", ""),
                        }
                        for m in result.get("messages", [])
                    ]
                    return json.dumps({
                        "channel": channel,
                        "messages": messages,
                    }, indent=2)
                return json.dumps({"error": result.get("error")})
                
    except Exception as e:
        return json.dumps({"error": str(e)})


async def send_slack_dm(
    user: str,
    message: str,
) -> str:
    """Send a direct message to a Slack user."""
    logger.info(f"Sending DM to {user}")
    
    if not SLACK_BOT_TOKEN:
        return json.dumps({
            "status": "not_configured",
            "message": "Slack integration not configured.",
        }, indent=2)
    
    import aiohttp
    
    try:
        async with aiohttp.ClientSession() as session:
            # First, open a DM channel
            url = "https://slack.com/api/conversations.open"
            headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}
            
            async with session.post(url, headers=headers, json={"users": user}) as resp:
                result = await resp.json()
                if not result.get("ok"):
                    return json.dumps({"error": result.get("error")})
                
                channel_id = result["channel"]["id"]
                
            # Then send the message
            url = "https://slack.com/api/chat.postMessage"
            data = {"channel": channel_id, "text": message}
            
            async with session.post(url, headers=headers, json=data) as resp:
                result = await resp.json()
                return json.dumps({
                    "status": "sent" if result.get("ok") else "error",
                    "result": result,
                }, indent=2)
                
    except Exception as e:
        return json.dumps({"error": str(e)})


SLACK_TOOLS = [
    {
        "name": "send_slack_message",
        "description": "Send a message to a Slack channel.",
        "input_schema": {
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "description": "Channel name or ID"
                },
                "message": {
                    "type": "string",
                    "description": "Message to send"
                },
                "thread_ts": {
                    "type": "string",
                    "description": "Thread timestamp for replies"
                }
            },
            "required": ["channel", "message"]
        }
    },
    {
        "name": "list_slack_channels",
        "description": "List available Slack channels.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "read_slack_channel",
        "description": "Read recent messages from a Slack channel.",
        "input_schema": {
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "description": "Channel name or ID"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of messages to read"
                }
            },
            "required": ["channel"]
        }
    },
    {
        "name": "send_slack_dm",
        "description": "Send a direct message to a Slack user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user": {
                    "type": "string",
                    "description": "User ID or email"
                },
                "message": {
                    "type": "string",
                    "description": "Message to send"
                }
            },
            "required": ["user", "message"]
        }
    },
]
