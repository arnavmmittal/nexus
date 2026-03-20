"""Pydantic schemas for goals."""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class GoalCreate(BaseModel):
    """Schema for creating a new goal."""

    title: str = Field(..., min_length=1, max_length=255)
    domain: str = Field(..., min_length=1, max_length=50)
    target_type: str = Field(
        default="numeric", description="Type: 'numeric', 'boolean', 'streak'"
    )
    target_value: Optional[float] = Field(default=None, description="Target value")
    unit: Optional[str] = Field(default=None, max_length=50, description="Unit of measure")
    deadline: Optional[date] = Field(default=None, description="Goal deadline")


class GoalUpdate(BaseModel):
    """Schema for updating a goal."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    domain: Optional[str] = Field(default=None, min_length=1, max_length=50)
    target_value: Optional[float] = None
    unit: Optional[str] = None
    deadline: Optional[date] = None
    status: Optional[str] = Field(default=None, description="Status: 'active', 'paused', 'completed', 'cancelled'")


class GoalProgressCreate(BaseModel):
    """Schema for logging goal progress."""

    new_value: float = Field(..., description="New progress value")


class GoalProgressResponse(BaseModel):
    """Schema for goal progress log response."""

    id: UUID
    goal_id: UUID
    previous_value: float
    new_value: float
    logged_at: datetime

    model_config = {"from_attributes": True}


class GoalResponse(BaseModel):
    """Schema for goal response."""

    id: UUID
    user_id: UUID
    title: str
    domain: str
    target_type: str
    target_value: Optional[float]
    current_value: float
    unit: Optional[str]
    deadline: Optional[date]
    status: str
    progress_percentage: float
    is_completed: bool
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class GoalWithProgressResponse(BaseModel):
    """Schema for goal with progress history."""

    goal: GoalResponse
    progress_history: List[GoalProgressResponse]

    model_config = {"from_attributes": True}
