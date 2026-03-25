"""API routes for autonomy settings and alerts.

This module provides endpoints for:
- Managing autonomy settings
- Viewing and managing alerts
- Controlling background monitoring
- User profile management
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.user_profile import (
    get_user_profile,
    save_user_profile,
    update_user_profile,
    ActionCategory,
    ConfirmationLevel,
)
from app.daemon import (
    get_background_monitor,
    Alert,
    AlertPriority,
    AlertCategory as DaemonAlertCategory,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ================== SCHEMAS ==================

class AutonomySettingsUpdate(BaseModel):
    """Schema for updating autonomy settings."""
    ultron_enabled: Optional[bool] = None
    background_monitoring_enabled: Optional[bool] = None
    proactive_suggestions_enabled: Optional[bool] = None
    auto_apply_jobs_enabled: Optional[bool] = None
    auto_send_followups_enabled: Optional[bool] = None
    daily_briefing_enabled: Optional[bool] = None
    daily_briefing_time: Optional[str] = None


class ActionConfirmationUpdate(BaseModel):
    """Schema for updating action confirmation levels."""
    action: str = Field(..., description="Action category (e.g., 'email_multiple')")
    level: str = Field(..., description="Confirmation level (always, sensitive, never)")


class JobPreferencesUpdate(BaseModel):
    """Schema for updating job preferences."""
    target_roles: Optional[List[str]] = None
    target_companies: Optional[List[str]] = None
    excluded_companies: Optional[List[str]] = None
    min_salary: Optional[int] = None
    locations: Optional[List[str]] = None
    remote_preference: Optional[str] = None
    auto_apply_enabled: Optional[bool] = None
    auto_apply_confidence_threshold: Optional[float] = None
    daily_application_limit: Optional[int] = None


class UserProfileUpdate(BaseModel):
    """Schema for updating user profile."""
    name: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    current_location: Optional[str] = None
    primary_skills: Optional[List[str]] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    resume_path: Optional[str] = None


class AlertResponse(BaseModel):
    """Schema for alert response."""
    id: str
    category: str
    priority: str
    title: str
    message: str
    action_required: bool
    suggested_actions: List[str]
    created_at: str
    dismissed: bool


# ================== PROFILE ENDPOINTS ==================

@router.get(
    "/profile",
    summary="Get user profile",
    description="Returns the complete user profile including preferences and settings.",
)
async def get_profile() -> Dict[str, Any]:
    """Get the current user profile."""
    profile = get_user_profile()
    return profile.to_dict()


@router.patch(
    "/profile",
    summary="Update user profile",
    description="Update user profile fields.",
)
async def update_profile(update: UserProfileUpdate) -> Dict[str, Any]:
    """Update user profile."""
    updates = {k: v for k, v in update.model_dump().items() if v is not None}
    profile = update_user_profile(**updates)
    return profile.to_dict()


@router.get(
    "/profile/context",
    summary="Get profile context string",
    description="Returns a formatted context string for AI prompts.",
)
async def get_profile_context() -> Dict[str, str]:
    """Get profile context for AI."""
    profile = get_user_profile()
    return {"context": profile.to_context_string()}


# ================== AUTONOMY SETTINGS ==================

@router.get(
    "/settings",
    summary="Get autonomy settings",
    description="Returns all autonomy settings including action confirmation levels.",
)
async def get_autonomy_settings() -> Dict[str, Any]:
    """Get current autonomy settings."""
    profile = get_user_profile()
    return {
        "ultron_enabled": profile.autonomy.ultron_enabled,
        "background_monitoring_enabled": profile.autonomy.background_monitoring_enabled,
        "proactive_suggestions_enabled": profile.autonomy.proactive_suggestions_enabled,
        "auto_apply_jobs_enabled": profile.autonomy.auto_apply_jobs_enabled,
        "auto_send_followups_enabled": profile.autonomy.auto_send_followups_enabled,
        "daily_briefing_enabled": profile.autonomy.daily_briefing_enabled,
        "daily_briefing_time": profile.autonomy.daily_briefing_time,
        "action_confirmations": profile.autonomy.category_overrides,
    }


@router.patch(
    "/settings",
    summary="Update autonomy settings",
    description="Update autonomy settings. Use this to enable/disable features.",
)
async def update_autonomy_settings(update: AutonomySettingsUpdate) -> Dict[str, Any]:
    """Update autonomy settings."""
    profile = get_user_profile()

    if update.ultron_enabled is not None:
        profile.autonomy.ultron_enabled = update.ultron_enabled
    if update.background_monitoring_enabled is not None:
        profile.autonomy.background_monitoring_enabled = update.background_monitoring_enabled
    if update.proactive_suggestions_enabled is not None:
        profile.autonomy.proactive_suggestions_enabled = update.proactive_suggestions_enabled
    if update.auto_apply_jobs_enabled is not None:
        profile.autonomy.auto_apply_jobs_enabled = update.auto_apply_jobs_enabled
    if update.auto_send_followups_enabled is not None:
        profile.autonomy.auto_send_followups_enabled = update.auto_send_followups_enabled
    if update.daily_briefing_enabled is not None:
        profile.autonomy.daily_briefing_enabled = update.daily_briefing_enabled
    if update.daily_briefing_time is not None:
        profile.autonomy.daily_briefing_time = update.daily_briefing_time

    save_user_profile(profile)

    return await get_autonomy_settings()


@router.post(
    "/settings/confirmation",
    summary="Set action confirmation level",
    description="Set the confirmation level for a specific action category.",
)
async def set_action_confirmation(update: ActionConfirmationUpdate) -> Dict[str, str]:
    """Set confirmation level for an action category."""
    profile = get_user_profile()

    # Validate action category
    try:
        ActionCategory(update.action)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action category: {update.action}. Valid: {[a.value for a in ActionCategory]}"
        )

    # Validate confirmation level
    try:
        level = ConfirmationLevel(update.level)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid level: {update.level}. Valid: always, sensitive, financial, never"
        )

    profile.autonomy.category_overrides[update.action] = level
    save_user_profile(profile)

    return {"action": update.action, "level": update.level}


# ================== JOB PREFERENCES ==================

@router.get(
    "/job-preferences",
    summary="Get job preferences",
    description="Returns job search preferences and auto-apply settings.",
)
async def get_job_preferences() -> Dict[str, Any]:
    """Get job preferences."""
    profile = get_user_profile()
    return {
        "target_roles": profile.job_preferences.target_roles,
        "target_companies": profile.job_preferences.target_companies,
        "excluded_companies": profile.job_preferences.excluded_companies,
        "min_salary": profile.job_preferences.min_salary,
        "max_salary": profile.job_preferences.max_salary,
        "locations": profile.job_preferences.locations,
        "remote_preference": profile.job_preferences.remote_preference,
        "company_size": profile.job_preferences.company_size,
        "industries": profile.job_preferences.industries,
        "auto_apply_enabled": profile.job_preferences.auto_apply_enabled,
        "auto_apply_confidence_threshold": profile.job_preferences.auto_apply_confidence_threshold,
        "daily_application_limit": profile.job_preferences.daily_application_limit,
    }


@router.patch(
    "/job-preferences",
    summary="Update job preferences",
    description="Update job search preferences.",
)
async def update_job_preferences(update: JobPreferencesUpdate) -> Dict[str, Any]:
    """Update job preferences."""
    profile = get_user_profile()
    prefs = profile.job_preferences

    if update.target_roles is not None:
        prefs.target_roles = update.target_roles
    if update.target_companies is not None:
        prefs.target_companies = update.target_companies
    if update.excluded_companies is not None:
        prefs.excluded_companies = update.excluded_companies
    if update.min_salary is not None:
        prefs.min_salary = update.min_salary
    if update.locations is not None:
        prefs.locations = update.locations
    if update.remote_preference is not None:
        prefs.remote_preference = update.remote_preference
    if update.auto_apply_enabled is not None:
        prefs.auto_apply_enabled = update.auto_apply_enabled
    if update.auto_apply_confidence_threshold is not None:
        prefs.auto_apply_confidence_threshold = update.auto_apply_confidence_threshold
    if update.daily_application_limit is not None:
        prefs.daily_application_limit = update.daily_application_limit

    save_user_profile(profile)

    return await get_job_preferences()


# ================== ALERTS ==================

@router.get(
    "/alerts",
    summary="Get pending alerts",
    description="Returns all pending (undismissed) alerts from the background monitor.",
    response_model=List[AlertResponse],
)
async def get_alerts(
    limit: int = Query(default=20, le=100),
    priority: Optional[str] = Query(default=None, description="Filter by priority"),
    category: Optional[str] = Query(default=None, description="Filter by category"),
) -> List[Dict[str, Any]]:
    """Get pending alerts."""
    monitor = get_background_monitor()
    alerts = monitor.get_pending_alerts(limit=limit)

    # Apply filters
    if priority:
        try:
            p = AlertPriority(priority)
            alerts = [a for a in alerts if a.priority == p]
        except ValueError:
            pass

    if category:
        try:
            c = DaemonAlertCategory(category)
            alerts = [a for a in alerts if a.category == c]
        except ValueError:
            pass

    return [a.to_dict() for a in alerts]


@router.post(
    "/alerts/{alert_id}/dismiss",
    summary="Dismiss an alert",
    description="Mark an alert as dismissed.",
)
async def dismiss_alert(alert_id: str) -> Dict[str, str]:
    """Dismiss an alert."""
    monitor = get_background_monitor()
    monitor.dismiss_alert(alert_id)
    return {"status": "dismissed", "alert_id": alert_id}


@router.post(
    "/alerts/{alert_id}/act",
    summary="Mark alert as acted upon",
    description="Mark an alert as acted upon (after taking the suggested action).",
)
async def act_on_alert(alert_id: str) -> Dict[str, str]:
    """Mark alert as acted upon."""
    monitor = get_background_monitor()
    monitor.mark_acted_upon(alert_id)
    return {"status": "acted_upon", "alert_id": alert_id}


# ================== MONITOR CONTROL ==================

@router.get(
    "/monitor/status",
    summary="Get monitor status",
    description="Returns the status of the background monitor and its tasks.",
)
async def get_monitor_status() -> Dict[str, Any]:
    """Get background monitor status."""
    monitor = get_background_monitor()

    return {
        "running": monitor.running,
        "total_alerts": len(monitor.alerts),
        "pending_alerts": len(monitor.get_pending_alerts()),
        "tasks": {
            name: {
                "enabled": task.enabled,
                "running": task.running,
                "last_run": task.last_run.isoformat() if task.last_run else None,
                "interval_seconds": task.interval_seconds,
                "error_count": task.error_count,
            }
            for name, task in monitor.tasks.items()
        },
    }


@router.post(
    "/monitor/task/{task_name}/toggle",
    summary="Toggle a monitor task",
    description="Enable or disable a specific monitoring task.",
)
async def toggle_monitor_task(task_name: str, enabled: bool = True) -> Dict[str, Any]:
    """Toggle a monitoring task."""
    monitor = get_background_monitor()

    if task_name not in monitor.tasks:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")

    monitor.tasks[task_name].enabled = enabled

    return {
        "task": task_name,
        "enabled": enabled,
    }
