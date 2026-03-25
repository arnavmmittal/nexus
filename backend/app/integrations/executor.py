"""Executor for integration tools.

Routes tool calls to the appropriate integration function.
"""

import json
import logging
from typing import Any, Dict

from app.integrations.jobs import (
    search_jobs,
    track_application,
    list_applications,
    update_application,
    research_company,
    save_job,
    get_saved_jobs,
)
from app.integrations.email_tools import (
    send_email,
    draft_email,
    list_email_drafts,
    search_emails,
    compose_cover_letter,
)
from app.integrations.browser import (
    browse_url,
    screenshot_webpage,
    fill_form,
    scrape_job_listing,
    web_search_detailed,
)
from app.integrations.slack_tools import (
    send_slack_message,
    list_slack_channels,
    read_slack_channel,
    send_slack_dm,
)
from app.integrations.github_tools import (
    list_repos,
    get_repo,
    create_issue,
    list_issues,
    create_pull_request,
    search_code,
    get_user_activity,
)
from app.integrations.job_intelligence import (
    aggregate_job_applications,
    get_job_recommendations,
)
from app.integrations.filesystem import (
    list_directory,
    read_file,
    search_files,
    get_file_info,
    write_file,
    get_common_directories,
)

logger = logging.getLogger(__name__)


# Map tool names to their executor functions
INTEGRATION_EXECUTORS = {
    # Job tools
    "search_jobs": search_jobs,
    "track_job_application": track_application,
    "list_job_applications": list_applications,
    "update_job_application": update_application,
    "research_company": research_company,
    "save_job": save_job,
    "get_saved_jobs": get_saved_jobs,
    
    # Email tools
    "send_email": send_email,
    "draft_email": draft_email,
    "list_email_drafts": list_email_drafts,
    "search_emails": search_emails,
    "compose_cover_letter": compose_cover_letter,
    
    # Browser tools
    "browse_url": browse_url,
    "screenshot_webpage": screenshot_webpage,
    "fill_web_form": fill_form,
    "scrape_job_listing": scrape_job_listing,
    "web_search_detailed": web_search_detailed,
    
    # Slack tools
    "send_slack_message": send_slack_message,
    "list_slack_channels": list_slack_channels,
    "read_slack_channel": read_slack_channel,
    "send_slack_dm": send_slack_dm,
    
    # GitHub tools
    "list_github_repos": list_repos,
    "get_github_repo": get_repo,
    "create_github_issue": create_issue,
    "list_github_issues": list_issues,
    "create_github_pr": create_pull_request,
    "search_github_code": search_code,
    "get_github_activity": get_user_activity,

    # Job Intelligence tools (deep integration)
    "scan_job_applications": aggregate_job_applications,
    "get_job_recommendations": get_job_recommendations,

    # Filesystem tools
    "list_directory": list_directory,
    "read_file": read_file,
    "search_files": search_files,
    "get_file_info": get_file_info,
    "write_file": write_file,
    "get_common_directories": get_common_directories,
}


def is_integration_tool(tool_name: str) -> bool:
    """Check if a tool is an integration tool."""
    return tool_name in INTEGRATION_EXECUTORS


async def execute_integration_tool(tool_name: str, args: Dict[str, Any]) -> str:
    """Execute an integration tool.
    
    Args:
        tool_name: Name of the tool
        args: Tool arguments
        
    Returns:
        Tool result as JSON string
    """
    if tool_name not in INTEGRATION_EXECUTORS:
        return json.dumps({"error": f"Unknown integration tool: {tool_name}"})
    
    try:
        executor = INTEGRATION_EXECUTORS[tool_name]
        result = await executor(**args)
        return result
    except Exception as e:
        logger.error(f"Integration tool error ({tool_name}): {e}")
        return json.dumps({"error": str(e)})
