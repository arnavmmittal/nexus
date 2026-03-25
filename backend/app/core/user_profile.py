"""User Profile System - The AI's complete understanding of you.

This is the brain's memory of who you are, what you want, and how you operate.
Both Jarvis and Ultron reference this to make intelligent decisions.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfirmationLevel(str, Enum):
    """When to ask for confirmation before acting."""
    ALWAYS = "always"           # Always ask before any action
    SENSITIVE = "sensitive"     # Ask for emails, posts, applications
    FINANCIAL = "financial"     # Only ask for money-related actions
    NEVER = "never"             # Full autonomy (use with caution)


class ActionCategory(str, Enum):
    """Categories of autonomous actions."""
    EMAIL_SINGLE = "email_single"           # Email to one person
    EMAIL_MULTIPLE = "email_multiple"       # Email to multiple people
    SOCIAL_POST = "social_post"             # LinkedIn, Twitter posts
    JOB_APPLICATION = "job_application"     # Apply to jobs
    CALENDAR_MODIFY = "calendar_modify"     # Change calendar events
    FILE_MODIFY = "file_modify"             # Modify files on system
    FINANCIAL = "financial"                 # Any money-related action
    GITHUB_PR = "github_pr"                 # Create PRs/issues
    RESEARCH = "research"                   # Web research (always allowed)
    NOTIFICATION = "notification"           # Send notifications


@dataclass
class JobPreferences:
    """Job search preferences."""
    target_roles: List[str] = field(default_factory=lambda: [
        "Software Engineer",
        "ML Engineer",
        "AI Engineer",
        "Full Stack Engineer",
        "Backend Engineer",
    ])
    target_companies: List[str] = field(default_factory=list)  # Empty = open to all
    excluded_companies: List[str] = field(default_factory=list)
    min_salary: int = 125000
    max_salary: Optional[int] = None
    locations: List[str] = field(default_factory=lambda: ["San Francisco", "New York", "Remote"])
    remote_preference: str = "hybrid"  # remote, hybrid, onsite, any
    company_size: List[str] = field(default_factory=lambda: ["startup", "mid", "large"])
    industries: List[str] = field(default_factory=lambda: ["tech", "ai", "fintech"])
    visa_sponsorship_required: bool = False

    # Auto-apply settings
    auto_apply_enabled: bool = False
    auto_apply_confidence_threshold: float = 0.85  # Only auto-apply if match > 85%
    daily_application_limit: int = 10


@dataclass
class AutonomySettings:
    """Granular controls for what actions require confirmation."""
    # Default confirmation level
    default_level: ConfirmationLevel = ConfirmationLevel.SENSITIVE

    # Per-category overrides
    category_overrides: Dict[str, ConfirmationLevel] = field(default_factory=lambda: {
        ActionCategory.EMAIL_MULTIPLE.value: ConfirmationLevel.ALWAYS,
        ActionCategory.SOCIAL_POST.value: ConfirmationLevel.ALWAYS,
        ActionCategory.FINANCIAL.value: ConfirmationLevel.ALWAYS,
        ActionCategory.JOB_APPLICATION.value: ConfirmationLevel.SENSITIVE,
        ActionCategory.EMAIL_SINGLE.value: ConfirmationLevel.SENSITIVE,
        ActionCategory.CALENDAR_MODIFY.value: ConfirmationLevel.SENSITIVE,
        ActionCategory.GITHUB_PR.value: ConfirmationLevel.SENSITIVE,
        ActionCategory.FILE_MODIFY.value: ConfirmationLevel.SENSITIVE,
        ActionCategory.RESEARCH.value: ConfirmationLevel.NEVER,
        ActionCategory.NOTIFICATION.value: ConfirmationLevel.NEVER,
    })

    # Master switches
    ultron_enabled: bool = True
    background_monitoring_enabled: bool = True
    proactive_suggestions_enabled: bool = True
    auto_apply_jobs_enabled: bool = False
    auto_send_followups_enabled: bool = False
    auto_schedule_interviews_enabled: bool = False

    # Notification preferences
    daily_briefing_enabled: bool = True
    daily_briefing_time: str = "08:00"  # 24h format
    urgent_alerts_enabled: bool = True

    def requires_confirmation(self, action: ActionCategory) -> bool:
        """Check if an action requires user confirmation."""
        level = self.category_overrides.get(
            action.value,
            self.default_level
        )
        return level in [ConfirmationLevel.ALWAYS, ConfirmationLevel.SENSITIVE]


@dataclass
class UserProfile:
    """Complete user profile - everything the AI knows about you."""

    # Identity
    name: str = "Arnav"
    full_name: str = "Arnav Mittal"
    email: str = ""
    phone: str = ""
    birthday: str = "2003-10-17"
    age: int = 22

    # Current situation
    current_status: str = "student"  # student, employed, job_seeking, etc.
    school: str = "Carnegie Mellon University"
    major: str = "Artificial Intelligence"
    graduation_date: str = "2026-05"
    gpa: Optional[float] = None

    # Location
    current_location: str = ""
    willing_to_relocate: bool = True
    target_locations: List[str] = field(default_factory=lambda: [
        "San Francisco", "New York", "Seattle", "Austin", "Remote"
    ])

    # Skills and experience
    primary_skills: List[str] = field(default_factory=lambda: [
        "Python", "Machine Learning", "Deep Learning", "NLP",
        "React", "TypeScript", "FastAPI", "PyTorch"
    ])
    years_experience: int = 0  # Professional experience
    internships: List[Dict[str, str]] = field(default_factory=list)
    projects: List[Dict[str, str]] = field(default_factory=list)

    # Job search
    job_preferences: JobPreferences = field(default_factory=JobPreferences)

    # Communication style
    communication_style: str = "professional_casual"  # formal, casual, professional_casual
    email_signature: str = ""
    linkedin_url: str = ""
    github_url: str = ""
    portfolio_url: str = ""
    resume_path: str = ""

    # Autonomy settings
    autonomy: AutonomySettings = field(default_factory=AutonomySettings)

    # Learned preferences (updated by AI over time)
    learned_preferences: Dict[str, Any] = field(default_factory=dict)

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        # Convert nested dataclasses
        data["job_preferences"] = asdict(self.job_preferences)
        data["autonomy"] = asdict(self.autonomy)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        """Create from dictionary."""
        if "job_preferences" in data and isinstance(data["job_preferences"], dict):
            data["job_preferences"] = JobPreferences(**data["job_preferences"])
        if "autonomy" in data and isinstance(data["autonomy"], dict):
            data["autonomy"] = AutonomySettings(**data["autonomy"])
        return cls(**data)

    def to_context_string(self) -> str:
        """Generate context string for AI prompts."""
        return self.get_context_for_prompt()

    def get_context_for_prompt(self) -> str:
        """Generate rich context string for AI prompts.

        This provides everything the AI needs to know about the user
        to give personalized, relevant responses.
        """
        lines = [
            "## User Identity",
            f"- **Name**: {self.full_name}",
            f"- **Age**: {self.age} (born {self.birthday})",
            f"- **Status**: {self.current_status.replace('_', ' ').title()}",
            "",
            "## Education",
            f"- **School**: {self.school}",
            f"- **Major**: {self.major}",
            f"- **Graduation**: {self.graduation_date}",
        ]

        if self.gpa:
            lines.append(f"- **GPA**: {self.gpa}")

        lines.extend([
            "",
            "## Skills & Experience",
            f"- **Primary Skills**: {', '.join(self.primary_skills[:8])}",
        ])

        if self.years_experience:
            lines.append(f"- **Professional Experience**: {self.years_experience} years")

        if self.internships:
            lines.append("- **Internships**: " + ", ".join(
                f"{i.get('company', 'Unknown')}" for i in self.internships[:3]
            ))

        lines.extend([
            "",
            "## Career Goals",
            f"- **Target Roles**: {', '.join(self.job_preferences.target_roles[:4])}",
            f"- **Minimum Salary**: ${self.job_preferences.min_salary:,}",
            f"- **Preferred Locations**: {', '.join(self.job_preferences.locations[:3])}",
            f"- **Remote Preference**: {self.job_preferences.remote_preference}",
        ])

        if self.job_preferences.target_companies:
            lines.append(f"- **Target Companies**: {', '.join(self.job_preferences.target_companies[:5])}")

        lines.extend([
            "",
            "## Autonomy Settings",
            f"- **Background Monitoring**: {'Enabled' if self.autonomy.background_monitoring_enabled else 'Disabled'}",
            f"- **Proactive Suggestions**: {'Enabled' if self.autonomy.proactive_suggestions_enabled else 'Disabled'}",
            f"- **Auto-Apply Jobs**: {'Enabled' if self.autonomy.auto_apply_jobs_enabled else 'Disabled'}",
            f"- **Daily Briefing**: {'Enabled at ' + self.autonomy.daily_briefing_time if self.autonomy.daily_briefing_enabled else 'Disabled'}",
        ])

        # Add any learned preferences
        if self.learned_preferences:
            lines.append("")
            lines.append("## Observed Preferences")
            for key, value in list(self.learned_preferences.items())[:5]:
                lines.append(f"- {key}: {value}")

        return "\n".join(lines)


# Global profile instance (loaded from disk/database)
_user_profile: Optional[UserProfile] = None
_profile_path = Path.home() / ".nexus" / "user_profile.json"


def get_user_profile() -> UserProfile:
    """Get the global user profile, loading from disk if needed."""
    global _user_profile

    if _user_profile is None:
        _user_profile = load_user_profile()

    return _user_profile


def load_user_profile() -> UserProfile:
    """Load user profile from disk."""
    if _profile_path.exists():
        try:
            with open(_profile_path, "r") as f:
                data = json.load(f)
            logger.info(f"Loaded user profile from {_profile_path}")
            return UserProfile.from_dict(data)
        except Exception as e:
            logger.warning(f"Failed to load profile: {e}, using defaults")

    # Return default profile for Arnav
    return UserProfile()


def save_user_profile(profile: UserProfile) -> None:
    """Save user profile to disk."""
    global _user_profile
    _user_profile = profile
    profile.updated_at = datetime.utcnow().isoformat()

    _profile_path.parent.mkdir(parents=True, exist_ok=True)
    with open(_profile_path, "w") as f:
        json.dump(profile.to_dict(), f, indent=2)

    logger.info(f"Saved user profile to {_profile_path}")


def update_user_profile(**kwargs) -> UserProfile:
    """Update specific fields of the user profile."""
    profile = get_user_profile()

    for key, value in kwargs.items():
        if hasattr(profile, key):
            setattr(profile, key, value)
        elif hasattr(profile.job_preferences, key):
            setattr(profile.job_preferences, key, value)
        elif hasattr(profile.autonomy, key):
            setattr(profile.autonomy, key, value)

    save_user_profile(profile)
    return profile
