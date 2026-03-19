"""Pydantic schemas for skills."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SkillCreate(BaseModel):
    """Schema for creating a new skill."""

    name: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., min_length=1, max_length=100)


class SkillXPLogCreate(BaseModel):
    """Schema for logging XP to a skill."""

    xp_amount: int = Field(..., gt=0, description="XP amount to add")
    source: str = Field(
        default="manual",
        description="Source of XP: 'claude_session', 'manual', 'integration'",
    )
    description: str | None = Field(default=None, description="Optional description")


class SkillXPLogResponse(BaseModel):
    """Schema for XP log response."""

    id: UUID
    skill_id: UUID
    xp_amount: int
    source: str
    description: str | None
    logged_at: datetime

    model_config = {"from_attributes": True}


class SkillResponse(BaseModel):
    """Schema for skill response."""

    id: UUID
    user_id: UUID
    name: str
    category: str
    current_level: int
    current_xp: int
    total_xp: int
    xp_for_next_level: int
    level_progress: float
    created_at: datetime
    last_practiced: datetime | None

    model_config = {"from_attributes": True}


class SkillWithHistoryResponse(BaseModel):
    """Schema for skill with XP history."""

    skill: SkillResponse
    history: list[SkillXPLogResponse]

    model_config = {"from_attributes": True}
