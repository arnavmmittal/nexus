"""Claude Code conversation history synchronization.

Parses Claude Code JSONL conversation files and extracts:
- User messages and assistant responses
- Code blocks with language detection
- Decisions made during sessions
- Skills practiced (programming languages, frameworks, tools)
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.memory.vector_store import VectorStore
from app.models.memory import Conversation
from app.models.skill import Skill, SkillXPLog

logger = logging.getLogger(__name__)


# Skill detection configuration
LANGUAGE_PATTERNS = {
    "python": {
        "code_fence": r"```python",
        "keywords": ["python", "pip", "virtualenv", "pytest", "fastapi", "django", "flask"],
        "category": "programming_language",
    },
    "typescript": {
        "code_fence": r"```(?:typescript|tsx?)",
        "keywords": ["typescript", "tsx", ".ts", "interface", "type "],
        "category": "programming_language",
    },
    "javascript": {
        "code_fence": r"```(?:javascript|jsx?)",
        "keywords": ["javascript", "jsx", ".js", "node", "npm", "yarn"],
        "category": "programming_language",
    },
    "rust": {
        "code_fence": r"```rust",
        "keywords": ["rust", "cargo", "rustc", ".rs"],
        "category": "programming_language",
    },
    "go": {
        "code_fence": r"```go",
        "keywords": ["golang", ".go", "go mod", "go build"],
        "category": "programming_language",
    },
    "sql": {
        "code_fence": r"```sql",
        "keywords": ["sql", "select", "postgresql", "mysql", "sqlite"],
        "category": "programming_language",
    },
    "bash": {
        "code_fence": r"```(?:bash|sh|shell)",
        "keywords": ["bash", "shell", "terminal", "cli"],
        "category": "programming_language",
    },
}

FRAMEWORK_PATTERNS = {
    "fastapi": {
        "keywords": ["fastapi", "uvicorn", "@app.get", "@app.post", "APIRouter"],
        "category": "framework",
    },
    "nextjs": {
        "keywords": ["next.js", "nextjs", "next/", "next config", "getServerSideProps"],
        "category": "framework",
    },
    "react": {
        "keywords": ["react", "usestate", "useeffect", "jsx", "component"],
        "category": "framework",
    },
    "django": {
        "keywords": ["django", "django.db", "django.views"],
        "category": "framework",
    },
    "tailwindcss": {
        "keywords": ["tailwind", "tailwindcss", "className"],
        "category": "framework",
    },
    "docker": {
        "keywords": ["docker", "dockerfile", "docker-compose", "container"],
        "category": "devops",
    },
    "kubernetes": {
        "keywords": ["kubernetes", "k8s", "kubectl", "helm"],
        "category": "devops",
    },
    "supabase": {
        "keywords": ["supabase", "supabase-js", "rls", "row level security"],
        "category": "database",
    },
    "chromadb": {
        "keywords": ["chromadb", "chroma", "vector store", "embedding"],
        "category": "database",
    },
    "git": {
        "keywords": ["git", "commit", "branch", "merge", "rebase"],
        "category": "version_control",
    },
}

# Decision patterns to detect
DECISION_PATTERNS = [
    r"(?:let's|let us|we should|we'll|i'll|i will|i chose|i decided|going to|we're going to)\s+(?:use|go with|implement|try|adopt|switch to)\s+([^.!?\n]+)",
    r"(?:decided|choosing|picked|selected)\s+(?:to use|to go with)?\s*([^.!?\n]+)",
    r"(?:better|best)\s+(?:to|approach|solution|option)\s+(?:is|would be)\s+([^.!?\n]+)",
    r"(?:implementation|architecture|design)\s+(?:will|should)\s+(?:use|be)\s+([^.!?\n]+)",
]


@dataclass
class CodeBlock:
    """Extracted code block from conversation."""

    language: str
    code: str
    line_count: int


@dataclass
class ClaudeMessage:
    """Parsed message from Claude conversation."""

    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime
    uuid: str
    thinking: str | None = None
    code_blocks: list[CodeBlock] = field(default_factory=list)


@dataclass
class ClaudeSession:
    """Parsed Claude Code session."""

    session_id: str
    project_path: str
    started_at: datetime | None
    ended_at: datetime | None
    messages: list[ClaudeMessage] = field(default_factory=list)
    detected_skills: dict[str, int] = field(default_factory=dict)
    detected_decisions: list[str] = field(default_factory=list)
    git_branch: str | None = None
    version: str | None = None

    @property
    def duration_minutes(self) -> int:
        """Calculate session duration in minutes."""
        if self.started_at and self.ended_at:
            return int((self.ended_at - self.started_at).total_seconds() / 60)
        return 0

    @property
    def message_count(self) -> int:
        """Count of user+assistant messages."""
        return len([m for m in self.messages if m.role in ("user", "assistant")])

    @property
    def total_code_blocks(self) -> int:
        """Total code blocks in session."""
        return sum(len(m.code_blocks) for m in self.messages)


class ClaudeSync:
    """
    Synchronizes Claude Code conversation history to Nexus.

    Parses JSONL files from ~/.claude/projects/ and:
    - Stores conversations in PostgreSQL
    - Indexes content in ChromaDB for semantic search
    - Awards XP to skills based on detected technologies
    """

    def __init__(
        self,
        history_path: str | None = None,
        vector_store: VectorStore | None = None,
    ):
        """
        Initialize Claude sync.

        Args:
            history_path: Path to Claude projects directory
            vector_store: Vector store instance
        """
        self.history_path = Path(history_path or settings.claude_history_path).expanduser()
        self.vector_store = vector_store

        if not self.history_path.exists():
            logger.warning(f"Claude history path not found: {self.history_path}")

    def discover_projects(self) -> list[dict[str, Any]]:
        """
        Discover all Claude Code projects.

        Returns:
            List of project info dicts
        """
        if not self.history_path.exists():
            return []

        projects = []
        for project_dir in self.history_path.iterdir():
            if project_dir.is_dir() and not project_dir.name.startswith("."):
                # Find JSONL files (conversations)
                jsonl_files = list(project_dir.glob("*.jsonl"))
                if jsonl_files:
                    # Decode project path from directory name
                    project_path = project_dir.name.replace("-", "/")
                    if project_path.startswith("/"):
                        project_path = project_path[1:]

                    projects.append(
                        {
                            "project_dir": str(project_dir),
                            "project_path": project_path,
                            "session_count": len(jsonl_files),
                            "sessions": [f.stem for f in jsonl_files],
                        }
                    )

        return projects

    def parse_jsonl_file(self, file_path: Path) -> ClaudeSession:
        """
        Parse a Claude Code JSONL conversation file.

        Args:
            file_path: Path to .jsonl file

        Returns:
            Parsed ClaudeSession
        """
        session = ClaudeSession(
            session_id=file_path.stem,
            project_path=file_path.parent.name.replace("-", "/"),
            started_at=None,
            ended_at=None,
        )

        messages = []
        timestamps = []

        with open(file_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f):
                if not line.strip():
                    continue

                try:
                    entry = json.loads(line)
                    self._process_entry(entry, session, messages, timestamps)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse line {line_num} in {file_path}: {e}")
                except Exception as e:
                    logger.warning(f"Error processing line {line_num} in {file_path}: {e}")

        # Set session timing
        if timestamps:
            session.started_at = min(timestamps)
            session.ended_at = max(timestamps)

        session.messages = messages

        # Detect skills and decisions
        self._detect_skills(session)
        self._detect_decisions(session)

        return session

    def _process_entry(
        self,
        entry: dict,
        session: ClaudeSession,
        messages: list,
        timestamps: list,
    ) -> None:
        """Process a single JSONL entry."""
        entry_type = entry.get("type")

        # Extract session metadata
        if not session.version and entry.get("version"):
            session.version = entry["version"]
        if not session.git_branch and entry.get("gitBranch"):
            session.git_branch = entry["gitBranch"]

        # Parse timestamp
        if "timestamp" in entry:
            try:
                ts = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
                timestamps.append(ts)
            except (ValueError, AttributeError):
                ts = None

        # User messages
        if entry_type == "user":
            msg_data = entry.get("message", {})
            content = msg_data.get("content", "")
            if isinstance(content, str) and content.strip():
                message = ClaudeMessage(
                    role="user",
                    content=content,
                    timestamp=ts,
                    uuid=entry.get("uuid", ""),
                )
                messages.append(message)

        # Assistant messages
        elif entry_type == "assistant":
            msg_data = entry.get("message", {})
            content_blocks = msg_data.get("content", [])

            text_content = []
            thinking_content = None
            code_blocks = []

            for block in content_blocks:
                if isinstance(block, dict):
                    block_type = block.get("type")
                    if block_type == "text":
                        text = block.get("text", "")
                        text_content.append(text)
                        # Extract code blocks from text
                        code_blocks.extend(self._extract_code_blocks(text))
                    elif block_type == "thinking":
                        thinking_content = block.get("thinking", "")
                    elif block_type == "tool_use":
                        # Capture tool usage
                        tool_name = block.get("name", "")
                        tool_input = block.get("input", {})
                        text_content.append(f"[Tool: {tool_name}]")

            full_content = "\n".join(text_content)
            if full_content.strip():
                message = ClaudeMessage(
                    role="assistant",
                    content=full_content,
                    timestamp=ts,
                    uuid=entry.get("uuid", ""),
                    thinking=thinking_content,
                    code_blocks=code_blocks,
                )
                messages.append(message)

    def _extract_code_blocks(self, text: str) -> list[CodeBlock]:
        """Extract code blocks from markdown text."""
        blocks = []
        pattern = r"```(\w*)\n(.*?)```"

        for match in re.finditer(pattern, text, re.DOTALL):
            language = match.group(1) or "text"
            code = match.group(2)
            blocks.append(
                CodeBlock(
                    language=language.lower(),
                    code=code,
                    line_count=len(code.splitlines()),
                )
            )

        return blocks

    def _detect_skills(self, session: ClaudeSession) -> None:
        """Detect skills practiced in the session."""
        # Combine all text for analysis
        full_text = ""
        code_languages = {}

        for msg in session.messages:
            full_text += f" {msg.content.lower()}"
            if msg.thinking:
                full_text += f" {msg.thinking.lower()}"

            # Count code block languages
            for block in msg.code_blocks:
                lang = block.language
                if lang not in code_languages:
                    code_languages[lang] = 0
                code_languages[lang] += block.line_count

        # Detect programming languages
        for skill_name, config in LANGUAGE_PATTERNS.items():
            score = 0

            # Check code fences
            if re.search(config["code_fence"], full_text, re.IGNORECASE):
                score += 20

            # Check keywords
            for keyword in config["keywords"]:
                if keyword.lower() in full_text:
                    score += 5

            # Check actual code blocks
            if skill_name in code_languages:
                # Award based on lines of code
                score += min(code_languages[skill_name], 50)

            if score > 0:
                session.detected_skills[skill_name] = score

        # Detect frameworks
        for skill_name, config in FRAMEWORK_PATTERNS.items():
            score = 0
            for keyword in config["keywords"]:
                if keyword.lower() in full_text:
                    score += 10

            if score > 0:
                session.detected_skills[skill_name] = score

    def _detect_decisions(self, session: ClaudeSession) -> None:
        """Detect decisions made in the session."""
        decisions = []

        for msg in session.messages:
            text = msg.content
            if msg.thinking:
                text += f" {msg.thinking}"

            for pattern in DECISION_PATTERNS:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    decision = match.group(1).strip()
                    if len(decision) > 10 and len(decision) < 200:
                        # Clean up the decision text
                        decision = decision.strip(",.;:")
                        if decision and decision not in decisions:
                            decisions.append(decision)

        session.detected_decisions = decisions[:20]  # Limit to 20 decisions

    async def import_session(
        self,
        session: ClaudeSession,
        user_id: UUID,
        db: AsyncSession,
    ) -> Conversation:
        """
        Import a parsed session to the database.

        Args:
            session: Parsed ClaudeSession
            user_id: User ID
            db: Database session

        Returns:
            Created Conversation record
        """
        # Create conversation record
        conversation = Conversation(
            user_id=user_id,
            source="claude_code",
            started_at=session.started_at,
            ended_at=session.ended_at,
            summary=self._generate_summary(session),
            extracted_facts={
                "session_id": session.session_id,
                "project_path": session.project_path,
                "message_count": session.message_count,
                "code_blocks": session.total_code_blocks,
                "duration_minutes": session.duration_minutes,
                "git_branch": session.git_branch,
                "decisions": session.detected_decisions,
            },
            extracted_skills=session.detected_skills,
        )
        db.add(conversation)
        await db.flush()

        # Award XP to skills
        await self._award_skill_xp(session, user_id, db, str(conversation.id))

        # Index in vector store
        if self.vector_store:
            await self._index_session(session, user_id, str(conversation.id))

        return conversation

    def _generate_summary(self, session: ClaudeSession) -> str:
        """Generate a summary of the session."""
        parts = []

        if session.message_count > 0:
            parts.append(f"{session.message_count} messages")

        if session.total_code_blocks > 0:
            parts.append(f"{session.total_code_blocks} code blocks")

        if session.duration_minutes > 0:
            parts.append(f"{session.duration_minutes}min duration")

        if session.detected_skills:
            top_skills = sorted(
                session.detected_skills.items(), key=lambda x: x[1], reverse=True
            )[:5]
            skills_str = ", ".join([s[0] for s in top_skills])
            parts.append(f"skills: {skills_str}")

        return " | ".join(parts) if parts else "Empty session"

    async def _award_skill_xp(
        self,
        session: ClaudeSession,
        user_id: UUID,
        db: AsyncSession,
        conversation_id: str,
    ) -> None:
        """Award XP to skills based on session content."""
        for skill_name, score in session.detected_skills.items():
            # Get category from patterns
            category = "programming_language"
            if skill_name in FRAMEWORK_PATTERNS:
                category = FRAMEWORK_PATTERNS[skill_name]["category"]
            elif skill_name in LANGUAGE_PATTERNS:
                category = LANGUAGE_PATTERNS[skill_name]["category"]

            # Find or create skill
            result = await db.execute(
                select(Skill).where(
                    Skill.user_id == user_id,
                    Skill.name == skill_name,
                )
            )
            skill = result.scalar_one_or_none()

            if not skill:
                skill = Skill(
                    user_id=user_id,
                    name=skill_name,
                    category=category,
                )
                db.add(skill)
                await db.flush()

            # Calculate XP based on score and session complexity
            xp_multiplier = 1.0
            if session.duration_minutes > 30:
                xp_multiplier = 1.5
            if session.duration_minutes > 60:
                xp_multiplier = 2.0

            xp_amount = int(score * xp_multiplier)
            if xp_amount > 0:
                # Log XP
                xp_log = SkillXPLog(
                    skill_id=skill.id,
                    xp_amount=xp_amount,
                    source="claude_session",
                    description=f"Session {session.session_id[:8]}... ({session.duration_minutes}min)",
                )
                db.add(xp_log)

                # Update skill
                skill.current_xp += xp_amount
                skill.total_xp += xp_amount
                skill.last_practiced = session.ended_at or datetime.utcnow()

                # Level up check
                while skill.current_xp >= skill.xp_for_next_level:
                    skill.current_xp -= skill.xp_for_next_level
                    skill.current_level += 1

    async def _index_session(
        self,
        session: ClaudeSession,
        user_id: UUID,
        conversation_id: str,
    ) -> None:
        """Index session content in vector store."""
        if not self.vector_store:
            return

        # Index each message
        for i, msg in enumerate(session.messages):
            if not msg.content.strip():
                continue

            # Truncate very long messages
            content = msg.content[:5000] if len(msg.content) > 5000 else msg.content

            await self.vector_store.add_document(
                content=content,
                user_id=str(user_id),
                metadata={
                    "source": "claude_code",
                    "type": "conversation_message",
                    "conversation_id": conversation_id,
                    "session_id": session.session_id,
                    "project_path": session.project_path,
                    "message_role": msg.role,
                    "message_index": i,
                    "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                },
                document_id=f"claude:{session.session_id}:{i}",
            )

    async def sync_directory(
        self,
        directory: str | None,
        user_id: UUID,
        db: AsyncSession,
        force: bool = False,
    ) -> dict[str, Any]:
        """
        Sync conversations from a directory.

        Args:
            directory: Directory path (defaults to config path)
            user_id: User ID
            db: Database session
            force: Force re-import of existing sessions

        Returns:
            Import statistics
        """
        import_path = Path(directory).expanduser() if directory else self.history_path

        if not import_path.exists():
            return {"error": f"Directory not found: {import_path}", "imported": 0}

        stats = {
            "imported": 0,
            "skipped": 0,
            "errors": 0,
            "skills_updated": 0,
            "sessions": [],
        }

        # Find all JSONL files
        jsonl_files = list(import_path.rglob("*.jsonl"))
        logger.info(f"Found {len(jsonl_files)} JSONL files in {import_path}")

        for jsonl_file in jsonl_files:
            try:
                # Check if already imported
                if not force:
                    existing = await db.execute(
                        select(Conversation).where(
                            Conversation.user_id == user_id,
                            Conversation.source == "claude_code",
                            Conversation.extracted_facts["session_id"].astext
                            == jsonl_file.stem,
                        )
                    )
                    if existing.scalar_one_or_none():
                        stats["skipped"] += 1
                        continue

                # Parse and import
                session = self.parse_jsonl_file(jsonl_file)

                if session.message_count > 0:
                    conversation = await self.import_session(session, user_id, db)
                    stats["imported"] += 1
                    stats["skills_updated"] += len(session.detected_skills)
                    stats["sessions"].append(
                        {
                            "session_id": session.session_id,
                            "project": session.project_path,
                            "messages": session.message_count,
                            "skills": list(session.detected_skills.keys()),
                        }
                    )
                else:
                    stats["skipped"] += 1

            except Exception as e:
                logger.error(f"Failed to import {jsonl_file}: {e}")
                stats["errors"] += 1

        return stats

    async def search_conversations(
        self,
        query: str,
        user_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search Claude conversations using semantic search.

        Args:
            query: Search query
            user_id: User ID
            limit: Maximum results

        Returns:
            List of matching results
        """
        if not self.vector_store:
            return []

        results = await self.vector_store.search(
            query=query,
            user_id=user_id,
            limit=limit,
        )

        # Filter to only Claude Code documents
        return [
            r for r in results if r.get("metadata", {}).get("source") == "claude_code"
        ]

    def list_sessions(self, project_path: str | None = None) -> list[dict[str, Any]]:
        """
        List available Claude Code sessions.

        Args:
            project_path: Optional filter by project

        Returns:
            List of session info
        """
        sessions = []

        if not self.history_path.exists():
            return sessions

        for project_dir in self.history_path.iterdir():
            if not project_dir.is_dir() or project_dir.name.startswith("."):
                continue

            decoded_path = project_dir.name.replace("-", "/")
            if project_path and project_path not in decoded_path:
                continue

            for jsonl_file in project_dir.glob("*.jsonl"):
                try:
                    stat = jsonl_file.stat()
                    sessions.append(
                        {
                            "session_id": jsonl_file.stem,
                            "project_path": decoded_path,
                            "file_path": str(jsonl_file),
                            "size_bytes": stat.st_size,
                            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to stat {jsonl_file}: {e}")

        # Sort by modification time
        sessions.sort(key=lambda x: x["modified_at"], reverse=True)
        return sessions


# Singleton instance
_claude_sync: ClaudeSync | None = None


def get_claude_sync(vector_store: VectorStore | None = None) -> ClaudeSync:
    """Get or create ClaudeSync instance."""
    global _claude_sync
    if _claude_sync is None:
        _claude_sync = ClaudeSync(vector_store=vector_store)
    return _claude_sync
