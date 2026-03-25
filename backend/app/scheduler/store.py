"""Persistence layer for scheduled actions.

This module provides SQLite-based async storage for scheduled actions,
supporting CRUD operations and queries for pending actions.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

import aiosqlite

from app.scheduler.actions import (
    ActionStatus,
    ActionType,
    CreatedBy,
    ScheduledAction,
)

logger = logging.getLogger(__name__)

# Default database path
DEFAULT_DB_PATH = Path("./data/scheduler.db")


class ActionStore:
    """SQLite-based storage for scheduled actions.

    Provides async CRUD operations for managing scheduled actions
    with support for querying pending actions and bulk updates.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize the action store.

        Args:
            db_path: Path to SQLite database file. Defaults to ./data/scheduler.db
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self._initialized = False
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the database and create tables if needed."""
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            # Ensure directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS scheduled_actions (
                        id TEXT PRIMARY KEY,
                        action_type TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        scheduled_time TEXT NOT NULL,
                        recurring TEXT,
                        created_by TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'pending',
                        description TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        executed_at TEXT,
                        retry_count INTEGER DEFAULT 0,
                        max_retries INTEGER DEFAULT 3,
                        last_error TEXT,
                        result TEXT,
                        metadata TEXT
                    )
                """)

                # Create indexes for common queries
                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_scheduled_time
                    ON scheduled_actions(scheduled_time)
                """)
                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_status
                    ON scheduled_actions(status)
                """)
                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_user_id
                    ON scheduled_actions(user_id)
                """)
                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_status_scheduled
                    ON scheduled_actions(status, scheduled_time)
                """)

                await db.commit()

            self._initialized = True
            logger.info(f"ActionStore initialized at {self.db_path}")

    async def _ensure_initialized(self) -> None:
        """Ensure the store is initialized before operations."""
        if not self._initialized:
            await self.initialize()

    def _action_to_row(self, action: ScheduledAction) -> Dict[str, Any]:
        """Convert a ScheduledAction to a database row."""
        return {
            "id": action.id,
            "action_type": action.action_type.value,
            "payload": json.dumps(action.payload),
            "scheduled_time": action.scheduled_time.isoformat(),
            "recurring": action.recurring,
            "created_by": action.created_by.value,
            "user_id": str(action.user_id),
            "status": action.status.value,
            "description": action.description,
            "created_at": action.created_at.isoformat(),
            "updated_at": action.updated_at.isoformat(),
            "executed_at": action.executed_at.isoformat() if action.executed_at else None,
            "retry_count": action.retry_count,
            "max_retries": action.max_retries,
            "last_error": action.last_error,
            "result": json.dumps(action.result) if action.result else None,
            "metadata": json.dumps(action.metadata),
        }

    def _row_to_action(self, row: aiosqlite.Row) -> ScheduledAction:
        """Convert a database row to a ScheduledAction."""
        return ScheduledAction(
            id=row["id"],
            action_type=ActionType(row["action_type"]),
            payload=json.loads(row["payload"]),
            scheduled_time=datetime.fromisoformat(row["scheduled_time"]),
            recurring=row["recurring"],
            created_by=CreatedBy(row["created_by"]),
            user_id=UUID(row["user_id"]),
            status=ActionStatus(row["status"]),
            description=row["description"] or "",
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            executed_at=datetime.fromisoformat(row["executed_at"]) if row["executed_at"] else None,
            retry_count=row["retry_count"],
            max_retries=row["max_retries"],
            last_error=row["last_error"],
            result=json.loads(row["result"]) if row["result"] else None,
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    async def create(self, action: ScheduledAction) -> ScheduledAction:
        """Create a new scheduled action.

        Args:
            action: The action to create

        Returns:
            The created action with any server-side modifications
        """
        await self._ensure_initialized()

        row = self._action_to_row(action)
        columns = ", ".join(row.keys())
        placeholders = ", ".join(["?" for _ in row])

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f"INSERT INTO scheduled_actions ({columns}) VALUES ({placeholders})",
                list(row.values())
            )
            await db.commit()

        logger.info(f"Created scheduled action: {action.id} - {action.description}")
        return action

    async def get(self, action_id: str) -> Optional[ScheduledAction]:
        """Get a scheduled action by ID.

        Args:
            action_id: The action ID to retrieve

        Returns:
            The action if found, None otherwise
        """
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM scheduled_actions WHERE id = ?",
                (action_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_action(row)

        return None

    async def get_by_user(
        self,
        user_id: UUID,
        status: Optional[ActionStatus] = None,
        limit: int = 100,
    ) -> List[ScheduledAction]:
        """Get scheduled actions for a user.

        Args:
            user_id: The user ID to filter by
            status: Optional status filter
            limit: Maximum number of results

        Returns:
            List of matching actions
        """
        await self._ensure_initialized()

        query = "SELECT * FROM scheduled_actions WHERE user_id = ?"
        params: List[Any] = [str(user_id)]

        if status:
            query += " AND status = ?"
            params.append(status.value)

        query += " ORDER BY scheduled_time ASC LIMIT ?"
        params.append(limit)

        actions = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                async for row in cursor:
                    actions.append(self._row_to_action(row))

        return actions

    async def list_pending(
        self,
        before: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[ScheduledAction]:
        """List pending actions that are due for execution.

        Args:
            before: Only include actions scheduled before this time.
                   Defaults to current time.
            limit: Maximum number of results

        Returns:
            List of pending actions due for execution
        """
        await self._ensure_initialized()

        if before is None:
            before = datetime.now(timezone.utc)

        # Include both PENDING and RETRYING actions
        query = """
            SELECT * FROM scheduled_actions
            WHERE status IN (?, ?)
            AND scheduled_time <= ?
            ORDER BY scheduled_time ASC
            LIMIT ?
        """
        params = [
            ActionStatus.PENDING.value,
            ActionStatus.RETRYING.value,
            before.isoformat(),
            limit,
        ]

        actions = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                async for row in cursor:
                    actions.append(self._row_to_action(row))

        logger.debug(f"Found {len(actions)} pending actions due for execution")
        return actions

    async def list_upcoming(
        self,
        user_id: Optional[UUID] = None,
        hours_ahead: int = 24,
        limit: int = 50,
    ) -> List[ScheduledAction]:
        """List upcoming scheduled actions.

        Args:
            user_id: Optional user ID to filter by
            hours_ahead: How many hours ahead to look
            limit: Maximum number of results

        Returns:
            List of upcoming actions
        """
        await self._ensure_initialized()

        now = datetime.now(timezone.utc)
        future = datetime.fromtimestamp(
            now.timestamp() + (hours_ahead * 3600),
            tz=timezone.utc
        )

        query = """
            SELECT * FROM scheduled_actions
            WHERE status = ?
            AND scheduled_time BETWEEN ? AND ?
        """
        params: List[Any] = [
            ActionStatus.PENDING.value,
            now.isoformat(),
            future.isoformat(),
        ]

        if user_id:
            query += " AND user_id = ?"
            params.append(str(user_id))

        query += " ORDER BY scheduled_time ASC LIMIT ?"
        params.append(limit)

        actions = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                async for row in cursor:
                    actions.append(self._row_to_action(row))

        return actions

    async def update(self, action: ScheduledAction) -> ScheduledAction:
        """Update an existing scheduled action.

        Args:
            action: The action with updated fields

        Returns:
            The updated action
        """
        await self._ensure_initialized()

        action.updated_at = datetime.now(timezone.utc)
        row = self._action_to_row(action)

        # Build UPDATE statement
        set_clause = ", ".join([f"{k} = ?" for k in row.keys() if k != "id"])
        values = [v for k, v in row.items() if k != "id"]
        values.append(action.id)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f"UPDATE scheduled_actions SET {set_clause} WHERE id = ?",
                values
            )
            await db.commit()

        logger.debug(f"Updated scheduled action: {action.id}")
        return action

    async def mark_completed(
        self,
        action_id: str,
        result: Optional[Dict[str, Any]] = None,
    ) -> Optional[ScheduledAction]:
        """Mark an action as completed.

        Args:
            action_id: The action ID to mark completed
            result: Optional result data

        Returns:
            The updated action, or None if not found
        """
        action = await self.get(action_id)
        if not action:
            return None

        action.mark_completed(result)
        return await self.update(action)

    async def mark_failed(
        self,
        action_id: str,
        error: str,
    ) -> Optional[ScheduledAction]:
        """Mark an action as failed.

        Args:
            action_id: The action ID to mark failed
            error: Error message

        Returns:
            The updated action, or None if not found
        """
        action = await self.get(action_id)
        if not action:
            return None

        action.mark_failed(error)
        return await self.update(action)

    async def cancel(self, action_id: str) -> Optional[ScheduledAction]:
        """Cancel a scheduled action.

        Args:
            action_id: The action ID to cancel

        Returns:
            The cancelled action, or None if not found
        """
        action = await self.get(action_id)
        if not action:
            return None

        if action.status in [ActionStatus.COMPLETED, ActionStatus.CANCELLED]:
            logger.warning(f"Cannot cancel action {action_id} with status {action.status}")
            return action

        action.mark_cancelled()
        return await self.update(action)

    async def reschedule(
        self,
        action_id: str,
        new_time: datetime,
        new_recurring: Optional[str] = None,
    ) -> Optional[ScheduledAction]:
        """Reschedule an action to a new time.

        Args:
            action_id: The action ID to reschedule
            new_time: The new scheduled time
            new_recurring: Optional new cron pattern

        Returns:
            The rescheduled action, or None if not found
        """
        action = await self.get(action_id)
        if not action:
            return None

        if action.status not in [ActionStatus.PENDING, ActionStatus.RETRYING]:
            logger.warning(f"Cannot reschedule action {action_id} with status {action.status}")
            return action

        # Ensure timezone
        if new_time.tzinfo is None:
            new_time = new_time.replace(tzinfo=timezone.utc)

        action.scheduled_time = new_time
        if new_recurring is not None:
            action.recurring = new_recurring
        action.status = ActionStatus.PENDING
        action.retry_count = 0
        action.last_error = None

        return await self.update(action)

    async def delete(self, action_id: str) -> bool:
        """Delete a scheduled action.

        Args:
            action_id: The action ID to delete

        Returns:
            True if deleted, False if not found
        """
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM scheduled_actions WHERE id = ?",
                (action_id,)
            )
            await db.commit()
            deleted = cursor.rowcount > 0

        if deleted:
            logger.info(f"Deleted scheduled action: {action_id}")
        return deleted

    async def cleanup_old(self, days: int = 30) -> int:
        """Clean up old completed/failed/cancelled actions.

        Args:
            days: Delete actions older than this many days

        Returns:
            Number of actions deleted
        """
        await self._ensure_initialized()

        cutoff = datetime.fromtimestamp(
            datetime.now(timezone.utc).timestamp() - (days * 86400),
            tz=timezone.utc
        )

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                DELETE FROM scheduled_actions
                WHERE status IN (?, ?, ?)
                AND updated_at < ?
                """,
                [
                    ActionStatus.COMPLETED.value,
                    ActionStatus.FAILED.value,
                    ActionStatus.CANCELLED.value,
                    cutoff.isoformat(),
                ]
            )
            await db.commit()
            deleted = cursor.rowcount

        logger.info(f"Cleaned up {deleted} old scheduled actions")
        return deleted

    async def get_stats(self, user_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Get statistics about scheduled actions.

        Args:
            user_id: Optional user ID to filter by

        Returns:
            Dictionary with action statistics
        """
        await self._ensure_initialized()

        stats = {
            "total": 0,
            "by_status": {},
            "by_type": {},
            "pending_count": 0,
            "upcoming_24h": 0,
        }

        base_query = "SELECT status, COUNT(*) as count FROM scheduled_actions"
        params: List[Any] = []

        if user_id:
            base_query += " WHERE user_id = ?"
            params.append(str(user_id))

        base_query += " GROUP BY status"

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # Count by status
            async with db.execute(base_query, params) as cursor:
                async for row in cursor:
                    stats["by_status"][row["status"]] = row["count"]
                    stats["total"] += row["count"]
                    if row["status"] == ActionStatus.PENDING.value:
                        stats["pending_count"] = row["count"]

            # Count by type
            type_query = "SELECT action_type, COUNT(*) as count FROM scheduled_actions"
            if user_id:
                type_query += " WHERE user_id = ?"
            type_query += " GROUP BY action_type"

            async with db.execute(type_query, params) as cursor:
                async for row in cursor:
                    stats["by_type"][row["action_type"]] = row["count"]

            # Count upcoming 24h
            now = datetime.now(timezone.utc)
            tomorrow = datetime.fromtimestamp(now.timestamp() + 86400, tz=timezone.utc)

            upcoming_query = """
                SELECT COUNT(*) as count FROM scheduled_actions
                WHERE status = ? AND scheduled_time BETWEEN ? AND ?
            """
            upcoming_params: List[Any] = [ActionStatus.PENDING.value, now.isoformat(), tomorrow.isoformat()]

            if user_id:
                upcoming_query += " AND user_id = ?"
                upcoming_params.append(str(user_id))

            async with db.execute(upcoming_query, upcoming_params) as cursor:
                row = await cursor.fetchone()
                if row:
                    stats["upcoming_24h"] = row["count"]

        return stats


# Global store instance
_store: Optional[ActionStore] = None


def get_action_store() -> ActionStore:
    """Get or create the global action store instance."""
    global _store
    if _store is None:
        _store = ActionStore()
    return _store


async def init_action_store() -> ActionStore:
    """Initialize and return the global action store."""
    store = get_action_store()
    await store.initialize()
    return store
