"""Obsidian vault synchronization with file watching and vector store indexing."""

import hashlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# Chunk size for long documents (in characters)
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200


class SyncStatus:
    """Tracks the status of Obsidian vault synchronization."""

    def __init__(self, status_file: Path | None = None):
        """Initialize sync status tracker.

        Args:
            status_file: Path to status JSON file
        """
        self.status_file = status_file or Path(settings.chromadb_path).expanduser().resolve() / "obsidian_sync_status.json"
        self._status = self._load_status()

    def _load_status(self) -> dict[str, Any]:
        """Load status from file."""
        if self.status_file.exists():
            try:
                return json.loads(self.status_file.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {
            "last_sync": None,
            "file_count": 0,
            "indexed_count": 0,
            "file_hashes": {},
            "errors": [],
        }

    def _save_status(self) -> None:
        """Save status to file."""
        self.status_file.parent.mkdir(parents=True, exist_ok=True)
        self.status_file.write_text(json.dumps(self._status, indent=2, default=str))

    def get_file_hash(self, file_path: str) -> str | None:
        """Get stored hash for a file."""
        return self._status["file_hashes"].get(file_path)

    def set_file_hash(self, file_path: str, content_hash: str) -> None:
        """Store hash for a file."""
        self._status["file_hashes"][file_path] = content_hash

    def remove_file(self, file_path: str) -> None:
        """Remove a file from tracking."""
        self._status["file_hashes"].pop(file_path, None)

    def get_tracked_files(self) -> set[str]:
        """Get set of all tracked file paths."""
        return set(self._status["file_hashes"].keys())

    def update_sync_stats(
        self,
        file_count: int,
        indexed_count: int,
        errors: list[str] | None = None,
    ) -> None:
        """Update sync statistics."""
        self._status["last_sync"] = datetime.utcnow().isoformat()
        self._status["file_count"] = file_count
        self._status["indexed_count"] = indexed_count
        if errors:
            self._status["errors"] = errors[-10:]  # Keep last 10 errors
        self._save_status()

    def get_status(self) -> dict[str, Any]:
        """Get current sync status."""
        return {
            "last_sync": self._status["last_sync"],
            "file_count": self._status["file_count"],
            "indexed_count": self._status["indexed_count"],
            "tracked_files": len(self._status["file_hashes"]),
            "recent_errors": self._status.get("errors", [])[-5:],
        }


def compute_content_hash(content: str) -> str:
    """Compute MD5 hash of content for change detection."""
    return hashlib.md5(content.encode()).hexdigest()


def chunk_content(content: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split content into overlapping chunks for better vector search.

    Args:
        content: Text content to chunk
        chunk_size: Maximum characters per chunk
        overlap: Overlap between chunks

    Returns:
        List of content chunks
    """
    if len(content) <= chunk_size:
        return [content]

    chunks = []
    start = 0

    while start < len(content):
        end = start + chunk_size

        # Try to break at paragraph or sentence boundary
        if end < len(content):
            # Look for paragraph break
            para_break = content.rfind("\n\n", start, end)
            if para_break > start + chunk_size // 2:
                end = para_break + 2
            else:
                # Look for sentence break
                sentence_break = content.rfind(". ", start, end)
                if sentence_break > start + chunk_size // 2:
                    end = sentence_break + 2
                else:
                    # Look for line break
                    line_break = content.rfind("\n", start, end)
                    if line_break > start + chunk_size // 2:
                        end = line_break + 1

        chunks.append(content[start:end].strip())
        start = end - overlap

        # Avoid tiny final chunks
        if len(content) - start < chunk_size // 4:
            if chunks:
                # Append remainder to last chunk if small
                chunks[-1] = chunks[-1] + " " + content[start:].strip()
            else:
                chunks.append(content[start:].strip())
            break

    return [c for c in chunks if c]  # Filter empty chunks


class ObsidianSync:
    """
    Synchronizes Obsidian vault content to vector store.

    Supports:
    - Markdown files with incremental sync
    - Daily notes detection
    - Tags and links extraction
    - Content chunking for long notes
    - File modification tracking
    """

    # File patterns to exclude
    EXCLUDE_PATTERNS = [
        r"\.obsidian/",
        r"\.trash/",
        r"templates/",
        r"\.git/",
        r"node_modules/",
    ]

    def __init__(self, vault_path: str | None = None, vector_store: Any | None = None):
        """
        Initialize Obsidian sync.

        Args:
            vault_path: Path to Obsidian vault
            vector_store: Vector store instance
        """
        self.vault_path = Path(vault_path or settings.obsidian_vault_path or "").expanduser().resolve()
        self.vector_store = vector_store
        self.sync_status = SyncStatus()

        if self.vault_path.as_posix() != "." and not self.vault_path.exists():
            logger.warning(f"Obsidian vault not found at {self.vault_path}")

    def is_configured(self) -> bool:
        """Check if Obsidian sync is properly configured."""
        return bool(
            self.vault_path.as_posix() != "."
            and self.vault_path.exists()
            and self.vector_store is not None
        )

    async def sync_vault(self, user_id: str, force: bool = False) -> dict[str, Any]:
        """
        Sync entire vault to vector store.

        Args:
            user_id: User ID
            force: Force full resync (ignore file hashes)

        Returns:
            Sync statistics
        """
        if not self.vault_path.exists() or self.vault_path.as_posix() == ".":
            return {"error": "Vault not found or not configured", "synced": 0}

        if not self.vector_store:
            return {"error": "Vector store not configured", "synced": 0}

        stats = {
            "synced": 0,
            "skipped": 0,
            "unchanged": 0,
            "deleted": 0,
            "errors": 0,
            "chunks_created": 0,
        }
        errors: list[str] = []

        # Track current files for deletion detection
        current_files: set[str] = set()

        # Find all markdown files
        for md_file in self.vault_path.rglob("*.md"):
            if self._should_exclude(md_file):
                stats["skipped"] += 1
                continue

            relative_path = str(md_file.relative_to(self.vault_path))
            current_files.add(relative_path)

            try:
                content = md_file.read_text(encoding="utf-8")
                content_hash = compute_content_hash(content)

                # Check if file has changed
                if not force and self.sync_status.get_file_hash(relative_path) == content_hash:
                    stats["unchanged"] += 1
                    continue

                # Sync file and update hash
                chunks = await self._sync_file(md_file, user_id, content)
                self.sync_status.set_file_hash(relative_path, content_hash)
                stats["synced"] += 1
                stats["chunks_created"] += chunks

            except Exception as e:
                logger.error(f"Failed to sync {md_file}: {e}")
                errors.append(f"{relative_path}: {str(e)}")
                stats["errors"] += 1

        # Handle deleted files
        tracked_files = self.sync_status.get_tracked_files()
        deleted_files = tracked_files - current_files

        for deleted_path in deleted_files:
            try:
                await self._delete_file_documents(deleted_path, user_id)
                self.sync_status.remove_file(deleted_path)
                stats["deleted"] += 1
            except Exception as e:
                logger.error(f"Failed to delete documents for {deleted_path}: {e}")
                errors.append(f"delete {deleted_path}: {str(e)}")

        # Update sync status
        total_files = len(current_files)
        self.sync_status.update_sync_stats(
            file_count=total_files,
            indexed_count=stats["synced"] + stats["unchanged"],
            errors=errors,
        )

        logger.info(f"Obsidian sync complete: {stats}")
        return stats

    async def _sync_file(self, file_path: Path, user_id: str, content: str) -> int:
        """
        Sync a single file to vector store.

        Args:
            file_path: Path to markdown file
            user_id: User ID
            content: File content

        Returns:
            Number of chunks created
        """
        # Extract metadata
        metadata = self._extract_metadata(file_path, content)
        relative_path = str(file_path.relative_to(self.vault_path))

        # Delete existing documents for this file
        await self._delete_file_documents(relative_path, user_id)

        # Chunk content for long notes
        chunks = chunk_content(content)

        # Add chunks to vector store
        for i, chunk in enumerate(chunks):
            doc_id = f"obsidian:{relative_path}:chunk_{i}"

            chunk_metadata = {
                **metadata,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "relative_path": relative_path,
            }

            await self.vector_store.add_document(
                content=chunk,
                user_id=user_id,
                metadata=chunk_metadata,
                document_id=doc_id,
            )

        return len(chunks)

    async def _delete_file_documents(self, relative_path: str, user_id: str) -> None:
        """Delete all documents associated with a file."""
        # Delete by pattern - try to delete chunks 0-100 (more than enough)
        for i in range(100):
            doc_id = f"obsidian:{relative_path}:chunk_{i}"
            try:
                await self.vector_store.delete_document(doc_id)
            except Exception:
                break  # No more chunks

    def _extract_metadata(self, file_path: Path, content: str) -> dict[str, Any]:
        """
        Extract metadata from markdown file.

        Args:
            file_path: Path to file
            content: File content

        Returns:
            Metadata dict
        """
        metadata: dict[str, Any] = {
            "source": "obsidian",
            "file_path": str(file_path),
            "file_name": file_path.stem,
            "modified_at": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
        }

        # Extract tags (hashtags in content)
        tags = re.findall(r"#([a-zA-Z][a-zA-Z0-9_/-]*)", content)
        if tags:
            # Store as comma-separated string for ChromaDB compatibility
            metadata["tags"] = ",".join(sorted(set(tags)))

        # Extract wikilinks
        links = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)
        if links:
            metadata["links"] = ",".join(sorted(set(links)))

        # Check if it's a daily note
        if self._is_daily_note(file_path):
            metadata["type"] = "daily_note"
            metadata["date"] = file_path.stem
        else:
            metadata["type"] = "note"

        # Extract YAML frontmatter
        frontmatter = self._extract_frontmatter(content)
        if frontmatter:
            # Flatten frontmatter for ChromaDB (only string values)
            for key, value in frontmatter.items():
                if isinstance(value, str):
                    metadata[f"fm_{key}"] = value
                elif isinstance(value, (list, tuple)):
                    metadata[f"fm_{key}"] = ",".join(str(v) for v in value)

            # Special handling for frontmatter tags
            if "tags" in frontmatter:
                fm_tags = frontmatter["tags"]
                if isinstance(fm_tags, str):
                    fm_tags = [t.strip() for t in fm_tags.split(",")]
                if isinstance(fm_tags, list):
                    existing_tags = set(metadata.get("tags", "").split(",")) if metadata.get("tags") else set()
                    existing_tags.update(str(t) for t in fm_tags if t)
                    existing_tags.discard("")
                    if existing_tags:
                        metadata["tags"] = ",".join(sorted(existing_tags))

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
                # Simple key-value extraction (handles basic YAML)
                result: dict[str, Any] = {}
                current_key = None
                current_list: list[str] = []

                for line in yaml_content.split("\n"):
                    stripped = line.strip()
                    if not stripped:
                        continue

                    # Check for list item
                    if stripped.startswith("- ") and current_key:
                        current_list.append(stripped[2:].strip())
                        result[current_key] = current_list
                        continue

                    # Check for key: value
                    if ":" in line:
                        # Save previous list if exists
                        if current_key and current_list:
                            result[current_key] = current_list

                        key, value = line.split(":", 1)
                        current_key = key.strip()
                        value = value.strip()

                        if value:
                            # Handle inline lists like [a, b, c]
                            if value.startswith("[") and value.endswith("]"):
                                items = [v.strip().strip("'\"") for v in value[1:-1].split(",")]
                                result[current_key] = items
                            else:
                                result[current_key] = value.strip("'\"")
                            current_list = []
                        else:
                            current_list = []

                return result if result else None
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
        self, query: str, user_id: str, limit: int = 5, tags: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """
        Search Obsidian notes semantically.

        Args:
            query: Search query
            user_id: User ID
            limit: Maximum results
            tags: Optional filter by tags

        Returns:
            List of matching notes with metadata
        """
        if not self.vector_store:
            return []

        results = await self.vector_store.search(
            query=query,
            user_id=user_id,
            limit=limit * 2,  # Get more results to filter
        )

        # Filter to only Obsidian documents
        obsidian_results = []
        seen_files: set[str] = set()

        for r in results:
            metadata = r.get("metadata", {})
            if metadata.get("source") != "obsidian":
                continue

            # Filter by tags if specified
            if tags:
                result_tags = set(metadata.get("tags", "").split(","))
                if not any(tag in result_tags for tag in tags):
                    continue

            # Deduplicate by file (multiple chunks from same file)
            file_path = metadata.get("relative_path", metadata.get("file_path", ""))
            if file_path in seen_files:
                continue
            seen_files.add(file_path)

            obsidian_results.append(r)

            if len(obsidian_results) >= limit:
                break

        return obsidian_results

    def get_recent_notes(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get recently modified notes from vault.

        Args:
            limit: Maximum results

        Returns:
            List of recent notes
        """
        if not self.vault_path.exists() or self.vault_path.as_posix() == ".":
            return []

        # Get all markdown files with modification times
        files = []
        for md_file in self.vault_path.rglob("*.md"):
            if not self._should_exclude(md_file):
                files.append(
                    {
                        "path": str(md_file.relative_to(self.vault_path)),
                        "name": md_file.stem,
                        "modified_at": datetime.fromtimestamp(md_file.stat().st_mtime).isoformat(),
                    }
                )

        # Sort by modification time
        files.sort(key=lambda x: x["modified_at"], reverse=True)
        return files[:limit]

    def get_vault_stats(self) -> dict[str, Any]:
        """Get statistics about the vault."""
        if not self.vault_path.exists() or self.vault_path.as_posix() == ".":
            return {
                "configured": False,
                "vault_path": str(self.vault_path),
            }

        # Count files
        total_files = 0
        daily_notes = 0
        total_size = 0

        for md_file in self.vault_path.rglob("*.md"):
            if not self._should_exclude(md_file):
                total_files += 1
                total_size += md_file.stat().st_size
                if self._is_daily_note(md_file):
                    daily_notes += 1

        return {
            "configured": True,
            "vault_path": str(self.vault_path),
            "total_files": total_files,
            "daily_notes": daily_notes,
            "regular_notes": total_files - daily_notes,
            "total_size_kb": round(total_size / 1024, 2),
            "sync_status": self.sync_status.get_status(),
        }


# Global instance (lazy initialization)
_obsidian_sync: ObsidianSync | None = None


def get_obsidian_sync() -> ObsidianSync:
    """Get or create ObsidianSync instance."""
    global _obsidian_sync
    if _obsidian_sync is None:
        from app.memory.vector_store import get_vector_store

        _obsidian_sync = ObsidianSync(vector_store=get_vector_store())
    return _obsidian_sync
