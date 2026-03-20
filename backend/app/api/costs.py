"""
Costs API endpoints for tracking and managing API usage costs.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.cost import APIUsage
from app.agent.cost_tracker import CostTracker
from app.schemas.cost import (
    APIUsageRecord,
    BudgetResponse,
    CostEstimates,
    DailyUsageResponse,
    UsageHistoryResponse,
)

router = APIRouter()

# Placeholder user ID (will be replaced with auth later)
DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


def get_cost_tracker() -> CostTracker:
    """Get a CostTracker instance for the current user."""
    return CostTracker(DEFAULT_USER_ID)


@router.get("/today", response_model=DailyUsageResponse)
async def get_today_usage(
    db: Annotated[AsyncSession, Depends(get_db)],
    tracker: Annotated[CostTracker, Depends(get_cost_tracker)],
):
    """
    Get today's API usage statistics.

    Returns:
        Daily usage including total cost, operation counts, and breakdown
    """
    usage = await tracker.get_daily_usage(db=db)
    return usage


@router.get("/budget", response_model=BudgetResponse)
async def get_budget_status(
    db: Annotated[AsyncSession, Depends(get_db)],
    tracker: Annotated[CostTracker, Depends(get_cost_tracker)],
):
    """
    Get current budget status.

    Returns:
        Remaining budget, usage percentage, and warning/exceeded flags
    """
    usage = await tracker.get_daily_usage(db=db)

    return BudgetResponse(
        remaining_budget=usage["remaining_budget"],
        daily_limit=usage["daily_limit"],
        current_usage=usage["total_cost"],
        usage_percentage=usage["usage_percentage"],
        is_warning=usage["usage_percentage"] >= (CostTracker.WARNING_THRESHOLD * 100),
        is_exceeded=usage["total_cost"] >= CostTracker.DAILY_LIMIT,
    )


@router.get("/history", response_model=UsageHistoryResponse)
async def get_usage_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    tracker: Annotated[CostTracker, Depends(get_cost_tracker)],
    days: int = Query(default=7, ge=1, le=90, description="Number of days to look back"),
):
    """
    Get historical usage data.

    Args:
        days: Number of days to look back (1-90, default 7)

    Returns:
        Historical usage data with daily breakdown
    """
    breakdown = await tracker.get_usage_breakdown(days=days, db=db)
    return breakdown


@router.get("/records", response_model=List[APIUsageRecord])
async def get_usage_records(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=200, description="Maximum records to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    operation: Optional[str] = Query(default=None, description="Filter by operation type"),
    start_date: Optional[date] = Query(default=None, description="Filter from date"),
    end_date: Optional[date] = Query(default=None, description="Filter until date"),
):
    """
    Get individual usage records.

    Args:
        limit: Maximum records to return
        offset: Pagination offset
        operation: Optional filter by operation type
        start_date: Optional filter by start date
        end_date: Optional filter by end date

    Returns:
        List of API usage records
    """
    query = (
        select(APIUsage)
        .where(APIUsage.user_id == DEFAULT_USER_ID)
        .order_by(APIUsage.timestamp.desc())
    )

    if operation:
        query = query.where(APIUsage.operation == operation)

    if start_date:
        start_datetime = datetime.combine(start_date, datetime.min.time())
        query = query.where(APIUsage.timestamp >= start_datetime)

    if end_date:
        end_datetime = datetime.combine(end_date, datetime.max.time())
        query = query.where(APIUsage.timestamp <= end_datetime)

    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    records = result.scalars().all()

    return records


@router.get("/estimates", response_model=CostEstimates)
async def get_cost_estimates():
    """
    Get cost estimates for all operations.

    Returns:
        Dictionary of operation types and their estimated costs
    """
    return CostEstimates(
        operations=CostTracker.COSTS,
        free_operations=list(CostTracker.FREE_OPERATIONS),
        daily_limit=CostTracker.DAILY_LIMIT,
        warning_threshold=CostTracker.WARNING_THRESHOLD,
    )


@router.get("/date/{target_date}", response_model=DailyUsageResponse)
async def get_usage_by_date(
    target_date: date,
    db: Annotated[AsyncSession, Depends(get_db)],
    tracker: Annotated[CostTracker, Depends(get_cost_tracker)],
):
    """
    Get usage statistics for a specific date.

    Args:
        target_date: The date to get usage for

    Returns:
        Daily usage statistics for the specified date
    """
    # Don't allow future dates
    if target_date > date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot query future dates",
        )

    usage = await tracker.get_daily_usage(target_date=target_date, db=db)
    return usage


@router.get("/can-afford/{operation}")
async def check_can_afford_operation(
    operation: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    tracker: Annotated[CostTracker, Depends(get_cost_tracker)],
):
    """
    Check if the user can afford to perform an operation.

    Args:
        operation: The operation type to check

    Returns:
        Whether the operation can be afforded and relevant budget info
    """
    estimated_cost = CostTracker.get_estimated_cost(operation)
    is_free = CostTracker.is_free_operation(operation)

    if is_free:
        return {
            "can_afford": True,
            "is_free": True,
            "operation": operation,
            "estimated_cost": 0.0,
        }

    can_afford = await tracker.is_within_budget(estimated_cost, db=db)
    remaining = await tracker.get_remaining_budget(db=db)

    return {
        "can_afford": can_afford,
        "is_free": False,
        "operation": operation,
        "estimated_cost": estimated_cost,
        "remaining_budget": remaining,
        "would_exceed": not can_afford,
    }
