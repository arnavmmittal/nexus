"""Coder Agent Tools for code generation, file manipulation, and git operations.

This module provides tools that enable the AI to write code, manage files,
execute shell commands, and interact with GitHub.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

logger = logging.getLogger(__name__)

# Safe directories that the coder can operate in
# Can be expanded or configured via environment
SAFE_DIRECTORIES: List[str] = [
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Projects"),
    os.path.expanduser("~/Desktop"),
    "/tmp",
]

# Commands that are explicitly blocked
BLOCKED_COMMANDS: List[str] = [
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "dd if=",
    ":(){:|:&};:",  # fork bomb
    "> /dev/sda",
    "chmod -R 777 /",
    "mv ~ /dev/null",
]

# Default timeout for shell commands (in seconds)
DEFAULT_TIMEOUT: int = 30

# Maximum output size to capture (in bytes)
MAX_OUTPUT_SIZE: int = 100000


class ToolResult(TypedDict, total=False):
    """Standard result structure for all coder tools."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]]
    error: Optional[str]
    requires_confirmation: bool


def _is_safe_path(path: str) -> bool:
    """Check if a path is within safe directories."""
    abs_path = os.path.abspath(os.path.expanduser(path))
    return any(
        abs_path.startswith(os.path.expanduser(safe_dir))
        for safe_dir in SAFE_DIRECTORIES
    )


def _is_command_safe(command: str) -> bool:
    """Check if a command doesn't contain blocked patterns."""
    command_lower = command.lower()
    return not any(blocked in command_lower for blocked in BLOCKED_COMMANDS)


def _has_sudo(command: str) -> bool:
    """Check if command uses sudo."""
    return command.strip().startswith("sudo") or " sudo " in command


async def run_shell_command(
    command: str,
    working_directory: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
    allow_sudo: bool = False,
    env: Optional[Dict[str, str]] = None,
) -> ToolResult:
    """Execute a shell command safely with timeout and output capture.

    Args:
        command: The shell command to execute
        working_directory: Directory to run the command in (optional)
        timeout: Maximum execution time in seconds (default: 30)
        allow_sudo: Whether to allow sudo commands (default: False)
        env: Additional environment variables to set

    Returns:
        ToolResult with success status, stdout/stderr output, and exit code
    """
    logger.info(f"Executing shell command: {command[:100]}...")

    # Safety checks
    if not _is_command_safe(command):
        return {
            "success": False,
            "message": "Command blocked for safety reasons",
            "error": "This command pattern is not allowed",
            "requires_confirmation": True,
        }

    if _has_sudo(command) and not allow_sudo:
        return {
            "success": False,
            "message": "Sudo commands require explicit permission",
            "error": "Set allow_sudo=True to run sudo commands",
            "requires_confirmation": True,
        }

    # Validate working directory if provided
    if working_directory:
        working_directory = os.path.expanduser(working_directory)
        if not os.path.isdir(working_directory):
            return {
                "success": False,
                "message": f"Working directory does not exist: {working_directory}",
                "error": "Invalid working directory",
                "requires_confirmation": False,
            }

    # Prepare environment
    process_env = os.environ.copy()
    if env:
        process_env.update(env)

    try:
        # Run the command asynchronously
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=working_directory,
            env=process_env,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return {
                "success": False,
                "message": f"Command timed out after {timeout} seconds",
                "error": "Execution timeout",
                "data": {"command": command, "timeout": timeout},
                "requires_confirmation": False,
            }

        # Decode output, limiting size
        stdout_str = stdout.decode("utf-8", errors="replace")[:MAX_OUTPUT_SIZE]
        stderr_str = stderr.decode("utf-8", errors="replace")[:MAX_OUTPUT_SIZE]

        exit_code = process.returncode
        success = exit_code == 0

        logger.info(f"Command completed with exit code: {exit_code}")

        return {
            "success": success,
            "message": f"Command {'completed successfully' if success else 'failed'}",
            "data": {
                "stdout": stdout_str,
                "stderr": stderr_str,
                "exit_code": exit_code,
                "command": command,
            },
            "requires_confirmation": False,
        }

    except Exception as e:
        logger.error(f"Error executing command: {e}")
        return {
            "success": False,
            "message": "Failed to execute command",
            "error": str(e),
            "requires_confirmation": False,
        }


async def write_file(
    file_path: str,
    content: str,
    create_dirs: bool = True,
    backup: bool = True,
) -> ToolResult:
    """Create or edit a file on disk.

    Args:
        file_path: Path to the file to write
        content: Content to write to the file
        create_dirs: Create parent directories if they don't exist (default: True)
        backup: Create a backup of existing file before overwriting (default: True)

    Returns:
        ToolResult with success status and file information
    """
    logger.info(f"Writing file: {file_path}")

    file_path = os.path.expanduser(file_path)
    abs_path = os.path.abspath(file_path)

    # Safety check
    if not _is_safe_path(abs_path):
        return {
            "success": False,
            "message": f"Path is outside safe directories",
            "error": f"Cannot write to {abs_path}. Safe directories: {SAFE_DIRECTORIES}",
            "requires_confirmation": True,
        }

    try:
        path = Path(abs_path)

        # Create parent directories if needed
        if create_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)
        elif not path.parent.exists():
            return {
                "success": False,
                "message": f"Parent directory does not exist: {path.parent}",
                "error": "Set create_dirs=True to create parent directories",
                "requires_confirmation": False,
            }

        # Backup existing file
        backup_path = None
        if backup and path.exists():
            backup_path = f"{abs_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(abs_path, backup_path)
            logger.info(f"Created backup at: {backup_path}")

        # Write the file
        is_new = not path.exists()
        path.write_text(content, encoding="utf-8")

        logger.info(f"File {'created' if is_new else 'updated'}: {abs_path}")

        return {
            "success": True,
            "message": f"File {'created' if is_new else 'updated'} successfully",
            "data": {
                "path": abs_path,
                "size": len(content),
                "lines": len(content.splitlines()),
                "is_new": is_new,
                "backup_path": backup_path,
            },
            "requires_confirmation": False,
        }

    except PermissionError:
        return {
            "success": False,
            "message": f"Permission denied writing to {abs_path}",
            "error": "Insufficient permissions",
            "requires_confirmation": False,
        }
    except Exception as e:
        logger.error(f"Error writing file: {e}")
        return {
            "success": False,
            "message": "Failed to write file",
            "error": str(e),
            "requires_confirmation": False,
        }


async def read_file(
    file_path: str,
    encoding: str = "utf-8",
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> ToolResult:
    """Read file contents from disk.

    Args:
        file_path: Path to the file to read
        encoding: File encoding (default: utf-8)
        start_line: Starting line number (1-indexed, optional)
        end_line: Ending line number (inclusive, optional)

    Returns:
        ToolResult with file contents and metadata
    """
    logger.info(f"Reading file: {file_path}")

    file_path = os.path.expanduser(file_path)
    abs_path = os.path.abspath(file_path)

    try:
        path = Path(abs_path)

        if not path.exists():
            return {
                "success": False,
                "message": f"File not found: {abs_path}",
                "error": "File does not exist",
                "requires_confirmation": False,
            }

        if not path.is_file():
            return {
                "success": False,
                "message": f"Path is not a file: {abs_path}",
                "error": "Expected a file, got directory or other",
                "requires_confirmation": False,
            }

        # Read the file
        content = path.read_text(encoding=encoding)
        lines = content.splitlines(keepends=True)
        total_lines = len(lines)

        # Apply line range if specified
        if start_line is not None or end_line is not None:
            start_idx = (start_line - 1) if start_line else 0
            end_idx = end_line if end_line else total_lines
            start_idx = max(0, start_idx)
            end_idx = min(total_lines, end_idx)
            lines = lines[start_idx:end_idx]
            content = "".join(lines)

        return {
            "success": True,
            "message": "File read successfully",
            "data": {
                "path": abs_path,
                "content": content,
                "size": path.stat().st_size,
                "total_lines": total_lines,
                "lines_read": len(lines),
                "encoding": encoding,
            },
            "requires_confirmation": False,
        }

    except UnicodeDecodeError:
        return {
            "success": False,
            "message": f"Failed to decode file with encoding {encoding}",
            "error": "Try a different encoding (e.g., 'latin-1', 'cp1252')",
            "requires_confirmation": False,
        }
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        return {
            "success": False,
            "message": "Failed to read file",
            "error": str(e),
            "requires_confirmation": False,
        }


async def create_github_repo(
    name: str,
    description: Optional[str] = None,
    private: bool = False,
    add_readme: bool = True,
    gitignore_template: Optional[str] = None,
    license_template: Optional[str] = None,
) -> ToolResult:
    """Create a new GitHub repository using the gh CLI.

    Args:
        name: Repository name
        description: Repository description (optional)
        private: Create as private repository (default: False)
        add_readme: Initialize with README (default: True)
        gitignore_template: Gitignore template (e.g., 'Python', 'Node')
        license_template: License template (e.g., 'mit', 'apache-2.0')

    Returns:
        ToolResult with repository URL and details
    """
    logger.info(f"Creating GitHub repository: {name}")

    # Build the gh command
    cmd_parts = ["gh", "repo", "create", name]

    if description:
        cmd_parts.extend(["--description", description])

    if private:
        cmd_parts.append("--private")
    else:
        cmd_parts.append("--public")

    if add_readme:
        cmd_parts.append("--add-readme")

    if gitignore_template:
        cmd_parts.extend(["--gitignore", gitignore_template])

    if license_template:
        cmd_parts.extend(["--license", license_template])

    # Add --confirm to skip interactive prompts
    cmd_parts.append("--confirm")

    command = " ".join(f'"{p}"' if " " in p else p for p in cmd_parts)

    result = await run_shell_command(command, timeout=60)

    if result["success"]:
        # Extract repo URL from output
        stdout = result.get("data", {}).get("stdout", "")
        repo_url = None
        for line in stdout.splitlines():
            if "github.com" in line:
                repo_url = line.strip()
                break

        return {
            "success": True,
            "message": f"Repository '{name}' created successfully",
            "data": {
                "name": name,
                "url": repo_url or f"https://github.com/{name}",
                "private": private,
                "description": description,
            },
            "requires_confirmation": False,
        }
    else:
        return {
            "success": False,
            "message": f"Failed to create repository '{name}'",
            "error": result.get("error") or result.get("data", {}).get("stderr", "Unknown error"),
            "requires_confirmation": False,
        }


async def git_commit_push(
    message: str,
    working_directory: str,
    files: Optional[List[str]] = None,
    branch: Optional[str] = None,
    push: bool = True,
    set_upstream: bool = True,
) -> ToolResult:
    """Stage, commit, and optionally push changes to git.

    Args:
        message: Commit message
        working_directory: Path to the git repository
        files: Specific files to stage (default: all changed files)
        branch: Branch to push to (optional, uses current branch)
        push: Whether to push after commit (default: True)
        set_upstream: Set upstream when pushing new branch (default: True)

    Returns:
        ToolResult with commit hash and branch information
    """
    logger.info(f"Git commit and push in: {working_directory}")

    working_directory = os.path.expanduser(working_directory)

    if not os.path.isdir(os.path.join(working_directory, ".git")):
        return {
            "success": False,
            "message": "Not a git repository",
            "error": f"No .git directory found in {working_directory}",
            "requires_confirmation": False,
        }

    results = {"stages": []}

    # Stage files
    if files:
        stage_cmd = f"git add {' '.join(files)}"
    else:
        stage_cmd = "git add -A"

    stage_result = await run_shell_command(
        stage_cmd,
        working_directory=working_directory,
        timeout=30
    )
    results["stages"].append({"stage": "add", "result": stage_result})

    if not stage_result["success"]:
        return {
            "success": False,
            "message": "Failed to stage files",
            "error": stage_result.get("error") or stage_result.get("data", {}).get("stderr"),
            "data": results,
            "requires_confirmation": False,
        }

    # Commit
    # Escape the message for shell
    escaped_message = message.replace('"', '\\"').replace("$", "\\$")
    commit_cmd = f'git commit -m "{escaped_message}"'

    commit_result = await run_shell_command(
        commit_cmd,
        working_directory=working_directory,
        timeout=30
    )
    results["stages"].append({"stage": "commit", "result": commit_result})

    if not commit_result["success"]:
        stderr = commit_result.get("data", {}).get("stderr", "")
        # Check if nothing to commit
        if "nothing to commit" in stderr or "nothing added to commit" in commit_result.get("data", {}).get("stdout", ""):
            return {
                "success": True,
                "message": "Nothing to commit - working tree clean",
                "data": results,
                "requires_confirmation": False,
            }
        return {
            "success": False,
            "message": "Failed to commit",
            "error": stderr or commit_result.get("error"),
            "data": results,
            "requires_confirmation": False,
        }

    # Extract commit hash
    commit_output = commit_result.get("data", {}).get("stdout", "")
    commit_hash = None
    for line in commit_output.splitlines():
        if line.strip().startswith("["):
            # Format: [branch hash] message
            parts = line.strip().split()
            if len(parts) >= 2:
                commit_hash = parts[1].rstrip("]")
                break

    # Push if requested
    if push:
        push_cmd = "git push"
        if set_upstream:
            # Get current branch name
            branch_result = await run_shell_command(
                "git branch --show-current",
                working_directory=working_directory,
                timeout=10
            )
            current_branch = branch_result.get("data", {}).get("stdout", "").strip()
            if current_branch:
                push_cmd = f"git push -u origin {current_branch}"

        push_result = await run_shell_command(
            push_cmd,
            working_directory=working_directory,
            timeout=60
        )
        results["stages"].append({"stage": "push", "result": push_result})

        if not push_result["success"]:
            return {
                "success": False,
                "message": "Committed but failed to push",
                "data": {
                    "commit_hash": commit_hash,
                    "stages": results["stages"],
                },
                "error": push_result.get("error") or push_result.get("data", {}).get("stderr"),
                "requires_confirmation": False,
            }

    return {
        "success": True,
        "message": f"Successfully committed{' and pushed' if push else ''}",
        "data": {
            "commit_hash": commit_hash,
            "message": message,
            "pushed": push,
            "stages": results["stages"],
        },
        "requires_confirmation": False,
    }


async def create_pull_request(
    title: str,
    body: str,
    working_directory: str,
    base_branch: str = "main",
    draft: bool = False,
    reviewers: Optional[List[str]] = None,
    labels: Optional[List[str]] = None,
) -> ToolResult:
    """Create a pull request using the gh CLI.

    Args:
        title: PR title
        body: PR description/body
        working_directory: Path to the git repository
        base_branch: Base branch to merge into (default: main)
        draft: Create as draft PR (default: False)
        reviewers: List of GitHub usernames to request review from
        labels: List of labels to add

    Returns:
        ToolResult with PR URL and number
    """
    logger.info(f"Creating pull request: {title}")

    working_directory = os.path.expanduser(working_directory)

    if not os.path.isdir(os.path.join(working_directory, ".git")):
        return {
            "success": False,
            "message": "Not a git repository",
            "error": f"No .git directory found in {working_directory}",
            "requires_confirmation": False,
        }

    # Build the gh pr create command
    cmd_parts = ["gh", "pr", "create"]
    cmd_parts.extend(["--title", f'"{title}"'])
    cmd_parts.extend(["--body", f'"{body}"'])
    cmd_parts.extend(["--base", base_branch])

    if draft:
        cmd_parts.append("--draft")

    if reviewers:
        cmd_parts.extend(["--reviewer", ",".join(reviewers)])

    if labels:
        cmd_parts.extend(["--label", ",".join(labels)])

    command = " ".join(cmd_parts)

    result = await run_shell_command(
        command,
        working_directory=working_directory,
        timeout=60
    )

    if result["success"]:
        stdout = result.get("data", {}).get("stdout", "")
        pr_url = None
        for line in stdout.splitlines():
            if "github.com" in line and "/pull/" in line:
                pr_url = line.strip()
                break

        # Extract PR number from URL
        pr_number = None
        if pr_url:
            parts = pr_url.rstrip("/").split("/")
            if parts:
                try:
                    pr_number = int(parts[-1])
                except ValueError:
                    pass

        return {
            "success": True,
            "message": f"Pull request created successfully",
            "data": {
                "title": title,
                "url": pr_url,
                "number": pr_number,
                "base_branch": base_branch,
                "draft": draft,
            },
            "requires_confirmation": False,
        }
    else:
        return {
            "success": False,
            "message": "Failed to create pull request",
            "error": result.get("error") or result.get("data", {}).get("stderr", "Unknown error"),
            "requires_confirmation": False,
        }


async def install_package(
    package: str,
    manager: str = "auto",
    working_directory: Optional[str] = None,
    dev: bool = False,
    global_install: bool = False,
) -> ToolResult:
    """Install a package using npm or pip.

    Args:
        package: Package name (can include version, e.g., 'react@18.2.0')
        manager: Package manager to use ('npm', 'pip', or 'auto' to detect)
        working_directory: Directory to run installation in
        dev: Install as dev dependency (npm --save-dev, pip not applicable)
        global_install: Install globally (npm -g, pip --user)

    Returns:
        ToolResult with installation details
    """
    logger.info(f"Installing package: {package} with {manager}")

    if working_directory:
        working_directory = os.path.expanduser(working_directory)

    # Auto-detect package manager
    if manager == "auto":
        if working_directory:
            if os.path.exists(os.path.join(working_directory, "package.json")):
                manager = "npm"
            elif os.path.exists(os.path.join(working_directory, "requirements.txt")) or \
                 os.path.exists(os.path.join(working_directory, "setup.py")) or \
                 os.path.exists(os.path.join(working_directory, "pyproject.toml")):
                manager = "pip"
            else:
                return {
                    "success": False,
                    "message": "Could not auto-detect package manager",
                    "error": "No package.json or Python project files found",
                    "requires_confirmation": False,
                }
        else:
            return {
                "success": False,
                "message": "Cannot auto-detect without working_directory",
                "error": "Specify manager='npm' or manager='pip'",
                "requires_confirmation": False,
            }

    # Build the install command
    if manager == "npm":
        cmd_parts = ["npm", "install"]
        if dev:
            cmd_parts.append("--save-dev")
        if global_install:
            cmd_parts.append("-g")
        cmd_parts.append(package)
        command = " ".join(cmd_parts)

    elif manager == "pip":
        cmd_parts = ["pip", "install"]
        if global_install:
            cmd_parts.append("--user")
        cmd_parts.append(package)
        command = " ".join(cmd_parts)

    else:
        return {
            "success": False,
            "message": f"Unknown package manager: {manager}",
            "error": "Use 'npm', 'pip', or 'auto'",
            "requires_confirmation": False,
        }

    result = await run_shell_command(
        command,
        working_directory=working_directory,
        timeout=120  # Package installs can take time
    )

    if result["success"]:
        return {
            "success": True,
            "message": f"Successfully installed {package}",
            "data": {
                "package": package,
                "manager": manager,
                "dev_dependency": dev,
                "global": global_install,
                "output": result.get("data", {}).get("stdout", ""),
            },
            "requires_confirmation": False,
        }
    else:
        return {
            "success": False,
            "message": f"Failed to install {package}",
            "error": result.get("error") or result.get("data", {}).get("stderr", "Unknown error"),
            "requires_confirmation": False,
        }


# Tool definitions for Claude AI (same format as app/ai/tools.py)
CODER_TOOLS = [
    {
        "name": "run_shell_command",
        "description": "Execute a shell command safely with timeout and output capture. Use for running build commands, tests, scripts, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute"
                },
                "working_directory": {
                    "type": "string",
                    "description": "Directory to run the command in (optional)"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Maximum execution time in seconds (default: 30)"
                },
                "allow_sudo": {
                    "type": "boolean",
                    "description": "Allow sudo commands (default: false, requires confirmation)"
                }
            },
            "required": ["command"]
        },
        "requires_confirmation": True
    },
    {
        "name": "write_file",
        "description": "Create or edit a file on disk. Automatically creates parent directories and backs up existing files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to write"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                },
                "create_dirs": {
                    "type": "boolean",
                    "description": "Create parent directories if they don't exist (default: true)"
                },
                "backup": {
                    "type": "boolean",
                    "description": "Backup existing file before overwriting (default: true)"
                }
            },
            "required": ["file_path", "content"]
        },
        "requires_confirmation": True
    },
    {
        "name": "read_file",
        "description": "Read file contents from disk. Supports reading specific line ranges.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to read"
                },
                "encoding": {
                    "type": "string",
                    "description": "File encoding (default: utf-8)"
                },
                "start_line": {
                    "type": "integer",
                    "description": "Starting line number (1-indexed, optional)"
                },
                "end_line": {
                    "type": "integer",
                    "description": "Ending line number (inclusive, optional)"
                }
            },
            "required": ["file_path"]
        },
        "requires_confirmation": False
    },
    {
        "name": "create_github_repo",
        "description": "Create a new GitHub repository using the gh CLI. Requires gh to be installed and authenticated.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Repository name"
                },
                "description": {
                    "type": "string",
                    "description": "Repository description"
                },
                "private": {
                    "type": "boolean",
                    "description": "Create as private repository (default: false)"
                },
                "add_readme": {
                    "type": "boolean",
                    "description": "Initialize with README (default: true)"
                },
                "gitignore_template": {
                    "type": "string",
                    "description": "Gitignore template (e.g., 'Python', 'Node')"
                },
                "license_template": {
                    "type": "string",
                    "description": "License template (e.g., 'mit', 'apache-2.0')"
                }
            },
            "required": ["name"]
        },
        "requires_confirmation": True
    },
    {
        "name": "git_commit_push",
        "description": "Stage, commit, and optionally push changes to git. Use for saving and sharing code changes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Commit message"
                },
                "working_directory": {
                    "type": "string",
                    "description": "Path to the git repository"
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific files to stage (default: all changed files)"
                },
                "branch": {
                    "type": "string",
                    "description": "Branch to push to (optional, uses current branch)"
                },
                "push": {
                    "type": "boolean",
                    "description": "Whether to push after commit (default: true)"
                }
            },
            "required": ["message", "working_directory"]
        },
        "requires_confirmation": True
    },
    {
        "name": "create_pull_request",
        "description": "Create a pull request using the gh CLI. Requires gh to be installed and authenticated.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "PR title"
                },
                "body": {
                    "type": "string",
                    "description": "PR description/body"
                },
                "working_directory": {
                    "type": "string",
                    "description": "Path to the git repository"
                },
                "base_branch": {
                    "type": "string",
                    "description": "Base branch to merge into (default: main)"
                },
                "draft": {
                    "type": "boolean",
                    "description": "Create as draft PR (default: false)"
                },
                "reviewers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "GitHub usernames to request review from"
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Labels to add to the PR"
                }
            },
            "required": ["title", "body", "working_directory"]
        },
        "requires_confirmation": True
    },
    {
        "name": "install_package",
        "description": "Install a package using npm or pip. Auto-detects package manager based on project files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "package": {
                    "type": "string",
                    "description": "Package name (can include version, e.g., 'react@18.2.0')"
                },
                "manager": {
                    "type": "string",
                    "enum": ["npm", "pip", "auto"],
                    "description": "Package manager to use (default: auto)"
                },
                "working_directory": {
                    "type": "string",
                    "description": "Directory to run installation in"
                },
                "dev": {
                    "type": "boolean",
                    "description": "Install as dev dependency (default: false)"
                },
                "global_install": {
                    "type": "boolean",
                    "description": "Install globally (default: false)"
                }
            },
            "required": ["package"]
        },
        "requires_confirmation": True
    }
]


class CoderToolExecutor:
    """Executes coder tools on behalf of the AI.

    This executor provides methods prefixed with _tool_ that match the
    tool names in CODER_TOOLS, following the pattern used by the
    AgenticExecutor in executor.py.
    """

    def __init__(self, db=None, user_id=None):
        """Initialize the executor.

        Args:
            db: Database session (optional, for future use)
            user_id: User ID (optional, for future use)
        """
        self.db = db
        self.user_id = user_id

    # Tool methods following the _tool_{name} pattern expected by executor.py

    async def _tool_run_shell_command(
        self,
        command: str,
        working_directory: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
        allow_sudo: bool = False,
        env: Optional[Dict[str, str]] = None,
    ) -> ToolResult:
        """Execute a shell command safely."""
        return await run_shell_command(
            command=command,
            working_directory=working_directory,
            timeout=timeout,
            allow_sudo=allow_sudo,
            env=env,
        )

    async def _tool_write_file(
        self,
        file_path: str,
        content: str,
        create_dirs: bool = True,
        backup: bool = True,
    ) -> ToolResult:
        """Create or edit a file on disk."""
        return await write_file(
            file_path=file_path,
            content=content,
            create_dirs=create_dirs,
            backup=backup,
        )

    async def _tool_read_file(
        self,
        file_path: str,
        encoding: str = "utf-8",
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
    ) -> ToolResult:
        """Read file contents from disk."""
        return await read_file(
            file_path=file_path,
            encoding=encoding,
            start_line=start_line,
            end_line=end_line,
        )

    async def _tool_create_github_repo(
        self,
        name: str,
        description: Optional[str] = None,
        private: bool = False,
        add_readme: bool = True,
        gitignore_template: Optional[str] = None,
        license_template: Optional[str] = None,
    ) -> ToolResult:
        """Create a new GitHub repository."""
        return await create_github_repo(
            name=name,
            description=description,
            private=private,
            add_readme=add_readme,
            gitignore_template=gitignore_template,
            license_template=license_template,
        )

    async def _tool_git_commit_push(
        self,
        message: str,
        working_directory: str,
        files: Optional[List[str]] = None,
        branch: Optional[str] = None,
        push: bool = True,
        set_upstream: bool = True,
    ) -> ToolResult:
        """Stage, commit, and optionally push changes."""
        return await git_commit_push(
            message=message,
            working_directory=working_directory,
            files=files,
            branch=branch,
            push=push,
            set_upstream=set_upstream,
        )

    async def _tool_create_pull_request(
        self,
        title: str,
        body: str,
        working_directory: str,
        base_branch: str = "main",
        draft: bool = False,
        reviewers: Optional[List[str]] = None,
        labels: Optional[List[str]] = None,
    ) -> ToolResult:
        """Create a pull request."""
        return await create_pull_request(
            title=title,
            body=body,
            working_directory=working_directory,
            base_branch=base_branch,
            draft=draft,
            reviewers=reviewers,
            labels=labels,
        )

    async def _tool_install_package(
        self,
        package: str,
        manager: str = "auto",
        working_directory: Optional[str] = None,
        dev: bool = False,
        global_install: bool = False,
    ) -> ToolResult:
        """Install a package using npm or pip."""
        return await install_package(
            package=package,
            manager=manager,
            working_directory=working_directory,
            dev=dev,
            global_install=global_install,
        )

    # General execution methods

    async def execute(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """Execute a tool and return the result as a JSON string."""
        try:
            method = getattr(self, f"_tool_{tool_name}", None)
            if method is None:
                return json.dumps({
                    "success": False,
                    "error": f"Unknown coder tool: {tool_name}"
                })

            result = await method(**tool_input)
            return json.dumps(result, default=str)

        except Exception as e:
            logger.error(f"Error executing coder tool {tool_name}: {e}")
            return json.dumps({
                "success": False,
                "error": f"Error executing {tool_name}: {str(e)}"
            })

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Return tool definitions for Claude."""
        return CODER_TOOLS

    def requires_confirmation(self, tool_name: str) -> bool:
        """Check if a tool requires user confirmation before execution."""
        for tool in CODER_TOOLS:
            if tool["name"] == tool_name:
                return tool.get("requires_confirmation", False)
        return True  # Default to requiring confirmation for unknown tools
