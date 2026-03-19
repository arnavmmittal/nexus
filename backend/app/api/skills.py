"""Skills API endpoints."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.skill import Skill, SkillXPLog
from app.schemas.skill import (
    SkillCreate,
    SkillResponse,
    SkillXPLogCreate,
    SkillXPLogResponse,
    SkillWithHistoryResponse,
)

router = APIRouter()

# Placeholder user ID (will be replaced with auth later)
DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@router.get("", response_model=list[SkillResponse])
async def list_skills(
    db: Annotated[AsyncSession, Depends(get_db)],
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """
    List all skills for the current user.

    Args:
        db: Database session
        category: Optional filter by category
        limit: Maximum results
        offset: Pagination offset

    Returns:
        List of skills
    """
    query = select(Skill).where(Skill.user_id == DEFAULT_USER_ID)

    if category:
        query = query.where(Skill.category == category)

    query = query.order_by(Skill.last_practiced.desc().nullslast()).limit(limit).offset(offset)

    result = await db.execute(query)
    skills = result.scalars().all()

    return skills


@router.post("", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
async def create_skill(
    skill_data: SkillCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Create a new skill.

    Args:
        skill_data: Skill creation data
        db: Database session

    Returns:
        Created skill
    """
    # Check if skill already exists
    existing = await db.execute(
        select(Skill).where(
            Skill.user_id == DEFAULT_USER_ID,
            Skill.name == skill_data.name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Skill '{skill_data.name}' already exists",
        )

    # Create skill
    skill = Skill(
        user_id=DEFAULT_USER_ID,
        name=skill_data.name,
        category=skill_data.category,
    )
    db.add(skill)
    await db.flush()

    return skill


@router.get("/{skill_id}", response_model=SkillWithHistoryResponse)
async def get_skill(
    skill_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    history_limit: int = 20,
):
    """
    Get skill details with XP history.

    Args:
        skill_id: Skill ID
        db: Database session
        history_limit: Maximum history entries

    Returns:
        Skill with history
    """
    # Get skill
    result = await db.execute(
        select(Skill).where(Skill.id == skill_id, Skill.user_id == DEFAULT_USER_ID)
    )
    skill = result.scalar_one_or_none()

    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found",
        )

    # Get history
    history_result = await db.execute(
        select(SkillXPLog)
        .where(SkillXPLog.skill_id == skill_id)
        .order_by(SkillXPLog.logged_at.desc())
        .limit(history_limit)
    )
    history = history_result.scalars().all()

    return SkillWithHistoryResponse(skill=skill, history=history)


@router.post("/{skill_id}/log", response_model=SkillResponse)
async def log_xp(
    skill_id: UUID,
    log_data: SkillXPLogCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Log XP for a skill.

    Args:
        skill_id: Skill ID
        log_data: XP log data
        db: Database session

    Returns:
        Updated skill
    """
    # Get skill
    result = await db.execute(
        select(Skill).where(Skill.id == skill_id, Skill.user_id == DEFAULT_USER_ID)
    )
    skill = result.scalar_one_or_none()

    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found",
        )

    # Create XP log entry
    xp_log = SkillXPLog(
        skill_id=skill_id,
        xp_amount=log_data.xp_amount,
        source=log_data.source,
        description=log_data.description,
    )
    db.add(xp_log)

    # Update skill XP
    skill.current_xp += log_data.xp_amount
    skill.total_xp += log_data.xp_amount
    skill.last_practiced = datetime.utcnow()

    # Check for level up
    while skill.current_xp >= skill.xp_for_next_level:
        skill.current_xp -= skill.xp_for_next_level
        skill.current_level += 1

    await db.flush()

    return skill


@router.get("/{skill_id}/history", response_model=list[SkillXPLogResponse])
async def get_skill_history(
    skill_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
):
    """
    Get XP history for a skill.

    Args:
        skill_id: Skill ID
        db: Database session
        limit: Maximum results
        offset: Pagination offset

    Returns:
        List of XP log entries
    """
    # Verify skill exists and belongs to user
    result = await db.execute(
        select(Skill).where(Skill.id == skill_id, Skill.user_id == DEFAULT_USER_ID)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found",
        )

    # Get history
    history_result = await db.execute(
        select(SkillXPLog)
        .where(SkillXPLog.skill_id == skill_id)
        .order_by(SkillXPLog.logged_at.desc())
        .limit(limit)
        .offset(offset)
    )

    return history_result.scalars().all()


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Delete a skill.

    Args:
        skill_id: Skill ID
        db: Database session
    """
    result = await db.execute(
        select(Skill).where(Skill.id == skill_id, Skill.user_id == DEFAULT_USER_ID)
    )
    skill = result.scalar_one_or_none()

    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found",
        )

    await db.delete(skill)
