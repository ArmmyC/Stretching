from __future__ import annotations

import logging
import platform
import sys
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Deque

import cv2
import fastapi
import numpy as np
import qrcode
import uvicorn


@dataclass(frozen=True)
class RuntimeEvent:
    timestamp: str
    level: str
    message: str


class RuntimeEventLog:
    """Small event feed for both logs and the OpenCV dashboard."""

    def __init__(self, max_events: int = 200) -> None:
        self.logger = logging.getLogger("stretch_station.events")
        self._events: Deque[RuntimeEvent] = deque(maxlen=max_events)
        self._lock = threading.Lock()
        self._total_count = 0

    def add(self, message: str, level: int = logging.INFO) -> None:
        self.logger.log(level, message)
        with self._lock:
            self._total_count += 1
            self._events.append(
                RuntimeEvent(
                    timestamp=datetime.now().isoformat(timespec="seconds"),
                    level=logging.getLevelName(level),
                    message=message,
                )
            )

    def count(self) -> int:
        with self._lock:
            return self._total_count

    def latest_message(self, default: str = "") -> str:
        with self._lock:
            if not self._events:
                return default
            return self._events[-1].message


def log_startup_diagnostics(event_log: RuntimeEventLog, log_path: Path) -> None:
    logger = logging.getLogger(__name__)
    event_log.add("Smart Stretch Coach station starting.")
    logger.info("Log file: %s", log_path)
    logger.info("Startup time: %s", datetime.now().isoformat(timespec="seconds"))
    logger.info("OS/platform: %s", platform.platform())
    logger.info("Machine: %s", platform.machine())
    logger.info("Python version: %s", sys.version.replace("\n", " "))
    logger.info("OpenCV version: %s", cv2.__version__)

    library_usage = [
        ("opencv-python", cv2.__version__, "USB capture, JPEG decode, dashboard rendering"),
        ("fastapi", fastapi.__version__, "phone camera HTTP page and WebSocket endpoint"),
        ("uvicorn", uvicorn.__version__, "ASGI server for phone camera mode"),
        ("numpy", np.__version__, "frame arrays and image buffers"),
        ("qrcode", getattr(qrcode, "__version__", "unknown"), "QR code generation for phone pairing"),
    ]

    try:
        import psutil

        library_usage.append(("psutil", psutil.__version__, "optional runtime diagnostics"))
        logger.info("CPU count: %s", psutil.cpu_count())
        logger.info("Memory total MB: %.1f", psutil.virtual_memory().total / (1024 * 1024))
    except Exception:
        logger.info("psutil is not available; optional runtime diagnostics disabled.")

    for name, version, reason in library_usage:
        logger.info("Imported library: %s version=%s reason=%s", name, version, reason)

    logger.info("Wellness note: this prototype is not a medical device or diagnostic system.")
