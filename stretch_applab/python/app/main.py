from __future__ import annotations

import asyncio
import base64
import binascii
import io
import logging
import os
import re
import threading
import time
import uuid
import zipfile
from typing import Any

import cv2
import numpy as np
from fastapi import FastAPI, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.hardware_bridge import hardware_bridge
from app import inference
from app.nano_ble import nano_ble_manager
from app.session_manager import SessionManager
from app.source_manager import SourceManager
from app.utils import PROJECT_ROOT, build_base_url, log_startup_details, make_qr_png_bytes, setup_logging

setup_logging()

logger = logging.getLogger(__name__)
app = FastAPI(title="YUEDMAI Local Kiosk")
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "app" / "templates"))
app.mount("/static", StaticFiles(directory=str(PROJECT_ROOT / "app" / "static")), name="static")

source_manager = SourceManager.from_environment()
session_manager = SessionManager()
BASE_URL = build_base_url()
PHONE_URL = f"{BASE_URL}/phone"


class CaptureStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._session_id = self._new_id()
        self._captures: dict[int, dict[str, Any]] = {}

    def _new_id(self) -> str:
        return uuid.uuid4().hex[:12]

    def reset(self) -> dict[str, Any]:
        with self._lock:
            self._session_id = self._new_id()
            self._captures = {}
            return self._status_locked()

    def status(self, base_url: str | None = None) -> dict[str, Any]:
        with self._lock:
            return self._status_locked(base_url)

    def _status_locked(self, base_url: str | None = None) -> dict[str, Any]:
        share_path = f"/summary/{self._session_id}"
        share_url = f"{base_url}{share_path}" if base_url else share_path
        return {
            "session_id": self._session_id,
            "count": len(self._captures),
            "share_url": share_url,
            "qr_url": f"/summary_qr/{self._session_id}.png",
            "download_url": f"{share_path}/download.zip",
        }

    def upsert(self, payload: dict[str, Any], base_url: str | None = None) -> dict[str, Any]:
        image = str(payload.get("image") or "")
        match = re.match(r"^data:image/(jpeg|jpg|png|webp);base64,(.+)$", image, re.DOTALL)
        if not match:
            raise ValueError("Capture image must be a base64 data URL")

        try:
            raw = base64.b64decode(match.group(2), validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError("Capture image is not valid base64") from error

        if len(raw) > 6 * 1024 * 1024:
            raise ValueError("Capture image is too large")

        try:
            index = max(0, int(payload.get("index", 0)))
        except (TypeError, ValueError):
            index = 0

        name = str(payload.get("name") or f"Stretch {index + 1}")[:80]
        try:
            score = max(0, int(float(payload.get("score", 0))))
        except (TypeError, ValueError):
            score = 0

        ext = "jpg" if match.group(1) == "jpeg" else match.group(1)
        with self._lock:
            self._captures[index] = {
                "index": index,
                "name": name,
                "score": score,
                "ext": ext,
                "content_type": f"image/{'jpeg' if ext == 'jpg' else ext}",
                "bytes": raw,
                "captured_at": time.time(),
            }
            return self._status_locked(base_url)

    def captures(self, session_id: str) -> list[dict[str, Any]]:
        with self._lock:
            if session_id != self._session_id:
                return []
            return [dict(item) for _, item in sorted(self._captures.items())]

    def get_capture(self, session_id: str, index: int) -> dict[str, Any] | None:
        with self._lock:
            if session_id != self._session_id:
                return None
            item = self._captures.get(index)
            return dict(item) if item else None


capture_store = CaptureStore()


@app.on_event("startup")
async def startup() -> None:
    log_startup_details(source_manager.force_mode, BASE_URL)
    logger.info("QR URL generated: %s", PHONE_URL)
    hardware_bridge.start()
    nano_ble_manager.start(hardware_bridge)
    source_manager.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    await nano_ble_manager.stop()
    source_manager.stop()
    logger.info("YUEDMAI app shutdown")


@app.get("/", response_class=HTMLResponse)
async def landing(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "landing.html",
        {"status": full_status(), "phone_url": PHONE_URL},
    )


@app.get("/setup", response_class=HTMLResponse)
async def setup_page(
    request: Request,
    mode: str = Query("before"),
    body_focus: str = Query("full"),
    duration: int = Query(5),
) -> HTMLResponse:
    capture_store.reset()
    session_manager.configure(mode=mode, body_focus=body_focus, duration=duration)
    return templates.TemplateResponse(
        request,
        "setup.html",
        {"status": full_status(), "phone_url": PHONE_URL},
    )


@app.get("/session", response_class=HTMLResponse)
async def session_page(
    request: Request,
    mode: str | None = None,
    body_focus: str | None = None,
    duration: int | None = None,
    debug: int = Query(0),
) -> HTMLResponse:
    if mode or body_focus or duration:
        capture_store.reset()
        session_manager.configure(mode=mode, body_focus=body_focus, duration=duration)
    return templates.TemplateResponse(
        request,
        "session.html",
        {"status": full_status(), "debug": bool(debug), "phone_url": PHONE_URL},
    )


@app.get("/phone", response_class=HTMLResponse)
async def phone_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "phone.html",
        {"target_fps": 10, "jpeg_quality": 0.65},
    )


@app.websocket("/ws/phone-frame")
async def phone_frame_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    client = websocket.client
    client_id = f"{client.host}:{client.port}" if client else "unknown-phone"
    source_manager.phone.mark_connected(client_id)
    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            payload = message.get("bytes")
            if payload:
                source_manager.phone.receive_jpeg(payload, client_id)
    except WebSocketDisconnect:
        logger.info("Phone WebSocket disconnected: %s", client_id)
    except Exception:
        logger.exception("Phone WebSocket error for %s", client_id)
    finally:
        source_manager.phone.mark_disconnected(client_id)


@app.websocket("/ws/hardware")
async def hardware_socket(websocket: WebSocket) -> None:
    await hardware_bridge.connect(websocket)


@app.get("/video_feed")
async def video_feed(overlay: bool = Query(True)) -> StreamingResponse:
    return StreamingResponse(mjpeg_generator(draw_overlay=overlay), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/qr.png")
async def qr_png() -> Response:
    return Response(content=make_qr_png_bytes(PHONE_URL), media_type="image/png")


@app.get("/summary_qr/{session_id}.png")
async def summary_qr_png(session_id: str) -> Response:
    return Response(content=make_qr_png_bytes(f"{BASE_URL}/summary/{session_id}"), media_type="image/png")


@app.get("/summary/{session_id}", response_class=HTMLResponse)
async def capture_summary_page(request: Request, session_id: str) -> HTMLResponse:
    captures = capture_store.captures(session_id)
    return templates.TemplateResponse(
        request,
        "captures.html",
        {
            "captures": captures,
            "session_id": session_id,
            "download_url": f"/summary/{session_id}/download.zip",
            "share_url": f"{BASE_URL}/summary/{session_id}",
        },
    )


@app.get("/summary/{session_id}/image/{index}.{ext}")
async def capture_image(session_id: str, index: int, ext: str) -> Response:
    capture = capture_store.get_capture(session_id, index)
    if not capture:
        return Response(status_code=404)
    return Response(content=capture["bytes"], media_type=capture["content_type"])


@app.get("/summary/{session_id}/download.zip")
async def capture_zip(session_id: str) -> Response:
    captures = capture_store.captures(session_id)
    if not captures:
        return Response(status_code=404)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for capture in captures:
            name = safe_capture_filename(capture)
            archive.writestr(name, capture["bytes"])
    buffer.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="YUEDMAI-photos.zip"'}
    return Response(content=buffer.getvalue(), media_type="application/zip", headers=headers)


@app.get("/api/status")
async def api_status(debug: bool = Query(False)) -> dict[str, Any]:
    return full_status(debug=debug)


@app.get("/api/hardware")
async def api_hardware() -> dict[str, Any]:
    return {"hardware": hardware_bridge.status()}


@app.post("/api/nano_imu")
async def api_nano_imu(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    event = hardware_bridge.publish_nano_imu(payload, source="http")
    return {"ok": True, "event": event, "nano_imu": hardware_bridge.latest_nano_imu()}


@app.post("/api/hardware/feedback")
async def api_hardware_feedback(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    return hardware_bridge.feedback(payload)


@app.get("/api/health")
async def api_health() -> dict[str, Any]:
    status = source_manager.get_status()
    return {
        "healthy": True,
        "app": "YUEDMAI",
        "selected_camera_source": status["selected_camera_source"],
        "force_camera_mode": status["force_camera_mode"],
        "local_base_url": BASE_URL,
        "app_host": os.getenv("APP_HOST", "0.0.0.0"),
        "app_port": os.getenv("APP_PORT", "8000"),
        "phone_url": PHONE_URL,
    }


@app.post("/api/rescan_usb")
async def api_rescan_usb() -> dict[str, Any]:
    return source_manager.rescan_usb()


@app.post("/api/session/start")
async def api_session_start() -> dict[str, Any]:
    if session_manager.get_status().get("state") == "IDLE":
        capture_store.reset()
    return {"session": session_manager.start(), "status": full_status()}


@app.post("/api/session/pause")
async def api_session_pause() -> dict[str, Any]:
    return {"session": session_manager.pause(), "status": full_status()}


@app.post("/api/session/next")
async def api_session_next() -> dict[str, Any]:
    return {"session": session_manager.next(), "status": full_status()}


@app.post("/api/session/reset")
async def api_session_reset() -> dict[str, Any]:
    capture_store.reset()
    return {"session": session_manager.reset(), "status": full_status()}


@app.post("/api/session/config")
async def api_session_config(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    duration = payload.get("duration")
    try:
        duration_int = int(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration_int = None
    capture_store.reset()
    return {
        "session": session_manager.configure(
            mode=payload.get("mode"),
            body_focus=payload.get("body_focus"),
            duration=duration_int,
        ),
        "status": full_status(),
    }


@app.post("/api/session/captures")
async def api_session_capture(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
        capture_status = capture_store.upsert(payload, BASE_URL)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    except Exception:
        logger.exception("Failed to store stretch capture")
        return JSONResponse({"error": "Failed to store capture"}, status_code=500)
    return JSONResponse({"captures": capture_status})


def full_status(debug: bool = False) -> dict[str, Any]:
    camera = source_manager.get_status()
    camera_state = camera["camera_state"]
    session_camera_state = "WAITING_FOR_PHONE" if camera_state == "WAITING_FOR_PHONE" else "NO_CAMERA" if camera_state == "NO_CAMERA" else None
    pose = inference.get_pose_status(debug=debug)
    nano_imu = hardware_bridge.latest_nano_imu()
    session = session_manager.get_status(camera_state=session_camera_state, pose_metrics=pose, nano_metrics=nano_imu)
    setup = setup_boundary_status(camera, pose)
    return {
        "camera": camera,
        "session": session,
        "local_ip_or_base_url": BASE_URL,
        "app_host": os.getenv("APP_HOST", "0.0.0.0"),
        "app_port": os.getenv("APP_PORT", "8000"),
        "pose": pose,
        "setup": setup,
        "hardware": hardware_bridge.status(),
        "nano_ble": nano_ble_manager.status(),
        "nano_imu": nano_imu,
        "qr_url": PHONE_URL,
        "captures": capture_store.status(BASE_URL),
        "timestamp": time.time(),
    }


def safe_capture_filename(capture: dict[str, Any]) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(capture.get("name") or "stretch").lower()).strip("-") or "stretch"
    step = int(capture.get("index") or 0) + 1
    ext = str(capture.get("ext") or "jpg")
    return f"YUEDMAI-{step:02d}-{slug[:48]}.{ext}"


def setup_boundary_status(camera: dict[str, Any], pose: dict[str, Any]) -> dict[str, Any]:
    camera_state = str(camera.get("camera_state") or "NO_CAMERA")
    pose_timestamp = pose.get("last_pose_timestamp")
    pose_age = None
    if isinstance(pose_timestamp, (int, float)):
        pose_age = max(0.0, time.time() - float(pose_timestamp))

    user_visible = bool(pose.get("user_visible"))
    torso_centered = bool(pose.get("torso_centered"))
    full_body_visible = bool(pose.get("full_body_visible"))
    confidence = float(pose.get("confidence") or 0.0)
    pose_ready = bool(pose.get("pose_enabled") and pose.get("model_loaded"))
    pose_fresh = pose_age is not None and pose_age <= 2.0

    state = "CHECKING_BOUNDARY"
    label = "Checking position"
    instruction = "Stand inside the camera boundary"
    badge_class = "info"
    ready = False

    if camera_state == "NO_CAMERA":
        state = "NO_CAMERA"
        label = "Camera needed"
        instruction = "Connect a camera first"
        badge_class = "bad"
    elif camera_state == "WAITING_FOR_PHONE":
        state = "WAITING_FOR_CAMERA"
        label = "Waiting for camera"
        instruction = "Scan QR or connect USB camera"
        badge_class = "warn"
    elif not pose_ready:
        state = "POSE_UNAVAILABLE"
        label = "Pose check offline"
        instruction = "Camera pose check is needed"
        badge_class = "bad"
    elif not pose_fresh:
        state = "CHECKING_BOUNDARY"
        label = "Checking position"
        instruction = "Stand inside the camera boundary"
        badge_class = "info"
    elif not user_visible:
        state = "STEP_INTO_FRAME"
        label = "Step into frame"
        instruction = "Move into the camera boundary"
        badge_class = "warn"
    elif not torso_centered:
        state = "CENTER_BODY"
        label = "Center body"
        instruction = "Move to the center of the frame"
        badge_class = "warn"
    elif not full_body_visible:
        state = "SHOW_FULL_BODY"
        label = "Show full body"
        instruction = "Step back until your body fits"
        badge_class = "warn"
    elif confidence < 0.45:
        state = "LOW_CONFIDENCE"
        label = "Hold still"
        instruction = "Hold still for camera check"
        badge_class = "warn"
    else:
        state = "READY_TO_START"
        label = "Ready"
        instruction = "Boundary check passed"
        badge_class = "ok"
        ready = True

    return {
        "state": state,
        "ready": ready,
        "label": label,
        "instruction": instruction,
        "badge_class": badge_class,
        "camera_ready": camera_state == "ACTIVE",
        "pose_ready": pose_ready,
        "pose_fresh": pose_fresh,
        "pose_age_sec": round(pose_age, 2) if pose_age is not None else None,
        "user_visible": user_visible,
        "torso_centered": torso_centered,
        "full_body_visible": full_body_visible,
        "confidence": round(confidence, 4),
    }


async def mjpeg_generator(draw_overlay: bool = True):
    while True:
        try:
            status = full_status()
            frame = source_manager.get_frame()
            if frame is None:
                frame = placeholder_frame(status)
            context = {
                "source_label": status["camera"]["source_label"],
                "fps": status["camera"]["fps"],
                "session_state": status["session"]["state"],
                "score": status["session"]["score"],
                "draw_frame_labels": draw_overlay,
            }
            processed, metrics = inference.process_frame(frame, context)
            status["inference"] = metrics
            ok, encoded = cv2.imencode(".jpg", processed, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
            if ok:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + encoded.tobytes() + b"\r\n"
            await asyncio.sleep(0.08)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("MJPEG stream error")
            await asyncio.sleep(0.5)


def placeholder_frame(status: dict[str, Any]) -> np.ndarray:
    frame = np.zeros((720, 960, 3), dtype=np.uint8)
    frame[:] = (12, 18, 22)
    source = status["camera"]["source_label"]
    instruction = status["session"]["instruction"]
    cv2.putText(frame, source, (60, 160), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (235, 245, 248), 3, cv2.LINE_AA)
    cv2.putText(frame, instruction, (60, 250), cv2.FONT_HERSHEY_SIMPLEX, 2.2, (141, 245, 33), 5, cv2.LINE_AA)
    cv2.putText(frame, "Open /setup or scan QR for phone camera", (60, 330), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (175, 190, 200), 2, cv2.LINE_AA)
    return frame
