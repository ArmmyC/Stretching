from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

import cv2
import numpy as np
from fastapi import FastAPI, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import inference
from app.session_manager import SessionManager
from app.source_manager import SourceManager
from app.utils import PROJECT_ROOT, build_base_url, log_startup_details, make_qr_png_bytes, setup_logging

setup_logging()

logger = logging.getLogger(__name__)
app = FastAPI(title="StretchSense Local Kiosk")
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "app" / "templates"))
app.mount("/static", StaticFiles(directory=str(PROJECT_ROOT / "app" / "static")), name="static")

source_manager = SourceManager.from_environment()
session_manager = SessionManager()
BASE_URL = build_base_url()
PHONE_URL = f"{BASE_URL}/phone"


@app.on_event("startup")
async def startup() -> None:
    log_startup_details(source_manager.force_mode, BASE_URL)
    logger.info("QR URL generated: %s", PHONE_URL)
    source_manager.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    source_manager.stop()
    logger.info("StretchSense app shutdown")


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


@app.get("/video_feed")
async def video_feed() -> StreamingResponse:
    return StreamingResponse(mjpeg_generator(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/qr.png")
async def qr_png() -> Response:
    return Response(content=make_qr_png_bytes(PHONE_URL), media_type="image/png")


@app.get("/api/status")
async def api_status(debug: bool = Query(False)) -> dict[str, Any]:
    return full_status(debug=debug)


@app.get("/api/health")
async def api_health() -> dict[str, Any]:
    status = source_manager.get_status()
    return {
        "healthy": True,
        "app": "StretchSense",
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
    return {"session": session_manager.start(), "status": full_status()}


@app.post("/api/session/pause")
async def api_session_pause() -> dict[str, Any]:
    return {"session": session_manager.pause(), "status": full_status()}


@app.post("/api/session/next")
async def api_session_next() -> dict[str, Any]:
    return {"session": session_manager.next(), "status": full_status()}


@app.post("/api/session/reset")
async def api_session_reset() -> dict[str, Any]:
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
    return {
        "session": session_manager.configure(
            mode=payload.get("mode"),
            body_focus=payload.get("body_focus"),
            duration=duration_int,
        ),
        "status": full_status(),
    }


def full_status(debug: bool = False) -> dict[str, Any]:
    camera = source_manager.get_status()
    camera_state = camera["camera_state"]
    session_camera_state = "WAITING_FOR_PHONE" if camera_state == "WAITING_FOR_PHONE" else "NO_CAMERA" if camera_state == "NO_CAMERA" else None
    session = session_manager.get_status(camera_state=session_camera_state)
    return {
        "camera": camera,
        "session": session,
        "local_ip_or_base_url": BASE_URL,
        "app_host": os.getenv("APP_HOST", "0.0.0.0"),
        "app_port": os.getenv("APP_PORT", "8000"),
        "pose": inference.get_pose_status(debug=debug),
        "qr_url": PHONE_URL,
        "timestamp": time.time(),
    }


async def mjpeg_generator():
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
