"""
Cost Tracker for the Nexus/Jarvis Agentic System.

Tracks API usage costs and enforces daily budget limits to prevent
runaway spending on AI operations.
"""

from __future__ import annotations

import logging
from datetime import datetime, date
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.cost import APIUsage

logger = logging.getLogger(__name__)

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])


class BudgetExceededError(Exception):
    """Raised when daily budget is exceeded."""

    def __init__(self, daily_usage: float, daily_limit: float):
        self.daily_usage = daily_usage
        self.daily_limit = daily_limit
        super().__init__(
            f"Daily budget exceeded: ${daily_usage:.2f} / ${daily_limit:.2f}"
        )


class CostTracker:
    """
    Tracks API usage costs and enforces budget limits.

    Budget behavior:
    - 80% ($4.00): Log warning
    - 100% ($5.00): Block paid operations, allow free ones
    """

    DAILY_LIMIT: float = 5.00  # $5/day

    # Cost estimates per operation (in dollars)
    COSTS: Dict[str, float] = {
        # AI API calls
        "claude_api_call": 0.03,  # Average per call
        "claude_api_call_small": 0.01,  # Small context
        "claude_api_call_large": 0.10,  # Large context/complex

        # Web operations
        "web_search": 0.01,
        "web_scrape": 0.005,

        # Code operations
        "code_generation": 0.05,
        "code_analysis": 0.02,
        "code_execution": 0.01,

        # Research operations
        "research_topic": 0.10,
        "research_deep": 0.25,

        # Embeddings and vector operations
        "embedding_generation": 0.0001,
        "vector_search": 0.0005,

        # Voice operations
        "voice_transcription": 0.006,  # Per minute of audio
        "voice_synthesis": 0.015,  # Per 1000 chars

        # Free operations (0 cost)
        "database_read": 0.0,
        "database_write": 0.0,
        "file_read": 0.0,
        "file_write": 0.0,
        "cache_hit": 0.0,
        "local_computation": 0.0,
    }

    # Operations that are always free (bypass budget check)
    FREE_OPERATIONS = {
        "database_read",
        "database_write",
        "file_read",
        "file_write",
        "cache_hit",
        "local_computation",
    }

    WARNING_THRESHOLD: float = 0.80  # 80% of daily limit

    def __init__(self, user_id: UUID):
        """
        Initialize cost tracker for a user.

        Args:
            user_id: The user ID to track costs for
        """
        self.user_id = user_id
        self._warning_logged_today: bool = False
        self._last_warning_date: Optional[date] = None

    async def track_cost(
        self,
        operation: str,
        actual_cost: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
        db: Optional[AsyncSession] = None,
    ) -> APIUsage:
        """
        Track a cost for an operation.

        Args:
            operation: The operation type (e.g., "claude_api_call")
            actual_cost: Actual cost if known, otherwise uses estimate
            metadata: Optional metadata about the operation
            db: Optional database session (creates one if not provided)

        Returns:
            The created APIUsage record
        """
        cost = actual_cost if actual_cost is not None else self.get_estimated_cost(operation)

        async def _track(session: AsyncSession) -> APIUsage:
            usage = APIUsage(
                user_id=self.user_id,
                operation=operation,
                cost=cost,
                details=details,
            )
            session.add(usage)
            await session.flush()

            # Check if we should log a warning
            await self._check_and_log_warning(session)

            return usage

        if db is not None:
            return await _track(db)
        else:
            async with get_db_session() as session:
                result = await _track(session)
                return result

    async def get_daily_usage(
        self,
        target_date: Optional[date] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Get usage statistics for a specific day.

        Args:
            target_date: The date to get usage for (defaults to today)
            db: Optional database session

        Returns:
            Dict with total_cost, operation_count, and operations breakdown
        """
        if target_date is None:
            target_date = date.today()

        async def _get_usage(session: AsyncSession) -> Dict[str, Any]:
            # Get start and end of day
            start_of_day = datetime.combine(target_date, datetime.min.time())
            end_of_day = datetime.combine(target_date, datetime.max.time())

            # Query total cost and count
            result = await session.execute(
                select(
                    func.sum(APIUsage.cost).label("total_cost"),
                    func.count(APIUsage.id).label("operation_count"),
                )
                .where(APIUsage.user_id == self.user_id)
                .where(APIUsage.timestamp >= start_of_day)
                .where(APIUsage.timestamp <= end_of_day)
            )
            row = result.one()
            total_cost = row.total_cost or 0.0
            operation_count = row.operation_count or 0

            # Query breakdown by operation
            breakdown_result = await session.execute(
                select(
                    APIUsage.operation,
                    func.sum(APIUsage.cost).label("cost"),
                    func.count(APIUsage.id).label("count"),
                )
                .where(APIUsage.user_id == self.user_id)
                .where(APIUsage.timestamp >= start_of_day)
                .where(APIUsage.timestamp <= end_of_day)
                .group_by(APIUsage.operation)
                .order_by(func.sum(APIUsage.cost).desc())
            )

            operations = {
                row.operation: {"cost": row.cost, "count": row.count}
                for row in breakdown_result
            }

            return {
                "date": target_date.isoformat(),
                "total_cost": round(total_cost, 4),
                "operation_count": operation_count,
                "daily_limit": self.DAILY_LIMIT,
                "remaining_budget": round(max(0, self.DAILY_LIMIT - total_cost), 4),
                "usage_percentage": round((total_cost / self.DAILY_LIMIT) * 100, 2),
                "operations": operations,
            }

        if db is not None:
            return await _get_usage(db)
        else:
            async with get_db_session() as session:
                return await _get_usage(session)

    async def get_remaining_budget(
        self,
        db: Optional[AsyncSession] = None,
    ) -> float:
        """
        Get remaining budget for today.

        Args:
            db: Optional database session

        Returns:
            Remaining budget in dollars
        """
        usage = await self.get_daily_usage(db=db)
        return usage["remaining_budget"]

    async def is_within_budget(
        self,
        estimated_cost: float,
        db: Optional[AsyncSession] = None,
    ) -> bool:
        """
        Check if an operation with estimated cost is within budget.

        Args:
            estimated_cost: The estimated cost of the operation
            db: Optional database session

        Returns:
            True if within budget, False otherwise
        """
        remaining = await self.get_remaining_budget(db=db)
        return remaining >= estimated_cost

    async def get_usage_breakdown(
        self,
        days: int = 7,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Get usage breakdown over multiple days.

        Args:
            days: Number of days to look back
            db: Optional database session

        Returns:
            Dict with daily breakdown and totals
        """
        from datetime import timedelta

        async def _get_breakdown(session: AsyncSession) -> Dict[str, Any]:
            start_date = date.today() - timedelta(days=days - 1)
            start_of_period = datetime.combine(start_date, datetime.min.time())

            # Query daily totals
            result = await session.execute(
                select(
                    func.date(APIUsage.timestamp).label("date"),
                    func.sum(APIUsage.cost).label("cost"),
                    func.count(APIUsage.id).label("count"),
                )
                .where(APIUsage.user_id == self.user_id)
                .where(APIUsage.timestamp >= start_of_period)
                .group_by(func.date(APIUsage.timestamp))
                .order_by(func.date(APIUsage.timestamp))
            )

            daily_usage = []
            total_cost = 0.0
            total_operations = 0

            for row in result:
                day_cost = row.cost or 0.0
                day_count = row.count or 0
                total_cost += day_cost
                total_operations += day_count
                daily_usage.append({
                    "date": str(row.date),
                    "cost": round(day_cost, 4),
                    "operation_count": day_count,
                })

            return {
                "period_days": days,
                "start_date": start_date.isoformat(),
                "end_date": date.today().isoformat(),
                "total_cost": round(total_cost, 4),
                "total_operations": total_operations,
                "average_daily_cost": round(total_cost / days, 4) if days > 0 else 0,
                "daily_limit": self.DAILY_LIMIT,
                "daily_usage": daily_usage,
            }

        if db is not None:
            return await _get_breakdown(db)
        else:
            async with get_db_session() as session:
                return await _get_breakdown(session)

    async def check_budget_before_operation(
        self,
        operation: str,
        db: Optional[AsyncSession] = None,
    ) -> None:
        """
        Check if an operation can proceed within budget.

        Args:
            operation: The operation type
            db: Optional database session

        Raises:
            BudgetExceededError: If budget would be exceeded
        """
        # Free operations always allowed
        if operation in self.FREE_OPERATIONS:
            return

        estimated_cost = self.get_estimated_cost(operation)

        if estimated_cost == 0:
            return

        usage = await self.get_daily_usage(db=db)
        current_usage = usage["total_cost"]

        if current_usage + estimated_cost > self.DAILY_LIMIT:
            raise BudgetExceededError(current_usage, self.DAILY_LIMIT)

    async def _check_and_log_warning(self, db: AsyncSession) -> None:
        """Check usage and log warning if above threshold."""
        today = date.today()

        # Only log warning once per day
        if self._last_warning_date == today and self._warning_logged_today:
            return

        usage = await self.get_daily_usage(db=db)
        usage_ratio = usage["total_cost"] / self.DAILY_LIMIT

        if usage_ratio >= self.WARNING_THRESHOLD:
            logger.warning(
                f"Budget warning: {usage['usage_percentage']:.1f}% of daily limit used "
                f"(${usage['total_cost']:.2f} / ${self.DAILY_LIMIT:.2f})"
            )
            self._warning_logged_today = True
            self._last_warning_date = today

    @classmethod
    def get_estimated_cost(cls, operation: str) -> float:
        """
        Get the estimated cost for an operation.

        Args:
            operation: The operation type

        Returns:
            Estimated cost in dollars
        """
        return cls.COSTS.get(operation, 0.01)  # Default to $0.01 for unknown ops

    @classmethod
    def is_free_operation(cls, operation: str) -> bool:
        """
        Check if an operation is free.

        Args:
            operation: The operation type

        Returns:
            True if the operation is free
        """
        return operation in cls.FREE_OPERATIONS or cls.get_estimated_cost(operation) == 0


def track_cost(operation: str) -> Callable[[F], F]:
    """
    Decorator to track costs for async functions.

    Usage:
        @track_cost("claude_api_call")
        async def call_claude(...):
            ...

    Args:
        operation: The operation type to track

    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Try to get user_id from kwargs or default
            user_id = kwargs.get("user_id")
            if user_id is None:
                # Use default user ID if not provided
                from uuid import UUID
                user_id = UUID("00000000-0000-0000-0000-000000000001")

            tracker = CostTracker(user_id)

            # Check budget before operation (skip for free operations)
            if not CostTracker.is_free_operation(operation):
                await tracker.check_budget_before_operation(operation)

            # Execute the function
            result = await func(*args, **kwargs)

            # Track the cost after successful execution
            await tracker.track_cost(operation)

            return result

        return wrapper  # type: ignore

    return decorator


def track_cost_with_actual(operation: str) -> Callable[[F], F]:
    """
    Decorator for functions that return their actual cost.

    The decorated function should return a tuple of (result, actual_cost).

    Usage:
        @track_cost_with_actual("claude_api_call")
        async def call_claude_with_cost(...) -> tuple[Response, float]:
            ...
            return response, actual_cost

    Args:
        operation: The operation type to track

    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Try to get user_id from kwargs or default
            user_id = kwargs.get("user_id")
            if user_id is None:
                from uuid import UUID
                user_id = UUID("00000000-0000-0000-0000-000000000001")

            tracker = CostTracker(user_id)

            # Check budget before operation (use estimate)
            if not CostTracker.is_free_operation(operation):
                await tracker.check_budget_before_operation(operation)

            # Execute the function
            result, actual_cost = await func(*args, **kwargs)

            # Track the actual cost
            await tracker.track_cost(operation, actual_cost=actual_cost)

            return result

        return wrapper  # type: ignore

    return decorator
