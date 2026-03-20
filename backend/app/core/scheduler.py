"""Background task scheduler for periodic operations."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: AsyncIOScheduler | None = None

# Default user ID for automated tasks (will be replaced with multi-user support)
DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_USER_UUID = UUID(DEFAULT_USER_ID)


async def sync_obsidian_vault() -> dict[str, Any]:
    """
    Background task to sync Obsidian vault.

    This runs periodically to keep the vector store in sync with
    the Obsidian vault, picking up any new or modified notes.
    """
    from app.memory.obsidian import get_obsidian_sync

    logger.info("Starting scheduled Obsidian vault sync...")
    start_time = datetime.utcnow()

    try:
        obsidian = get_obsidian_sync()

        if not obsidian.is_configured():
            logger.debug("Obsidian vault not configured, skipping scheduled sync")
            return {"status": "skipped", "reason": "not_configured"}

        stats = await obsidian.sync_vault(DEFAULT_USER_ID, force=False)

        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.info(
            f"Obsidian sync completed in {duration:.2f}s: "
            f"synced={stats.get('synced', 0)}, "
            f"unchanged={stats.get('unchanged', 0)}, "
            f"deleted={stats.get('deleted', 0)}"
        )

        return {"status": "success", "duration_seconds": duration, **stats}

    except Exception as e:
        logger.error(f"Scheduled Obsidian sync failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


async def sync_github_activity() -> dict[str, Any]:
    """
    Background task to sync GitHub activity and award XP.

    This runs daily to track coding activity from GitHub and
    award XP to the corresponding programming skills.
    """
    from app.core.database import get_db_session
    from app.integrations.github import get_github_integration

    logger.info("Starting scheduled GitHub activity sync...")
    start_time = datetime.utcnow()

    try:
        github = get_github_integration()

        if not github.is_configured():
            logger.debug("GitHub not configured, skipping scheduled sync")
            return {"status": "skipped", "reason": "not_configured"}

        # Get a database session for the background task
        async with get_db_session() as db:
            result = await github.sync_activity(
                db,
                days=1,  # Only sync last day for daily job
                user_id=DEFAULT_USER_UUID,
            )

        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.info(
            f"GitHub sync completed in {duration:.2f}s: "
            f"commits={result.get('commits_processed', 0)}, "
            f"prs={result.get('prs_processed', 0)}, "
            f"xp={result.get('total_xp', 0)}"
        )

        return {"status": "success", "duration_seconds": duration, **result}

    except Exception as e:
        logger.error(f"Scheduled GitHub sync failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


def get_scheduler() -> AsyncIOScheduler:
    """Get or create the scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


async def start_scheduler() -> None:
    """
    Start the background scheduler.

    Adds scheduled jobs for:
    - Obsidian vault sync every 5 minutes
    - GitHub activity sync daily at 6 AM
    """
    scheduler = get_scheduler()

    if scheduler.running:
        logger.warning("Scheduler already running")
        return

    # Add Obsidian sync job (every 5 minutes)
    scheduler.add_job(
        sync_obsidian_vault,
        trigger=IntervalTrigger(minutes=5),
        id="obsidian_sync",
        name="Obsidian Vault Sync",
        replace_existing=True,
        max_instances=1,  # Prevent overlapping syncs
    )

    # Add GitHub sync job (daily at 6 AM)
    scheduler.add_job(
        sync_github_activity,
        trigger=CronTrigger(hour=6, minute=0),
        id="github_sync",
        name="GitHub Activity Sync",
        replace_existing=True,
        max_instances=1,
    )

    # Start the scheduler
    scheduler.start()
    logger.info("Background scheduler started")

    # Run initial sync after a short delay (10 seconds)
    # This gives the app time to fully initialize
    asyncio.create_task(_delayed_initial_sync())


async def _delayed_initial_sync() -> None:
    """Run initial sync after a delay."""
    await asyncio.sleep(10)
    logger.info("Running initial Obsidian sync...")
    await sync_obsidian_vault()


async def stop_scheduler() -> None:
    """Stop the background scheduler gracefully."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=True)
        logger.info("Background scheduler stopped")
    _scheduler = None


def get_scheduled_jobs() -> List[dict[str, Any]]:
    """Get information about scheduled jobs."""
    scheduler = get_scheduler()
    jobs = []

    for job in scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": next_run.isoformat() if next_run else None,
            "trigger": str(job.trigger),
        })

    return jobs
