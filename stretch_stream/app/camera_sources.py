from __future__ import annotations

import logging
import platform
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import cv2
import numpy as np


USB_INDEXES = range(0, 6)
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
TARGET_FPS = 15


@dataclass
class FrameStats:
    fps: float = 0.0
    width: int = 0
    height: int = 0
    timestamp: str = ""


class LatestFrameStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame: np.ndarray | None = None
        self._stats = FrameStats()
        self._last_time: float | None = None

    def update(self, frame: np.ndarray) -> None:
        now = time.monotonic()
        with self._lock:
            if self._last_time is not None:
                delta = now - self._last_time
                if delta > 0:
                    instant = 1.0 / delta
                    self._stats.fps = instant if self._stats.fps <= 0 else (self._stats.fps * 0.85) + (instant * 0.15)
            self._last_time = now
            self._frame = frame.copy()
            self._stats.width = int(frame.shape[1])
            self._stats.height = int(frame.shape[0])
            self._stats.timestamp = datetime.now().isoformat(timespec="seconds")

    def get(self) -> np.ndarray | None:
        with self._lock:
            if self._frame is None:
                return None
            return self._frame.copy()

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "fps": self._stats.fps,
                "frame_width": self._stats.width,
                "frame_height": self._stats.height,
                "last_frame_timestamp": self._stats.timestamp,
            }


class USBCameraSource:
    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.store = LatestFrameStore()
        self.capture: cv2.VideoCapture | None = None
        self.index: int | None = None
        self.detected = False
        self.failure_count = 0

    def start(self) -> bool:
        self.stop()
        for index in USB_INDEXES:
            self.logger.info("Trying USB camera index %s", index)
            capture = self._open_capture(index)
            if not capture or not capture.isOpened():
                self._release(capture)
                continue
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
            capture.set(cv2.CAP_PROP_FPS, TARGET_FPS)
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            frame = self._validation_frame(capture)
            if frame is None:
                self._release(capture)
                continue
            self.capture = capture
            self.index = index
            self.detected = True
            self.failure_count = 0
            self.store.update(frame)
            self.logger.info("USB camera detected index=%s size=%sx%s", index, frame.shape[1], frame.shape[0])
            return True
        self.detected = False
        self.logger.info("No USB camera detected")
        return False

    def read(self) -> np.ndarray | None:
        if not self.capture or not self.capture.isOpened():
            self.detected = False
            return None
        ok, frame = self.capture.read()
        if not ok or frame is None:
            self.failure_count += 1
            self.logger.warning("USB camera read failure count=%s", self.failure_count)
            if self.failure_count >= 8:
                self.logger.error("USB camera disconnected after repeated failures")
                self.stop()
            return None
        self.failure_count = 0
        self.store.update(frame)
        return frame

    def stop(self) -> None:
        self._release(self.capture)
        self.capture = None
        self.index = None
        self.detected = False
        self.failure_count = 0

    def _open_capture(self, index: int) -> cv2.VideoCapture:
        if platform.system().lower() == "windows":
            capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if capture.isOpened():
                return capture
            self._release(capture)
        return cv2.VideoCapture(index)

    def _validation_frame(self, capture: cv2.VideoCapture) -> np.ndarray | None:
        for _ in range(5):
            ok, frame = capture.read()
            if ok and frame is not None and frame.size > 0:
                return frame
            time.sleep(0.08)
        return None

    def _release(self, capture: cv2.VideoCapture | None) -> None:
        try:
            if capture is not None:
                capture.release()
        except Exception:
            self.logger.exception("Failed to release USB camera")


class PhoneCameraSource:
    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.store = LatestFrameStore()
        self._lock = threading.Lock()
        self._clients: set[str] = set()
        self.frames_received = 0
        self.decode_errors = 0

    def mark_connected(self, client_id: str) -> None:
        with self._lock:
            self._clients.add(client_id)
        self.logger.info("Phone camera connected: %s", client_id)

    def mark_disconnected(self, client_id: str) -> None:
        with self._lock:
            self._clients.discard(client_id)
        self.logger.info("Phone camera disconnected: %s", client_id)

    def receive_jpeg(self, payload: bytes, client_id: str) -> bool:
        try:
            encoded = np.frombuffer(payload, dtype=np.uint8)
            frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
            if frame is None:
                self.decode_errors += 1
                self.logger.warning("Phone frame decode error from %s", client_id)
                return False
            self.store.update(frame)
            self.frames_received += 1
            return True
        except Exception:
            self.decode_errors += 1
            self.logger.exception("Phone frame decode exception from %s", client_id)
            return False

    def is_connected(self) -> bool:
        with self._lock:
            return bool(self._clients)

    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)
