"""Pydantic schemas for goals."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GoalCreate(BaseModel):
    """Schema for creating a new goal."""

    title: str = Field(..., min_length=1, max_length=255)
    domain: str = Field(..., min_length=1, max_length=50)
    target_type: str = Field(
        default="numeric", description="Type: 'numeric', 'boolean', 'streak'"
    )
    target_value: float | None = Field(default=None, description="Target value")
    unit: str | None = Field(default=None, max_length=50, description="Unit of measure")
    deadline: date | None = Field(default=None, description="Goal deadline")


class GoalUpdate(BaseModel):
    """Schema for updating a goal."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    domain: str | None = Field(default=None, min_length=1, max_length=50)
    target_value: float | None = None
    unit: str | None = None
    deadline: date | None = None
    status: str | None = Field(default=None, description="Status: 'active', 'paused', 'completed', 'cancelled'")


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
    target_value: float | None
    current_value: float
    unit: str | None
    deadline: date | None
    status: str
    progress_percentage: float
    is_completed: bool
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class GoalWithProgressResponse(BaseModel):
    """Schema for goal with progress history."""

    goal: GoalResponse
    progress_history: list[GoalProgressResponse]

    model_config = {"from_attributes": True}
