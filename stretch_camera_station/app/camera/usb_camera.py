from __future__ import annotations

import logging
import platform
import time
from datetime import datetime
from typing import Any

import cv2
import numpy as np

from app import config
from app.camera.base import CameraSource


class USBCameraSource(CameraSource):
    """OpenCV VideoCapture source that validates cameras by reading real frames."""

    source_type = config.SOURCE_USB

    def __init__(
        self,
        indexes: range = config.USB_CAMERA_INDEXES,
        width: int = config.USB_FRAME_WIDTH,
        height: int = config.USB_FRAME_HEIGHT,
        target_fps: int = config.USB_TARGET_FPS,
        forced_index: int | None = None,
    ) -> None:
        self.indexes = indexes
        self.width = width
        self.height = height
        self.target_fps = target_fps
        self.forced_index = forced_index
        self.logger = logging.getLogger(__name__)
        self.capture: cv2.VideoCapture | None = None
        self.index: int | None = None
        self._active = False
        self._failure_count = 0
        self._last_frame_time: float | None = None
        self._observed_fps = 0.0
        self._last_timestamp = ""
        self._frame_size: tuple[int, int] | None = None

    def start(self) -> bool:
        candidate_indexes = [self.forced_index] if self.forced_index is not None else list(self.indexes)
        self.logger.info("Starting USB camera detection. Candidate indexes: %s", candidate_indexes)

        self.stop()
        for index in candidate_indexes:
            if index is None:
                continue
            self.logger.info("Trying USB camera index %s", index)
            capture = self._open_capture(index)
            if capture is None or not capture.isOpened():
                self.logger.info("USB camera index %s did not open.", index)
                self._safe_release(capture)
                continue

            self._configure_capture(capture)
            frame = self._read_validation_frame(capture, index)
            if frame is None:
                self.logger.info("USB camera index %s opened but returned no valid frames.", index)
                self._safe_release(capture)
                continue

            self.capture = capture
            self.index = index
            self._active = True
            self._failure_count = 0
            self._update_stats(frame)
            actual_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = capture.get(cv2.CAP_PROP_FPS)
            self.logger.info(
                "Selected USB camera index %s. Requested=%sx%s@%s FPS, actual=%sx%s@%.2f FPS",
                index,
                self.width,
                self.height,
                self.target_fps,
                actual_width,
                actual_height,
                actual_fps,
            )
            return True

        self.logger.warning("No working USB camera found after trying indexes %s.", candidate_indexes)
        self._active = False
        return False

    def read(self) -> np.ndarray | None:
        if not self.capture or not self._active:
            return None

        ok, frame = self.capture.read()
        if not ok or frame is None:
            self._failure_count += 1
            self.logger.warning(
                "USB camera read failed. index=%s failure_count=%s",
                self.index,
                self._failure_count,
            )
            if self._failure_count >= config.USB_MAX_RUNTIME_FAILURES:
                self.logger.error("USB camera index %s marked inactive after repeated failures.", self.index)
                self._active = False
            return None

        self._failure_count = 0
        self._update_stats(frame)
        return frame

    def stop(self) -> None:
        if self.capture is not None:
            self.logger.info("Releasing USB camera index %s", self.index)
            self._safe_release(self.capture)
        self.capture = None
        self.index = None
        self._active = False

    def is_active(self) -> bool:
        return self._active and self.capture is not None and self.capture.isOpened()

    def get_info(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "active": self.is_active(),
            "index": self.index,
            "connection_status": "CONNECTED" if self.is_active() else "DISCONNECTED",
            "fps": self._observed_fps,
            "target_fps": self.target_fps,
            "frame_size": self._frame_size,
            "timestamp": self._last_timestamp,
            "failure_count": self._failure_count,
        }

    def _open_capture(self, index: int) -> cv2.VideoCapture:
        if platform.system().lower() == "windows":
            capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if capture.isOpened():
                return capture
            self._safe_release(capture)
        return cv2.VideoCapture(index)

    def _configure_capture(self, capture: cv2.VideoCapture) -> None:
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        capture.set(cv2.CAP_PROP_FPS, self.target_fps)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def _read_validation_frame(self, capture: cv2.VideoCapture, index: int) -> np.ndarray | None:
        for attempt in range(1, 6):
            ok, frame = capture.read()
            self.logger.debug(
                "USB validation read. index=%s attempt=%s ok=%s frame_none=%s",
                index,
                attempt,
                ok,
                frame is None,
            )
            if ok and frame is not None and frame.size > 0:
                return frame
            time.sleep(0.1)
        return None

    def _update_stats(self, frame: np.ndarray) -> None:
        now = time.monotonic()
        if self._last_frame_time is not None:
            delta = now - self._last_frame_time
            if delta > 0:
                instant_fps = 1.0 / delta
                if self._observed_fps <= 0:
                    self._observed_fps = instant_fps
                else:
                    self._observed_fps = (self._observed_fps * 0.85) + (instant_fps * 0.15)
        self._last_frame_time = now
        self._last_timestamp = datetime.now().isoformat(timespec="seconds")
        self._frame_size = (int(frame.shape[1]), int(frame.shape[0]))

    def _safe_release(self, capture: cv2.VideoCapture | None) -> None:
        try:
            if capture is not None:
                capture.release()
        except Exception:
            self.logger.exception("Exception while releasing USB camera.")
