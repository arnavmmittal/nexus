"""Goals API endpoints."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.goal import Goal, GoalProgressLog
from app.schemas.goal import (
    GoalCreate,
    GoalUpdate,
    GoalResponse,
    GoalProgressCreate,
    GoalProgressResponse,
    GoalWithProgressResponse,
)

router = APIRouter()

# Placeholder user ID (will be replaced with auth later)
DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@router.get("", response_model=list[GoalResponse])
async def list_goals(
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: str | None = None,
    domain: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """
    List all goals for the current user.

    Args:
        db: Database session
        status_filter: Filter by status (active, paused, completed, cancelled)
        domain: Filter by domain
        limit: Maximum results
        offset: Pagination offset

    Returns:
        List of goals
    """
    query = select(Goal).where(Goal.user_id == DEFAULT_USER_ID)

    if status_filter:
        query = query.where(Goal.status == status_filter)

    if domain:
        query = query.where(Goal.domain == domain)

    query = query.order_by(Goal.deadline.asc().nullslast()).limit(limit).offset(offset)

    result = await db.execute(query)
    goals = result.scalars().all()

    return goals


@router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
async def create_goal(
    goal_data: GoalCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Create a new goal.

    Args:
        goal_data: Goal creation data
        db: Database session

    Returns:
        Created goal
    """
    goal = Goal(
        user_id=DEFAULT_USER_ID,
        title=goal_data.title,
        domain=goal_data.domain,
        target_type=goal_data.target_type,
        target_value=goal_data.target_value,
        unit=goal_data.unit,
        deadline=goal_data.deadline,
    )
    db.add(goal)
    await db.flush()

    return goal


@router.get("/{goal_id}", response_model=GoalWithProgressResponse)
async def get_goal(
    goal_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    history_limit: int = 20,
):
    """
    Get goal details with progress history.

    Args:
        goal_id: Goal ID
        db: Database session
        history_limit: Maximum history entries

    Returns:
        Goal with progress history
    """
    # Get goal
    result = await db.execute(
        select(Goal).where(Goal.id == goal_id, Goal.user_id == DEFAULT_USER_ID)
    )
    goal = result.scalar_one_or_none()

    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found",
        )

    # Get progress history
    history_result = await db.execute(
        select(GoalProgressLog)
        .where(GoalProgressLog.goal_id == goal_id)
        .order_by(GoalProgressLog.logged_at.desc())
        .limit(history_limit)
    )
    history = history_result.scalars().all()

    return GoalWithProgressResponse(goal=goal, progress_history=history)


@router.patch("/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: UUID,
    goal_data: GoalUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Update a goal.

    Args:
        goal_id: Goal ID
        goal_data: Update data
        db: Database session

    Returns:
        Updated goal
    """
    result = await db.execute(
        select(Goal).where(Goal.id == goal_id, Goal.user_id == DEFAULT_USER_ID)
    )
    goal = result.scalar_one_or_none()

    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found",
        )

    # Update fields
    update_data = goal_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(goal, field, value)

    # If marking as completed, set completed_at
    if goal_data.status == "completed" and goal.completed_at is None:
        goal.completed_at = datetime.utcnow()

    await db.flush()

    return goal


@router.post("/{goal_id}/progress", response_model=GoalResponse)
async def log_progress(
    goal_id: UUID,
    progress_data: GoalProgressCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Log progress for a goal.

    Args:
        goal_id: Goal ID
        progress_data: Progress data
        db: Database session

    Returns:
        Updated goal
    """
    # Get goal
    result = await db.execute(
        select(Goal).where(Goal.id == goal_id, Goal.user_id == DEFAULT_USER_ID)
    )
    goal = result.scalar_one_or_none()

    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found",
        )

    # Create progress log entry
    progress_log = GoalProgressLog(
        goal_id=goal_id,
        previous_value=goal.current_value,
        new_value=progress_data.new_value,
    )
    db.add(progress_log)

    # Update goal
    goal.current_value = progress_data.new_value

    # Check if goal is completed
    if goal.target_value and goal.current_value >= goal.target_value:
        if goal.status != "completed":
            goal.status = "completed"
            goal.completed_at = datetime.utcnow()

    await db.flush()

    return goal


@router.get("/{goal_id}/progress", response_model=list[GoalProgressResponse])
async def get_goal_progress(
    goal_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
):
    """
    Get progress history for a goal.

    Args:
        goal_id: Goal ID
        db: Database session
        limit: Maximum results
        offset: Pagination offset

    Returns:
        List of progress log entries
    """
    # Verify goal exists and belongs to user
    result = await db.execute(
        select(Goal).where(Goal.id == goal_id, Goal.user_id == DEFAULT_USER_ID)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found",
        )

    # Get progress history
    history_result = await db.execute(
        select(GoalProgressLog)
        .where(GoalProgressLog.goal_id == goal_id)
        .order_by(GoalProgressLog.logged_at.desc())
        .limit(limit)
        .offset(offset)
    )

    return history_result.scalars().all()


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    goal_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Delete a goal.

    Args:
        goal_id: Goal ID
        db: Database session
    """
    result = await db.execute(
        select(Goal).where(Goal.id == goal_id, Goal.user_id == DEFAULT_USER_ID)
    )
    goal = result.scalar_one_or_none()

    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found",
        )

    await db.delete(goal)
