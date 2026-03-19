"""Widget data API endpoints."""

from datetime import datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.goal import Goal, Streak
from app.models.skill import Skill, SkillXPLog

router = APIRouter()

# Placeholder user ID (will be replaced with auth later)
DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@router.get("/today")
async def get_todays_focus(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Get today's focus data for the widget.

    Returns:
        Today's focus information including goals, streaks, and tasks
    """
    today = datetime.now().date()

    # Get active goals with nearest deadlines
    goals_result = await db.execute(
        select(Goal)
        .where(Goal.user_id == DEFAULT_USER_ID, Goal.status == "active")
        .order_by(Goal.deadline.asc().nullslast())
        .limit(3)
    )
    active_goals = goals_result.scalars().all()

    # Get active streaks
    streaks_result = await db.execute(
        select(Streak)
        .where(Streak.user_id == DEFAULT_USER_ID, Streak.current_count > 0)
        .order_by(Streak.current_count.desc())
        .limit(5)
    )
    active_streaks = streaks_result.scalars().all()

    return {
        "date": today.isoformat(),
        "focus_goals": [
            {
                "id": str(g.id),
                "title": g.title,
                "progress": g.progress_percentage,
                "deadline": g.deadline.isoformat() if g.deadline else None,
            }
            for g in active_goals
        ],
        "active_streaks": [
            {
                "activity": s.activity,
                "count": s.current_count,
                "longest": s.longest_count,
            }
            for s in active_streaks
        ],
        "daily_tasks": [],  # TODO: Integrate with task system
    }


@router.get("/money")
async def get_money_dashboard(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Get financial data for the money widget.

    Returns:
        Financial summary (placeholder for Plaid integration)
    """
    # Placeholder - will integrate with Plaid
    return {
        "status": "not_connected",
        "message": "Connect your bank accounts to see financial data",
        "summary": {
            "net_worth": None,
            "monthly_spending": None,
            "monthly_income": None,
            "savings_rate": None,
        },
    }


@router.get("/skills")
async def get_skills_widget(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Get skill progress data for the widget.

    Returns:
        Skill progress summary
    """
    # Get top skills by level
    skills_result = await db.execute(
        select(Skill)
        .where(Skill.user_id == DEFAULT_USER_ID)
        .order_by(Skill.total_xp.desc())
        .limit(6)
    )
    top_skills = skills_result.scalars().all()

    # Get recently practiced
    recent_result = await db.execute(
        select(Skill)
        .where(
            Skill.user_id == DEFAULT_USER_ID,
            Skill.last_practiced.isnot(None),
        )
        .order_by(Skill.last_practiced.desc())
        .limit(3)
    )
    recent_skills = recent_result.scalars().all()

    # Get XP gained this week
    week_ago = datetime.now() - timedelta(days=7)
    xp_result = await db.execute(
        select(func.sum(SkillXPLog.xp_amount))
        .join(Skill)
        .where(
            Skill.user_id == DEFAULT_USER_ID,
            SkillXPLog.logged_at >= week_ago,
        )
    )
    weekly_xp = xp_result.scalar() or 0

    return {
        "top_skills": [
            {
                "id": str(s.id),
                "name": s.name,
                "category": s.category,
                "level": s.current_level,
                "progress": s.level_progress,
                "total_xp": s.total_xp,
            }
            for s in top_skills
        ],
        "recently_practiced": [
            {
                "id": str(s.id),
                "name": s.name,
                "last_practiced": s.last_practiced.isoformat() if s.last_practiced else None,
            }
            for s in recent_skills
        ],
        "weekly_xp": weekly_xp,
        "total_skills": len(top_skills),
    }


@router.get("/health")
async def get_health_snapshot(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Get health data for the widget.

    Returns:
        Health summary (placeholder for health tracking integration)
    """
    # Placeholder - will integrate with health tracking service
    return {
        "status": "not_connected",
        "message": "Connect a health tracking service to see health metrics",
        "summary": {
            "steps_today": None,
            "sleep_hours": None,
            "exercise_minutes": None,
            "heart_rate": None,
        },
    }


@router.get("/goals")
async def get_goals_widget(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Get goal progress data for the widget.

    Returns:
        Goal progress summary
    """
    # Get active goals
    active_result = await db.execute(
        select(Goal)
        .where(Goal.user_id == DEFAULT_USER_ID, Goal.status == "active")
        .order_by(Goal.deadline.asc().nullslast())
    )
    active_goals = active_result.scalars().all()

    # Get recently completed
    completed_result = await db.execute(
        select(Goal)
        .where(Goal.user_id == DEFAULT_USER_ID, Goal.status == "completed")
        .order_by(Goal.completed_at.desc())
        .limit(3)
    )
    completed_goals = completed_result.scalars().all()

    # Group by domain
    by_domain: dict[str, list] = {}
    for goal in active_goals:
        if goal.domain not in by_domain:
            by_domain[goal.domain] = []
        by_domain[goal.domain].append(
            {
                "id": str(goal.id),
                "title": goal.title,
                "progress": goal.progress_percentage,
                "deadline": goal.deadline.isoformat() if goal.deadline else None,
            }
        )

    return {
        "active_count": len(active_goals),
        "completed_count": len(completed_goals),
        "by_domain": by_domain,
        "recently_completed": [
            {
                "id": str(g.id),
                "title": g.title,
                "completed_at": g.completed_at.isoformat() if g.completed_at else None,
            }
            for g in completed_goals
        ],
    }
