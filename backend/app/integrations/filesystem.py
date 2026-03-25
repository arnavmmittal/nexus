"""File System Tools - Access to local folders and files.

Allows Jarvis/Ultron to:
- Browse directories (Desktop, Downloads, Documents, etc.)
- Read file contents
- Search for files
- Get file information
- Create/write files (with confirmation)

This gives your AI assistant access to your local file system.
"""

from __future__ import annotations

import os
import json
import logging
import mimetypes
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Common user directories
USER_HOME = Path.home()
COMMON_DIRS = {
    "desktop": USER_HOME / "Desktop",
    "downloads": USER_HOME / "Downloads",
    "documents": USER_HOME / "Documents",
    "pictures": USER_HOME / "Pictures",
    "music": USER_HOME / "Music",
    "videos": USER_HOME / "Movies",
    "home": USER_HOME,
}

# File size limits for reading
MAX_READ_SIZE = 1024 * 1024  # 1MB max for text files
MAX_PREVIEW_SIZE = 10000  # 10KB preview for large files


def _format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def _format_time(timestamp: float) -> str:
    """Format timestamp to readable date."""
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def _get_file_info(path: Path) -> Dict[str, Any]:
    """Get detailed info about a file or directory."""
    try:
        stat = path.stat()
        return {
            "name": path.name,
            "path": str(path),
            "is_directory": path.is_dir(),
            "is_file": path.is_file(),
            "size": stat.st_size if path.is_file() else None,
            "size_formatted": _format_size(stat.st_size) if path.is_file() else None,
            "modified": _format_time(stat.st_mtime),
            "created": _format_time(stat.st_ctime),
            "extension": path.suffix.lower() if path.is_file() else None,
            "mime_type": mimetypes.guess_type(str(path))[0] if path.is_file() else None,
        }
    except Exception as e:
        return {"name": path.name, "path": str(path), "error": str(e)}


async def list_directory(
    path: str = "desktop",
    show_hidden: bool = False,
    sort_by: str = "name",
) -> str:
    """List contents of a directory.

    Args:
        path: Directory path or shortcut (desktop, downloads, documents, etc.)
        show_hidden: Whether to show hidden files (starting with .)
        sort_by: Sort by 'name', 'size', 'modified', or 'type'

    Returns:
        JSON string with directory contents
    """
    # Resolve path shortcuts
    if path.lower() in COMMON_DIRS:
        target_path = COMMON_DIRS[path.lower()]
    else:
        target_path = Path(path).expanduser()

    if not target_path.exists():
        return json.dumps({"error": f"Directory not found: {path}"})

    if not target_path.is_dir():
        return json.dumps({"error": f"Not a directory: {path}"})

    try:
        items = []
        for item in target_path.iterdir():
            # Skip hidden files if not requested
            if not show_hidden and item.name.startswith("."):
                continue

            items.append(_get_file_info(item))

        # Sort items
        if sort_by == "size":
            items.sort(key=lambda x: x.get("size") or 0, reverse=True)
        elif sort_by == "modified":
            items.sort(key=lambda x: x.get("modified", ""), reverse=True)
        elif sort_by == "type":
            items.sort(key=lambda x: (not x.get("is_directory", False), x.get("extension", "")))
        else:  # name
            items.sort(key=lambda x: x.get("name", "").lower())

        # Separate directories and files
        directories = [i for i in items if i.get("is_directory")]
        files = [i for i in items if i.get("is_file")]

        result = {
            "path": str(target_path),
            "total_items": len(items),
            "directories": len(directories),
            "files": len(files),
            "items": items,
        }

        logger.info(f"Listed directory: {target_path} ({len(items)} items)")
        return json.dumps(result, indent=2)

    except PermissionError:
        return json.dumps({"error": f"Permission denied: {path}"})
    except Exception as e:
        logger.error(f"Error listing directory: {e}")
        return json.dumps({"error": str(e)})


async def read_file(
    path: str,
    preview_only: bool = False,
) -> str:
    """Read contents of a file.

    Args:
        path: File path (can use ~ for home directory)
        preview_only: If True, only read first 10KB

    Returns:
        JSON string with file contents or error
    """
    target_path = Path(path).expanduser()

    if not target_path.exists():
        return json.dumps({"error": f"File not found: {path}"})

    if not target_path.is_file():
        return json.dumps({"error": f"Not a file: {path}"})

    try:
        file_info = _get_file_info(target_path)
        file_size = target_path.stat().st_size

        # Check if file is too large
        if file_size > MAX_READ_SIZE and not preview_only:
            return json.dumps({
                "error": f"File too large ({_format_size(file_size)}). Use preview_only=True for preview.",
                "file_info": file_info,
            })

        # Determine if file is binary
        mime_type = mimetypes.guess_type(str(target_path))[0]
        is_text = mime_type and (
            mime_type.startswith("text/") or
            mime_type in ["application/json", "application/xml", "application/javascript"]
        )

        if not is_text and target_path.suffix.lower() not in [
            ".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml",
            ".html", ".css", ".csv", ".xml", ".sh", ".bash", ".zsh",
            ".env", ".gitignore", ".log", ".ini", ".cfg", ".conf",
        ]:
            return json.dumps({
                "message": f"Binary file detected: {mime_type or 'unknown type'}",
                "file_info": file_info,
                "suggestion": "This appears to be a binary file. I can tell you about it but can't read its contents as text.",
            })

        # Read file
        max_size = MAX_PREVIEW_SIZE if preview_only else MAX_READ_SIZE
        with open(target_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(max_size)

        truncated = file_size > max_size

        result = {
            "path": str(target_path),
            "file_info": file_info,
            "content": content,
            "truncated": truncated,
            "bytes_read": len(content),
        }

        if truncated:
            result["message"] = f"File truncated. Showing first {_format_size(max_size)} of {_format_size(file_size)}"

        logger.info(f"Read file: {target_path} ({len(content)} chars)")
        return json.dumps(result, indent=2)

    except PermissionError:
        return json.dumps({"error": f"Permission denied: {path}"})
    except UnicodeDecodeError:
        return json.dumps({
            "error": "Cannot read file as text (binary file)",
            "file_info": _get_file_info(target_path),
        })
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        return json.dumps({"error": str(e)})


async def search_files(
    query: str,
    path: str = "home",
    file_type: Optional[str] = None,
    max_results: int = 20,
) -> str:
    """Search for files by name.

    Args:
        query: Search query (supports wildcards like *.pdf)
        path: Directory to search in (default: home)
        file_type: Filter by extension (e.g., 'pdf', 'docx')
        max_results: Maximum number of results

    Returns:
        JSON string with search results
    """
    # Resolve path shortcuts
    if path.lower() in COMMON_DIRS:
        search_path = COMMON_DIRS[path.lower()]
    else:
        search_path = Path(path).expanduser()

    if not search_path.exists():
        return json.dumps({"error": f"Directory not found: {path}"})

    try:
        results = []
        query_lower = query.lower()

        # Use glob for wildcard searches
        if "*" in query:
            pattern = query
        else:
            pattern = f"*{query}*"

        for match in search_path.rglob(pattern):
            # Skip hidden files and directories
            if any(part.startswith(".") for part in match.parts):
                continue

            # Filter by file type if specified
            if file_type and not match.suffix.lower() == f".{file_type.lower().lstrip('.')}":
                continue

            results.append(_get_file_info(match))

            if len(results) >= max_results:
                break

        result = {
            "query": query,
            "search_path": str(search_path),
            "results_count": len(results),
            "results": results,
        }

        logger.info(f"Search '{query}' in {search_path}: {len(results)} results")
        return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"Error searching files: {e}")
        return json.dumps({"error": str(e)})


async def get_file_info(path: str) -> str:
    """Get detailed information about a file or directory.

    Args:
        path: File or directory path

    Returns:
        JSON string with file information
    """
    target_path = Path(path).expanduser()

    if not target_path.exists():
        return json.dumps({"error": f"Path not found: {path}"})

    try:
        info = _get_file_info(target_path)

        # Add extra info for directories
        if target_path.is_dir():
            try:
                contents = list(target_path.iterdir())
                info["contains"] = {
                    "total": len(contents),
                    "files": len([c for c in contents if c.is_file()]),
                    "directories": len([c for c in contents if c.is_dir()]),
                }
            except PermissionError:
                info["contains"] = {"error": "Permission denied"}

        return json.dumps(info, indent=2)

    except Exception as e:
        logger.error(f"Error getting file info: {e}")
        return json.dumps({"error": str(e)})


async def write_file(
    path: str,
    content: str,
    create_dirs: bool = False,
) -> str:
    """Write content to a file.

    Args:
        path: File path
        content: Content to write
        create_dirs: Create parent directories if they don't exist

    Returns:
        JSON string with result
    """
    target_path = Path(path).expanduser()

    try:
        # Create parent directories if requested
        if create_dirs:
            target_path.parent.mkdir(parents=True, exist_ok=True)

        if not target_path.parent.exists():
            return json.dumps({"error": f"Parent directory does not exist: {target_path.parent}"})

        # Write file
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"Wrote file: {target_path} ({len(content)} chars)")

        return json.dumps({
            "success": True,
            "path": str(target_path),
            "bytes_written": len(content.encode("utf-8")),
            "message": f"Successfully wrote to {target_path.name}",
        })

    except PermissionError:
        return json.dumps({"error": f"Permission denied: {path}"})
    except Exception as e:
        logger.error(f"Error writing file: {e}")
        return json.dumps({"error": str(e)})


async def get_common_directories() -> str:
    """Get list of common directories and their paths.

    Returns:
        JSON string with common directory shortcuts
    """
    dirs = {}
    for name, path in COMMON_DIRS.items():
        dirs[name] = {
            "path": str(path),
            "exists": path.exists(),
        }

    return json.dumps({
        "directories": dirs,
        "usage": "Use these shortcuts in path arguments, e.g., 'desktop', 'downloads'",
    }, indent=2)


# Tool definitions for AI
FILESYSTEM_TOOLS = [
    {
        "name": "list_directory",
        "description": "List files and folders in a directory. Use shortcuts like 'desktop', 'downloads', 'documents', or provide a full path. Returns file names, sizes, and modification dates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path or shortcut (desktop, downloads, documents, pictures, music, videos, home)",
                    "default": "desktop",
                },
                "show_hidden": {
                    "type": "boolean",
                    "description": "Show hidden files (starting with .)",
                    "default": False,
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["name", "size", "modified", "type"],
                    "description": "How to sort the results",
                    "default": "name",
                },
            },
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a text file. Works with .txt, .md, .py, .js, .json, .csv, and other text files. Use preview_only=True for large files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Full path to the file (can use ~ for home directory)",
                },
                "preview_only": {
                    "type": "boolean",
                    "description": "Only read first 10KB of the file",
                    "default": False,
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "search_files",
        "description": "Search for files by name in a directory and subdirectories. Supports wildcards like *.pdf",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (e.g., 'resume', '*.pdf', 'project*.docx')",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (default: home)",
                    "default": "home",
                },
                "file_type": {
                    "type": "string",
                    "description": "Filter by file extension (e.g., 'pdf', 'docx')",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results",
                    "default": 20,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_file_info",
        "description": "Get detailed information about a file or folder (size, dates, type, etc.)",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file or directory",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file. Creates the file if it doesn't exist. Use with caution.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path where to write the file",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
                "create_dirs": {
                    "type": "boolean",
                    "description": "Create parent directories if they don't exist",
                    "default": False,
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "get_common_directories",
        "description": "Get a list of common directory shortcuts (desktop, downloads, documents, etc.) and their full paths",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]
