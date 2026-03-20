"""Alembic environment configuration with SQLite and PostgreSQL support."""

import asyncio
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool, create_engine
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Import Base for metadata
from app.core.database import Base
from app.core.config import settings

# Import all models to ensure they're registered with Base.metadata
from app.models import (  # noqa: F401
    User,
    Fact,
    Pattern,
    Conversation,
    Skill,
    SkillXPLog,
    Goal,
    GoalProgressLog,
    Streak,
    Achievement,
    APIUsage,
)

# Alembic Config object
config = context.config

# Set SQLAlchemy URL from settings (synchronous version for alembic)
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model metadata for autogenerate support
target_metadata = Base.metadata


def _ensure_sqlite_directory() -> None:
    """Ensure SQLite database directory exists."""
    if settings.is_sqlite:
        db_path = settings.database_url_sync.replace("sqlite:///", "")
        if db_path.startswith("./"):
            db_path = db_path[2:]
        db_dir = Path(db_path).parent
        if db_dir and str(db_dir) != ".":
            db_dir.mkdir(parents=True, exist_ok=True)


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine. By skipping the Engine creation
    we don't even need a DBAPI to be available.
    """
    url = config.get_main_option("sqlalchemy.url")

    # SQLite-specific configuration
    render_as_batch = settings.is_sqlite

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=render_as_batch,  # Required for SQLite ALTER TABLE support
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection."""
    # SQLite-specific configuration
    render_as_batch = settings.is_sqlite

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=render_as_batch,  # Required for SQLite ALTER TABLE support
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online_sync() -> None:
    """Run migrations synchronously (for SQLite)."""
    _ensure_sqlite_directory()

    connect_args = {}
    if settings.is_sqlite:
        connect_args = {"check_same_thread": False}

    connectable = create_engine(
        settings.database_url_sync,
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    with connectable.connect() as connection:
        do_run_migrations(connection)

    connectable.dispose()


async def run_async_migrations() -> None:
    """Run migrations in async mode (for PostgreSQL)."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    if settings.is_sqlite:
        # Use synchronous engine for SQLite
        run_migrations_online_sync()
    else:
        # Use async engine for PostgreSQL
        asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
