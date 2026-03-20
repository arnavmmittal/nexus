"""Async SQLAlchemy database setup with SQLite (default) and PostgreSQL support."""

import os
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""

    pass


def _get_engine_config() -> dict:
    """Get database engine configuration based on database type."""
    config = {
        "echo": settings.debug,
    }

    if settings.is_sqlite:
        # SQLite-specific configuration
        # Ensure data directory exists
        db_path = settings.database_url.replace("sqlite+aiosqlite:///", "")
        if db_path.startswith("./"):
            db_path = db_path[2:]
        db_dir = Path(db_path).parent
        if db_dir and str(db_dir) != ".":
            db_dir.mkdir(parents=True, exist_ok=True)

        # SQLite connection args
        config["connect_args"] = {"check_same_thread": False}
    else:
        # PostgreSQL configuration
        config["pool_pre_ping"] = True
        config["pool_size"] = 5
        config["max_overflow"] = 10

        # Supabase connections may require SSL
        if settings.database_url and "supabase" in settings.database_url:
            config["connect_args"] = {"ssl": "prefer"}

    return config


# Create async engine (SQLite or PostgreSQL)
engine = create_async_engine(
    settings.database_url,
    **_get_engine_config(),
)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides an async database session.

    Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


from contextlib import asynccontextmanager


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for getting a database session (for background tasks).

    Usage:
        async with get_db_session() as db:
            # Use db session
            ...
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
