"""
macOS LaunchAgent Auto-start Configuration.

Provides functionality to install/uninstall a macOS LaunchAgent
that automatically starts the Nexus backend on system boot.

Usage:
    python -m app.core.autostart install     # Install LaunchAgent
    python -m app.core.autostart uninstall   # Remove LaunchAgent
    python -m app.core.autostart status      # Check status
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

# LaunchAgent configuration
LAUNCH_AGENT_LABEL = "com.nexus.backend"
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
PLIST_PATH = LAUNCH_AGENTS_DIR / f"{LAUNCH_AGENT_LABEL}.plist"
LOG_DIR = Path.home() / "Library" / "Logs"
LOG_FILE = LOG_DIR / "nexus-backend.log"
ERROR_LOG_FILE = LOG_DIR / "nexus-backend-error.log"


def get_python_path() -> str:
    """Get the path to the current Python interpreter."""
    return sys.executable


def get_backend_dir() -> Path:
    """Get the path to the backend directory."""
    # This file is at app/core/autostart.py, so go up 2 levels
    return Path(__file__).parent.parent.parent.resolve()


def generate_plist_content(
    python_path: Optional[str] = None,
    backend_dir: Optional[Path] = None,
    port: int = 8000,
    host: str = "0.0.0.0",
) -> str:
    """
    Generate the LaunchAgent plist XML content.

    Args:
        python_path: Path to Python interpreter
        backend_dir: Path to backend directory
        port: Port to run server on
        host: Host to bind to

    Returns:
        Plist XML content as string
    """
    python_path = python_path or get_python_path()
    backend_dir = backend_dir or get_backend_dir()

    # Ensure log directory exists
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{LAUNCH_AGENT_LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>-m</string>
        <string>uvicorn</string>
        <string>app.main:app</string>
        <string>--host</string>
        <string>{host}</string>
        <string>--port</string>
        <string>{port}</string>
    </array>

    <key>WorkingDirectory</key>
    <string>{backend_dir}</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>{os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")}</string>
        <key>PYTHONPATH</key>
        <string>{backend_dir}</string>
    </dict>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
        <key>Crashed</key>
        <true/>
    </dict>

    <key>ThrottleInterval</key>
    <integer>10</integer>

    <key>StandardOutPath</key>
    <string>{LOG_FILE}</string>

    <key>StandardErrorPath</key>
    <string>{ERROR_LOG_FILE}</string>

    <key>ProcessType</key>
    <string>Background</string>
</dict>
</plist>
"""


def install_launch_agent(
    port: int = 8000,
    host: str = "0.0.0.0",
    start_now: bool = True,
) -> bool:
    """
    Install the macOS LaunchAgent for Nexus backend.

    Args:
        port: Port to run server on
        host: Host to bind to
        start_now: Whether to start the service immediately

    Returns:
        True if successful, False otherwise
    """
    print(f"Installing Nexus LaunchAgent...")

    # Ensure LaunchAgents directory exists
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)

    # Generate plist content
    plist_content = generate_plist_content(port=port, host=host)

    # Unload existing agent if present
    if PLIST_PATH.exists():
        print("Unloading existing LaunchAgent...")
        subprocess.run(
            ["launchctl", "unload", str(PLIST_PATH)],
            capture_output=True,
        )

    # Write plist file
    try:
        PLIST_PATH.write_text(plist_content)
        print(f"Created plist at: {PLIST_PATH}")
    except Exception as e:
        print(f"Error writing plist: {e}")
        return False

    # Load the agent
    if start_now:
        print("Loading LaunchAgent...")
        result = subprocess.run(
            ["launchctl", "load", str(PLIST_PATH)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"Warning: Failed to load agent: {result.stderr}")
        else:
            print("LaunchAgent loaded successfully!")

    print(f"""
Nexus Backend LaunchAgent installed!

Configuration:
  - Label: {LAUNCH_AGENT_LABEL}
  - Plist: {PLIST_PATH}
  - Log file: {LOG_FILE}
  - Error log: {ERROR_LOG_FILE}
  - Port: {port}
  - Host: {host}

The backend will automatically start on login and restart on crash.

Commands:
  - Stop:    launchctl unload {PLIST_PATH}
  - Start:   launchctl load {PLIST_PATH}
  - Status:  launchctl list | grep nexus
  - Logs:    tail -f {LOG_FILE}
""")

    return True


def uninstall_launch_agent() -> bool:
    """
    Uninstall the macOS LaunchAgent.

    Returns:
        True if successful, False otherwise
    """
    print(f"Uninstalling Nexus LaunchAgent...")

    if not PLIST_PATH.exists():
        print("LaunchAgent not installed.")
        return True

    # Unload the agent
    print("Unloading LaunchAgent...")
    result = subprocess.run(
        ["launchctl", "unload", str(PLIST_PATH)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"Warning: Failed to unload agent: {result.stderr}")

    # Remove plist file
    try:
        PLIST_PATH.unlink()
        print(f"Removed plist: {PLIST_PATH}")
    except Exception as e:
        print(f"Error removing plist: {e}")
        return False

    print("LaunchAgent uninstalled successfully!")
    return True


def check_status() -> dict:
    """
    Check the status of the LaunchAgent.

    Returns:
        Dictionary with status information
    """
    status = {
        "installed": PLIST_PATH.exists(),
        "plist_path": str(PLIST_PATH),
        "log_file": str(LOG_FILE),
        "error_log": str(ERROR_LOG_FILE),
        "running": False,
        "pid": None,
    }

    if status["installed"]:
        # Check if running
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True,
            text=True,
        )

        for line in result.stdout.split("\n"):
            if LAUNCH_AGENT_LABEL in line:
                parts = line.split()
                if len(parts) >= 3:
                    pid = parts[0]
                    if pid != "-":
                        status["running"] = True
                        status["pid"] = int(pid)
                break

    return status


def print_status():
    """Print the current status of the LaunchAgent."""
    status = check_status()

    print(f"Nexus Backend LaunchAgent Status:")
    print(f"  Installed: {'Yes' if status['installed'] else 'No'}")

    if status["installed"]:
        print(f"  Plist: {status['plist_path']}")
        print(f"  Running: {'Yes' if status['running'] else 'No'}")
        if status["running"]:
            print(f"  PID: {status['pid']}")
        print(f"  Log file: {status['log_file']}")
        print(f"  Error log: {status['error_log']}")

        # Check if log file exists and show recent logs
        if Path(status["log_file"]).exists():
            print(f"\nRecent logs (last 5 lines):")
            result = subprocess.run(
                ["tail", "-5", status["log_file"]],
                capture_output=True,
                text=True,
            )
            for line in result.stdout.strip().split("\n"):
                print(f"    {line}")


def main():
    """Main entry point for CLI usage."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Manage Nexus Backend macOS LaunchAgent"
    )
    parser.add_argument(
        "action",
        choices=["install", "uninstall", "status"],
        help="Action to perform",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for the backend server (default: 8000)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host for the backend server (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--no-start",
        action="store_true",
        help="Don't start the service after installing",
    )

    args = parser.parse_args()

    if args.action == "install":
        success = install_launch_agent(
            port=args.port,
            host=args.host,
            start_now=not args.no_start,
        )
        sys.exit(0 if success else 1)

    elif args.action == "uninstall":
        success = uninstall_launch_agent()
        sys.exit(0 if success else 1)

    elif args.action == "status":
        print_status()
        status = check_status()
        sys.exit(0 if status["installed"] else 1)


if __name__ == "__main__":
    main()
