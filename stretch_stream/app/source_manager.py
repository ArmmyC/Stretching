from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

import numpy as np

from app.camera_sources import PhoneCameraSource, USBCameraSource

FORCE_MODES = {"auto", "usb", "phone"}


class SourceManager:
    """Selects USB or phone camera and keeps the latest frame ready for HTTP."""

    def __init__(self, force_mode: str = "auto") -> None:
        self.logger = logging.getLogger(__name__)
        self.force_mode = force_mode if force_mode in FORCE_MODES else "auto"
        self.usb = USBCameraSource()
        self.phone = PhoneCameraSource()
        self._lock = threading.Lock()
        self._selected_source = "NO_CAMERA"
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_usb_scan = 0.0
        self.logger.info("Source manager created force_mode=%s", self.force_mode)

    @classmethod
    def from_environment(cls) -> "SourceManager":
        return cls(os.getenv("FORCE_CAMERA_MODE", "auto").strip().lower() or "auto")

    def start(self) -> None:
        if self._running:
            return
        self.logger.info("Starting camera source manager")
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="camera-source-manager", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self.usb.stop()
        self.logger.info("Camera source manager stopped")

    def rescan_usb(self) -> dict[str, Any]:
        self.logger.info("Manual USB rescan requested")
        ok = self.usb.start()
        if ok and self.force_mode != "phone":
            self._set_selected("USB_CAMERA")
        elif self.force_mode == "phone":
            self._set_selected("PHONE_QR")
        else:
            self._set_selected("PHONE_QR")
        return self.get_status()

    def get_frame(self) -> np.ndarray | None:
        selected = self.selected_source
        if selected == "USB_CAMERA":
            return self.usb.store.get()
        if selected == "PHONE_QR":
            return self.phone.store.get()
        return None

    @property
    def selected_source(self) -> str:
        with self._lock:
            return self._selected_source

    def get_status(self) -> dict[str, Any]:
        selected = self.selected_source
        usb_stats = self.usb.store.stats()
        phone_stats = self.phone.store.stats()
        stats = usb_stats if selected == "USB_CAMERA" else phone_stats if selected == "PHONE_QR" else {}
        phone_connected = self.phone.is_connected()
        connection_status = "NO_CAMERA"
        source_label = "No Camera"
        camera_state = "NO_CAMERA"

        if selected == "USB_CAMERA" and self.usb.detected:
            connection_status = "CONNECTED"
            source_label = "USB Camera"
            camera_state = "ACTIVE"
        elif selected == "PHONE_QR":
            if phone_connected:
                connection_status = "CONNECTED"
                source_label = "Phone Camera"
                camera_state = "ACTIVE"
            else:
                connection_status = "WAITING_FOR_PHONE"
                source_label = "Waiting for Phone"
                camera_state = "WAITING_FOR_PHONE"

        return {
            "selected_camera_source": selected,
            "source_label": source_label,
            "connection_status": connection_status,
            "camera_state": camera_state,
            "usb_camera_detected": self.usb.detected,
            "usb_index": self.usb.index,
            "phone_connected": phone_connected,
            "phone_clients": self.phone.client_count(),
            "phone_frames_received": self.phone.frames_received,
            "phone_decode_errors": self.phone.decode_errors,
            "force_camera_mode": self.force_mode,
            "fps": float(stats.get("fps") or 0.0),
            "frame_width": int(stats.get("frame_width") or 0),
            "frame_height": int(stats.get("frame_height") or 0),
            "last_frame_timestamp": stats.get("last_frame_timestamp") or "",
        }

    def _loop(self) -> None:
        self.logger.info("Camera source manager loop started")
        while self._running:
            try:
                self._select_source()
                if self.selected_source == "USB_CAMERA":
                    frame = self.usb.read()
                    if frame is None and not self.usb.detected:
                        self.logger.warning("USB camera unavailable; falling back if allowed")
                        if self.force_mode == "auto":
                            self._set_selected("PHONE_QR")
                time.sleep(0.02)
            except Exception:
                self.logger.exception("Camera source manager loop error")
                time.sleep(0.5)

    def _select_source(self) -> None:
        now = time.monotonic()
        if self.force_mode == "phone":
            self._set_selected("PHONE_QR")
            return

        if self.force_mode == "usb":
            if not self.usb.detected and now - self._last_usb_scan > 3.0:
                self._last_usb_scan = now
                self.usb.start()
            self._set_selected("USB_CAMERA" if self.usb.detected else "NO_CAMERA")
            return

        if self.usb.detected:
            self._set_selected("USB_CAMERA")
            return

        if now - self._last_usb_scan > 4.0:
            self._last_usb_scan = now
            if self.usb.start():
                self.logger.info("USB camera found during auto scan; switching to USB")
                self._set_selected("USB_CAMERA")
                return

        self._set_selected("PHONE_QR")

    def _set_selected(self, source: str) -> None:
        with self._lock:
            if self._selected_source != source:
                self.logger.info("Camera source switching %s -> %s", self._selected_source, source)
                self._selected_source = source
