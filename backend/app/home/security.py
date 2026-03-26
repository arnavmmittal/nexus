"""Security camera management with snapshot capture and AI analysis."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Literal, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

CameraType = Literal["ring", "nest", "rtsp", "local_usb"]


@dataclass
class Camera:
    """A registered security camera."""

    camera_id: str
    name: str
    location: str
    stream_url: str  # RTSP or HTTP stream URL
    type: CameraType
    is_online: bool = True
    last_motion_at: Optional[str] = None  # ISO timestamp


@dataclass
class MotionEvent:
    """A detected motion event from a camera."""

    camera_id: str
    timestamp: str  # ISO timestamp
    snapshot_path: str
    confidence: float = 0.0
    description: str = ""


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class SecurityManager:
    """Manages security cameras, snapshots, and AI-powered analysis."""

    def __init__(
        self,
        data_path: Path | None = None,
        snapshots_dir: Path | None = None,
    ) -> None:
        self._data_path = data_path or Path("data/cameras.json")
        self._snapshots_dir = snapshots_dir or Path("data/snapshots")
        self._cameras: dict[str, Camera] = {}
        self._motion_events: list[MotionEvent] = []
        self._motion_callbacks: list[Callable] = []
        self._monitoring_tasks: dict[str, asyncio.Task] = {}
        self._load()

    # -- persistence --------------------------------------------------------

    def _load(self) -> None:
        if self._data_path.exists():
            raw = json.loads(self._data_path.read_text())
            for entry in raw.get("cameras", []):
                cam = Camera(**entry)
                self._cameras[cam.camera_id] = cam
            for entry in raw.get("motion_events", []):
                self._motion_events.append(MotionEvent(**entry))

    def _save(self) -> None:
        self._data_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "cameras": [asdict(c) for c in self._cameras.values()],
            "motion_events": [asdict(e) for e in self._motion_events[-500:]],
        }
        self._data_path.write_text(json.dumps(payload, indent=2, default=str))

    # -- camera CRUD --------------------------------------------------------

    async def register_camera(
        self,
        name: str,
        location: str,
        stream_url: str,
        type: CameraType,
    ) -> Camera:
        camera_id = uuid.uuid4().hex[:12]
        camera = Camera(
            camera_id=camera_id,
            name=name,
            location=location,
            stream_url=stream_url,
            type=type,
        )
        self._cameras[camera_id] = camera
        self._save()
        logger.info("Camera registered: %s (%s) at %s", name, type, location)
        return camera

    async def remove_camera(self, camera_id: str) -> bool:
        if camera_id in self._cameras:
            # Stop monitoring if active
            if camera_id in self._monitoring_tasks:
                self._monitoring_tasks[camera_id].cancel()
                del self._monitoring_tasks[camera_id]
            del self._cameras[camera_id]
            self._save()
            return True
        return False

    async def list_cameras(self) -> list[Camera]:
        return list(self._cameras.values())

    def get_camera(self, camera_id: str) -> Camera | None:
        return self._cameras.get(camera_id)

    # -- snapshot -----------------------------------------------------------

    async def capture_snapshot(self, camera_id: str) -> str:
        """Grab a single frame from the camera stream using ffmpeg.

        Returns the path to the saved snapshot image.
        """
        camera = self._cameras.get(camera_id)
        if not camera:
            raise ValueError(f"Camera {camera_id} not found")

        self._snapshots_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{camera_id}_{ts}.jpg"
        output_path = self._snapshots_dir / filename

        # Build ffmpeg command based on camera type
        if camera.type == "local_usb":
            # Local USB / webcam via avfoundation (macOS) or v4l2 (Linux)
            cmd = [
                "ffmpeg", "-y",
                "-f", "avfoundation",
                "-framerate", "1",
                "-i", camera.stream_url,
                "-frames:v", "1",
                "-q:v", "2",
                str(output_path),
            ]
        else:
            # RTSP / HTTP stream
            cmd = [
                "ffmpeg", "-y",
                "-rtsp_transport", "tcp",
                "-i", camera.stream_url,
                "-frames:v", "1",
                "-q:v", "2",
                str(output_path),
            ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)

            if proc.returncode != 0:
                error_msg = stderr.decode(errors="replace")[-500:]
                logger.error("ffmpeg snapshot failed for %s: %s", camera_id, error_msg)
                camera.is_online = False
                self._save()
                raise RuntimeError(f"ffmpeg failed (exit {proc.returncode}): {error_msg}")

            camera.is_online = True
            self._save()
            logger.info("Snapshot captured: %s", output_path)
            return str(output_path)

        except asyncio.TimeoutError:
            logger.error("ffmpeg timed out for camera %s", camera_id)
            camera.is_online = False
            self._save()
            raise RuntimeError(f"Snapshot timed out for camera {camera_id}")

    # -- AI analysis --------------------------------------------------------

    async def analyze_snapshot(self, camera_id: str) -> dict:
        """Capture a snapshot and analyze it with Claude Vision API.

        Returns a dict with keys: description, people_detected, anomalies, raw_response.
        """
        snapshot_path = await self.capture_snapshot(camera_id)

        # Read and encode image
        image_data = Path(snapshot_path).read_bytes()
        b64_image = base64.b64encode(image_data).decode("utf-8")

        camera = self._cameras[camera_id]
        prompt = (
            f"You are a security camera AI assistant analyzing a frame from "
            f"camera '{camera.name}' located at '{camera.location}'.\n\n"
            f"Analyze this image and provide:\n"
            f"1. A brief description of what you see\n"
            f"2. Number of people visible and their descriptions\n"
            f"3. Any anomalies or security concerns (unknown persons, packages, open doors/windows, etc.)\n"
            f"4. Whether this appears to be normal activity\n\n"
            f"Respond in JSON format with keys: description, people_count, people_descriptions, "
            f"anomalies, is_normal, confidence (0-1)."
        )

        api_key = settings.anthropic_api_key
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 1024,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/jpeg",
                                        "data": b64_image,
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": prompt,
                                },
                            ],
                        }
                    ],
                },
            )
            resp.raise_for_status()
            result = resp.json()

        raw_text = result["content"][0]["text"]

        # Try to parse JSON from the response
        analysis = {"raw_response": raw_text, "snapshot_path": snapshot_path}
        try:
            # Claude may wrap JSON in markdown code fences
            cleaned = raw_text.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            parsed = json.loads(cleaned)
            analysis.update(parsed)
        except (json.JSONDecodeError, IndexError):
            analysis["description"] = raw_text
            analysis["parse_error"] = True

        logger.info("Snapshot analyzed for camera %s", camera_id)
        return analysis

    # -- motion events ------------------------------------------------------

    async def get_recent_motion(
        self, camera_id: str, hours: int = 24
    ) -> list[MotionEvent]:
        cutoff = datetime.now() - timedelta(hours=hours)
        cutoff_str = cutoff.isoformat()
        return [
            e
            for e in self._motion_events
            if e.camera_id == camera_id and e.timestamp >= cutoff_str
        ]

    async def _record_motion(
        self, camera_id: str, snapshot_path: str, confidence: float = 0.0, description: str = ""
    ) -> MotionEvent:
        event = MotionEvent(
            camera_id=camera_id,
            timestamp=datetime.now().isoformat(),
            snapshot_path=snapshot_path,
            confidence=confidence,
            description=description,
        )
        self._motion_events.append(event)

        # Update camera last_motion_at
        camera = self._cameras.get(camera_id)
        if camera:
            camera.last_motion_at = event.timestamp

        self._save()

        # Fire callbacks
        for cb in self._motion_callbacks:
            try:
                await cb(event)
            except Exception:
                logger.exception("Motion callback failed for camera %s", camera_id)

        return event

    # -- motion monitoring --------------------------------------------------

    async def start_motion_monitoring(
        self, camera_id: str, interval_seconds: int = 5
    ) -> bool:
        """Start polling a camera for motion by comparing consecutive frames.

        Uses ffmpeg to capture frames at an interval and compares file sizes
        as a lightweight motion heuristic (significant size change = motion).
        """
        camera = self._cameras.get(camera_id)
        if not camera:
            raise ValueError(f"Camera {camera_id} not found")

        if camera_id in self._monitoring_tasks:
            return False  # Already monitoring

        async def _monitor_loop():
            last_size: int | None = None
            while True:
                try:
                    snapshot_path = await self.capture_snapshot(camera_id)
                    current_size = Path(snapshot_path).stat().st_size

                    if last_size is not None:
                        size_diff = abs(current_size - last_size) / max(last_size, 1)
                        # >15% size change suggests motion
                        if size_diff > 0.15:
                            confidence = min(size_diff, 1.0)
                            await self._record_motion(
                                camera_id=camera_id,
                                snapshot_path=snapshot_path,
                                confidence=confidence,
                                description=f"Motion detected (frame delta: {size_diff:.1%})",
                            )
                            logger.info(
                                "Motion detected on %s (delta=%.1f%%)",
                                camera_id, size_diff * 100,
                            )

                    last_size = current_size
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("Motion monitor error for %s", camera_id)

                await asyncio.sleep(interval_seconds)

        task = asyncio.create_task(_monitor_loop())
        self._monitoring_tasks[camera_id] = task
        logger.info("Motion monitoring started for camera %s", camera_id)
        return True

    async def stop_motion_monitoring(self, camera_id: str) -> bool:
        task = self._monitoring_tasks.pop(camera_id, None)
        if task:
            task.cancel()
            logger.info("Motion monitoring stopped for camera %s", camera_id)
            return True
        return False

    # -- callbacks ----------------------------------------------------------

    def register_motion_callback(self, callback: Callable) -> None:
        """Register an async callback that fires on motion events.

        Useful for integrating with presence system or notifications.
        """
        self._motion_callbacks.append(callback)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_security_manager: SecurityManager | None = None


def get_security_manager() -> SecurityManager:
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager
