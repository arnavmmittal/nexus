#!/usr/bin/env python3
"""
Nexus Home Terminal - Health Monitor
=====================================

Monitors system health on the Raspberry Pi hardware terminal and reports
metrics to the Nexus backend. Also handles:
  - Auto-restarting Chromium if it crashes
  - Display dimming / blanking based on time of day
  - Log rotation

Runs as a systemd service (nexus-health.service).
"""

import json
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore[assignment]

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NEXUS_API_URL = os.environ.get("NEXUS_API_URL", "http://localhost:3001")
HEALTH_ENDPOINT = f"{NEXUS_API_URL}/api/health/terminal"
CHECK_INTERVAL = 30  # seconds between health checks
CHROMIUM_RESTART_COOLDOWN = 60  # minimum seconds between Chromium restarts

DISPLAY_ON_HOUR = int(os.environ.get("DISPLAY_ON_HOUR", "6"))
DISPLAY_OFF_HOUR = int(os.environ.get("DISPLAY_OFF_HOUR", "23"))

LOG_FILE = "/var/log/nexus-health-monitor.log"
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
LOG_BACKUP_COUNT = 3

# Thresholds
CPU_TEMP_WARNING = 70.0   # Celsius
CPU_TEMP_CRITICAL = 80.0
MEMORY_WARNING = 85.0     # Percent
DISK_WARNING = 90.0       # Percent

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("nexus-health")
logger.setLevel(logging.INFO)

# Console handler
_ch = logging.StreamHandler(sys.stdout)
_ch.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", "%H:%M:%S"))
logger.addHandler(_ch)

# Rotating file handler
try:
    Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
    _fh = RotatingFileHandler(LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT)
    _fh.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s"))
    logger.addHandler(_fh)
except PermissionError:
    logger.warning("Cannot write to %s, file logging disabled.", LOG_FILE)

# ---------------------------------------------------------------------------
# System Health Collectors
# ---------------------------------------------------------------------------


def get_cpu_temp() -> float | None:
    """Read CPU temperature from thermal zone or vcgencmd."""
    # Method 1: thermal zone (standard on Pi 5)
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return int(f.read().strip()) / 1000.0
    except (FileNotFoundError, ValueError):
        pass

    # Method 2: vcgencmd
    try:
        result = subprocess.run(
            ["vcgencmd", "measure_temp"],
            capture_output=True, text=True, timeout=5,
        )
        # Output: temp=42.8'C
        temp_str = result.stdout.strip().replace("temp=", "").replace("'C", "")
        return float(temp_str)
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass

    return None


def get_memory_usage() -> dict:
    """Return memory stats as a dict."""
    if psutil:
        mem = psutil.virtual_memory()
        return {
            "total_mb": round(mem.total / (1024 * 1024)),
            "used_mb": round(mem.used / (1024 * 1024)),
            "percent": mem.percent,
        }

    # Fallback: parse /proc/meminfo
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if parts[0] in ("MemTotal:", "MemAvailable:", "MemFree:"):
                    info[parts[0].rstrip(":")] = int(parts[1])  # kB

        total = info.get("MemTotal", 0)
        available = info.get("MemAvailable", info.get("MemFree", 0))
        used = total - available
        pct = (used / total * 100) if total > 0 else 0
        return {
            "total_mb": round(total / 1024),
            "used_mb": round(used / 1024),
            "percent": round(pct, 1),
        }
    except Exception:
        return {"total_mb": 0, "used_mb": 0, "percent": 0}


def get_disk_usage() -> dict:
    """Return root partition disk stats."""
    if psutil:
        disk = psutil.disk_usage("/")
        return {
            "total_gb": round(disk.total / (1024 ** 3), 1),
            "used_gb": round(disk.used / (1024 ** 3), 1),
            "percent": disk.percent,
        }

    try:
        result = subprocess.run(
            ["df", "-B1", "/"],
            capture_output=True, text=True, timeout=5,
        )
        lines = result.stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            total = int(parts[1])
            used = int(parts[2])
            pct = float(parts[4].rstrip("%"))
            return {
                "total_gb": round(total / (1024 ** 3), 1),
                "used_gb": round(used / (1024 ** 3), 1),
                "percent": pct,
            }
    except Exception:
        pass

    return {"total_gb": 0, "used_gb": 0, "percent": 0}


def get_network_status() -> dict:
    """Check network connectivity."""
    connected = False
    latency_ms = None

    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "3", "8.8.8.8"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            connected = True
            # Extract latency from ping output
            for line in result.stdout.split("\n"):
                if "time=" in line:
                    time_part = line.split("time=")[1].split()[0]
                    latency_ms = float(time_part)
                    break
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Get WiFi signal strength
    signal_dbm = None
    try:
        result = subprocess.run(
            ["iwconfig", "wlan0"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.split("\n"):
            if "Signal level" in line:
                parts = line.split("Signal level=")
                if len(parts) > 1:
                    signal_dbm = int(parts[1].split()[0].replace("dBm", ""))
                    break
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass

    return {
        "connected": connected,
        "latency_ms": latency_ms,
        "wifi_signal_dbm": signal_dbm,
    }


def get_display_status() -> dict:
    """Check if the display is currently on."""
    display_on = True
    try:
        result = subprocess.run(
            ["xset", "-q"],
            capture_output=True, text=True, timeout=5,
            env={**os.environ, "DISPLAY": ":0"},
        )
        if "Monitor is Off" in result.stdout:
            display_on = False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return {"display_on": display_on}


def is_chromium_running() -> bool:
    """Check if Chromium is running."""
    if psutil:
        for proc in psutil.process_iter(["name"]):
            if "chromium" in (proc.info.get("name") or "").lower():
                return True
        return False

    try:
        result = subprocess.run(
            ["pgrep", "-x", "chromium-browser"],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


def restart_chromium() -> None:
    """Restart the Chromium kiosk via its systemd service."""
    logger.warning("Chromium not running. Restarting nexus-kiosk.service...")
    try:
        subprocess.run(
            ["systemctl", "restart", "nexus-kiosk.service"],
            capture_output=True, timeout=15,
        )
        logger.info("nexus-kiosk.service restart requested.")
    except subprocess.TimeoutExpired:
        logger.error("Timed out restarting nexus-kiosk.service.")


def manage_display_schedule() -> None:
    """Turn display on/off based on time of day."""
    hour = datetime.now().hour
    should_be_on = DISPLAY_ON_HOUR <= hour < DISPLAY_OFF_HOUR

    env = {**os.environ, "DISPLAY": ":0"}

    try:
        if should_be_on:
            subprocess.run(["xset", "dpms", "force", "on"], env=env,
                           capture_output=True, timeout=5)
        else:
            subprocess.run(["xset", "dpms", "force", "off"], env=env,
                           capture_output=True, timeout=5)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


def send_health_report(data: dict) -> None:
    """POST health data to the Nexus backend."""
    if requests is None:
        return

    try:
        resp = requests.post(
            HEALTH_ENDPOINT,
            json=data,
            timeout=10,
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code >= 400:
            logger.warning("Health report rejected: %s %s", resp.status_code, resp.text[:200])
    except requests.RequestException as e:
        logger.debug("Could not send health report: %s", e)


# ---------------------------------------------------------------------------
# Main Loop
# ---------------------------------------------------------------------------

_running = True
_last_chromium_restart = 0.0


def _handle_signal(signum, frame):
    global _running
    logger.info("Received signal %s, stopping...", signum)
    _running = False


def collect_health() -> dict:
    """Gather all health metrics into a single dict."""
    cpu_temp = get_cpu_temp()
    memory = get_memory_usage()
    disk = get_disk_usage()
    network = get_network_status()
    display = get_display_status()
    chromium_running = is_chromium_running()

    # Determine overall status
    status = "healthy"
    issues = []

    if cpu_temp is not None:
        if cpu_temp >= CPU_TEMP_CRITICAL:
            status = "critical"
            issues.append(f"CPU temp critical: {cpu_temp:.1f}C")
        elif cpu_temp >= CPU_TEMP_WARNING:
            status = "warning"
            issues.append(f"CPU temp high: {cpu_temp:.1f}C")

    if memory["percent"] >= MEMORY_WARNING:
        if status != "critical":
            status = "warning"
        issues.append(f"Memory usage high: {memory['percent']}%")

    if disk["percent"] >= DISK_WARNING:
        if status != "critical":
            status = "warning"
        issues.append(f"Disk usage high: {disk['percent']}%")

    if not network["connected"]:
        status = "critical"
        issues.append("Network disconnected")

    if not chromium_running:
        if status != "critical":
            status = "warning"
        issues.append("Chromium not running")

    return {
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "issues": issues,
        "cpu_temp_c": cpu_temp,
        "memory": memory,
        "disk": disk,
        "network": network,
        "display": display,
        "chromium_running": chromium_running,
    }


def main() -> None:
    global _last_chromium_restart

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info("Nexus Health Monitor starting...")
    logger.info("API endpoint: %s", HEALTH_ENDPOINT)
    logger.info("Check interval: %ds", CHECK_INTERVAL)
    logger.info("Display schedule: %02d:00 - %02d:00", DISPLAY_ON_HOUR, DISPLAY_OFF_HOUR)

    while _running:
        try:
            health = collect_health()

            # Log summary
            temp_str = f"{health['cpu_temp_c']:.1f}C" if health["cpu_temp_c"] else "N/A"
            logger.info(
                "Status=%s | CPU=%s | Mem=%s%% | Disk=%s%% | Net=%s | Chromium=%s",
                health["status"],
                temp_str,
                health["memory"]["percent"],
                health["disk"]["percent"],
                "OK" if health["network"]["connected"] else "DOWN",
                "OK" if health["chromium_running"] else "DOWN",
            )

            if health["issues"]:
                for issue in health["issues"]:
                    logger.warning("  Issue: %s", issue)

            # Auto-restart Chromium if crashed
            if not health["chromium_running"]:
                now = time.time()
                if now - _last_chromium_restart > CHROMIUM_RESTART_COOLDOWN:
                    restart_chromium()
                    _last_chromium_restart = now
                else:
                    logger.info(
                        "Chromium down but cooldown active (%ds remaining).",
                        int(CHROMIUM_RESTART_COOLDOWN - (now - _last_chromium_restart)),
                    )

            # Manage display schedule
            manage_display_schedule()

            # Send report to backend
            send_health_report(health)

        except Exception:
            logger.exception("Unexpected error in health check loop")

        # Sleep in small increments so we can respond to signals promptly
        for _ in range(CHECK_INTERVAL):
            if not _running:
                break
            time.sleep(1)

    logger.info("Health monitor stopped.")


if __name__ == "__main__":
    main()
