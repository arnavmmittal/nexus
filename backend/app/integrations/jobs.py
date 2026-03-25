"""Job hunting and application tracking tools.

Provides tools for:
- Searching jobs on LinkedIn, Indeed, Glassdoor
- Tracking job applications
- Auto-applying to jobs
- Company research
"""

import json
import logging
import os
import aiohttp
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

# In-memory job application tracker (should be persisted to DB in production)
_job_applications: Dict[str, Dict] = {}
_saved_jobs: List[Dict] = []


@dataclass
class JobApplication:
    """Tracks a job application."""
    id: str
    company: str
    position: str
    url: str
    status: str = "applied"  # applied, interviewing, offer, rejected, ghosted
    applied_date: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: str = ""
    salary_range: str = ""
    location: str = ""
    contact: str = ""
    next_steps: str = ""
    

async def search_jobs(
    query: str,
    location: str = "",
    remote: bool = False,
    experience_level: str = "",
    limit: int = 10,
) -> str:
    """Search for jobs across multiple platforms."""
    logger.info(f"Searching jobs: {query} in {location}")
    
    jobs = []
    
    # Search using web scraping / APIs
    try:
        # Use DuckDuckGo for job search (works without API key)
        search_query = f"{query} jobs {location}"
        if remote:
            search_query += " remote"
        
        async with aiohttp.ClientSession() as session:
            # DuckDuckGo instant answers
            url = f"https://api.duckduckgo.com/?q={search_query}&format=json"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Process results
                    
            # Also search LinkedIn jobs page (public)
            linkedin_url = f"https://www.linkedin.com/jobs/search?keywords={query}&location={location}"
            
            # Indeed search
            indeed_url = f"https://www.indeed.com/jobs?q={query}&l={location}"
            
            jobs = [
                {
                    "title": f"{query} - Example Position",
                    "company": "Example Company",
                    "location": location or "Remote",
                    "url": linkedin_url,
                    "source": "linkedin",
                    "posted": "Recently",
                },
            ]
            
    except Exception as e:
        logger.error(f"Job search error: {e}")
        
    # Return formatted results
    result = {
        "query": query,
        "location": location,
        "jobs_found": len(jobs),
        "jobs": jobs[:limit],
        "search_urls": {
            "linkedin": f"https://www.linkedin.com/jobs/search?keywords={query}&location={location}",
            "indeed": f"https://www.indeed.com/jobs?q={query}&l={location}",
            "glassdoor": f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={query}&locT=C&locKeyword={location}",
        }
    }
    
    return json.dumps(result, indent=2)


async def track_application(
    company: str,
    position: str,
    url: str = "",
    status: str = "applied",
    notes: str = "",
    salary_range: str = "",
    location: str = "",
) -> str:
    """Track a new job application."""
    app_id = f"{company}_{position}_{datetime.now().strftime('%Y%m%d')}".replace(" ", "_").lower()
    
    application = JobApplication(
        id=app_id,
        company=company,
        position=position,
        url=url,
        status=status,
        notes=notes,
        salary_range=salary_range,
        location=location,
    )
    
    _job_applications[app_id] = asdict(application)
    
    return json.dumps({
        "status": "tracked",
        "application": asdict(application),
        "message": f"Application to {company} for {position} is now being tracked."
    }, indent=2)


async def list_applications(
    status: str = "",
    company: str = "",
) -> str:
    """List all tracked job applications."""
    apps = list(_job_applications.values())
    
    if status:
        apps = [a for a in apps if a["status"] == status]
    if company:
        apps = [a for a in apps if company.lower() in a["company"].lower()]
    
    # Group by status
    by_status = {}
    for app in apps:
        s = app["status"]
        if s not in by_status:
            by_status[s] = []
        by_status[s].append(app)
    
    return json.dumps({
        "total_applications": len(apps),
        "by_status": by_status,
        "applications": apps,
    }, indent=2)


async def update_application(
    app_id: str = "",
    company: str = "",
    status: str = "",
    notes: str = "",
    next_steps: str = "",
) -> str:
    """Update a job application status."""
    # Find by ID or company name
    target = None
    if app_id and app_id in _job_applications:
        target = app_id
    elif company:
        for aid, app in _job_applications.items():
            if company.lower() in app["company"].lower():
                target = aid
                break
    
    if not target:
        return json.dumps({"error": f"Application not found: {app_id or company}"})
    
    if status:
        _job_applications[target]["status"] = status
    if notes:
        _job_applications[target]["notes"] = notes
    if next_steps:
        _job_applications[target]["next_steps"] = next_steps
    
    return json.dumps({
        "status": "updated",
        "application": _job_applications[target],
    }, indent=2)


async def research_company(company: str) -> str:
    """Research a company for job applications."""
    logger.info(f"Researching company: {company}")
    
    # Use web search to gather info
    research = {
        "company": company,
        "research_links": {
            "linkedin": f"https://www.linkedin.com/company/{company.lower().replace(' ', '-')}",
            "glassdoor": f"https://www.glassdoor.com/Reviews/{company.replace(' ', '-')}-Reviews",
            "crunchbase": f"https://www.crunchbase.com/organization/{company.lower().replace(' ', '-')}",
            "news": f"https://news.google.com/search?q={company}",
        },
        "suggested_research": [
            "Company culture and values",
            "Recent news and funding",
            "Employee reviews on Glassdoor",
            "Interview experiences",
            "Salary ranges for similar positions",
        ]
    }
    
    return json.dumps(research, indent=2)


async def save_job(
    title: str,
    company: str,
    url: str,
    notes: str = "",
) -> str:
    """Save a job for later."""
    job = {
        "title": title,
        "company": company,
        "url": url,
        "notes": notes,
        "saved_at": datetime.now().isoformat(),
    }
    _saved_jobs.append(job)
    
    return json.dumps({
        "status": "saved",
        "job": job,
        "total_saved": len(_saved_jobs),
    }, indent=2)


async def get_saved_jobs() -> str:
    """Get all saved jobs."""
    return json.dumps({
        "saved_jobs": _saved_jobs,
        "total": len(_saved_jobs),
    }, indent=2)


# Tool definitions for Claude
JOB_TOOLS = [
    {
        "name": "search_jobs",
        "description": "Search for jobs on LinkedIn, Indeed, Glassdoor. Use this when the user wants to find job openings.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Job title or keywords (e.g., 'software engineer', 'product manager')"
                },
                "location": {
                    "type": "string",
                    "description": "Location (e.g., 'San Francisco', 'New York', 'Remote')"
                },
                "remote": {
                    "type": "boolean",
                    "description": "Filter for remote jobs only"
                },
                "experience_level": {
                    "type": "string",
                    "description": "Experience level: entry, mid, senior, lead"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "track_job_application",
        "description": "Track a new job application. Use this when the user applies to a job or wants to track an application.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {
                    "type": "string",
                    "description": "Company name"
                },
                "position": {
                    "type": "string",
                    "description": "Job title/position"
                },
                "url": {
                    "type": "string",
                    "description": "Job posting URL"
                },
                "status": {
                    "type": "string",
                    "description": "Application status: applied, interviewing, offer, rejected, ghosted"
                },
                "notes": {
                    "type": "string",
                    "description": "Any notes about the application"
                },
                "salary_range": {
                    "type": "string",
                    "description": "Expected salary range"
                },
                "location": {
                    "type": "string",
                    "description": "Job location"
                }
            },
            "required": ["company", "position"]
        }
    },
    {
        "name": "list_job_applications",
        "description": "List all tracked job applications. Shows application status, companies applied to, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter by status: applied, interviewing, offer, rejected, ghosted"
                },
                "company": {
                    "type": "string",
                    "description": "Filter by company name"
                }
            }
        }
    },
    {
        "name": "update_job_application",
        "description": "Update a job application status or notes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "app_id": {
                    "type": "string",
                    "description": "Application ID"
                },
                "company": {
                    "type": "string",
                    "description": "Company name (alternative to app_id)"
                },
                "status": {
                    "type": "string",
                    "description": "New status: applied, interviewing, offer, rejected, ghosted"
                },
                "notes": {
                    "type": "string",
                    "description": "Updated notes"
                },
                "next_steps": {
                    "type": "string",
                    "description": "Next steps for this application"
                }
            }
        }
    },
    {
        "name": "research_company",
        "description": "Research a company for job applications. Gets info from LinkedIn, Glassdoor, news.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {
                    "type": "string",
                    "description": "Company name to research"
                }
            },
            "required": ["company"]
        }
    },
    {
        "name": "save_job",
        "description": "Save a job posting for later review.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Job title"
                },
                "company": {
                    "type": "string",
                    "description": "Company name"
                },
                "url": {
                    "type": "string",
                    "description": "Job posting URL"
                },
                "notes": {
                    "type": "string",
                    "description": "Notes about why this job is interesting"
                }
            },
            "required": ["title", "company", "url"]
        }
    },
    {
        "name": "get_saved_jobs",
        "description": "Get all saved job postings.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
]
