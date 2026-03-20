"""
GitHub Integration for Nexus.

Tracks coding activity from GitHub and awards XP to skills based on
commits, PRs, and language usage.
"""

import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from github import Github, GithubException, Auth
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.skill import Skill, SkillXPLog

logger = logging.getLogger(__name__)

# Default user ID (will be replaced with auth later)
DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")

# Language to skill category mapping
LANGUAGE_SKILL_MAP = {
    # Programming languages
    "Python": ("Python", "Programming"),
    "JavaScript": ("JavaScript", "Programming"),
    "TypeScript": ("TypeScript", "Programming"),
    "Java": ("Java", "Programming"),
    "Go": ("Go", "Programming"),
    "Rust": ("Rust", "Programming"),
    "C": ("C", "Programming"),
    "C++": ("C++", "Programming"),
    "C#": ("C#", "Programming"),
    "Ruby": ("Ruby", "Programming"),
    "PHP": ("PHP", "Programming"),
    "Swift": ("Swift", "Programming"),
    "Kotlin": ("Kotlin", "Programming"),
    "Scala": ("Scala", "Programming"),
    "R": ("R", "Programming"),
    "Shell": ("Shell", "Programming"),
    "Bash": ("Shell", "Programming"),
    "PowerShell": ("PowerShell", "Programming"),
    "Lua": ("Lua", "Programming"),
    "Perl": ("Perl", "Programming"),
    "Haskell": ("Haskell", "Programming"),
    "Elixir": ("Elixir", "Programming"),
    "Clojure": ("Clojure", "Programming"),
    "F#": ("F#", "Programming"),
    "Dart": ("Dart", "Programming"),
    "Julia": ("Julia", "Programming"),
    # Web technologies
    "HTML": ("HTML/CSS", "Web Development"),
    "CSS": ("HTML/CSS", "Web Development"),
    "SCSS": ("HTML/CSS", "Web Development"),
    "Sass": ("HTML/CSS", "Web Development"),
    "Vue": ("Vue.js", "Web Development"),
    # Data & Config
    "SQL": ("SQL", "Data"),
    "JSON": ("Data Formats", "Data"),
    "YAML": ("Data Formats", "Data"),
    "XML": ("Data Formats", "Data"),
    # Infrastructure
    "Dockerfile": ("Docker", "DevOps"),
    "HCL": ("Terraform", "DevOps"),
    "Makefile": ("Build Tools", "DevOps"),
}

# File extension to language mapping
EXTENSION_LANGUAGE_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".c": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".h": "C",
    ".hpp": "C++",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".scala": "Scala",
    ".r": "R",
    ".R": "R",
    ".sh": "Shell",
    ".bash": "Bash",
    ".ps1": "PowerShell",
    ".lua": "Lua",
    ".pl": "Perl",
    ".hs": "Haskell",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".clj": "Clojure",
    ".fs": "F#",
    ".dart": "Dart",
    ".jl": "Julia",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "Sass",
    ".vue": "Vue",
    ".sql": "SQL",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".xml": "XML",
    ".dockerfile": "Dockerfile",
    ".tf": "HCL",
    ".mk": "Makefile",
}


class GitHubIntegration:
    """GitHub integration for tracking coding activity."""

    def __init__(self, token: str | None = None):
        """
        Initialize GitHub integration.

        Args:
            token: GitHub personal access token. If not provided, uses settings.
        """
        self._token = token or getattr(settings, "github_token", "")
        self._client: Github | None = None

    @property
    def client(self) -> Github:
        """Get or create GitHub client."""
        if self._client is None:
            if not self._token:
                raise ValueError("GitHub token not configured")
            auth = Auth.Token(self._token)
            self._client = Github(auth=auth)
        return self._client

    def is_configured(self) -> bool:
        """Check if GitHub integration is properly configured."""
        return bool(self._token)

    def get_user_activity(self, days: int = 30) -> dict[str, Any]:
        """
        Get recent user activity from GitHub.

        Args:
            days: Number of days to look back

        Returns:
            Dictionary containing commits, PRs, and issues
        """
        if not self.is_configured():
            return {"error": "GitHub token not configured"}

        try:
            user = self.client.get_user()
            since = datetime.utcnow() - timedelta(days=days)

            # Get all repos the user has access to
            repos = list(user.get_repos())

            activity = {
                "user": user.login,
                "commits": [],
                "pull_requests": [],
                "issues": [],
                "repos_analyzed": len(repos),
            }

            for repo in repos[:50]:  # Limit to 50 repos to avoid rate limits
                try:
                    # Get commits by the user
                    commits = repo.get_commits(
                        author=user.login,
                        since=since,
                    )
                    for commit in commits[:100]:  # Limit commits per repo
                        activity["commits"].append({
                            "sha": commit.sha[:7],
                            "repo": repo.full_name,
                            "message": commit.commit.message.split("\n")[0],
                            "date": commit.commit.author.date.isoformat(),
                            "additions": commit.stats.additions if commit.stats else 0,
                            "deletions": commit.stats.deletions if commit.stats else 0,
                            "files": [f.filename for f in commit.files] if commit.files else [],
                        })

                    # Get PRs by the user
                    prs = repo.get_pulls(state="all", sort="updated", direction="desc")
                    for pr in prs[:20]:
                        if pr.user.login == user.login and pr.created_at >= since:
                            activity["pull_requests"].append({
                                "number": pr.number,
                                "repo": repo.full_name,
                                "title": pr.title,
                                "state": pr.state,
                                "merged": pr.merged,
                                "created_at": pr.created_at.isoformat(),
                                "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
                            })

                    # Get issues by the user
                    issues = repo.get_issues(
                        state="all",
                        creator=user.login,
                        since=since,
                    )
                    for issue in issues[:20]:
                        if issue.pull_request is None:  # Exclude PRs
                            activity["issues"].append({
                                "number": issue.number,
                                "repo": repo.full_name,
                                "title": issue.title,
                                "state": issue.state,
                                "created_at": issue.created_at.isoformat(),
                            })

                except GithubException as e:
                    logger.warning(f"Error accessing repo {repo.full_name}: {e}")
                    continue

            return activity

        except GithubException as e:
            logger.error(f"GitHub API error: {e}")
            return {"error": str(e)}

    def get_commit_stats(self) -> dict[str, Any]:
        """
        Get commit statistics for the user.

        Returns:
            Dictionary with commit stats per day/week
        """
        if not self.is_configured():
            return {"error": "GitHub token not configured"}

        try:
            user = self.client.get_user()
            repos = list(user.get_repos())

            # Get commits from last 30 days
            since = datetime.utcnow() - timedelta(days=30)
            commits_by_day: dict[str, int] = {}
            commits_by_week: dict[int, int] = {}
            total_additions = 0
            total_deletions = 0

            for repo in repos[:50]:
                try:
                    commits = repo.get_commits(author=user.login, since=since)
                    for commit in commits[:100]:
                        date = commit.commit.author.date
                        day_key = date.strftime("%Y-%m-%d")
                        week_num = date.isocalendar()[1]

                        commits_by_day[day_key] = commits_by_day.get(day_key, 0) + 1
                        commits_by_week[week_num] = commits_by_week.get(week_num, 0) + 1

                        if commit.stats:
                            total_additions += commit.stats.additions
                            total_deletions += commit.stats.deletions

                except GithubException:
                    continue

            total_commits = sum(commits_by_day.values())

            return {
                "user": user.login,
                "period": "30 days",
                "total_commits": total_commits,
                "commits_by_day": dict(sorted(commits_by_day.items())),
                "commits_by_week": dict(sorted(commits_by_week.items())),
                "total_additions": total_additions,
                "total_deletions": total_deletions,
                "avg_commits_per_day": round(total_commits / 30, 2),
            }

        except GithubException as e:
            logger.error(f"GitHub API error: {e}")
            return {"error": str(e)}

    def get_language_stats(self) -> dict[str, Any]:
        """
        Get language statistics from user's repositories.

        Returns:
            Dictionary with language usage stats
        """
        if not self.is_configured():
            return {"error": "GitHub token not configured"}

        try:
            user = self.client.get_user()
            repos = list(user.get_repos())

            language_bytes: dict[str, int] = {}
            repos_by_language: dict[str, list[str]] = {}

            for repo in repos[:100]:
                try:
                    languages = repo.get_languages()
                    for lang, bytes_count in languages.items():
                        language_bytes[lang] = language_bytes.get(lang, 0) + bytes_count
                        if lang not in repos_by_language:
                            repos_by_language[lang] = []
                        repos_by_language[lang].append(repo.name)

                except GithubException:
                    continue

            # Sort by bytes
            sorted_languages = dict(
                sorted(language_bytes.items(), key=lambda x: x[1], reverse=True)
            )

            # Calculate percentages
            total_bytes = sum(language_bytes.values())
            language_percentages = {
                lang: round((bytes_count / total_bytes) * 100, 2)
                for lang, bytes_count in sorted_languages.items()
            } if total_bytes > 0 else {}

            return {
                "user": user.login,
                "languages": sorted_languages,
                "percentages": language_percentages,
                "top_5": list(sorted_languages.keys())[:5],
                "repos_by_language": {
                    k: repos_by_language[k][:5]  # Limit to 5 repos per language
                    for k in list(sorted_languages.keys())[:10]
                },
            }

        except GithubException as e:
            logger.error(f"GitHub API error: {e}")
            return {"error": str(e)}

    def _detect_languages_from_files(self, files: list[str]) -> dict[str, int]:
        """
        Detect languages from file names/extensions.

        Args:
            files: List of file paths

        Returns:
            Dictionary mapping language to file count
        """
        language_counts: dict[str, int] = {}

        for file_path in files:
            # Get extension
            if "." not in file_path:
                continue

            ext = "." + file_path.rsplit(".", 1)[-1].lower()

            # Check for special files first
            file_name = file_path.split("/")[-1].lower()
            if file_name == "dockerfile":
                language_counts["Dockerfile"] = language_counts.get("Dockerfile", 0) + 1
                continue
            if file_name == "makefile":
                language_counts["Makefile"] = language_counts.get("Makefile", 0) + 1
                continue

            # Map extension to language
            language = EXTENSION_LANGUAGE_MAP.get(ext)
            if language:
                language_counts[language] = language_counts.get(language, 0) + 1

        return language_counts

    def _calculate_xp_for_commit(
        self,
        additions: int,
        deletions: int,
        files_changed: int,
    ) -> int:
        """
        Calculate XP for a commit based on its size.

        Args:
            additions: Lines added
            deletions: Lines deleted
            files_changed: Number of files changed

        Returns:
            XP amount (5-20)
        """
        total_lines = additions + deletions

        # Base XP
        xp = 5

        # Add XP based on lines changed
        if total_lines > 10:
            xp += 2
        if total_lines > 50:
            xp += 3
        if total_lines > 100:
            xp += 3
        if total_lines > 200:
            xp += 2

        # Add XP for multiple files
        if files_changed > 3:
            xp += 2
        if files_changed > 10:
            xp += 3

        # Cap at 20
        return min(xp, 20)

    async def sync_activity(
        self,
        db: AsyncSession,
        days: int = 7,
        user_id: UUID | None = None,
    ) -> dict[str, Any]:
        """
        Sync GitHub activity and award XP to skills.

        Args:
            db: Database session
            days: Number of days to sync
            user_id: User ID to sync for

        Returns:
            Dictionary with sync results
        """
        if not self.is_configured():
            return {"error": "GitHub token not configured", "xp_awarded": {}}

        user_id = user_id or DEFAULT_USER_ID
        activity = self.get_user_activity(days=days)

        if "error" in activity:
            return {"error": activity["error"], "xp_awarded": {}}

        xp_by_skill: dict[str, int] = {}
        commits_processed = 0
        prs_processed = 0

        # Process commits
        for commit in activity.get("commits", []):
            files = commit.get("files", [])
            additions = commit.get("additions", 0)
            deletions = commit.get("deletions", 0)

            # Detect languages from files
            languages = self._detect_languages_from_files(files)

            # Calculate base XP for this commit
            base_xp = self._calculate_xp_for_commit(additions, deletions, len(files))

            # Award XP to each detected language skill
            for language, file_count in languages.items():
                if language in LANGUAGE_SKILL_MAP:
                    skill_name, category = LANGUAGE_SKILL_MAP[language]

                    # Scale XP by proportion of files in this language
                    total_files = sum(languages.values())
                    proportion = file_count / total_files if total_files > 0 else 1
                    xp = max(1, int(base_xp * proportion))

                    # Get or create skill
                    skill = await self._get_or_create_skill(
                        db, user_id, skill_name, category
                    )

                    # Check if we already logged XP for this commit
                    commit_sha = commit.get("sha", "")
                    existing_log = await db.execute(
                        select(SkillXPLog).where(
                            SkillXPLog.skill_id == skill.id,
                            SkillXPLog.description.contains(commit_sha),
                        )
                    )
                    if existing_log.scalar_one_or_none():
                        continue  # Already processed

                    # Log XP
                    await self._award_xp(
                        db,
                        skill,
                        xp,
                        f"github_commit:{commit_sha}",
                        f"Commit {commit_sha}: {commit.get('message', '')[:50]}",
                    )

                    key = f"{skill_name} ({category})"
                    xp_by_skill[key] = xp_by_skill.get(key, 0) + xp

            commits_processed += 1

        # Process merged PRs (bonus XP)
        for pr in activity.get("pull_requests", []):
            if pr.get("merged"):
                # Award bonus XP for merged PRs
                bonus_xp = 25  # Flat bonus for merged PRs

                # Try to detect primary language from repo name
                # In a real implementation, we'd fetch the PR files
                skill_name = "General"
                category = "Programming"

                skill = await self._get_or_create_skill(
                    db, user_id, skill_name, category
                )

                # Check if already logged
                pr_key = f"github_pr:{pr.get('repo')}#{pr.get('number')}"
                existing_log = await db.execute(
                    select(SkillXPLog).where(
                        SkillXPLog.skill_id == skill.id,
                        SkillXPLog.description.contains(pr_key),
                    )
                )
                if existing_log.scalar_one_or_none():
                    continue

                await self._award_xp(
                    db,
                    skill,
                    bonus_xp,
                    "github_pr_merged",
                    f"{pr_key}: {pr.get('title', '')[:50]}",
                )

                key = f"{skill_name} ({category})"
                xp_by_skill[key] = xp_by_skill.get(key, 0) + bonus_xp
                prs_processed += 1

        await db.commit()

        return {
            "status": "success",
            "commits_processed": commits_processed,
            "prs_processed": prs_processed,
            "xp_awarded": xp_by_skill,
            "total_xp": sum(xp_by_skill.values()),
        }

    async def _get_or_create_skill(
        self,
        db: AsyncSession,
        user_id: UUID,
        name: str,
        category: str,
    ) -> Skill:
        """
        Get or create a skill.

        Args:
            db: Database session
            user_id: User ID
            name: Skill name
            category: Skill category

        Returns:
            Skill instance
        """
        result = await db.execute(
            select(Skill).where(
                Skill.user_id == user_id,
                Skill.name == name,
            )
        )
        skill = result.scalar_one_or_none()

        if not skill:
            skill = Skill(
                user_id=user_id,
                name=name,
                category=category,
            )
            db.add(skill)
            await db.flush()
            logger.info(f"Created new skill: {name} ({category})")

        return skill

    async def _award_xp(
        self,
        db: AsyncSession,
        skill: Skill,
        xp_amount: int,
        source: str,
        description: str,
    ) -> None:
        """
        Award XP to a skill.

        Args:
            db: Database session
            skill: Skill to award XP to
            xp_amount: Amount of XP to award
            source: Source of XP
            description: Description of XP source
        """
        # Create XP log entry
        xp_log = SkillXPLog(
            skill_id=skill.id,
            xp_amount=xp_amount,
            source=source,
            description=description,
        )
        db.add(xp_log)

        # Update skill XP
        skill.current_xp += xp_amount
        skill.total_xp += xp_amount
        skill.last_practiced = datetime.utcnow()

        # Check for level up
        while skill.current_xp >= skill.xp_for_next_level:
            skill.current_xp -= skill.xp_for_next_level
            skill.current_level += 1
            logger.info(f"Level up! {skill.name} is now level {skill.current_level}")


# Singleton instance
_github_integration: GitHubIntegration | None = None


def get_github_integration(token: str | None = None) -> GitHubIntegration:
    """
    Get or create the GitHub integration singleton.

    Args:
        token: Optional token to override settings

    Returns:
        GitHubIntegration instance
    """
    global _github_integration
    if _github_integration is None or token is not None:
        _github_integration = GitHubIntegration(token)
    return _github_integration
