"""Deep job hunting intelligence.

This module provides advanced job tracking capabilities:
- Scans Gmail for job-related emails (applications, responses, rejections)
- Analyzes browser history for job sites visited
- Correlates data across sources
- Provides unified application tracking
"""

import json
import logging
import os
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class DetectedApplication:
    """A job application detected from various sources."""
    company: str
    position: str = ""
    source: str = ""  # email, browser, manual
    status: str = "detected"  # detected, applied, interviewing, offer, rejected
    applied_date: Optional[str] = None
    last_activity: Optional[str] = None
    emails: List[Dict[str, str]] = field(default_factory=list)
    urls_visited: List[str] = field(default_factory=list)
    notes: str = ""
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Job-related patterns for email detection
JOB_EMAIL_PATTERNS = {
    "application_sent": [
        r"application.*received",
        r"thank you for (your )?application",
        r"we received your application",
        r"application submitted",
        r"you applied to",
    ],
    "interview_request": [
        r"interview invitation",
        r"schedule.*interview",
        r"would like to interview",
        r"next step.*interview",
        r"phone screen",
        r"technical interview",
    ],
    "rejection": [
        r"unfortunately",
        r"not moving forward",
        r"other candidates",
        r"not selected",
        r"position has been filled",
        r"decided to move forward with",
    ],
    "offer": [
        r"pleased to offer",
        r"offer letter",
        r"job offer",
        r"compensation package",
        r"start date",
    ],
}

# Job sites to look for in browser history
JOB_SITES = [
    "linkedin.com/jobs",
    "indeed.com",
    "glassdoor.com",
    "lever.co",
    "greenhouse.io",
    "workday.com",
    "jobs.ashbyhq.com",
    "careers.google.com",
    "jobs.apple.com",
    "amazon.jobs",
    "angel.co/jobs",
    "wellfound.com",
    "ycombinator.com/jobs",
    "workatastartup.com",
]


def get_chrome_history_path() -> Optional[Path]:
    """Get the Chrome history database path based on OS."""
    home = Path.home()

    # macOS
    mac_path = home / "Library/Application Support/Google/Chrome/Default/History"
    if mac_path.exists():
        return mac_path

    # Linux
    linux_path = home / ".config/google-chrome/Default/History"
    if linux_path.exists():
        return linux_path

    # Windows
    win_path = home / "AppData/Local/Google/Chrome/User Data/Default/History"
    if win_path.exists():
        return win_path

    return None


async def scan_browser_history(days: int = 30) -> List[Dict[str, Any]]:
    """Scan Chrome browser history for job-related URLs.

    Args:
        days: Number of days of history to scan

    Returns:
        List of job-related URLs with timestamps
    """
    history_path = get_chrome_history_path()
    if not history_path:
        logger.warning("Chrome history not found")
        return []

    job_urls = []
    cutoff = datetime.now() - timedelta(days=days)
    cutoff_timestamp = cutoff.timestamp() * 1000000  # Chrome uses microseconds

    try:
        # Chrome locks its history file, so copy it first
        import shutil
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            shutil.copy2(history_path, tmp.name)

            conn = sqlite3.connect(tmp.name)
            cursor = conn.cursor()

            # Query for job-related URLs
            for site in JOB_SITES:
                cursor.execute("""
                    SELECT url, title, visit_count, last_visit_time
                    FROM urls
                    WHERE url LIKE ?
                    AND last_visit_time > ?
                    ORDER BY last_visit_time DESC
                """, (f"%{site}%", cutoff_timestamp))

                for row in cursor.fetchall():
                    url, title, visit_count, last_visit = row
                    # Convert Chrome timestamp to datetime
                    visit_date = datetime(1601, 1, 1) + timedelta(microseconds=last_visit)

                    job_urls.append({
                        "url": url,
                        "title": title or "",
                        "visit_count": visit_count,
                        "last_visit": visit_date.isoformat(),
                        "site": site.split('/')[0],
                    })

            conn.close()
            os.unlink(tmp.name)

    except Exception as e:
        logger.error(f"Error scanning browser history: {e}")

    return job_urls


def extract_company_from_email(subject: str, body: str, sender: str) -> Optional[str]:
    """Extract company name from email content."""
    # Try to extract from sender domain
    if "@" in sender:
        domain = sender.split("@")[1].split(".")[0]
        if domain not in ["gmail", "yahoo", "outlook", "hotmail", "mail"]:
            return domain.title()

    # Try common patterns in subject/body
    patterns = [
        r"at\s+([A-Z][A-Za-z0-9\s&]+)",
        r"from\s+([A-Z][A-Za-z0-9\s&]+)",
        r"(?:application|interview).*?(?:at|for|with)\s+([A-Z][A-Za-z0-9\s&]+)",
    ]

    text = f"{subject} {body}"
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()

    return None


def classify_email(subject: str, body: str) -> Optional[str]:
    """Classify an email into job application categories."""
    text = f"{subject} {body}".lower()

    for category, patterns in JOB_EMAIL_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return category

    return None


async def scan_gmail_for_jobs(days: int = 90) -> List[Dict[str, Any]]:
    """Scan Gmail for job-related emails.

    Requires Gmail API credentials to be configured.

    Args:
        days: Number of days to scan

    Returns:
        List of job-related emails with classifications
    """
    job_emails = []

    try:
        # Try to use existing Gmail integration
        from app.integrations.email_tools import search_emails

        # Search for job-related emails
        queries = [
            "application received",
            "interview invitation",
            "job offer",
            "thank you for applying",
            "your application",
        ]

        for query in queries:
            result = await search_emails(query=query, max_results=50)
            result_data = json.loads(result)

            if "emails" in result_data:
                for email in result_data["emails"]:
                    classification = classify_email(
                        email.get("subject", ""),
                        email.get("snippet", "")
                    )
                    if classification:
                        company = extract_company_from_email(
                            email.get("subject", ""),
                            email.get("snippet", ""),
                            email.get("from", "")
                        )
                        job_emails.append({
                            "id": email.get("id"),
                            "subject": email.get("subject"),
                            "from": email.get("from"),
                            "date": email.get("date"),
                            "classification": classification,
                            "company": company,
                            "snippet": email.get("snippet", "")[:200],
                        })

    except Exception as e:
        logger.warning(f"Gmail scanning not available: {e}")

    return job_emails


async def aggregate_job_applications() -> str:
    """Aggregate job application data from all sources.

    Returns:
        JSON string with unified application tracking
    """
    applications: Dict[str, DetectedApplication] = {}

    # Scan browser history
    logger.info("Scanning browser history for job sites...")
    browser_urls = await scan_browser_history(days=60)

    for url_info in browser_urls:
        # Extract company from URL
        company = None
        url = url_info["url"]
        title = url_info.get("title", "")

        # Try to extract company from lever/greenhouse URLs
        if "lever.co" in url or "greenhouse.io" in url:
            parts = url.split("/")
            for i, part in enumerate(parts):
                if part in ["lever.co", "greenhouse.io"] and i + 1 < len(parts):
                    company = parts[i + 1].replace("-", " ").title()
                    break

        # Extract from title
        if not company and title:
            # Remove common suffixes
            title_clean = re.sub(r"\s*[\-\|].*$", "", title)
            if len(title_clean) < 50:
                company = title_clean

        if company and company not in applications:
            applications[company] = DetectedApplication(
                company=company,
                source="browser",
                urls_visited=[url],
                last_activity=url_info.get("last_visit"),
                confidence=0.6,
            )
        elif company:
            applications[company].urls_visited.append(url)

    # Scan Gmail
    logger.info("Scanning Gmail for job-related emails...")
    job_emails = await scan_gmail_for_jobs(days=90)

    for email in job_emails:
        company = email.get("company")
        if not company:
            continue

        if company not in applications:
            applications[company] = DetectedApplication(
                company=company,
                source="email",
                emails=[email],
                confidence=0.8,
            )
        else:
            applications[company].emails.append(email)
            applications[company].confidence = min(1.0, applications[company].confidence + 0.2)

        # Update status based on email classification
        classification = email.get("classification")
        if classification == "application_sent":
            applications[company].status = "applied"
            applications[company].applied_date = email.get("date")
        elif classification == "interview_request":
            applications[company].status = "interviewing"
        elif classification == "rejection":
            applications[company].status = "rejected"
        elif classification == "offer":
            applications[company].status = "offer"

        applications[company].last_activity = email.get("date")

    # Sort by confidence and last activity
    sorted_apps = sorted(
        applications.values(),
        key=lambda x: (x.confidence, x.last_activity or ""),
        reverse=True
    )

    return json.dumps({
        "total_detected": len(sorted_apps),
        "by_status": {
            "applied": len([a for a in sorted_apps if a.status == "applied"]),
            "interviewing": len([a for a in sorted_apps if a.status == "interviewing"]),
            "offer": len([a for a in sorted_apps if a.status == "offer"]),
            "rejected": len([a for a in sorted_apps if a.status == "rejected"]),
            "detected": len([a for a in sorted_apps if a.status == "detected"]),
        },
        "applications": [a.to_dict() for a in sorted_apps],
        "sources_scanned": {
            "browser_urls": len(browser_urls),
            "emails": len(job_emails),
        },
    }, indent=2)


async def get_job_recommendations(skills: List[str] = None, preferences: Dict[str, Any] = None) -> str:
    """Get personalized job recommendations based on history and preferences.

    Args:
        skills: List of skills to match
        preferences: Job preferences (location, salary, remote, etc.)

    Returns:
        JSON with job recommendations
    """
    # Analyze past applications to understand preferences
    aggregated = await aggregate_job_applications()
    history = json.loads(aggregated)

    # Extract patterns from history
    companies_applied = [a["company"] for a in history.get("applications", [])]

    # Use job search to find similar opportunities
    from app.integrations.jobs import search_jobs

    recommendations = []

    # Search based on skills
    if skills:
        for skill in skills[:3]:  # Limit to top 3 skills
            result = await search_jobs(
                query=skill,
                location=preferences.get("location", ""),
                job_type=preferences.get("job_type", "full-time"),
            )
            result_data = json.loads(result)
            if "jobs" in result_data:
                recommendations.extend(result_data["jobs"])

    # Deduplicate
    seen = set()
    unique_recommendations = []
    for job in recommendations:
        key = f"{job.get('company')}_{job.get('title')}"
        if key not in seen:
            seen.add(key)
            # Check if already applied
            job["already_applied"] = job.get("company", "").lower() in [c.lower() for c in companies_applied]
            unique_recommendations.append(job)

    return json.dumps({
        "recommendations": unique_recommendations[:20],
        "based_on_skills": skills,
        "excluded_applied": len([j for j in unique_recommendations if j.get("already_applied")]),
    }, indent=2)


# Tool definitions
JOB_INTELLIGENCE_TOOLS = [
    {
        "name": "scan_job_applications",
        "description": "Scan email and browser history to find all job applications. Returns a comprehensive list of detected applications with status, company, and activity timeline.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_job_recommendations",
        "description": "Get personalized job recommendations based on skills and preferences. Analyzes past applications and suggests new opportunities.",
        "input_schema": {
            "type": "object",
            "properties": {
                "skills": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of skills to match against job listings"
                },
                "location": {
                    "type": "string",
                    "description": "Preferred job location"
                },
                "remote": {
                    "type": "boolean",
                    "description": "Whether to include remote jobs"
                }
            },
            "required": []
        }
    },
]
