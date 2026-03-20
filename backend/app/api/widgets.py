"""Widget data API endpoints."""

import logging
from datetime import datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.integrations.google_calendar import get_google_calendar_integration
from app.integrations.plaid import get_plaid_integration
from app.models.goal import Goal, Streak
from app.models.plaid import PlaidItem, PlaidAccount
from app.models.skill import Skill, SkillXPLog
from app.models.user import User

logger = logging.getLogger(__name__)

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
        Today's focus information including goals, streaks, calendar events, and tasks
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

    # Get today's calendar events (if Google Calendar is connected)
    calendar_events = []
    calendar_connected = False
    try:
        user_result = await db.execute(select(User).where(User.id == DEFAULT_USER_ID))
        user = user_result.scalar_one_or_none()

        if user and user.settings and "google_calendar_tokens" in user.settings:
            calendar_connected = True
            token_data = user.settings["google_calendar_tokens"]
            integration = get_google_calendar_integration(token_data)
            events = await integration.get_todays_events()
            calendar_events = [
                {
                    "id": event.get("id"),
                    "summary": event.get("summary"),
                    "start": event.get("start"),
                    "end": event.get("end"),
                    "is_all_day": event.get("is_all_day", False),
                    "location": event.get("location"),
                }
                for event in events[:10]  # Limit to 10 events for the widget
            ]
    except Exception as e:
        logger.warning(f"Failed to fetch calendar events: {e}")
        # Continue without calendar events

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
        "calendar": {
            "connected": calendar_connected,
            "events": calendar_events,
            "count": len(calendar_events),
        },
        "daily_tasks": [],  # TODO: Integrate with task system
    }


@router.get("/money")
async def get_money_dashboard(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Get financial data for the money widget.

    Uses Plaid integration to fetch real bank/investment data if connected.
    Otherwise returns placeholder indicating setup is needed.

    Returns:
        Financial summary including net worth, spending, and recent transactions
    """
    plaid = get_plaid_integration()

    # Check if Plaid is connected
    items_result = await db.execute(
        select(PlaidItem).where(
            PlaidItem.user_id == DEFAULT_USER_ID, PlaidItem.status == "active"
        )
    )
    items = items_result.scalars().all()

    if not items:
        return {
            "status": "not_connected",
            "message": "Connect your bank accounts to see financial data",
            "summary": {
                "net_worth": None,
                "monthly_spending": None,
                "monthly_income": None,
                "savings_rate": None,
            },
            "accounts": [],
            "recent_transactions": [],
        }

    # Calculate net worth from cached account balances
    accounts_result = await db.execute(
        select(PlaidAccount).where(
            PlaidAccount.user_id == DEFAULT_USER_ID,
            PlaidAccount.include_in_net_worth == True,
        )
    )
    accounts = accounts_result.scalars().all()

    total_assets = 0.0
    total_liabilities = 0.0
    account_list = []

    for acc in accounts:
        balance = acc.current_balance or 0.0
        account_list.append({
            "id": str(acc.id),
            "name": acc.custom_name or acc.name,
            "type": acc.type,
            "subtype": acc.subtype,
            "balance": balance,
            "mask": acc.mask,
        })

        if acc.type in ["depository", "investment", "brokerage", "other"]:
            total_assets += balance
        elif acc.type in ["credit", "loan"]:
            total_liabilities += balance

    net_worth = total_assets - total_liabilities

    # Fetch recent transactions (last 30 days) for spending analysis
    monthly_spending = 0.0
    monthly_income = 0.0
    recent_transactions = []

    if plaid.is_configured:
        for item in items:
            try:
                result = await plaid.get_transactions(item.access_token, days=30)
                monthly_spending += result["summary"]["total_spending"]
                monthly_income += result["summary"]["total_income"]

                # Add recent transactions (limit to first 5 per item for widget)
                recent_transactions.extend(
                    [
                        {
                            "id": t["id"],
                            "date": t.get("date"),
                            "name": t["name"],
                            "amount": t["amount"],
                            "category": t.get("category", "Uncategorized"),
                        }
                        for t in result["transactions"][:5]
                    ]
                )
            except Exception as e:
                logger.warning(f"Failed to fetch transactions for widget: {e}")

    # Sort and limit recent transactions
    recent_transactions.sort(key=lambda x: x.get("date", ""), reverse=True)
    recent_transactions = recent_transactions[:10]

    # Calculate savings rate
    savings_rate = None
    if monthly_income > 0:
        savings_rate = round((monthly_income - monthly_spending) / monthly_income * 100, 1)

    return {
        "status": "connected",
        "institutions": [item.institution_name for item in items if item.institution_name],
        "summary": {
            "net_worth": round(net_worth, 2),
            "total_assets": round(total_assets, 2),
            "total_liabilities": round(total_liabilities, 2),
            "monthly_spending": round(monthly_spending, 2),
            "monthly_income": round(monthly_income, 2),
            "savings_rate": savings_rate,
        },
        "accounts": account_list[:6],  # Limit to 6 accounts for widget
        "recent_transactions": recent_transactions,
        "last_updated": datetime.utcnow().isoformat(),
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
