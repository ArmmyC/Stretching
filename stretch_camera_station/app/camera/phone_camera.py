from __future__ import annotations

import logging
from typing import Any

import numpy as np

from app import config
from app.camera.base import CameraSource
from app.server.web_server import PhoneFrameBuffer, PhoneWebServer
from app.utils.network import get_local_ip
from app.utils.qr import make_qr_bgr


class PhoneWebSocketCameraSource(CameraSource):
    """Phone browser camera source using a QR-launched WebSocket page."""

    source_type = config.SOURCE_PHONE

    def __init__(
        self,
        event_log: Any | None = None,
        host: str = config.SERVER_HOST,
        port: int = config.SERVER_PORT,
        public_host: str = config.PUBLIC_HOST,
        use_https: bool = config.USE_HTTPS,
        ssl_certfile: str = config.SSL_CERTFILE,
        ssl_keyfile: str = config.SSL_KEYFILE,
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.event_log = event_log
        self.local_ip = public_host.strip() or get_local_ip()
        self.buffer = PhoneFrameBuffer(event_log=event_log)
        self.server = PhoneWebServer(
            frame_buffer=self.buffer,
            local_ip=self.local_ip,
            host=host,
            port=port,
            use_https=use_https,
            ssl_certfile=ssl_certfile,
            ssl_keyfile=ssl_keyfile,
            event_log=event_log,
        )
        self._active = False
        self._qr_image: np.ndarray | None = None

    @property
    def connection_url(self) -> str:
        return self.server.connection_url

    @property
    def qr_image(self) -> np.ndarray | None:
        if self._qr_image is None:
            self._qr_image = make_qr_bgr(self.connection_url)
        return self._qr_image

    def start(self) -> bool:
        self.logger.info("Starting phone QR camera mode. URL=%s", self.connection_url)
        started = self.server.start()
        self._active = started
        if started:
            self._qr_image = make_qr_bgr(self.connection_url)
            self._log_event(f"Phone QR camera mode active at {self.connection_url}")
        else:
            self._log_event("Phone QR camera web server failed to start.", logging.ERROR)
        return started

    def read(self) -> np.ndarray | None:
        return self.buffer.get_latest_frame()

    def stop(self) -> None:
        self.logger.info("Stopping phone QR camera mode.")
        self.server.stop()
        self._active = False

    def is_active(self) -> bool:
        return self._active and self.server.is_running()

    def get_info(self) -> dict[str, Any]:
        buffer_info = self.buffer.get_info()
        return {
            "source_type": self.source_type,
            "active": self.is_active(),
            "connection_status": buffer_info["connection_status"],
            "url": self.connection_url,
            "local_ip": self.local_ip,
            "fps": buffer_info["fps"],
            "target_fps": config.PHONE_TARGET_FPS,
            "frame_size": buffer_info["frame_size"],
            "timestamp": buffer_info["timestamp"],
            "connected_clients": buffer_info["connected_clients"],
            "frames_received": buffer_info["frames_received"],
            "decode_errors": buffer_info["decode_errors"],
        }

    def _log_event(self, message: str, level: int = logging.INFO) -> None:
        if self.event_log is not None:
            self.event_log.add(message, level=level)
        else:
            self.logger.log(level, message)
