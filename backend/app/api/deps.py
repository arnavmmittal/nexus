"""API dependencies for Nexus.

This module provides common dependencies for FastAPI routes including
authentication, database sessions, and other shared utilities.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db_session
from app.models import User


async def get_db() -> AsyncSession:
    """Get database session dependency.

    Yields:
        Database session
    """
    async with get_db_session() as session:
        yield session


async def get_current_user(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current user from request headers.

    For now, this uses a simple header-based authentication.
    In production, this should use proper JWT or session-based auth.

    Args:
        x_user_id: User ID from header
        db: Database session

    Returns:
        Current user

    Raises:
        HTTPException: If user not found or not authenticated
    """
    # Default user for development
    DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"

    user_id_str = x_user_id or DEFAULT_USER_ID

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format",
        )

    # Try to get user from database
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        # For development, create a default user if not exists
        if user_id_str == DEFAULT_USER_ID:
            user = User(
                id=user_id,
                email="default@nexus.local",
                name="Default User",
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

    return user


async def get_optional_user(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Get current user if authenticated, None otherwise.

    Args:
        x_user_id: User ID from header
        db: Database session

    Returns:
        Current user or None
    """
    if not x_user_id:
        return None

    try:
        return await get_current_user(x_user_id, db)
    except HTTPException:
        return None
