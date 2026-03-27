"""Telegram polling mode for local development.

Polls Telegram's getUpdates API instead of requiring webhooks.
Run alongside the FastAPI server: python telegram_poll.py

Usage:
    # Start the backend first:
    uvicorn app.main:app --port 8000

    # Then in another terminal:
    python telegram_poll.py
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys

# Add backend dir to path
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from app.api.telegram import (
    TelegramBot,
    TelegramUpdate,
    get_telegram_bot,
    process_update,
)
from app.api.telegram_config import get_telegram_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("telegram.poll")


async def poll_updates():
    """Long-poll Telegram for updates and process them."""
    settings = get_telegram_settings()
    if not settings.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not set in .env")
        return

    bot = get_telegram_bot()

    # Delete any existing webhook so polling works
    await bot.delete_webhook()
    logger.info("Webhook cleared, starting polling mode")

    # Get bot info
    try:
        me = await bot.get_me()
        logger.info(f"Bot started: @{me.get('username', '?')} ({me.get('first_name', '?')})")
    except Exception as e:
        logger.error(f"Failed to connect to Telegram: {e}")
        return

    offset = 0
    running = True

    def stop(*_):
        nonlocal running
        running = False
        logger.info("Shutting down...")

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    logger.info("Listening for messages... Send a message to your bot in Telegram!")

    while running:
        try:
            # Long polling with 30s timeout
            import httpx
            url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/getUpdates"
            params = {"offset": offset, "timeout": 30, "allowed_updates": ["message", "callback_query"]}

            async with httpx.AsyncClient(timeout=35) as client:
                resp = await client.get(url, params=params)
                data = resp.json()

            if not data.get("ok"):
                logger.error(f"Telegram API error: {data}")
                await asyncio.sleep(5)
                continue

            updates = data.get("result", [])
            for raw_update in updates:
                offset = raw_update["update_id"] + 1
                try:
                    update = TelegramUpdate(**raw_update)
                    # Log what we received
                    if update.message:
                        user = update.message.from_user
                        text = update.message.text or "[non-text]"
                        name = user.first_name if user else "?"
                        logger.info(f"Message from {name}: {text[:80]}")
                    elif update.callback_query:
                        logger.info(f"Callback: {update.callback_query.data or '?'}")

                    # Process using the same handler as webhook mode
                    try:
                        await process_update(update)
                    except Exception as e:
                        logger.error(f"Error in process_update: {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"Error parsing update: {e}", exc_info=True)

        except httpx.TimeoutException:
            # Normal — long poll timed out with no updates
            continue
        except Exception as e:
            logger.error(f"Polling error: {e}", exc_info=True)
            await asyncio.sleep(3)


if __name__ == "__main__":
    print("\n🤖 Nexus Telegram Bot — Polling Mode")
    print("=" * 40)
    print("Send a message to your bot in Telegram!\n")
    asyncio.run(poll_updates())
