from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import config


class PhoneFrameBuffer:
    """Thread-safe latest-frame store shared by FastAPI and OpenCV dashboard."""

    def __init__(self, event_log: Any | None = None) -> None:
        self.event_log = event_log
        self.logger = logging.getLogger(__name__)
        self._lock = threading.Lock()
        self._latest_frame: np.ndarray | None = None
        self._latest_timestamp = ""
        self._latest_monotonic = 0.0
        self._frame_size: tuple[int, int] | None = None
        self._connected_clients: set[str] = set()
        self._frames_received = 0
        self._decode_errors = 0
        self._last_frame_time: float | None = None
        self._observed_fps = 0.0

    def mark_connected(self, client_id: str) -> None:
        with self._lock:
            self._connected_clients.add(client_id)
        self._log_event(f"Phone connected: {client_id}")

    def mark_disconnected(self, client_id: str) -> None:
        with self._lock:
            self._connected_clients.discard(client_id)
        self._log_event(f"Phone disconnected: {client_id}")

    def update_frame(self, frame: np.ndarray, client_id: str) -> None:
        now = time.monotonic()
        timestamp = datetime.now().isoformat(timespec="seconds")
        with self._lock:
            if self._last_frame_time is not None:
                delta = now - self._last_frame_time
                if delta > 0:
                    instant_fps = 1.0 / delta
                    if self._observed_fps <= 0:
                        self._observed_fps = instant_fps
                    else:
                        self._observed_fps = (self._observed_fps * 0.85) + (instant_fps * 0.15)
            self._last_frame_time = now
            self._latest_frame = frame
            self._latest_timestamp = timestamp
            self._latest_monotonic = now
            self._frame_size = (int(frame.shape[1]), int(frame.shape[0]))
            self._frames_received += 1
        self.logger.debug("Phone frame accepted from %s size=%s", client_id, self._frame_size)

    def record_decode_error(self, client_id: str) -> None:
        with self._lock:
            self._decode_errors += 1
        self._log_event(f"Frame decode error from {client_id}", logging.WARNING)

    def get_latest_frame(self) -> np.ndarray | None:
        with self._lock:
            if self._latest_frame is None:
                return None
            return self._latest_frame.copy()

    def get_info(self) -> dict[str, Any]:
        with self._lock:
            connected_count = len(self._connected_clients)
            has_recent_frame = self._latest_frame is not None and (time.monotonic() - self._latest_monotonic) < 3.0
            status = "CONNECTED" if connected_count > 0 else "WAITING_FOR_PHONE"
            if connected_count > 0 and not has_recent_frame:
                status = "CONNECTED_NO_FRAMES"
            return {
                "connection_status": status,
                "connected_clients": connected_count,
                "frames_received": self._frames_received,
                "decode_errors": self._decode_errors,
                "fps": self._observed_fps,
                "frame_size": self._frame_size,
                "timestamp": self._latest_timestamp,
            }

    def _log_event(self, message: str, level: int = logging.INFO) -> None:
        if self.event_log is not None:
            self.event_log.add(message, level=level)
        else:
            self.logger.log(level, message)


class PhoneWebServer:
    """FastAPI server that receives JPEG frames from a phone browser."""

    def __init__(
        self,
        frame_buffer: PhoneFrameBuffer,
        local_ip: str,
        host: str = config.SERVER_HOST,
        port: int = config.SERVER_PORT,
        use_https: bool = config.USE_HTTPS,
        ssl_certfile: str = config.SSL_CERTFILE,
        ssl_keyfile: str = config.SSL_KEYFILE,
        event_log: Any | None = None,
    ) -> None:
        self.frame_buffer = frame_buffer
        self.local_ip = local_ip
        self.host = host
        self.port = port
        self.event_log = event_log
        self.logger = logging.getLogger(__name__)
        self.use_https = self._validate_https(use_https, ssl_certfile, ssl_keyfile)
        self.ssl_certfile = ssl_certfile if self.use_https else ""
        self.ssl_keyfile = ssl_keyfile if self.use_https else ""
        self.app = self._build_app()
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._last_error: Exception | None = None

    @property
    def scheme(self) -> str:
        return "https" if self.use_https else "http"

    @property
    def connection_url(self) -> str:
        return f"{self.scheme}://{self.local_ip}:{self.port}/phone"

    def start(self) -> bool:
        if self.is_running():
            self.logger.info("Phone web server already running at %s", self.connection_url)
            return True

        self._last_error = None
        uvicorn_config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
            access_log=False,
            ssl_certfile=self.ssl_certfile or None,
            ssl_keyfile=self.ssl_keyfile or None,
        )
        self._server = uvicorn.Server(uvicorn_config)
        self._thread = threading.Thread(
            target=self._run_server,
            name="phone-camera-web-server",
            daemon=True,
        )
        self._thread.start()

        deadline = time.time() + 3.0
        while time.time() < deadline:
            if self._last_error is not None:
                return False
            if self._server.started:
                self._log_event(f"Phone web server started at {self.connection_url}")
                return True
            if not self._thread.is_alive():
                return False
            time.sleep(0.05)

        running = self._thread.is_alive()
        if running:
            self._log_event(f"Phone web server is starting at {self.connection_url}")
        return running

    def stop(self) -> None:
        if self._server is not None:
            self.logger.info("Stopping phone web server.")
            self._server.should_exit = True
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._thread = None
        self._server = None

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run_server(self) -> None:
        assert self._server is not None
        try:
            self._server.run()
        except Exception as exc:
            self._last_error = exc
            self.logger.exception("Phone web server crashed.")
            self._log_event("Phone web server crashed. See logs for stack trace.", logging.ERROR)

    def _build_app(self) -> FastAPI:
        app = FastAPI(title="Smart Stretch Coach Phone Camera")
        template_dir = Path(__file__).resolve().parent / "templates"
        templates = Jinja2Templates(directory=str(template_dir))

        @app.get("/")
        async def root() -> RedirectResponse:
            return RedirectResponse(url="/phone")

        @app.get("/health")
        async def health() -> dict[str, Any]:
            return {
                "ok": True,
                "mode": config.SOURCE_PHONE,
                "connection_url": self.connection_url,
                "buffer": self.frame_buffer.get_info(),
            }

        @app.get("/phone")
        async def phone_page(request: Request):
            return templates.TemplateResponse(
                "phone_camera.html",
                {
                    "request": request,
                    "target_fps": config.PHONE_TARGET_FPS,
                    "jpeg_quality": config.PHONE_JPEG_QUALITY,
                    "frame_width": config.PHONE_FRAME_WIDTH,
                    "frame_height": config.PHONE_FRAME_HEIGHT,
                    "connection_url": self.connection_url,
                },
            )

        @app.websocket("/ws/phone-frame")
        async def phone_frame_socket(websocket: WebSocket) -> None:
            await websocket.accept()
            client = websocket.client
            client_id = f"{client.host}:{client.port}" if client else "unknown-phone"
            self.frame_buffer.mark_connected(client_id)
            try:
                while True:
                    message = await websocket.receive()
                    if message.get("type") == "websocket.disconnect":
                        break
                    payload = message.get("bytes")
                    if payload is None:
                        continue

                    frame = self._decode_jpeg(payload, client_id)
                    if frame is None:
                        continue
                    self.frame_buffer.update_frame(frame, client_id)
            except WebSocketDisconnect:
                self.logger.info("Phone WebSocket disconnected: %s", client_id)
            except Exception:
                self.logger.exception("Phone WebSocket error for %s", client_id)
                self._log_event(f"WebSocket error for {client_id}. See logs.", logging.ERROR)
            finally:
                self.frame_buffer.mark_disconnected(client_id)

        return app

    def _decode_jpeg(self, payload: bytes, client_id: str) -> np.ndarray | None:
        try:
            encoded = np.frombuffer(payload, dtype=np.uint8)
            frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
            if frame is None:
                self.frame_buffer.record_decode_error(client_id)
                return None
            return frame
        except Exception:
            self.logger.exception("Frame decode exception from %s", client_id)
            self.frame_buffer.record_decode_error(client_id)
            return None

    def _validate_https(self, use_https: bool, ssl_certfile: str, ssl_keyfile: str) -> bool:
        if not use_https:
            return False
        cert_ok = bool(ssl_certfile) and Path(ssl_certfile).exists()
        key_ok = bool(ssl_keyfile) and Path(ssl_keyfile).exists()
        if cert_ok and key_ok:
            return True
        self.logger.warning(
            "HTTPS requested, but certificate/key files were not found. Falling back to HTTP."
        )
        self._log_event(
            "HTTPS requested without valid cert/key. Falling back to HTTP for phone QR mode.",
            logging.WARNING,
        )
        return False

    def _log_event(self, message: str, level: int = logging.INFO) -> None:
        if self.event_log is not None:
            self.event_log.add(message, level=level)
        else:
            self.logger.log(level, message)
