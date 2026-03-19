"""Obsidian vault synchronization."""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.memory.vector_store import VectorStore

logger = logging.getLogger(__name__)


class ObsidianSync:
    """
    Synchronizes Obsidian vault content to vector store.

    Supports:
    - Markdown files
    - Daily notes
    - Tags and links extraction
    """

    # File patterns to exclude
    EXCLUDE_PATTERNS = [
        r"\.obsidian/",
        r"\.trash/",
        r"templates/",
        r"\.git/",
    ]

    def __init__(self, vault_path: str | None = None, vector_store: VectorStore | None = None):
        """
        Initialize Obsidian sync.

        Args:
            vault_path: Path to Obsidian vault
            vector_store: Vector store instance
        """
        self.vault_path = Path(vault_path or settings.obsidian_vault_path or "")
        self.vector_store = vector_store

        if not self.vault_path.exists():
            logger.warning(f"Obsidian vault not found at {self.vault_path}")

    async def sync_vault(self, user_id: str, force: bool = False) -> dict[str, Any]:
        """
        Sync entire vault to vector store.

        Args:
            user_id: User ID
            force: Force full resync

        Returns:
            Sync statistics
        """
        if not self.vault_path.exists():
            return {"error": "Vault not found", "synced": 0}

        if not self.vector_store:
            return {"error": "Vector store not configured", "synced": 0}

        stats = {
            "synced": 0,
            "skipped": 0,
            "errors": 0,
        }

        # Find all markdown files
        for md_file in self.vault_path.rglob("*.md"):
            if self._should_exclude(md_file):
                stats["skipped"] += 1
                continue

            try:
                await self._sync_file(md_file, user_id)
                stats["synced"] += 1
            except Exception as e:
                logger.error(f"Failed to sync {md_file}: {e}")
                stats["errors"] += 1

        logger.info(f"Obsidian sync complete: {stats}")
        return stats

    async def _sync_file(self, file_path: Path, user_id: str) -> str:
        """
        Sync a single file to vector store.

        Args:
            file_path: Path to markdown file
            user_id: User ID

        Returns:
            Document ID
        """
        content = file_path.read_text(encoding="utf-8")

        # Extract metadata
        metadata = self._extract_metadata(file_path, content)

        # Create document ID from path
        relative_path = file_path.relative_to(self.vault_path)
        doc_id = f"obsidian:{relative_path}"

        # Add to vector store
        await self.vector_store.add_document(
            content=content,
            user_id=user_id,
            metadata=metadata,
            document_id=doc_id,
        )

        return doc_id

    def _extract_metadata(self, file_path: Path, content: str) -> dict[str, Any]:
        """
        Extract metadata from markdown file.

        Args:
            file_path: Path to file
            content: File content

        Returns:
            Metadata dict
        """
        metadata = {
            "source": "obsidian",
            "file_path": str(file_path),
            "file_name": file_path.stem,
            "modified_at": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
        }

        # Extract tags
        tags = re.findall(r"#([a-zA-Z][a-zA-Z0-9_/-]*)", content)
        if tags:
            metadata["tags"] = list(set(tags))

        # Extract wikilinks
        links = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)
        if links:
            metadata["links"] = list(set(links))

        # Check if it's a daily note
        if self._is_daily_note(file_path):
            metadata["type"] = "daily_note"
            metadata["date"] = file_path.stem

        # Extract YAML frontmatter
        frontmatter = self._extract_frontmatter(content)
        if frontmatter:
            metadata["frontmatter"] = frontmatter

        return metadata

    def _is_daily_note(self, file_path: Path) -> bool:
        """Check if file is a daily note (YYYY-MM-DD format)."""
        return bool(re.match(r"\d{4}-\d{2}-\d{2}", file_path.stem))

    def _extract_frontmatter(self, content: str) -> dict[str, Any] | None:
        """Extract YAML frontmatter from markdown."""
        if not content.startswith("---"):
            return None

        try:
            end_match = re.search(r"\n---\n", content[3:])
            if end_match:
                yaml_content = content[3 : end_match.start() + 3]
                # Simple key-value extraction (for basic cases)
                result = {}
                for line in yaml_content.split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        result[key.strip()] = value.strip()
                return result
        except Exception:
            pass
        return None

    def _should_exclude(self, file_path: Path) -> bool:
        """Check if file should be excluded from sync."""
        path_str = str(file_path)
        for pattern in self.EXCLUDE_PATTERNS:
            if re.search(pattern, path_str):
                return True
        return False

    async def search_notes(
        self, query: str, user_id: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """
        Search Obsidian notes.

        Args:
            query: Search query
            user_id: User ID
            limit: Maximum results

        Returns:
            List of matching notes
        """
        if not self.vector_store:
            return []

        results = await self.vector_store.search(
            query=query,
            user_id=user_id,
            limit=limit,
        )

        # Filter to only Obsidian documents
        return [r for r in results if r.get("metadata", {}).get("source") == "obsidian"]

    def get_recent_notes(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get recently modified notes.

        Args:
            limit: Maximum results

        Returns:
            List of recent notes
        """
        if not self.vault_path.exists():
            return []

        # Get all markdown files with modification times
        files = []
        for md_file in self.vault_path.rglob("*.md"):
            if not self._should_exclude(md_file):
                files.append(
                    {
                        "path": str(md_file.relative_to(self.vault_path)),
                        "name": md_file.stem,
                        "modified_at": datetime.fromtimestamp(md_file.stat().st_mtime),
                    }
                )

        # Sort by modification time
        files.sort(key=lambda x: x["modified_at"], reverse=True)
        return files[:limit]
