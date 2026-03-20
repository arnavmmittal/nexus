"""System control tools for macOS automation.

This module provides tools for Jarvis to interact with the macOS system,
including launching applications, managing files, taking screenshots,
and executing AppleScript commands.

SAFETY FIRST: All file operations are restricted to safe directories only.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


# Safe directories where file operations are allowed
SAFE_DIRECTORIES: List[str] = [
    os.path.expanduser("~"),  # User's home directory
    "/tmp",  # Temporary directory
    "/Users/arnavmmittal/Documents/nexus",  # Project directory
]

# Explicitly blocked directories (never allow operations here)
BLOCKED_DIRECTORIES: List[str] = [
    "/System",
    "/Library",
    "/usr",
    "/bin",
    "/sbin",
    "/var",
    "/etc",
    "/private/var",
    "/private/etc",
    "/Applications",  # System applications
]


def is_path_safe(path: str) -> bool:
    """Check if a path is within allowed directories.

    Args:
        path: The path to validate.

    Returns:
        True if the path is safe to operate on, False otherwise.
    """
    try:
        # Resolve the path to handle symlinks and relative paths
        resolved_path = os.path.realpath(os.path.expanduser(path))

        # Check if path is in any blocked directory
        for blocked in BLOCKED_DIRECTORIES:
            if resolved_path.startswith(blocked):
                return False

        # Check if path is in any safe directory
        for safe_dir in SAFE_DIRECTORIES:
            safe_resolved = os.path.realpath(os.path.expanduser(safe_dir))
            if resolved_path.startswith(safe_resolved):
                return True

        return False
    except Exception:
        return False


def get_safe_directories_display() -> str:
    """Get a display string of safe directories for user feedback."""
    return ", ".join(SAFE_DIRECTORIES)


# Tool definitions for Claude (matching the format in app/ai/tools.py)
SYSTEM_CONTROL_TOOLS: List[Dict[str, Any]] = [
    # ============ APPLICATION CONTROL ============
    {
        "name": "open_app",
        "description": "Launch a macOS application by name. Use this to open apps like Safari, Finder, Terminal, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "Name of the application to open (e.g., 'Safari', 'Finder', 'Terminal', 'Visual Studio Code')"
                }
            },
            "required": ["app_name"]
        },
        "requires_confirmation": False
    },
    {
        "name": "open_url",
        "description": "Open a URL in the default web browser.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to open (e.g., 'https://google.com')"
                }
            },
            "required": ["url"]
        },
        "requires_confirmation": False
    },

    # ============ FILE SYSTEM OPERATIONS ============
    {
        "name": "list_files",
        "description": "List files and directories in a specified path with details like size, modification time, and type.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list (must be within allowed directories)"
                },
                "show_hidden": {
                    "type": "boolean",
                    "description": "Whether to show hidden files (starting with .)"
                }
            },
            "required": ["path"]
        },
        "requires_confirmation": False
    },
    {
        "name": "move_file",
        "description": "Move or rename a file or directory. Both source and destination must be within allowed directories.",
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Source file or directory path"
                },
                "destination": {
                    "type": "string",
                    "description": "Destination path"
                }
            },
            "required": ["source", "destination"]
        },
        "requires_confirmation": True
    },
    {
        "name": "delete_file",
        "description": "Delete a file or directory. REQUIRES CONFIRMATION. Only works within allowed directories.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file or directory to delete"
                },
                "confirmed": {
                    "type": "boolean",
                    "description": "Must be set to true to confirm deletion. This is a safety measure."
                }
            },
            "required": ["path", "confirmed"]
        },
        "requires_confirmation": True
    },
    {
        "name": "create_folder",
        "description": "Create a new directory. Parent directories will be created if they don't exist.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path for the new directory"
                }
            },
            "required": ["path"]
        },
        "requires_confirmation": False
    },

    # ============ SYSTEM UTILITIES ============
    {
        "name": "take_screenshot",
        "description": "Take a screenshot and save it to a specified location. Defaults to Desktop if no path provided.",
        "input_schema": {
            "type": "object",
            "properties": {
                "output_path": {
                    "type": "string",
                    "description": "Path where to save the screenshot (optional, defaults to Desktop)"
                },
                "capture_type": {
                    "type": "string",
                    "enum": ["fullscreen", "selection", "window"],
                    "description": "Type of screenshot: fullscreen, selection (interactive), or window"
                },
                "delay_seconds": {
                    "type": "integer",
                    "description": "Delay before taking screenshot (0-10 seconds)"
                }
            },
            "required": []
        },
        "requires_confirmation": False
    },
    {
        "name": "get_clipboard",
        "description": "Get the current contents of the system clipboard (text only).",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        },
        "requires_confirmation": False
    },
    {
        "name": "set_clipboard",
        "description": "Set the system clipboard contents (text only).",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to copy to the clipboard"
                }
            },
            "required": ["text"]
        },
        "requires_confirmation": False
    },

    # ============ APPLESCRIPT ============
    {
        "name": "run_applescript",
        "description": "Execute an AppleScript command. The full script will be shown for review before execution. Use for advanced macOS automation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "script": {
                    "type": "string",
                    "description": "The AppleScript code to execute"
                },
                "confirmed": {
                    "type": "boolean",
                    "description": "Must be set to true to confirm execution. The script will be displayed for review."
                }
            },
            "required": ["script", "confirmed"]
        },
        "requires_confirmation": True
    },
]


class SystemControlExecutor:
    """Executes system control tools on behalf of the AI.

    This class provides a safe interface for executing system operations,
    with built-in validation and error handling.
    """

    def __init__(self) -> None:
        """Initialize the executor."""
        self.safe_directories = SAFE_DIRECTORIES.copy()

    def add_safe_directory(self, path: str) -> None:
        """Add a directory to the list of safe directories.

        Args:
            path: The directory path to add.
        """
        resolved = os.path.realpath(os.path.expanduser(path))
        if resolved not in self.safe_directories:
            self.safe_directories.append(resolved)

    async def execute(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """Execute a tool and return the result as a string.

        Args:
            tool_name: Name of the tool to execute.
            tool_input: Input parameters for the tool.

        Returns:
            JSON string with the result.
        """
        try:
            method = getattr(self, f"_tool_{tool_name}", None)
            if method is None:
                return json.dumps({
                    "success": False,
                    "error": f"Unknown tool '{tool_name}'"
                })
            result = await method(**tool_input)
            return json.dumps(result, default=str)
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error executing {tool_name}: {str(e)}"
            })

    # ============ APPLICATION CONTROL ============

    async def _tool_open_app(self, app_name: str) -> Dict[str, Any]:
        """Launch a macOS application.

        Args:
            app_name: Name of the application to open.

        Returns:
            Result dictionary with success status and message.
        """
        try:
            # Use the 'open' command to launch the app
            result = subprocess.run(
                ["open", "-a", app_name],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "message": f"Launched application: {app_name}"
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to launch '{app_name}': {result.stderr.strip()}"
                }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Timeout while launching '{app_name}'"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error launching '{app_name}': {str(e)}"
            }

    async def _tool_open_url(self, url: str) -> Dict[str, Any]:
        """Open a URL in the default browser.

        Args:
            url: The URL to open.

        Returns:
            Result dictionary with success status and message.
        """
        try:
            # Basic URL validation
            if not url.startswith(("http://", "https://", "file://")):
                url = "https://" + url

            result = subprocess.run(
                ["open", url],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "message": f"Opened URL: {url}"
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to open URL: {result.stderr.strip()}"
                }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Timeout while opening URL"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error opening URL: {str(e)}"
            }

    # ============ FILE SYSTEM OPERATIONS ============

    async def _tool_list_files(
        self,
        path: str,
        show_hidden: bool = False
    ) -> Dict[str, Any]:
        """List files and directories in a path.

        Args:
            path: Directory path to list.
            show_hidden: Whether to include hidden files.

        Returns:
            Result dictionary with file listing.
        """
        try:
            expanded_path = os.path.expanduser(path)

            if not is_path_safe(expanded_path):
                return {
                    "success": False,
                    "error": f"Path is not within allowed directories. Allowed: {get_safe_directories_display()}"
                }

            if not os.path.exists(expanded_path):
                return {
                    "success": False,
                    "error": f"Path does not exist: {path}"
                }

            if not os.path.isdir(expanded_path):
                return {
                    "success": False,
                    "error": f"Path is not a directory: {path}"
                }

            entries = []
            for entry in os.scandir(expanded_path):
                # Skip hidden files unless requested
                if not show_hidden and entry.name.startswith("."):
                    continue

                try:
                    stat_info = entry.stat()
                    entries.append({
                        "name": entry.name,
                        "type": "directory" if entry.is_dir() else "file",
                        "size": stat_info.st_size if entry.is_file() else None,
                        "modified": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                        "permissions": oct(stat_info.st_mode)[-3:]
                    })
                except (PermissionError, OSError):
                    entries.append({
                        "name": entry.name,
                        "type": "unknown",
                        "error": "Permission denied"
                    })

            # Sort: directories first, then files, alphabetically
            entries.sort(key=lambda x: (x["type"] != "directory", x["name"].lower()))

            return {
                "success": True,
                "path": expanded_path,
                "count": len(entries),
                "entries": entries
            }
        except PermissionError:
            return {
                "success": False,
                "error": f"Permission denied: {path}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error listing directory: {str(e)}"
            }

    async def _tool_move_file(
        self,
        source: str,
        destination: str
    ) -> Dict[str, Any]:
        """Move or rename a file or directory.

        Args:
            source: Source path.
            destination: Destination path.

        Returns:
            Result dictionary with success status.
        """
        try:
            source_path = os.path.expanduser(source)
            dest_path = os.path.expanduser(destination)

            # Validate both paths are safe
            if not is_path_safe(source_path):
                return {
                    "success": False,
                    "error": f"Source path is not within allowed directories. Allowed: {get_safe_directories_display()}"
                }

            if not is_path_safe(dest_path):
                return {
                    "success": False,
                    "error": f"Destination path is not within allowed directories. Allowed: {get_safe_directories_display()}"
                }

            if not os.path.exists(source_path):
                return {
                    "success": False,
                    "error": f"Source does not exist: {source}"
                }

            # Perform the move
            shutil.move(source_path, dest_path)

            return {
                "success": True,
                "message": f"Moved '{source}' to '{destination}'"
            }
        except PermissionError:
            return {
                "success": False,
                "error": "Permission denied"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error moving file: {str(e)}"
            }

    async def _tool_delete_file(
        self,
        path: str,
        confirmed: bool = False
    ) -> Dict[str, Any]:
        """Delete a file or directory.

        Args:
            path: Path to delete.
            confirmed: Must be True to proceed with deletion.

        Returns:
            Result dictionary with success status.
        """
        try:
            expanded_path = os.path.expanduser(path)

            # Safety check: require explicit confirmation
            if not confirmed:
                return {
                    "success": False,
                    "error": "Deletion requires confirmation. Set 'confirmed' to true to proceed.",
                    "requires_confirmation": True,
                    "path_to_delete": expanded_path
                }

            if not is_path_safe(expanded_path):
                return {
                    "success": False,
                    "error": f"Path is not within allowed directories. Allowed: {get_safe_directories_display()}"
                }

            if not os.path.exists(expanded_path):
                return {
                    "success": False,
                    "error": f"Path does not exist: {path}"
                }

            # Perform the deletion
            if os.path.isdir(expanded_path):
                shutil.rmtree(expanded_path)
                return {
                    "success": True,
                    "message": f"Deleted directory: {path}"
                }
            else:
                os.remove(expanded_path)
                return {
                    "success": True,
                    "message": f"Deleted file: {path}"
                }
        except PermissionError:
            return {
                "success": False,
                "error": "Permission denied"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error deleting: {str(e)}"
            }

    async def _tool_create_folder(self, path: str) -> Dict[str, Any]:
        """Create a new directory.

        Args:
            path: Path for the new directory.

        Returns:
            Result dictionary with success status.
        """
        try:
            expanded_path = os.path.expanduser(path)

            if not is_path_safe(expanded_path):
                return {
                    "success": False,
                    "error": f"Path is not within allowed directories. Allowed: {get_safe_directories_display()}"
                }

            if os.path.exists(expanded_path):
                return {
                    "success": False,
                    "error": f"Path already exists: {path}"
                }

            # Create the directory (including parents)
            os.makedirs(expanded_path, exist_ok=True)

            return {
                "success": True,
                "message": f"Created directory: {path}"
            }
        except PermissionError:
            return {
                "success": False,
                "error": "Permission denied"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error creating directory: {str(e)}"
            }

    # ============ SYSTEM UTILITIES ============

    async def _tool_take_screenshot(
        self,
        output_path: Optional[str] = None,
        capture_type: str = "fullscreen",
        delay_seconds: int = 0
    ) -> Dict[str, Any]:
        """Take a screenshot.

        Args:
            output_path: Where to save the screenshot.
            capture_type: Type of capture (fullscreen, selection, window).
            delay_seconds: Delay before capture.

        Returns:
            Result dictionary with success status and file path.
        """
        try:
            # Default to Desktop if no path specified
            if output_path is None:
                desktop = os.path.expanduser("~/Desktop")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = os.path.join(desktop, f"screenshot_{timestamp}.png")
            else:
                output_path = os.path.expanduser(output_path)

            # Validate output path
            if not is_path_safe(output_path):
                return {
                    "success": False,
                    "error": f"Output path is not within allowed directories. Allowed: {get_safe_directories_display()}"
                }

            # Ensure parent directory exists
            parent_dir = os.path.dirname(output_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)

            # Build screencapture command
            cmd = ["screencapture"]

            # Add capture type flags
            if capture_type == "selection":
                cmd.append("-i")  # Interactive selection
            elif capture_type == "window":
                cmd.append("-w")  # Window capture
            # fullscreen is the default (no flag needed)

            # Add delay if specified
            if delay_seconds > 0:
                delay_seconds = min(delay_seconds, 10)  # Cap at 10 seconds
                cmd.extend(["-T", str(delay_seconds)])

            cmd.append(output_path)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60  # Allow time for user interaction
            )

            if result.returncode == 0 and os.path.exists(output_path):
                return {
                    "success": True,
                    "message": f"Screenshot saved to: {output_path}",
                    "path": output_path
                }
            else:
                return {
                    "success": False,
                    "error": "Screenshot was cancelled or failed"
                }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Screenshot timed out"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error taking screenshot: {str(e)}"
            }

    async def _tool_get_clipboard(self) -> Dict[str, Any]:
        """Get the current clipboard contents.

        Returns:
            Result dictionary with clipboard contents.
        """
        try:
            result = subprocess.run(
                ["pbpaste"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                content = result.stdout
                return {
                    "success": True,
                    "content": content,
                    "length": len(content)
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to read clipboard"
                }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Timeout reading clipboard"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error reading clipboard: {str(e)}"
            }

    async def _tool_set_clipboard(self, text: str) -> Dict[str, Any]:
        """Set the clipboard contents.

        Args:
            text: Text to copy to clipboard.

        Returns:
            Result dictionary with success status.
        """
        try:
            result = subprocess.run(
                ["pbcopy"],
                input=text,
                text=True,
                capture_output=True,
                timeout=5
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "message": f"Copied {len(text)} characters to clipboard"
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to set clipboard"
                }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Timeout setting clipboard"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error setting clipboard: {str(e)}"
            }

    # ============ APPLESCRIPT ============

    async def _tool_run_applescript(
        self,
        script: str,
        confirmed: bool = False
    ) -> Dict[str, Any]:
        """Execute an AppleScript command.

        Args:
            script: The AppleScript code to execute.
            confirmed: Must be True to proceed.

        Returns:
            Result dictionary with execution result.
        """
        # Safety: always show the script for review if not confirmed
        if not confirmed:
            return {
                "success": False,
                "error": "AppleScript execution requires confirmation.",
                "requires_confirmation": True,
                "script_to_execute": script,
                "message": "Please review the script above and confirm execution."
            }

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "message": "AppleScript executed successfully",
                    "output": result.stdout.strip() if result.stdout else None
                }
            else:
                return {
                    "success": False,
                    "error": f"AppleScript error: {result.stderr.strip()}"
                }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "AppleScript execution timed out"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error executing AppleScript: {str(e)}"
            }


# Export the tool executor for easy use
def get_system_control_executor() -> SystemControlExecutor:
    """Get a new instance of the SystemControlExecutor.

    Returns:
        A new SystemControlExecutor instance.
    """
    return SystemControlExecutor()
