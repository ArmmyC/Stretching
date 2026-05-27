from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app import config
from app.camera.camera_manager import CameraManager
from app.processing.pipeline import ProcessingPipeline


class OpenCVDashboard:
    """Simple OpenCV dashboard showing source, processing state, and feedback."""

    def __init__(
        self,
        camera_manager: CameraManager,
        pipeline: ProcessingPipeline,
        event_log: Any,
    ) -> None:
        self.camera_manager = camera_manager
        self.pipeline = pipeline
        self.event_log = event_log
        self.logger = logging.getLogger(__name__)
        self._running = False
        self._last_frame: np.ndarray | None = None

    def run(self) -> None:
        self._running = True
        self.event_log.add("OpenCV dashboard started.")
        cv2.namedWindow(config.DASHBOARD_WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(config.DASHBOARD_WINDOW_NAME, config.DASHBOARD_WIDTH, config.DASHBOARD_HEIGHT)

        while self._running:
            frame = self.camera_manager.read()
            info = self.camera_manager.get_info()
            result = self.pipeline.process(frame) if frame is not None else self.pipeline.process(None)
            if frame is not None:
                self._last_frame = frame
                dashboard_frame = self._render_live_dashboard(frame, info, result)
            else:
                dashboard_frame = self._render_waiting_dashboard(info, result)

            cv2.imshow(config.DASHBOARD_WINDOW_NAME, dashboard_frame)
            key = cv2.waitKey(1) & 0xFF
            if key != 255:
                self._handle_key(key)

    def stop(self) -> None:
        if self._running:
            self.event_log.add("OpenCV dashboard stopping.")
        self._running = False
        try:
            cv2.destroyWindow(config.DASHBOARD_WINDOW_NAME)
        except Exception:
            self.logger.debug("Dashboard window was already closed.")

    def _handle_key(self, key: int) -> None:
        if key == ord("q"):
            self.event_log.add("Dashboard quit requested with key 'q'.")
            self._running = False
        elif key == ord("r"):
            self.event_log.add("Dashboard restart detection requested with key 'r'.")
            self.camera_manager.restart_detection()
        elif key == ord("p"):
            self.event_log.add("Dashboard force PHONE_QR requested with key 'p'.")
            self.camera_manager.force_phone()
        elif key == ord("u"):
            self.event_log.add("Dashboard force USB_CAMERA requested with key 'u'.")
            self.camera_manager.force_usb()
        elif key == ord("s"):
            self._save_debug_frame()

    def _save_debug_frame(self) -> None:
        if self._last_frame is None:
            self.event_log.add("Save debug frame requested, but no frame is available.", logging.WARNING)
            return
        config.DEBUG_FRAME_DIR.mkdir(parents=True, exist_ok=True)
        output_path = config.DEBUG_FRAME_DIR / f"debug_frame_{datetime.now():%Y%m%d_%H%M%S}.jpg"
        ok = cv2.imwrite(str(output_path), self._last_frame)
        if ok:
            self.event_log.add(f"Saved debug frame: {output_path}")
        else:
            self.event_log.add(f"Failed to save debug frame: {output_path}", logging.ERROR)

    def _render_live_dashboard(
        self,
        frame: np.ndarray,
        info: dict[str, Any],
        result: dict[str, Any],
    ) -> np.ndarray:
        canvas = self._empty_canvas()
        self._place_frame(canvas, frame)
        self._draw_status_panel(canvas, info, result)
        return canvas

    def _render_waiting_dashboard(
        self,
        info: dict[str, Any],
        result: dict[str, Any],
    ) -> np.ndarray:
        canvas = self._empty_canvas()
        x, y = 24, 30
        live_w = config.DASHBOARD_LIVE_AREA_WIDTH
        live_h = config.DASHBOARD_LIVE_AREA_HEIGHT
        cv2.rectangle(canvas, (x, y), (x + live_w, y + live_h), (23, 29, 35), thickness=-1)
        cv2.rectangle(canvas, (x, y), (x + live_w, y + live_h), (65, 76, 89), thickness=1)

        qr_image = self.camera_manager.get_qr_image()
        if qr_image is not None:
            self._draw_text(canvas, "Scan QR to use phone camera", x + 34, y + 46, scale=0.85)
            self._draw_text(canvas, self.camera_manager.get_phone_url(), x + 34, y + live_h - 35, scale=0.55, color=(180, 205, 230))
            qr_size = min(360, live_h - 160)
            qr = cv2.resize(qr_image, (qr_size, qr_size), interpolation=cv2.INTER_NEAREST)
            qx = x + (live_w - qr_size) // 2
            qy = y + 110
            canvas[qy: qy + qr_size, qx: qx + qr_size] = qr
        else:
            self._draw_text(canvas, "Waiting for camera frames", x + 34, y + 70, scale=0.95)
            self._draw_text(canvas, "Press r to retry detection, p for phone QR, u for USB.", x + 34, y + 120, scale=0.62, color=(190, 200, 210))

        self._draw_status_panel(canvas, info, result)
        return canvas

    def _empty_canvas(self) -> np.ndarray:
        canvas = np.zeros((config.DASHBOARD_HEIGHT, config.DASHBOARD_WIDTH, 3), dtype=np.uint8)
        canvas[:] = (14, 18, 22)
        return canvas

    def _place_frame(self, canvas: np.ndarray, frame: np.ndarray) -> None:
        x, y = 24, 30
        area_w = config.DASHBOARD_LIVE_AREA_WIDTH
        area_h = config.DASHBOARD_LIVE_AREA_HEIGHT
        cv2.rectangle(canvas, (x, y), (x + area_w, y + area_h), (23, 29, 35), thickness=-1)

        frame_h, frame_w = frame.shape[:2]
        scale = min(area_w / frame_w, area_h / frame_h)
        resized_w = max(1, int(frame_w * scale))
        resized_h = max(1, int(frame_h * scale))
        resized = cv2.resize(frame, (resized_w, resized_h), interpolation=cv2.INTER_AREA)
        px = x + (area_w - resized_w) // 2
        py = y + (area_h - resized_h) // 2
        canvas[py: py + resized_h, px: px + resized_w] = resized
        cv2.rectangle(canvas, (x, y), (x + area_w, y + area_h), (65, 76, 89), thickness=1)

    def _draw_status_panel(
        self,
        canvas: np.ndarray,
        info: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        x = 940
        y = 42
        self._draw_text(canvas, "Smart Stretch Coach", x, y, scale=0.82, color=(246, 248, 250), thickness=2)
        y += 42
        self._draw_text(canvas, "Wellness guidance prototype", x, y, scale=0.52, color=(170, 185, 200))
        y += 42

        frame_size = info.get("frame_size")
        resolution = f"{frame_size[0]}x{frame_size[1]}" if frame_size else "N/A"
        latest_event = self.event_log.latest_message(default="No events yet")
        rows = [
            ("Source", str(info.get("source_type", config.SOURCE_NONE))),
            ("Status", str(info.get("connection_status", "UNKNOWN"))),
            ("FPS", f"{float(info.get('fps') or 0.0):.1f}"),
            ("Resolution", resolution),
            ("Timestamp", str(info.get("timestamp") or "N/A")),
            ("Inference", str(result.get("message", "N/A"))),
            ("Stretch State", str(result.get("stretch_state", "N/A"))),
            ("Confidence", f"{float(result.get('confidence') or 0.0):.2f}"),
            ("Events", str(self.event_log.count())),
            ("Latest", latest_event[:32]),
        ]

        for label, value in rows:
            self._draw_text(canvas, label, x, y, scale=0.48, color=(150, 168, 188))
            y += 24
            self._draw_text(canvas, value, x, y, scale=0.58, color=(244, 247, 250), thickness=2)
            y += 34

        y = config.DASHBOARD_HEIGHT - 88
        self._draw_text(canvas, "Controls", x, y, scale=0.52, color=(150, 168, 188))
        y += 28
        self._draw_text(canvas, "q quit  r retry  p phone  u usb  s save", x, y, scale=0.47, color=(218, 226, 235))

    def _draw_text(
        self,
        canvas: np.ndarray,
        text: str,
        x: int,
        y: int,
        scale: float = 0.6,
        color: tuple[int, int, int] = (240, 244, 248),
        thickness: int = 1,
    ) -> None:
        cv2.putText(
            canvas,
            text,
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            scale,
            color,
            thickness,
            cv2.LINE_AA,
        )
