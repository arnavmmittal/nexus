"""Telegram Bot Integration for Nexus AI.

This module provides a Telegram bot interface for chatting with Jarvis/Ultron
from anywhere. It supports text, voice, images, documents, and location messages.

Features:
- Text messages: Processed by AI engine with full context
- Voice messages: Transcribed with Whisper, optionally replied with voice
- Images: Analyzed using Claude's vision capabilities
- Documents: Processed for extraction and summarization
- Location: Stored for presence awareness
- Inline keyboards: Rich interactions for smart home and quick actions
- Proactive messages: Scheduled briefings and alerts

Usage:
    # Include in your FastAPI app
    from app.api.telegram import router as telegram_router
    app.include_router(telegram_router, prefix="/api/v1/telegram", tags=["telegram"])
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import io
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.telegram_config import (
    COMMAND_DESCRIPTIONS,
    QUICK_ACTIONS_KEYBOARD,
    SETTINGS_KEYBOARD,
    SMART_HOME_KEYBOARD,
    VOICE_IDS,
    VOICE_SETTINGS,
    UserSession,
    get_or_create_session,
    get_telegram_settings,
    get_user_session,
    update_user_mode,
)
from app.core.config import settings
from app.core.database import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter()


# ============ Pydantic Models for Telegram API ============


class TelegramUser(BaseModel):
    """Telegram user object."""

    id: int
    is_bot: bool = False
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None


class TelegramChat(BaseModel):
    """Telegram chat object."""

    id: int
    type: str  # private, group, supergroup, channel
    title: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class TelegramVoice(BaseModel):
    """Telegram voice message object."""

    file_id: str
    file_unique_id: str
    duration: int
    mime_type: Optional[str] = None
    file_size: Optional[int] = None


class TelegramPhoto(BaseModel):
    """Telegram photo object (represents one size of a photo)."""

    file_id: str
    file_unique_id: str
    width: int
    height: int
    file_size: Optional[int] = None


class TelegramDocument(BaseModel):
    """Telegram document object."""

    file_id: str
    file_unique_id: str
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None


class TelegramLocation(BaseModel):
    """Telegram location object."""

    latitude: float
    longitude: float
    horizontal_accuracy: Optional[float] = None


class TelegramCallbackQuery(BaseModel):
    """Telegram callback query from inline keyboard."""

    id: str
    from_user: TelegramUser = Field(alias="from")
    chat_instance: str
    message: Optional[Dict[str, Any]] = None
    data: Optional[str] = None

    class Config:
        populate_by_name = True


class TelegramMessage(BaseModel):
    """Telegram message object."""

    message_id: int
    date: int
    chat: TelegramChat
    from_user: Optional[TelegramUser] = Field(None, alias="from")
    text: Optional[str] = None
    voice: Optional[TelegramVoice] = None
    photo: Optional[List[TelegramPhoto]] = None
    document: Optional[TelegramDocument] = None
    location: Optional[TelegramLocation] = None
    caption: Optional[str] = None
    reply_to_message: Optional[Dict[str, Any]] = None

    class Config:
        populate_by_name = True


class TelegramUpdate(BaseModel):
    """Telegram update object (webhook payload)."""

    update_id: int
    message: Optional[TelegramMessage] = None
    edited_message: Optional[TelegramMessage] = None
    callback_query: Optional[TelegramCallbackQuery] = None


# ============ TelegramBot Class ============


class TelegramBot:
    """Telegram Bot API client for sending messages and handling interactions."""

    BASE_URL = "https://api.telegram.org"

    def __init__(self, token: Optional[str] = None):
        """Initialize the Telegram bot.

        Args:
            token: Bot token. Falls back to settings if not provided.
        """
        tg_settings = get_telegram_settings()
        self.token = token or tg_settings.telegram_bot_token

        if not self.token:
            logger.warning(
                "Telegram bot token not configured. "
                "Set TELEGRAM_BOT_TOKEN environment variable."
            )

        self._client: Optional[httpx.AsyncClient] = None

    @property
    def api_url(self) -> str:
        """Get the base API URL for this bot."""
        return f"{self.BASE_URL}/bot{self.token}"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a request to the Telegram API.

        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint
            data: JSON data to send
            files: Files to upload

        Returns:
            API response data

        Raises:
            HTTPException: If the request fails
        """
        if not self.token:
            raise HTTPException(
                status_code=503,
                detail="Telegram bot not configured"
            )

        url = f"{self.api_url}/{endpoint}"
        client = await self._get_client()

        try:
            if files:
                # Multipart form data for file uploads
                response = await client.post(url, data=data or {}, files=files)
            elif method.upper() == "GET":
                response = await client.get(url, params=data)
            else:
                response = await client.post(url, json=data)

            response.raise_for_status()
            result = response.json()

            if not result.get("ok"):
                error_desc = result.get("description", "Unknown error")
                logger.error(f"Telegram API error: {error_desc}")
                raise HTTPException(status_code=400, detail=error_desc)

            return result.get("result", {})

        except httpx.HTTPStatusError as e:
            logger.error(f"Telegram API HTTP error: {e}")
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except Exception as e:
            logger.error(f"Telegram API error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
        parse_mode: str = "HTML",
        reply_to_message_id: Optional[int] = None,
        disable_notification: bool = False,
    ) -> Dict[str, Any]:
        """Send a text message to a chat.

        Args:
            chat_id: Target chat ID
            text: Message text
            reply_markup: Inline keyboard or reply keyboard
            parse_mode: Text parsing mode (HTML, Markdown, MarkdownV2)
            reply_to_message_id: Message to reply to
            disable_notification: Send silently

        Returns:
            Sent message data
        """
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_notification": disable_notification,
        }

        if reply_markup:
            data["reply_markup"] = reply_markup

        if reply_to_message_id:
            data["reply_to_message_id"] = reply_to_message_id

        return await self._request("POST", "sendMessage", data)

    async def send_voice(
        self,
        chat_id: int,
        voice_bytes: bytes,
        caption: Optional[str] = None,
        reply_to_message_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Send a voice message to a chat.

        Args:
            chat_id: Target chat ID
            voice_bytes: Voice audio data (OGG with Opus codec preferred)
            caption: Optional caption
            reply_to_message_id: Message to reply to

        Returns:
            Sent message data
        """
        data = {"chat_id": str(chat_id)}

        if caption:
            data["caption"] = caption

        if reply_to_message_id:
            data["reply_to_message_id"] = str(reply_to_message_id)

        files = {"voice": ("voice.ogg", voice_bytes, "audio/ogg")}

        return await self._request("POST", "sendVoice", data=data, files=files)

    async def send_audio(
        self,
        chat_id: int,
        audio_bytes: bytes,
        title: str = "Voice Response",
        reply_to_message_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Send an audio file to a chat.

        Args:
            chat_id: Target chat ID
            audio_bytes: Audio file data (MP3 format)
            title: Audio title
            reply_to_message_id: Message to reply to

        Returns:
            Sent message data
        """
        data = {"chat_id": str(chat_id), "title": title}

        if reply_to_message_id:
            data["reply_to_message_id"] = str(reply_to_message_id)

        files = {"audio": ("response.mp3", audio_bytes, "audio/mpeg")}

        return await self._request("POST", "sendAudio", data=data, files=files)

    async def send_photo(
        self,
        chat_id: int,
        photo: Union[bytes, str],
        caption: Optional[str] = None,
        reply_to_message_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Send a photo to a chat.

        Args:
            chat_id: Target chat ID
            photo: Photo data (bytes) or file_id (str)
            caption: Photo caption
            reply_to_message_id: Message to reply to

        Returns:
            Sent message data
        """
        data = {"chat_id": str(chat_id)}

        if caption:
            data["caption"] = caption

        if reply_to_message_id:
            data["reply_to_message_id"] = str(reply_to_message_id)

        if isinstance(photo, bytes):
            files = {"photo": ("photo.jpg", photo, "image/jpeg")}
            return await self._request("POST", "sendPhoto", data=data, files=files)
        else:
            data["photo"] = photo
            return await self._request("POST", "sendPhoto", data)

    async def send_typing_action(self, chat_id: int) -> bool:
        """Send typing indicator to show "bot is typing..."

        Args:
            chat_id: Target chat ID

        Returns:
            True if successful
        """
        try:
            await self._request("POST", "sendChatAction", {
                "chat_id": chat_id,
                "action": "typing"
            })
            return True
        except Exception:
            return False

    async def send_voice_recording_action(self, chat_id: int) -> bool:
        """Send voice recording indicator.

        Args:
            chat_id: Target chat ID

        Returns:
            True if successful
        """
        try:
            await self._request("POST", "sendChatAction", {
                "chat_id": chat_id,
                "action": "record_voice"
            })
            return True
        except Exception:
            return False

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: Optional[str] = None,
        show_alert: bool = False,
    ) -> bool:
        """Answer a callback query from inline keyboard.

        Args:
            callback_query_id: Query ID to answer
            text: Notification text to show
            show_alert: Show as alert popup instead of notification

        Returns:
            True if successful
        """
        data = {"callback_query_id": callback_query_id}

        if text:
            data["text"] = text
            data["show_alert"] = show_alert

        try:
            await self._request("POST", "answerCallbackQuery", data)
            return True
        except Exception:
            return False

    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
        parse_mode: str = "HTML",
    ) -> Dict[str, Any]:
        """Edit the text of a message.

        Args:
            chat_id: Chat containing the message
            message_id: Message to edit
            text: New text
            reply_markup: New inline keyboard
            parse_mode: Text parsing mode

        Returns:
            Edited message data
        """
        data = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode,
        }

        if reply_markup:
            data["reply_markup"] = reply_markup

        return await self._request("POST", "editMessageText", data)

    async def get_file(self, file_id: str) -> Dict[str, Any]:
        """Get file info for downloading.

        Args:
            file_id: Telegram file ID

        Returns:
            File info with file_path
        """
        return await self._request("POST", "getFile", {"file_id": file_id})

    async def download_file(self, file_path: str) -> bytes:
        """Download a file from Telegram servers.

        Args:
            file_path: Path from get_file response

        Returns:
            File data as bytes
        """
        url = f"{self.BASE_URL}/file/bot{self.token}/{file_path}"
        client = await self._get_client()

        response = await client.get(url)
        response.raise_for_status()
        return response.content

    async def set_webhook(
        self,
        url: str,
        secret_token: Optional[str] = None,
        max_connections: int = 40,
        allowed_updates: Optional[List[str]] = None,
    ) -> bool:
        """Set the webhook URL for receiving updates.

        Args:
            url: Webhook URL (must be HTTPS)
            secret_token: Secret token for verification
            max_connections: Max concurrent connections
            allowed_updates: List of update types to receive

        Returns:
            True if successful
        """
        data = {
            "url": url,
            "max_connections": max_connections,
        }

        if secret_token:
            data["secret_token"] = secret_token

        if allowed_updates:
            data["allowed_updates"] = allowed_updates
        else:
            # Default: receive all relevant updates
            data["allowed_updates"] = [
                "message",
                "edited_message",
                "callback_query",
            ]

        result = await self._request("POST", "setWebhook", data)
        return bool(result)

    async def delete_webhook(self) -> bool:
        """Delete the webhook to switch to polling mode."""
        result = await self._request("POST", "deleteWebhook")
        return bool(result)

    async def get_me(self) -> Dict[str, Any]:
        """Get bot information."""
        return await self._request("GET", "getMe")


# Singleton bot instance
_telegram_bot: Optional[TelegramBot] = None


def get_telegram_bot() -> TelegramBot:
    """Get or create Telegram bot singleton."""
    global _telegram_bot
    if _telegram_bot is None:
        _telegram_bot = TelegramBot()
    return _telegram_bot


# ============ Message Handlers ============


async def handle_text_message(
    message: TelegramMessage,
    session: UserSession,
    bot: TelegramBot,
) -> None:
    """Handle incoming text messages.

    Args:
        message: The incoming message
        session: User session
        bot: Telegram bot instance
    """
    text = message.text or ""

    # Check for commands
    if text.startswith("/"):
        await handle_command(message, session, bot)
        return

    # Show typing indicator
    await bot.send_typing_action(message.chat.id)

    # Import AI engine and process message
    try:
        from app.ai.engine import AIEngine
        from app.memory.vector_store import get_vector_store

        async with get_db_session() as db:
            vector_store = get_vector_store()
            engine = AIEngine(db, vector_store)

            # Set active agent based on user mode
            if session.mode == "ultron":
                engine._active_agent_id = "ultron"
            else:
                engine._active_agent_id = "jarvis"

            # Get AI response
            response = await engine.chat(
                message=text,
                user_id=UUID(int=session.user_id),
                conversation_id=session.conversation_id,
                user_name=session.get_full_name(),
            )

            session.message_count += 1

            # Send response
            await bot.send_message(
                chat_id=message.chat.id,
                text=response,
                reply_to_message_id=message.message_id,
            )

    except Exception as e:
        logger.error(f"Error processing text message: {e}")
        await bot.send_message(
            chat_id=message.chat.id,
            text="I apologize, but I encountered an error processing your message. Please try again.",
            reply_to_message_id=message.message_id,
        )


async def handle_voice_message(
    message: TelegramMessage,
    session: UserSession,
    bot: TelegramBot,
) -> None:
    """Handle incoming voice messages.

    Args:
        message: The incoming message with voice
        session: User session
        bot: Telegram bot instance
    """
    if not message.voice:
        return

    tg_settings = get_telegram_settings()

    # Show recording indicator
    await bot.send_voice_recording_action(message.chat.id)

    try:
        # Download voice file
        file_info = await bot.get_file(message.voice.file_id)
        file_path = file_info.get("file_path")

        if not file_path:
            raise ValueError("Could not get voice file path")

        voice_data = await bot.download_file(file_path)

        # Transcribe using Whisper
        from app.voice.transcription import get_whisper_client

        whisper_client = get_whisper_client()
        transcript = await whisper_client.transcribe(
            audio_data=voice_data,
            filename="voice.ogg",
        )

        if not transcript:
            await bot.send_message(
                chat_id=message.chat.id,
                text="I couldn't understand the voice message. Could you please try again or type your message?",
                reply_to_message_id=message.message_id,
            )
            return

        # Process with AI engine
        from app.ai.engine import AIEngine
        from app.memory.vector_store import get_vector_store

        async with get_db_session() as db:
            vector_store = get_vector_store()
            engine = AIEngine(db, vector_store)

            if session.mode == "ultron":
                engine._active_agent_id = "ultron"
            else:
                engine._active_agent_id = "jarvis"

            response = await engine.chat(
                message=transcript,
                user_id=UUID(int=session.user_id),
                conversation_id=session.conversation_id,
                user_name=session.get_full_name(),
            )

            session.message_count += 1

        # Check if we should reply with voice
        should_voice_reply = (
            tg_settings.telegram_voice_enabled
            and tg_settings.telegram_voice_reply_to_voice
            and session.voice_reply_mode
        )

        if should_voice_reply:
            try:
                # Generate voice response using ElevenLabs
                from app.voice.elevenlabs import ElevenLabsClient, VoiceSettings

                voice_id = VOICE_IDS.get(session.mode, VOICE_IDS["jarvis"])
                voice_settings_dict = VOICE_SETTINGS.get(session.mode, VOICE_SETTINGS["jarvis"])
                voice_settings = VoiceSettings(
                    stability=voice_settings_dict["stability"],
                    similarity_boost=voice_settings_dict["similarity_boost"],
                    style=voice_settings_dict["style"],
                )

                tts_client = ElevenLabsClient()
                audio_data = await tts_client.synthesize(
                    text=response,
                    voice_id=voice_id,
                    voice_settings=voice_settings,
                )

                # Send as audio (MP3)
                await bot.send_audio(
                    chat_id=message.chat.id,
                    audio_bytes=audio_data,
                    title=f"{session.mode.capitalize()} Response",
                    reply_to_message_id=message.message_id,
                )

                # Also send text version
                await bot.send_message(
                    chat_id=message.chat.id,
                    text=f"<i>Transcribed:</i> {transcript}\n\n{response}",
                )

            except Exception as e:
                logger.warning(f"Voice synthesis failed, falling back to text: {e}")
                await bot.send_message(
                    chat_id=message.chat.id,
                    text=f"<i>Transcribed:</i> {transcript}\n\n{response}",
                    reply_to_message_id=message.message_id,
                )
        else:
            # Text-only response
            await bot.send_message(
                chat_id=message.chat.id,
                text=f"<i>Transcribed:</i> {transcript}\n\n{response}",
                reply_to_message_id=message.message_id,
            )

    except Exception as e:
        logger.error(f"Error processing voice message: {e}")
        await bot.send_message(
            chat_id=message.chat.id,
            text="I apologize, but I couldn't process your voice message. Please try again or send a text message.",
            reply_to_message_id=message.message_id,
        )


async def handle_photo_message(
    message: TelegramMessage,
    session: UserSession,
    bot: TelegramBot,
) -> None:
    """Handle incoming photo messages.

    Args:
        message: The incoming message with photo
        session: User session
        bot: Telegram bot instance
    """
    if not message.photo:
        return

    # Show typing indicator
    await bot.send_typing_action(message.chat.id)

    try:
        # Get the largest photo (last in array)
        photo = message.photo[-1]

        # Download the photo
        file_info = await bot.get_file(photo.file_id)
        file_path = file_info.get("file_path")

        if not file_path:
            raise ValueError("Could not get photo file path")

        photo_data = await bot.download_file(file_path)

        # Analyze with vision
        from app.ai.vision import get_vision_analyzer

        analyzer = get_vision_analyzer()

        # Use caption as prompt if provided, otherwise default
        prompt = message.caption or (
            "Analyze this image and describe what you see. "
            "Include any relevant details, text, or information visible."
        )

        result = await analyzer.analyze_image(
            image_data=photo_data,
            prompt=prompt,
            media_type="image/jpeg",
        )

        if result.get("success"):
            analysis = result.get("analysis", "I couldn't analyze the image.")
            await bot.send_message(
                chat_id=message.chat.id,
                text=f"<b>Image Analysis:</b>\n\n{analysis}",
                reply_to_message_id=message.message_id,
            )
        else:
            error = result.get("error", "Unknown error")
            await bot.send_message(
                chat_id=message.chat.id,
                text=f"I couldn't analyze the image: {error}",
                reply_to_message_id=message.message_id,
            )

    except Exception as e:
        logger.error(f"Error processing photo: {e}")
        await bot.send_message(
            chat_id=message.chat.id,
            text="I apologize, but I couldn't analyze the image. Please try again.",
            reply_to_message_id=message.message_id,
        )


async def handle_document_message(
    message: TelegramMessage,
    session: UserSession,
    bot: TelegramBot,
) -> None:
    """Handle incoming document messages.

    Args:
        message: The incoming message with document
        session: User session
        bot: Telegram bot instance
    """
    if not message.document:
        return

    # Show typing indicator
    await bot.send_typing_action(message.chat.id)

    doc = message.document
    mime_type = doc.mime_type or "application/octet-stream"
    file_name = doc.file_name or "document"

    try:
        # Download the document
        file_info = await bot.get_file(doc.file_id)
        file_path = file_info.get("file_path")

        if not file_path:
            raise ValueError("Could not get document file path")

        doc_data = await bot.download_file(file_path)

        # Handle based on document type
        if mime_type.startswith("image/"):
            # Treat as image
            from app.ai.vision import get_vision_analyzer

            analyzer = get_vision_analyzer()
            prompt = message.caption or "Analyze this document image and extract all relevant information."

            result = await analyzer.analyze_image(
                image_data=doc_data,
                prompt=prompt,
                media_type=mime_type,
            )

            if result.get("success"):
                await bot.send_message(
                    chat_id=message.chat.id,
                    text=f"<b>Document Analysis ({file_name}):</b>\n\n{result.get('analysis', '')}",
                    reply_to_message_id=message.message_id,
                )
            else:
                await bot.send_message(
                    chat_id=message.chat.id,
                    text=f"I couldn't analyze the document: {result.get('error', 'Unknown error')}",
                    reply_to_message_id=message.message_id,
                )

        elif mime_type == "application/pdf" or file_name.endswith(".pdf"):
            # Handle PDF - save temporarily and process
            import tempfile
            from app.ai.documents import get_document_analyzer

            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(doc_data)
                tmp_path = tmp.name

            try:
                analyzer = get_document_analyzer()
                analysis = await analyzer.analyze(tmp_path)

                if analysis.success:
                    # Summarize the content
                    summary_result = await analyzer.summarize_document(analysis.text, max_length=800)
                    summary = summary_result.get("summary", "")
                    page_count = analysis.metadata.page_count

                    await bot.send_message(
                        chat_id=message.chat.id,
                        text=f"<b>PDF Analysis ({file_name}, {page_count} pages):</b>\n\n{summary}",
                        reply_to_message_id=message.message_id,
                    )
                else:
                    await bot.send_message(
                        chat_id=message.chat.id,
                        text=f"I couldn't process the PDF: {analysis.error}",
                        reply_to_message_id=message.message_id,
                    )
            finally:
                # Clean up temp file
                import os
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        else:
            # Unsupported document type
            await bot.send_message(
                chat_id=message.chat.id,
                text=f"I received your document ({file_name}), but I currently don't support processing {mime_type} files directly. "
                     "Please send images (PNG, JPG) or PDFs for analysis.",
                reply_to_message_id=message.message_id,
            )

    except Exception as e:
        logger.error(f"Error processing document: {e}")
        await bot.send_message(
            chat_id=message.chat.id,
            text="I apologize, but I couldn't process the document. Please try again.",
            reply_to_message_id=message.message_id,
        )


async def handle_location_message(
    message: TelegramMessage,
    session: UserSession,
    bot: TelegramBot,
) -> None:
    """Handle incoming location messages.

    Args:
        message: The incoming message with location
        session: User session
        bot: Telegram bot instance
    """
    if not message.location:
        return

    # Store location in session for context
    session.last_location = {
        "latitude": message.location.latitude,
        "longitude": message.location.longitude,
        "timestamp": datetime.utcnow().isoformat(),
    }

    await bot.send_message(
        chat_id=message.chat.id,
        text=f"Got your location! I've noted that you're at "
             f"({message.location.latitude:.4f}, {message.location.longitude:.4f}). "
             "I'll keep this in mind for context-aware responses and smart home automation.",
        reply_to_message_id=message.message_id,
    )


# ============ Command Handlers ============


async def handle_command(
    message: TelegramMessage,
    session: UserSession,
    bot: TelegramBot,
) -> None:
    """Route commands to appropriate handlers.

    Args:
        message: The incoming message
        session: User session
        bot: Telegram bot instance
    """
    text = message.text or ""
    command = text.split()[0].lower()

    # Remove bot username if present (e.g., /start@MyBot)
    if "@" in command:
        command = command.split("@")[0]

    handlers = {
        "/start": handle_start_command,
        "/jarvis": handle_jarvis_command,
        "/ultron": handle_ultron_command,
        "/home": handle_home_command,
        "/schedule": handle_schedule_command,
        "/memory": handle_memory_command,
        "/status": handle_status_command,
        "/settings": handle_settings_command,
        "/help": handle_help_command,
    }

    handler = handlers.get(command)
    if handler:
        await handler(message, session, bot)
    else:
        await bot.send_message(
            chat_id=message.chat.id,
            text=f"Unknown command: {command}\n\nUse /help to see available commands.",
        )


async def handle_start_command(
    message: TelegramMessage,
    session: UserSession,
    bot: TelegramBot,
) -> None:
    """Handle /start command - welcome message and setup."""
    mode_emoji = "🤖" if session.mode == "jarvis" else "⚡"

    welcome_text = f"""
<b>Welcome to Nexus AI!</b> {mode_emoji}

I'm your personal AI assistant, ready to help you from anywhere.

<b>Current Mode:</b> {session.mode.capitalize()}
{"🤖 <i>Jarvis mode: I'll ask before taking major actions</i>" if session.mode == "jarvis" else "⚡ <i>Ultron mode: Autonomous and efficient</i>"}

<b>What I can do:</b>
• Chat naturally about anything
• Send voice messages for voice responses
• Send images for analysis
• Send documents for processing
• Control your smart home
• Manage your schedule

<b>Quick Commands:</b>
/jarvis - Switch to helpful assistant mode
/ultron - Switch to autonomous mode
/home - Smart home controls
/help - See all commands

Send me a message to get started!
"""

    await bot.send_message(
        chat_id=message.chat.id,
        text=welcome_text,
        reply_markup={
            "inline_keyboard": QUICK_ACTIONS_KEYBOARD
        },
    )


async def handle_jarvis_command(
    message: TelegramMessage,
    session: UserSession,
    bot: TelegramBot,
) -> None:
    """Handle /jarvis command - switch to Jarvis mode."""
    update_user_mode(session.telegram_user_id, "jarvis")
    session.mode = "jarvis"

    await bot.send_message(
        chat_id=message.chat.id,
        text="🤖 <b>Switched to Jarvis Mode</b>\n\n"
             "I'm your helpful assistant. I'll:\n"
             "• Ask permission before major actions\n"
             "• Explain my reasoning\n"
             "• Prioritize your preferences\n\n"
             "How can I help you today?",
    )


async def handle_ultron_command(
    message: TelegramMessage,
    session: UserSession,
    bot: TelegramBot,
) -> None:
    """Handle /ultron command - switch to Ultron mode."""
    update_user_mode(session.telegram_user_id, "ultron")
    session.mode = "ultron"

    await bot.send_message(
        chat_id=message.chat.id,
        text="⚡ <b>Switched to Ultron Mode</b>\n\n"
             "Operating in autonomous mode. I'll:\n"
             "• Execute tasks efficiently\n"
             "• Make optimal decisions autonomously\n"
             "• Report results after completion\n\n"
             "What task should I handle?",
    )


async def handle_home_command(
    message: TelegramMessage,
    session: UserSession,
    bot: TelegramBot,
) -> None:
    """Handle /home command - show smart home control panel."""
    await bot.send_message(
        chat_id=message.chat.id,
        text="🏠 <b>Smart Home Controls</b>\n\n"
             "Select an action below:",
        reply_markup={
            "inline_keyboard": SMART_HOME_KEYBOARD
        },
    )


async def handle_schedule_command(
    message: TelegramMessage,
    session: UserSession,
    bot: TelegramBot,
) -> None:
    """Handle /schedule command - show scheduled actions."""
    await bot.send_typing_action(message.chat.id)

    try:
        # Get schedule from Google Calendar integration
        from app.integrations.google_calendar import get_google_calendar_integration

        calendar = get_google_calendar_integration()
        events = await calendar.get_todays_events()

        if events:
            event_list = "\n".join([
                f"• {e.get('summary', 'Untitled')} - {e.get('start', {}).get('dateTime', 'All day')}"
                for e in events[:10]
            ])
            text = f"📅 <b>Today's Schedule</b>\n\n{event_list}"
        else:
            text = "📅 <b>Today's Schedule</b>\n\nNo events scheduled for today."

        await bot.send_message(
            chat_id=message.chat.id,
            text=text,
            reply_markup={
                "inline_keyboard": [
                    [
                        {"text": "📝 Add Event", "callback_data": "schedule:add"},
                        {"text": "📋 Week View", "callback_data": "schedule:week"},
                    ]
                ]
            },
        )

    except Exception as e:
        logger.warning(f"Calendar not available: {e}")
        await bot.send_message(
            chat_id=message.chat.id,
            text="📅 <b>Schedule</b>\n\n"
                 "Calendar integration not configured. "
                 "Ask me to set up Google Calendar to view your schedule.",
        )


async def handle_memory_command(
    message: TelegramMessage,
    session: UserSession,
    bot: TelegramBot,
) -> None:
    """Handle /memory command - what does the AI remember?"""
    await bot.send_typing_action(message.chat.id)

    try:
        from app.ai.engine import AIEngine
        from app.memory.vector_store import get_vector_store

        async with get_db_session() as db:
            vector_store = get_vector_store()
            engine = AIEngine(db, vector_store)

            # Get memory stats
            stats = await engine.get_memory_stats(UUID(int=session.user_id))

            # Recall some recent memories
            memories = await engine.recall_memory(
                query="recent conversations and preferences",
                user_id=UUID(int=session.user_id),
                limit=5,
            )

            memory_text = "🧠 <b>What I Remember</b>\n\n"

            if stats.get("enabled"):
                memory_text += f"<b>Memory System:</b> Active\n"
                memory_text += f"<b>Conversations tracked:</b> {stats.get('conversations_last_30_days', 0)} (last 30 days)\n"
                memory_text += f"<b>Facts cached:</b> {stats.get('facts_cached', 0)}\n\n"
            else:
                memory_text += "<b>Memory System:</b> Limited mode\n\n"

            if memories:
                memory_text += "<b>Recent Context:</b>\n"
                for mem in memories[:3]:
                    content = mem.get("content", "")[:100]
                    memory_text += f"• {content}...\n"
            else:
                memory_text += "No specific memories found yet. Chat more and I'll remember!\n"

            await bot.send_message(
                chat_id=message.chat.id,
                text=memory_text,
            )

    except Exception as e:
        logger.error(f"Memory command error: {e}")
        await bot.send_message(
            chat_id=message.chat.id,
            text="🧠 <b>Memory</b>\n\n"
                 f"I've had {session.message_count} conversations with you in this session. "
                 "My long-term memory system helps me remember important details across sessions.",
        )


async def handle_status_command(
    message: TelegramMessage,
    session: UserSession,
    bot: TelegramBot,
) -> None:
    """Handle /status command - system status and recent activity."""
    mode_emoji = "🤖" if session.mode == "jarvis" else "⚡"

    status_text = f"""
📊 <b>System Status</b>

<b>Mode:</b> {session.mode.capitalize()} {mode_emoji}
<b>Messages this session:</b> {session.message_count}
<b>Voice replies:</b> {"Enabled" if session.voice_reply_mode else "Disabled"}

<b>Services:</b>
• AI Engine: ✅ Online
• Voice: ✅ Available
• Vision: ✅ Available
• Smart Home: ✅ Connected

<b>Your Profile:</b>
• Name: {session.get_full_name()}
• Telegram: @{session.username or 'N/A'}
"""

    if session.last_location:
        status_text += f"\n• Last Location: {session.last_location.get('latitude', 0):.2f}, {session.last_location.get('longitude', 0):.2f}"

    await bot.send_message(
        chat_id=message.chat.id,
        text=status_text,
    )


async def handle_settings_command(
    message: TelegramMessage,
    session: UserSession,
    bot: TelegramBot,
) -> None:
    """Handle /settings command - user preferences."""
    voice_status = "✅ On" if session.voice_reply_mode else "❌ Off"
    mode_status = f"{'🤖 Jarvis' if session.mode == 'jarvis' else '⚡ Ultron'}"

    await bot.send_message(
        chat_id=message.chat.id,
        text=f"⚙️ <b>Settings</b>\n\n"
             f"<b>Current Mode:</b> {mode_status}\n"
             f"<b>Voice Replies:</b> {voice_status}\n\n"
             "Tap a button below to change settings:",
        reply_markup={
            "inline_keyboard": SETTINGS_KEYBOARD
        },
    )


async def handle_help_command(
    message: TelegramMessage,
    session: UserSession,
    bot: TelegramBot,
) -> None:
    """Handle /help command - show available commands."""
    help_text = "<b>Available Commands</b>\n\n"

    for cmd, desc in COMMAND_DESCRIPTIONS.items():
        help_text += f"{cmd} - {desc}\n"

    help_text += "\n<b>Message Types Supported:</b>\n"
    help_text += "• 💬 Text - Chat with the AI\n"
    help_text += "• 🎤 Voice - I'll transcribe and respond\n"
    help_text += "• 📷 Photos - I'll analyze the image\n"
    help_text += "• 📄 Documents - I'll extract information\n"
    help_text += "• 📍 Location - I'll note your position\n"

    await bot.send_message(
        chat_id=message.chat.id,
        text=help_text,
    )


# ============ Callback Query Handlers ============


async def handle_callback_query(
    callback: TelegramCallbackQuery,
    bot: TelegramBot,
) -> None:
    """Handle callback queries from inline keyboards.

    Args:
        callback: The callback query
        bot: Telegram bot instance
    """
    data = callback.data or ""
    user_id = callback.from_user.id

    session = get_or_create_session(
        telegram_user_id=user_id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name,
    )

    # Parse callback data
    parts = data.split(":")

    if parts[0] == "home":
        await handle_home_callback(callback, session, bot, parts)
    elif parts[0] == "action":
        await handle_action_callback(callback, session, bot, parts)
    elif parts[0] == "settings":
        await handle_settings_callback(callback, session, bot, parts)
    elif parts[0] == "schedule":
        await handle_schedule_callback(callback, session, bot, parts)
    else:
        await bot.answer_callback_query(
            callback.id,
            text="Unknown action",
        )


async def handle_home_callback(
    callback: TelegramCallbackQuery,
    session: UserSession,
    bot: TelegramBot,
    parts: List[str],
) -> None:
    """Handle smart home callbacks."""
    if len(parts) < 2:
        await bot.answer_callback_query(callback.id, "Invalid action")
        return

    chat_id = callback.message["chat"]["id"] if callback.message else session.telegram_user_id

    try:
        # Import smart home tools
        from app.integrations.smart_home import (
            control_lights,
            set_thermostat,
            activate_scene,
            get_home_status,
        )

        action_type = parts[1]
        action_value = parts[2] if len(parts) > 2 else None
        result_text = ""

        if action_type == "lights":
            if action_value == "on":
                result_text = await control_lights(action="on")
            elif action_value == "off":
                result_text = await control_lights(action="off")
        elif action_type == "temp":
            if action_value == "up":
                result_text = await set_thermostat(temperature=72)  # Increase
            elif action_value == "down":
                result_text = await set_thermostat(temperature=68)  # Decrease
        elif action_type == "scene":
            if action_value == "movie":
                result_text = await activate_scene("Movie Mode")
            elif action_value == "night":
                result_text = await activate_scene("Night Mode")
        elif action_type == "status":
            result_text = await get_home_status()
        elif action_type == "all":
            if action_value == "off":
                result_text = await control_lights(action="off")
                result_text = "All devices turned off"

        await bot.answer_callback_query(
            callback.id,
            text="Action executed",
            show_alert=False,
        )

        # Update the message with result
        if callback.message:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback.message["message_id"],
                text=f"🏠 <b>Smart Home</b>\n\n{result_text}\n\nSelect another action:",
                reply_markup={"inline_keyboard": SMART_HOME_KEYBOARD},
            )

    except Exception as e:
        logger.error(f"Smart home action failed: {e}")
        await bot.answer_callback_query(
            callback.id,
            text=f"Failed: {str(e)[:100]}",
            show_alert=True,
        )


async def handle_action_callback(
    callback: TelegramCallbackQuery,
    session: UserSession,
    bot: TelegramBot,
    parts: List[str],
) -> None:
    """Handle quick action callbacks."""
    if len(parts) < 3:
        await bot.answer_callback_query(callback.id, "Invalid action")
        return

    category = parts[1]
    action = parts[2]
    chat_id = callback.message["chat"]["id"] if callback.message else session.telegram_user_id

    await bot.answer_callback_query(callback.id, text="Processing...")

    if category == "schedule":
        if action == "today":
            # Show today's schedule
            await handle_schedule_command(
                TelegramMessage(
                    message_id=0,
                    date=int(time.time()),
                    chat=TelegramChat(id=chat_id, type="private"),
                    from_user=callback.from_user,
                    text="/schedule",
                ),
                session,
                bot,
            )
    elif category == "brief":
        if action == "daily":
            # Generate daily brief
            await bot.send_typing_action(chat_id)

            try:
                from app.ai.engine import AIEngine
                from app.memory.vector_store import get_vector_store

                async with get_db_session() as db:
                    vector_store = get_vector_store()
                    engine = AIEngine(db, vector_store)

                    response = await engine.chat(
                        message="Give me my daily briefing - schedule, weather, important reminders, and any predictions.",
                        user_id=UUID(int=session.user_id),
                        conversation_id=session.conversation_id,
                        user_name=session.get_full_name(),
                    )

                    await bot.send_message(
                        chat_id=chat_id,
                        text=f"📊 <b>Daily Brief</b>\n\n{response}",
                    )

            except Exception as e:
                logger.error(f"Daily brief error: {e}")
                await bot.send_message(
                    chat_id=chat_id,
                    text="Sorry, I couldn't generate your daily brief. Please try again.",
                )
    elif category == "home":
        if action == "status":
            await handle_home_command(
                TelegramMessage(
                    message_id=0,
                    date=int(time.time()),
                    chat=TelegramChat(id=chat_id, type="private"),
                    from_user=callback.from_user,
                    text="/home",
                ),
                session,
                bot,
            )
    elif category == "reminder":
        if action == "new":
            await bot.send_message(
                chat_id=chat_id,
                text="To set a reminder, just tell me naturally:\n\n"
                     "<i>\"Remind me to call mom at 5pm\"</i>\n"
                     "<i>\"Set a reminder for the meeting in 30 minutes\"</i>",
            )


async def handle_settings_callback(
    callback: TelegramCallbackQuery,
    session: UserSession,
    bot: TelegramBot,
    parts: List[str],
) -> None:
    """Handle settings callbacks."""
    if len(parts) < 3:
        await bot.answer_callback_query(callback.id, "Invalid action")
        return

    setting = parts[1]
    action = parts[2]
    chat_id = callback.message["chat"]["id"] if callback.message else session.telegram_user_id

    if setting == "voice":
        if action == "toggle":
            session.voice_reply_mode = not session.voice_reply_mode
            status = "enabled" if session.voice_reply_mode else "disabled"
            await bot.answer_callback_query(
                callback.id,
                text=f"Voice replies {status}",
            )

            # Update the settings message
            await handle_settings_command(
                TelegramMessage(
                    message_id=callback.message["message_id"] if callback.message else 0,
                    date=int(time.time()),
                    chat=TelegramChat(id=chat_id, type="private"),
                    from_user=callback.from_user,
                    text="/settings",
                ),
                session,
                bot,
            )

    elif setting == "conversation":
        if action == "clear":
            import uuid
            session.conversation_id = str(uuid.uuid4())
            session.message_count = 0
            await bot.answer_callback_query(
                callback.id,
                text="Conversation cleared! Starting fresh.",
                show_alert=True,
            )

    elif setting == "mode":
        if action == "switch":
            new_mode = "ultron" if session.mode == "jarvis" else "jarvis"
            update_user_mode(session.telegram_user_id, new_mode)
            session.mode = new_mode

            emoji = "⚡" if new_mode == "ultron" else "🤖"
            await bot.answer_callback_query(
                callback.id,
                text=f"Switched to {new_mode.capitalize()} mode {emoji}",
            )

            # Update the settings message
            await handle_settings_command(
                TelegramMessage(
                    message_id=callback.message["message_id"] if callback.message else 0,
                    date=int(time.time()),
                    chat=TelegramChat(id=chat_id, type="private"),
                    from_user=callback.from_user,
                    text="/settings",
                ),
                session,
                bot,
            )


async def handle_schedule_callback(
    callback: TelegramCallbackQuery,
    session: UserSession,
    bot: TelegramBot,
    parts: List[str],
) -> None:
    """Handle schedule callbacks."""
    if len(parts) < 2:
        await bot.answer_callback_query(callback.id, "Invalid action")
        return

    action = parts[1]
    chat_id = callback.message["chat"]["id"] if callback.message else session.telegram_user_id

    await bot.answer_callback_query(callback.id, text="Processing...")

    if action == "add":
        await bot.send_message(
            chat_id=chat_id,
            text="To add an event, just tell me naturally:\n\n"
                 "<i>\"Schedule a meeting tomorrow at 2pm\"</i>\n"
                 "<i>\"Add dentist appointment on Friday at 10am\"</i>",
        )
    elif action == "week":
        await bot.send_typing_action(chat_id)

        try:
            from app.integrations.google_calendar import get_google_calendar_integration

            calendar = get_google_calendar_integration()
            events = await calendar.get_upcoming_events(days=7)

            if events:
                event_list = "\n".join([
                    f"• {e.get('summary', 'Untitled')} - {e.get('start', {}).get('dateTime', 'TBD')}"
                    for e in events[:15]
                ])
                text = f"📅 <b>This Week's Schedule</b>\n\n{event_list}"
            else:
                text = "📅 <b>This Week's Schedule</b>\n\nNo events scheduled for this week."

            await bot.send_message(chat_id=chat_id, text=text)

        except Exception as e:
            logger.warning(f"Calendar not available: {e}")
            await bot.send_message(
                chat_id=chat_id,
                text="Calendar integration not configured. Ask me to set it up!",
            )


# ============ Webhook Security ============


def verify_telegram_signature(
    token: str,
    secret: str,
) -> bool:
    """Verify the X-Telegram-Bot-Api-Secret-Token header.

    Args:
        token: Token from request header
        secret: Expected secret token

    Returns:
        True if valid
    """
    if not secret:
        return True  # No secret configured, skip verification

    return hmac.compare_digest(token, secret)


def check_rate_limit(session: UserSession, max_requests: int = 30) -> bool:
    """Check if user is within rate limits.

    Args:
        session: User session
        max_requests: Max requests per minute

    Returns:
        True if within limits
    """
    now = time.time()
    minute_ago = now - 60

    # Remove old timestamps
    session.request_timestamps = [
        ts for ts in session.request_timestamps if ts > minute_ago
    ]

    # Check limit
    if len(session.request_timestamps) >= max_requests:
        return False

    # Add current timestamp
    session.request_timestamps.append(now)
    return True


# ============ API Endpoints ============


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None),
) -> JSONResponse:
    """
    Webhook endpoint for receiving Telegram updates.

    This endpoint is called by Telegram whenever there's a new update
    (message, callback query, etc.). The update is processed asynchronously
    for responsiveness.

    Args:
        request: FastAPI request object
        background_tasks: Background task manager
        x_telegram_bot_api_secret_token: Secret token for verification

    Returns:
        Empty JSON response (Telegram requires 200 OK)
    """
    tg_settings = get_telegram_settings()

    # Verify webhook secret
    if tg_settings.telegram_webhook_secret:
        if not verify_telegram_signature(
            x_telegram_bot_api_secret_token or "",
            tg_settings.telegram_webhook_secret,
        ):
            logger.warning("Invalid webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse update
    try:
        body = await request.json()
        update = TelegramUpdate(**body)
    except Exception as e:
        logger.error(f"Failed to parse webhook update: {e}")
        return JSONResponse(content={"ok": True})

    # Process update in background for quick response
    background_tasks.add_task(process_update, update)

    return JSONResponse(content={"ok": True})


async def process_update(update: TelegramUpdate) -> None:
    """Process a Telegram update asynchronously.

    Args:
        update: The update to process
    """
    bot = get_telegram_bot()
    tg_settings = get_telegram_settings()

    try:
        if update.callback_query:
            await handle_callback_query(update.callback_query, bot)

        elif update.message:
            message = update.message

            # Get or create user session
            if not message.from_user:
                logger.warning("Message without from_user")
                return

            # Check if user is allowed
            if tg_settings.allowed_user_ids:
                if message.from_user.id not in tg_settings.allowed_user_ids:
                    logger.warning(f"Unauthorized user: {message.from_user.id}")
                    await bot.send_message(
                        chat_id=message.chat.id,
                        text="Sorry, you're not authorized to use this bot.",
                    )
                    return

            session = get_or_create_session(
                telegram_user_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
            )

            # Check rate limit
            if not check_rate_limit(session, tg_settings.telegram_rate_limit):
                await bot.send_message(
                    chat_id=message.chat.id,
                    text="You're sending messages too quickly. Please wait a moment.",
                )
                return

            # Route to appropriate handler
            if message.text:
                await handle_text_message(message, session, bot)
            elif message.voice:
                await handle_voice_message(message, session, bot)
            elif message.photo:
                await handle_photo_message(message, session, bot)
            elif message.document:
                await handle_document_message(message, session, bot)
            elif message.location:
                await handle_location_message(message, session, bot)
            else:
                await bot.send_message(
                    chat_id=message.chat.id,
                    text="I received your message but I'm not sure how to handle it. "
                         "Try sending text, voice, photos, documents, or location.",
                )

    except Exception as e:
        logger.error(f"Error processing update: {e}")


@router.post("/setup")
async def setup_webhook() -> Dict[str, Any]:
    """
    Set up the Telegram webhook.

    Call this endpoint to configure Telegram to send updates to your webhook URL.
    Requires TELEGRAM_WEBHOOK_URL to be set in environment.

    Returns:
        Setup status
    """
    tg_settings = get_telegram_settings()

    if not tg_settings.is_configured:
        raise HTTPException(
            status_code=503,
            detail="Telegram bot not configured. Set TELEGRAM_BOT_TOKEN."
        )

    if not tg_settings.telegram_webhook_url:
        raise HTTPException(
            status_code=400,
            detail="Webhook URL not configured. Set TELEGRAM_WEBHOOK_URL."
        )

    bot = get_telegram_bot()

    success = await bot.set_webhook(
        url=tg_settings.telegram_webhook_url,
        secret_token=tg_settings.telegram_webhook_secret,
    )

    if success:
        bot_info = await bot.get_me()
        return {
            "status": "success",
            "message": "Webhook configured successfully",
            "webhook_url": tg_settings.telegram_webhook_url,
            "bot": {
                "username": bot_info.get("username"),
                "name": bot_info.get("first_name"),
            },
        }
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to set up webhook"
        )


@router.delete("/webhook")
async def delete_webhook() -> Dict[str, Any]:
    """
    Delete the Telegram webhook.

    Use this to switch to polling mode or disable the bot temporarily.

    Returns:
        Deletion status
    """
    tg_settings = get_telegram_settings()

    if not tg_settings.is_configured:
        raise HTTPException(
            status_code=503,
            detail="Telegram bot not configured"
        )

    bot = get_telegram_bot()
    success = await bot.delete_webhook()

    return {
        "status": "success" if success else "failed",
        "message": "Webhook deleted" if success else "Failed to delete webhook",
    }


@router.get("/status")
async def get_status() -> Dict[str, Any]:
    """
    Get Telegram bot status.

    Returns:
        Bot status and configuration info
    """
    tg_settings = get_telegram_settings()

    if not tg_settings.is_configured:
        return {
            "configured": False,
            "message": "Bot token not configured",
        }

    bot = get_telegram_bot()

    try:
        bot_info = await bot.get_me()
        return {
            "configured": True,
            "bot": {
                "id": bot_info.get("id"),
                "username": bot_info.get("username"),
                "name": bot_info.get("first_name"),
                "can_join_groups": bot_info.get("can_join_groups"),
                "can_read_all_group_messages": bot_info.get("can_read_all_group_messages"),
                "supports_inline_queries": bot_info.get("supports_inline_queries"),
            },
            "settings": {
                "voice_enabled": tg_settings.telegram_voice_enabled,
                "voice_reply_to_voice": tg_settings.telegram_voice_reply_to_voice,
                "default_persona": tg_settings.telegram_default_persona,
                "rate_limit": tg_settings.telegram_rate_limit,
            },
        }
    except Exception as e:
        logger.error(f"Failed to get bot info: {e}")
        return {
            "configured": True,
            "error": str(e),
        }


@router.post("/send")
async def send_proactive_message(
    chat_id: int,
    text: str,
    parse_mode: str = "HTML",
) -> Dict[str, Any]:
    """
    Send a proactive message to a user.

    This endpoint allows sending messages to users without them initiating
    the conversation. Useful for scheduled briefings, alerts, and predictions.

    Args:
        chat_id: Target Telegram chat/user ID
        text: Message text
        parse_mode: Text parsing mode

    Returns:
        Sent message info
    """
    tg_settings = get_telegram_settings()

    if not tg_settings.is_configured:
        raise HTTPException(
            status_code=503,
            detail="Telegram bot not configured"
        )

    bot = get_telegram_bot()

    try:
        result = await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
        )
        return {
            "status": "success",
            "message_id": result.get("message_id"),
        }
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============ Proactive Message Functions ============


async def send_prediction_alert(
    chat_id: int,
    prediction: str,
    confidence: float,
    action_required: bool = False,
) -> bool:
    """
    Send a prediction alert to a user.

    Args:
        chat_id: Target chat ID
        prediction: Prediction text
        confidence: Confidence score (0-1)
        action_required: Whether user action is needed

    Returns:
        True if sent successfully
    """
    bot = get_telegram_bot()

    emoji = "🔮" if confidence > 0.8 else "💭"
    confidence_text = f"{confidence * 100:.0f}%"

    text = f"{emoji} <b>Prediction</b> ({confidence_text} confidence)\n\n{prediction}"

    if action_required:
        text += "\n\n⚡ <i>Action may be required</i>"

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup={
                "inline_keyboard": [
                    [
                        {"text": "✅ Acknowledge", "callback_data": "prediction:ack"},
                        {"text": "🔕 Dismiss", "callback_data": "prediction:dismiss"},
                    ]
                ]
            } if action_required else None,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send prediction alert: {e}")
        return False


async def send_scheduled_briefing(
    chat_id: int,
    briefing_type: str = "morning",
) -> bool:
    """
    Send a scheduled briefing to a user.

    Args:
        chat_id: Target chat ID
        briefing_type: Type of briefing (morning, evening, weekly)

    Returns:
        True if sent successfully
    """
    bot = get_telegram_bot()

    emoji = "☀️" if briefing_type == "morning" else "🌙" if briefing_type == "evening" else "📊"
    title = f"{emoji} <b>{briefing_type.capitalize()} Briefing</b>\n\n"

    # Generate briefing content
    try:
        from app.ai.engine import AIEngine
        from app.memory.vector_store import get_vector_store

        async with get_db_session() as db:
            vector_store = get_vector_store()
            engine = AIEngine(db, vector_store)

            prompt = f"Generate a {briefing_type} briefing including schedule, weather, reminders, and any predictions."
            briefing = await engine.chat(
                message=prompt,
                user_id=UUID(int=chat_id),
                user_name="User",
            )

            await bot.send_message(
                chat_id=chat_id,
                text=title + briefing,
            )
            return True

    except Exception as e:
        logger.error(f"Failed to send scheduled briefing: {e}")
        return False


async def send_action_confirmation(
    chat_id: int,
    action: str,
    result: str,
    success: bool = True,
) -> bool:
    """
    Send an action confirmation to a user.

    Args:
        chat_id: Target chat ID
        action: Action that was performed
        result: Result of the action
        success: Whether action was successful

    Returns:
        True if sent successfully
    """
    bot = get_telegram_bot()

    emoji = "✅" if success else "❌"
    text = f"{emoji} <b>Action {'Completed' if success else 'Failed'}</b>\n\n"
    text += f"<b>Action:</b> {action}\n"
    text += f"<b>Result:</b> {result}"

    try:
        await bot.send_message(chat_id=chat_id, text=text)
        return True
    except Exception as e:
        logger.error(f"Failed to send action confirmation: {e}")
        return False
