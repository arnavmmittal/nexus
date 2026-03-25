"""Auto-Apply Pipeline - Autonomous job application system.

When enabled, this system will:
1. Monitor job boards for matching opportunities
2. Generate tailored resumes and cover letters
3. Submit applications automatically (with user's consent settings)
4. Track all applications and follow up appropriately

This is Ultron operating at maximum efficiency for your career.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ApplicationStatus(str, Enum):
    """Status of a job application."""
    IDENTIFIED = "identified"           # Job found, not yet applied
    QUEUED = "queued"                   # In queue to apply
    DRAFTING = "drafting"               # Drafting application materials
    PENDING_APPROVAL = "pending_approval"  # Waiting for user approval
    SUBMITTED = "submitted"             # Application submitted
    CONFIRMED = "confirmed"             # Received confirmation
    INTERVIEWING = "interviewing"       # In interview process
    OFFER = "offer"                     # Received offer
    REJECTED = "rejected"               # Rejected
    WITHDRAWN = "withdrawn"             # User withdrew
    EXPIRED = "expired"                 # Job posting expired


@dataclass
class JobOpportunity:
    """A job opportunity found by the system."""
    id: str = field(default_factory=lambda: str(uuid4())[:12])

    # Job details
    title: str = ""
    company: str = ""
    location: str = ""
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    job_type: str = "full-time"
    remote: bool = False
    description: str = ""
    requirements: List[str] = field(default_factory=list)
    url: str = ""
    source: str = ""  # linkedin, indeed, company_site, etc.

    # Match analysis
    match_score: float = 0.0
    match_reasons: List[str] = field(default_factory=list)
    concerns: List[str] = field(default_factory=list)

    # Application materials
    tailored_resume_path: Optional[str] = None
    cover_letter: Optional[str] = None
    custom_answers: Dict[str, str] = field(default_factory=dict)

    # Status tracking
    status: ApplicationStatus = ApplicationStatus.IDENTIFIED
    status_history: List[Dict[str, Any]] = field(default_factory=list)

    # Timestamps
    found_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    applied_at: Optional[str] = None
    last_activity: Optional[str] = None
    follow_up_date: Optional[str] = None

    # User interaction
    user_notes: str = ""
    user_rating: Optional[int] = None  # 1-5 stars

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    def update_status(self, new_status: ApplicationStatus, note: str = ""):
        """Update status with history tracking."""
        self.status_history.append({
            "from": self.status.value,
            "to": new_status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "note": note,
        })
        self.status = new_status
        self.last_activity = datetime.utcnow().isoformat()


class AutoApplyPipeline:
    """The autonomous job application pipeline.

    Workflow:
    1. Jobs are identified by the background monitor
    2. High-match jobs (>85%) are queued for auto-apply
    3. Application materials are generated
    4. Based on autonomy settings:
       - Full auto: Submit immediately
       - With approval: Queue for user approval
    5. Track outcomes and learn from results
    """

    def __init__(self):
        self.opportunities: Dict[str, JobOpportunity] = {}
        self.application_queue: List[str] = []  # Job IDs
        self.daily_applications: int = 0
        self.last_reset: datetime = datetime.utcnow()
        self.running = False

    async def start(self):
        """Start the auto-apply pipeline."""
        self.running = True
        logger.info("Starting auto-apply pipeline...")

        while self.running:
            try:
                # Reset daily counter
                if (datetime.utcnow() - self.last_reset).days >= 1:
                    self.daily_applications = 0
                    self.last_reset = datetime.utcnow()

                # Process queue
                await self._process_queue()

                # Check for follow-ups needed
                await self._check_follow_ups()

            except Exception as e:
                logger.error(f"Auto-apply pipeline error: {e}")

            await asyncio.sleep(300)  # Check every 5 minutes

    async def stop(self):
        """Stop the pipeline."""
        self.running = False
        logger.info("Stopping auto-apply pipeline...")

    def add_opportunity(self, job: JobOpportunity):
        """Add a job opportunity to tracking."""
        self.opportunities[job.id] = job
        logger.info(f"Added opportunity: {job.title} at {job.company} (match: {job.match_score:.0%})")

    def queue_for_application(self, job_id: str):
        """Queue a job for application."""
        if job_id in self.opportunities and job_id not in self.application_queue:
            self.application_queue.append(job_id)
            self.opportunities[job_id].update_status(
                ApplicationStatus.QUEUED,
                "Queued for auto-apply"
            )

    async def _process_queue(self):
        """Process the application queue."""
        from app.core.user_profile import get_user_profile

        profile = get_user_profile()
        prefs = profile.job_preferences

        # Check if auto-apply is enabled
        if not prefs.auto_apply_enabled:
            return

        # Check daily limit
        if self.daily_applications >= prefs.daily_application_limit:
            logger.debug("Daily application limit reached")
            return

        # Process queue
        while self.application_queue and self.daily_applications < prefs.daily_application_limit:
            job_id = self.application_queue.pop(0)
            job = self.opportunities.get(job_id)

            if not job:
                continue

            # Check confidence threshold
            if job.match_score < prefs.auto_apply_confidence_threshold:
                job.update_status(
                    ApplicationStatus.PENDING_APPROVAL,
                    f"Match score {job.match_score:.0%} below threshold"
                )
                continue

            # Generate application materials
            await self._generate_application(job, profile)

            # Check autonomy settings
            if profile.autonomy.auto_apply_jobs_enabled:
                # Full auto mode - submit immediately
                await self._submit_application(job)
                self.daily_applications += 1
            else:
                # Needs approval
                job.update_status(
                    ApplicationStatus.PENDING_APPROVAL,
                    "Ready for submission, awaiting approval"
                )

    async def _generate_application(self, job: JobOpportunity, profile: 'UserProfile'):
        """Generate tailored application materials."""
        job.update_status(ApplicationStatus.DRAFTING, "Generating application materials")

        try:
            # Generate cover letter
            cover_letter = await self._generate_cover_letter(job, profile)
            job.cover_letter = cover_letter

            logger.info(f"Generated application materials for {job.company}")

        except Exception as e:
            logger.error(f"Failed to generate application for {job.company}: {e}")

    async def _generate_cover_letter(self, job: JobOpportunity, profile: 'UserProfile') -> str:
        """Generate a tailored cover letter using AI."""
        try:
            from anthropic import AsyncAnthropic
            from app.core.config import settings

            client = AsyncAnthropic(api_key=settings.anthropic_api_key)

            prompt = f"""Write a compelling cover letter for the following job application.

APPLICANT:
- Name: {profile.full_name}
- Education: {profile.major} at {profile.school}, graduating {profile.graduation_date}
- Skills: {', '.join(profile.primary_skills[:8])}

JOB:
- Title: {job.title}
- Company: {job.company}
- Description: {job.description[:1000]}

REQUIREMENTS:
{chr(10).join(f'- {req}' for req in job.requirements[:5])}

Write a professional, enthusiastic cover letter (3 paragraphs) that:
1. Opens with a compelling hook about why this role excites the candidate
2. Highlights 2-3 relevant skills/experiences that match the requirements
3. Closes with enthusiasm and a call to action

Keep it concise and genuine. Do not be overly formal or use clichés."""

            response = await client.messages.create(
                model="claude-3-haiku-20240307",  # Use Haiku for cost efficiency
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"Cover letter generation failed: {e}")
            return ""

    async def _submit_application(self, job: JobOpportunity):
        """Submit a job application."""
        logger.info(f"Submitting application to {job.company} for {job.title}")

        # For now, simulate submission
        # In production, this would integrate with job board APIs or use browser automation

        job.update_status(ApplicationStatus.SUBMITTED, "Application submitted")
        job.applied_at = datetime.utcnow().isoformat()

        # Schedule follow-up
        follow_up = datetime.utcnow() + timedelta(days=7)
        job.follow_up_date = follow_up.isoformat()

        # Learn from this action
        from app.ai.learning import learn, LearningCategory
        learn(
            category=LearningCategory.JOB_PREFERENCES,
            key=f"applied_to:{job.company}",
            value={
                "title": job.title,
                "match_score": job.match_score,
                "applied_at": job.applied_at,
            },
            context=f"Auto-applied to {job.title} at {job.company}",
        )

    async def _check_follow_ups(self):
        """Check for applications needing follow-up."""
        now = datetime.utcnow()

        for job in self.opportunities.values():
            if job.status != ApplicationStatus.SUBMITTED:
                continue

            if not job.follow_up_date:
                continue

            follow_up = datetime.fromisoformat(job.follow_up_date)
            if now >= follow_up:
                # Create follow-up alert
                from app.daemon.monitor import get_background_monitor, Alert, AlertCategory, AlertPriority

                monitor = get_background_monitor()
                alert = Alert(
                    category=AlertCategory.PROACTIVE_SUGGESTION,
                    priority=AlertPriority.MEDIUM,
                    title=f"Follow up with {job.company}?",
                    message=f"It's been a week since you applied to {job.title}. Consider sending a follow-up email.",
                    data={"job_id": job.id, "job": job.to_dict()},
                    action_required=True,
                    suggested_actions=[
                        "Draft follow-up email",
                        "Mark as no response",
                        "Snooze for 3 days",
                    ],
                )
                monitor._emit_alert(alert)

                # Update follow-up date
                job.follow_up_date = (now + timedelta(days=7)).isoformat()

    def approve_application(self, job_id: str) -> bool:
        """User approves an application for submission."""
        job = self.opportunities.get(job_id)
        if not job or job.status != ApplicationStatus.PENDING_APPROVAL:
            return False

        # Queue for submission
        asyncio.create_task(self._submit_application(job))
        return True

    def reject_application(self, job_id: str, reason: str = "") -> bool:
        """User rejects an application."""
        job = self.opportunities.get(job_id)
        if not job:
            return False

        job.update_status(ApplicationStatus.WITHDRAWN, f"User rejected: {reason}")

        # Learn from rejection
        from app.ai.learning import learn, LearningCategory, FeedbackType
        learn(
            category=LearningCategory.JOB_PREFERENCES,
            key=f"rejected:{job.company}:{job.title}",
            value={"reason": reason, "company": job.company},
            feedback_type=FeedbackType.REJECTION,
            context=f"User rejected application to {job.company}",
        )

        return True

    def get_pending_approvals(self) -> List[JobOpportunity]:
        """Get jobs pending user approval."""
        return [
            job for job in self.opportunities.values()
            if job.status == ApplicationStatus.PENDING_APPROVAL
        ]

    def get_statistics(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        stats = {
            "total_opportunities": len(self.opportunities),
            "by_status": {},
            "daily_applications": self.daily_applications,
            "queue_size": len(self.application_queue),
            "pending_approvals": len(self.get_pending_approvals()),
        }

        for job in self.opportunities.values():
            status = job.status.value
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

        return stats


# Global pipeline instance
_auto_apply_pipeline: Optional[AutoApplyPipeline] = None


def get_auto_apply_pipeline() -> AutoApplyPipeline:
    """Get the global auto-apply pipeline."""
    global _auto_apply_pipeline
    if _auto_apply_pipeline is None:
        _auto_apply_pipeline = AutoApplyPipeline()
    return _auto_apply_pipeline
