"""GitHub integration tools.

Provides tools for:
- Managing repositories
- Creating issues/PRs
- Code search
- Activity tracking
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_API = "https://api.github.com"


def get_headers():
    """Get GitHub API headers."""
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }


async def list_repos(
    user: str = "",
    org: str = "",
    limit: int = 10,
) -> str:
    """List GitHub repositories."""
    logger.info(f"Listing repos for {user or org or 'authenticated user'}")
    
    if not GITHUB_TOKEN:
        return json.dumps({
            "status": "not_configured",
            "message": "GitHub token not configured.",
            "instructions": ["Set GITHUB_TOKEN in .env"]
        }, indent=2)
    
    import aiohttp
    
    try:
        async with aiohttp.ClientSession() as session:
            if org:
                url = f"{GITHUB_API}/orgs/{org}/repos"
            elif user:
                url = f"{GITHUB_API}/users/{user}/repos"
            else:
                url = f"{GITHUB_API}/user/repos"
            
            async with session.get(url, headers=get_headers()) as resp:
                if resp.status == 200:
                    repos = await resp.json()
                    result = [
                        {
                            "name": r["name"],
                            "full_name": r["full_name"],
                            "description": r.get("description", ""),
                            "url": r["html_url"],
                            "stars": r["stargazers_count"],
                            "language": r.get("language", ""),
                            "updated": r["updated_at"],
                        }
                        for r in repos[:limit]
                    ]
                    return json.dumps({
                        "repos": result,
                        "total": len(result),
                    }, indent=2)
                else:
                    error = await resp.text()
                    return json.dumps({"error": error, "status": resp.status})
                    
    except Exception as e:
        return json.dumps({"error": str(e)})


async def get_repo(owner: str, repo: str) -> str:
    """Get repository details."""
    logger.info(f"Getting repo: {owner}/{repo}")
    
    if not GITHUB_TOKEN:
        return json.dumps({"error": "GitHub token not configured"})
    
    import aiohttp
    
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{GITHUB_API}/repos/{owner}/{repo}"
            
            async with session.get(url, headers=get_headers()) as resp:
                if resp.status == 200:
                    r = await resp.json()
                    return json.dumps({
                        "name": r["name"],
                        "full_name": r["full_name"],
                        "description": r.get("description", ""),
                        "url": r["html_url"],
                        "stars": r["stargazers_count"],
                        "forks": r["forks_count"],
                        "open_issues": r["open_issues_count"],
                        "language": r.get("language", ""),
                        "created": r["created_at"],
                        "updated": r["updated_at"],
                        "topics": r.get("topics", []),
                    }, indent=2)
                else:
                    error = await resp.text()
                    return json.dumps({"error": error})
                    
    except Exception as e:
        return json.dumps({"error": str(e)})


async def create_issue(
    owner: str,
    repo: str,
    title: str,
    body: str = "",
    labels: List[str] = None,
) -> str:
    """Create a GitHub issue."""
    logger.info(f"Creating issue in {owner}/{repo}: {title}")
    
    if not GITHUB_TOKEN:
        return json.dumps({"error": "GitHub token not configured"})
    
    import aiohttp
    
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{GITHUB_API}/repos/{owner}/{repo}/issues"
            data = {"title": title, "body": body}
            if labels:
                data["labels"] = labels
            
            async with session.post(url, headers=get_headers(), json=data) as resp:
                if resp.status == 201:
                    issue = await resp.json()
                    return json.dumps({
                        "status": "created",
                        "issue_number": issue["number"],
                        "url": issue["html_url"],
                    }, indent=2)
                else:
                    error = await resp.text()
                    return json.dumps({"error": error})
                    
    except Exception as e:
        return json.dumps({"error": str(e)})


async def list_issues(
    owner: str,
    repo: str,
    state: str = "open",
    limit: int = 10,
) -> str:
    """List repository issues."""
    logger.info(f"Listing issues for {owner}/{repo}")
    
    if not GITHUB_TOKEN:
        return json.dumps({"error": "GitHub token not configured"})
    
    import aiohttp
    
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{GITHUB_API}/repos/{owner}/{repo}/issues"
            params = {"state": state, "per_page": limit}
            
            async with session.get(url, headers=get_headers(), params=params) as resp:
                if resp.status == 200:
                    issues = await resp.json()
                    result = [
                        {
                            "number": i["number"],
                            "title": i["title"],
                            "state": i["state"],
                            "url": i["html_url"],
                            "created": i["created_at"],
                            "labels": [l["name"] for l in i.get("labels", [])],
                        }
                        for i in issues
                    ]
                    return json.dumps({
                        "issues": result,
                        "total": len(result),
                    }, indent=2)
                else:
                    error = await resp.text()
                    return json.dumps({"error": error})
                    
    except Exception as e:
        return json.dumps({"error": str(e)})


async def create_pull_request(
    owner: str,
    repo: str,
    title: str,
    head: str,
    base: str = "main",
    body: str = "",
) -> str:
    """Create a pull request."""
    logger.info(f"Creating PR in {owner}/{repo}: {title}")
    
    if not GITHUB_TOKEN:
        return json.dumps({"error": "GitHub token not configured"})
    
    import aiohttp
    
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls"
            data = {
                "title": title,
                "head": head,
                "base": base,
                "body": body,
            }
            
            async with session.post(url, headers=get_headers(), json=data) as resp:
                if resp.status == 201:
                    pr = await resp.json()
                    return json.dumps({
                        "status": "created",
                        "pr_number": pr["number"],
                        "url": pr["html_url"],
                    }, indent=2)
                else:
                    error = await resp.text()
                    return json.dumps({"error": error})
                    
    except Exception as e:
        return json.dumps({"error": str(e)})


async def search_code(
    query: str,
    language: str = "",
    repo: str = "",
    limit: int = 10,
) -> str:
    """Search GitHub code."""
    logger.info(f"Searching code: {query}")
    
    if not GITHUB_TOKEN:
        return json.dumps({"error": "GitHub token not configured"})
    
    import aiohttp
    
    try:
        search_query = query
        if language:
            search_query += f" language:{language}"
        if repo:
            search_query += f" repo:{repo}"
        
        async with aiohttp.ClientSession() as session:
            url = f"{GITHUB_API}/search/code"
            params = {"q": search_query, "per_page": limit}
            
            async with session.get(url, headers=get_headers(), params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = [
                        {
                            "name": r["name"],
                            "path": r["path"],
                            "repo": r["repository"]["full_name"],
                            "url": r["html_url"],
                        }
                        for r in data.get("items", [])
                    ]
                    return json.dumps({
                        "query": query,
                        "results": results,
                        "total": data.get("total_count", 0),
                    }, indent=2)
                else:
                    error = await resp.text()
                    return json.dumps({"error": error})
                    
    except Exception as e:
        return json.dumps({"error": str(e)})


async def get_user_activity(username: str = "") -> str:
    """Get GitHub user activity."""
    logger.info(f"Getting activity for {username or 'authenticated user'}")
    
    if not GITHUB_TOKEN:
        return json.dumps({"error": "GitHub token not configured"})
    
    import aiohttp
    
    try:
        async with aiohttp.ClientSession() as session:
            if username:
                url = f"{GITHUB_API}/users/{username}/events/public"
            else:
                url = f"{GITHUB_API}/users/events"
            
            async with session.get(url, headers=get_headers()) as resp:
                if resp.status == 200:
                    events = await resp.json()
                    result = [
                        {
                            "type": e["type"],
                            "repo": e["repo"]["name"],
                            "created": e["created_at"],
                        }
                        for e in events[:20]
                    ]
                    return json.dumps({
                        "events": result,
                        "total": len(result),
                    }, indent=2)
                else:
                    error = await resp.text()
                    return json.dumps({"error": error})
                    
    except Exception as e:
        return json.dumps({"error": str(e)})


GITHUB_TOOLS = [
    {
        "name": "list_github_repos",
        "description": "List GitHub repositories for a user, org, or authenticated user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user": {
                    "type": "string",
                    "description": "GitHub username"
                },
                "org": {
                    "type": "string",
                    "description": "GitHub organization"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum repos to return"
                }
            }
        }
    },
    {
        "name": "get_github_repo",
        "description": "Get details about a GitHub repository.",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "Repository owner"
                },
                "repo": {
                    "type": "string",
                    "description": "Repository name"
                }
            },
            "required": ["owner", "repo"]
        }
    },
    {
        "name": "create_github_issue",
        "description": "Create a GitHub issue.",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "Repository owner"
                },
                "repo": {
                    "type": "string",
                    "description": "Repository name"
                },
                "title": {
                    "type": "string",
                    "description": "Issue title"
                },
                "body": {
                    "type": "string",
                    "description": "Issue body"
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Issue labels"
                }
            },
            "required": ["owner", "repo", "title"]
        }
    },
    {
        "name": "list_github_issues",
        "description": "List issues in a GitHub repository.",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "Repository owner"
                },
                "repo": {
                    "type": "string",
                    "description": "Repository name"
                },
                "state": {
                    "type": "string",
                    "description": "Issue state: open, closed, all"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum issues to return"
                }
            },
            "required": ["owner", "repo"]
        }
    },
    {
        "name": "create_github_pr",
        "description": "Create a GitHub pull request.",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "Repository owner"
                },
                "repo": {
                    "type": "string",
                    "description": "Repository name"
                },
                "title": {
                    "type": "string",
                    "description": "PR title"
                },
                "head": {
                    "type": "string",
                    "description": "Branch with changes"
                },
                "base": {
                    "type": "string",
                    "description": "Branch to merge into"
                },
                "body": {
                    "type": "string",
                    "description": "PR description"
                }
            },
            "required": ["owner", "repo", "title", "head"]
        }
    },
    {
        "name": "search_github_code",
        "description": "Search for code on GitHub.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "language": {
                    "type": "string",
                    "description": "Filter by language"
                },
                "repo": {
                    "type": "string",
                    "description": "Filter by repo (owner/name)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_github_activity",
        "description": "Get recent GitHub activity for a user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "GitHub username (empty for authenticated user)"
                }
            }
        }
    },
]
