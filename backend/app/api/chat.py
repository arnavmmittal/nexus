"""Chat API endpoints with WebSocket streaming."""

import json
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.ai.engine import AIEngine
from app.memory.vector_store import get_vector_store
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatStreamEvent,
    WebSocketMessage,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Placeholder user ID (will be replaced with auth later)
DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_USER_NAME = "User"


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept and track connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"Client {client_id} connected")

    def disconnect(self, client_id: str):
        """Remove connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"Client {client_id} disconnected")

    async def send_json(self, client_id: str, data: dict):
        """Send JSON to specific client."""
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(data)


manager = ConnectionManager()


@router.post("", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Send a message and get a response (non-streaming).

    Args:
        request: Chat request with message
        db: Database session

    Returns:
        Chat response
    """
    try:
        # Initialize AI engine
        vector_store = get_vector_store()
        engine = AIEngine(db, vector_store)

        # Get response
        response = await engine.chat(
            message=request.message,
            user_id=DEFAULT_USER_ID,
            conversation_id=request.conversation_id,
            user_name=DEFAULT_USER_NAME,
        )

        # Generate conversation ID if not provided
        conversation_id = request.conversation_id or str(UUID(int=0))

        return ChatResponse(
            message=response,
            conversation_id=conversation_id,
        )

    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process message: {str(e)}",
        )


@router.websocket("/stream")
async def websocket_chat(
    websocket: WebSocket,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    WebSocket endpoint for streaming chat.

    Supports:
    - chat_message: Send a message and receive streaming response
    - ping: Keep-alive ping
    """
    import uuid as uuid_module

    client_id = str(uuid_module.uuid4())
    await manager.connect(websocket, client_id)

    try:
        # Initialize AI engine
        vector_store = get_vector_store()
        engine = AIEngine(db, vector_store)

        while True:
            # Receive message
            data = await websocket.receive_text()

            try:
                message_data = json.loads(data)
                msg = WebSocketMessage(**message_data)
            except (json.JSONDecodeError, ValueError) as e:
                await websocket.send_json(
                    ChatStreamEvent(
                        type="error",
                        error=f"Invalid message format: {e}",
                    ).model_dump()
                )
                continue

            if msg.type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg.type == "chat_message":
                if not msg.content:
                    await websocket.send_json(
                        ChatStreamEvent(
                            type="error",
                            error="Message content is required",
                        ).model_dump()
                    )
                    continue

                # Stream response
                conversation_id = str(uuid_module.uuid4())

                try:
                    async for chunk in engine.stream_chat(
                        message=msg.content,
                        user_id=DEFAULT_USER_ID,
                        conversation_id=conversation_id,
                        user_name=DEFAULT_USER_NAME,
                    ):
                        await websocket.send_json(
                            ChatStreamEvent(
                                type="content",
                                content=chunk,
                                conversation_id=conversation_id,
                            ).model_dump()
                        )

                    # Send completion
                    await websocket.send_json(
                        ChatStreamEvent(
                            type="done",
                            conversation_id=conversation_id,
                        ).model_dump()
                    )

                except Exception as e:
                    logger.error(f"Stream error: {e}")
                    await websocket.send_json(
                        ChatStreamEvent(
                            type="error",
                            error=str(e),
                        ).model_dump()
                    )

            elif msg.type in ("subscribe_widget", "unsubscribe_widget"):
                # Widget subscriptions (to be implemented)
                await websocket.send_json(
                    {"type": "ack", "message": f"Widget {msg.type} acknowledged"}
                )

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(client_id)


@router.get("/history")
async def get_chat_history(
    conversation_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Get conversation history.

    Args:
        conversation_id: Conversation ID
        db: Database session

    Returns:
        List of messages in conversation
    """
    # Initialize AI engine (uses in-memory history for now)
    engine = AIEngine(db, None)
    history = engine.get_conversation_history(conversation_id)

    return {"conversation_id": conversation_id, "messages": history}


@router.delete("/history/{conversation_id}")
async def clear_chat_history(
    conversation_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Clear conversation history.

    Args:
        conversation_id: Conversation ID
        db: Database session
    """
    engine = AIEngine(db, None)
    engine.clear_conversation(conversation_id)

    return {"status": "cleared", "conversation_id": conversation_id}
