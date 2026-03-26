"""FastAPI routes for security camera management and AI analysis."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.home.security import (
    SecurityManager,
    get_security_manager,
)

router = APIRouter(tags=["security"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class CameraCreate(BaseModel):
    name: str
    location: str
    stream_url: str
    type: Literal["ring", "nest", "rtsp", "local_usb"]


class CameraResponse(BaseModel):
    camera_id: str
    name: str
    location: str
    stream_url: str
    type: str
    is_online: bool
    last_motion_at: Optional[str] = None


class SnapshotResponse(BaseModel):
    camera_id: str
    snapshot_path: str


class AnalysisResponse(BaseModel):
    camera_id: str
    snapshot_path: str
    analysis: dict


class MotionEventResponse(BaseModel):
    camera_id: str
    timestamp: str
    snapshot_path: str
    confidence: float
    description: str


class StreamRequest(BaseModel):
    interval_seconds: int = 5


class StreamResponse(BaseModel):
    camera_id: str
    monitoring: bool
    message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cam_response(cam) -> CameraResponse:
    return CameraResponse(
        camera_id=cam.camera_id,
        name=cam.name,
        location=cam.location,
        stream_url=cam.stream_url,
        type=cam.type,
        is_online=cam.is_online,
        last_motion_at=cam.last_motion_at,
    )


def _get_camera_or_404(mgr: SecurityManager, camera_id: str):
    cam = mgr.get_camera(camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    return cam


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/cameras", response_model=list[CameraResponse])
async def list_cameras():
    """List all registered security cameras."""
    mgr = get_security_manager()
    cameras = await mgr.list_cameras()
    return [_cam_response(c) for c in cameras]


@router.post("/cameras", response_model=CameraResponse, status_code=201)
async def register_camera(data: CameraCreate):
    """Register a new security camera."""
    mgr = get_security_manager()
    cam = await mgr.register_camera(
        name=data.name,
        location=data.location,
        stream_url=data.stream_url,
        type=data.type,
    )
    return _cam_response(cam)


@router.delete("/cameras/{camera_id}", status_code=204)
async def remove_camera(camera_id: str):
    """Remove a registered camera."""
    mgr = get_security_manager()
    removed = await mgr.remove_camera(camera_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Camera not found")


@router.get("/cameras/{camera_id}/snapshot", response_model=SnapshotResponse)
async def capture_snapshot(camera_id: str):
    """Capture a snapshot from the camera."""
    mgr = get_security_manager()
    _get_camera_or_404(mgr, camera_id)
    try:
        path = await mgr.capture_snapshot(camera_id)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return SnapshotResponse(camera_id=camera_id, snapshot_path=path)


@router.post("/cameras/{camera_id}/analyze", response_model=AnalysisResponse)
async def analyze_snapshot(camera_id: str):
    """Capture a snapshot and analyze it with Claude Vision (\"Who's at the door?\")."""
    mgr = get_security_manager()
    _get_camera_or_404(mgr, camera_id)
    try:
        analysis = await mgr.analyze_snapshot(camera_id)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return AnalysisResponse(
        camera_id=camera_id,
        snapshot_path=analysis.get("snapshot_path", ""),
        analysis=analysis,
    )


@router.get("/cameras/{camera_id}/motion", response_model=list[MotionEventResponse])
async def get_recent_motion(camera_id: str, hours: int = 24):
    """Get recent motion events for a camera."""
    mgr = get_security_manager()
    _get_camera_or_404(mgr, camera_id)
    events = await mgr.get_recent_motion(camera_id, hours=hours)
    return [
        MotionEventResponse(
            camera_id=e.camera_id,
            timestamp=e.timestamp,
            snapshot_path=e.snapshot_path,
            confidence=e.confidence,
            description=e.description,
        )
        for e in events
    ]


@router.post("/cameras/{camera_id}/stream", response_model=StreamResponse)
async def start_motion_monitoring(camera_id: str, data: StreamRequest | None = None):
    """Start motion detection monitoring on a camera."""
    mgr = get_security_manager()
    _get_camera_or_404(mgr, camera_id)
    interval = data.interval_seconds if data else 5
    try:
        started = await mgr.start_motion_monitoring(camera_id, interval_seconds=interval)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if not started:
        return StreamResponse(
            camera_id=camera_id,
            monitoring=True,
            message="Already monitoring this camera",
        )
    return StreamResponse(
        camera_id=camera_id,
        monitoring=True,
        message=f"Motion monitoring started (interval={interval}s)",
    )
