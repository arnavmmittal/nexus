"""Pydantic schemas for cost tracking API."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class OperationBreakdown(BaseModel):
    """Breakdown of cost and count for a single operation type."""

    cost: float = Field(..., description="Total cost for this operation type")
    count: int = Field(..., description="Number of times this operation was performed")


class DailyUsageResponse(BaseModel):
    """Response for daily usage statistics."""

    date: str = Field(..., description="The date (ISO format)")
    total_cost: float = Field(..., description="Total cost for the day")
    operation_count: int = Field(..., description="Total number of operations")
    daily_limit: float = Field(..., description="Daily budget limit")
    remaining_budget: float = Field(..., description="Remaining budget for the day")
    usage_percentage: float = Field(..., description="Percentage of daily limit used")
    operations: Dict[str, OperationBreakdown] = Field(
        ..., description="Breakdown by operation type"
    )


class BudgetResponse(BaseModel):
    """Response for budget status."""

    remaining_budget: float = Field(..., description="Remaining budget for today")
    daily_limit: float = Field(..., description="Daily budget limit")
    current_usage: float = Field(..., description="Current usage for today")
    usage_percentage: float = Field(..., description="Percentage of daily limit used")
    is_warning: bool = Field(
        ..., description="True if usage is above warning threshold (80%)"
    )
    is_exceeded: bool = Field(..., description="True if budget is exceeded")


class DailyHistoryEntry(BaseModel):
    """A single day's usage in history."""

    date: str = Field(..., description="The date (ISO format)")
    cost: float = Field(..., description="Total cost for this day")
    operation_count: int = Field(..., description="Number of operations")


class UsageHistoryResponse(BaseModel):
    """Response for historical usage data."""

    period_days: int = Field(..., description="Number of days in the period")
    start_date: str = Field(..., description="Start date of the period")
    end_date: str = Field(..., description="End date of the period")
    total_cost: float = Field(..., description="Total cost over the period")
    total_operations: int = Field(..., description="Total operations over the period")
    average_daily_cost: float = Field(..., description="Average daily cost")
    daily_limit: float = Field(..., description="Daily budget limit")
    daily_usage: List[DailyHistoryEntry] = Field(
        ..., description="Daily usage breakdown"
    )


class APIUsageRecord(BaseModel):
    """A single API usage record."""

    id: UUID
    operation: str
    cost: float
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class CostEstimates(BaseModel):
    """Available cost estimates for different operations."""

    operations: Dict[str, float] = Field(
        ..., description="Operation name to estimated cost mapping"
    )
    free_operations: List[str] = Field(
        ..., description="List of operations that are free"
    )
    daily_limit: float = Field(..., description="Daily budget limit")
    warning_threshold: float = Field(
        ..., description="Warning threshold as percentage (0-1)"
    )
