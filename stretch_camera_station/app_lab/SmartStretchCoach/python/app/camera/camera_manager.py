from __future__ import annotations

import logging
from typing import Any

import numpy as np

from app import config
from app.camera.base import CameraSource
from app.camera.phone_camera import PhoneWebSocketCameraSource
from app.camera.usb_camera import USBCameraSource


class CameraManager:
    """Owns camera source selection, mode switching, and runtime fallback."""

    def __init__(
        self,
        event_log: Any | None = None,
        server_host: str = config.SERVER_HOST,
        server_port: int = config.SERVER_PORT,
        public_host: str = config.PUBLIC_HOST,
        use_https: bool = config.USE_HTTPS,
        ssl_certfile: str = config.SSL_CERTFILE,
        ssl_keyfile: str = config.SSL_KEYFILE,
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.event_log = event_log
        self.server_host = server_host
        self.server_port = server_port
        self.public_host = public_host
        self.use_https = use_https
        self.ssl_certfile = ssl_certfile
        self.ssl_keyfile = ssl_keyfile
        self.active_source: CameraSource | None = None
        self.phone_source: PhoneWebSocketCameraSource | None = None

    def start_auto(self) -> None:
        self._log_event("Starting automatic camera selection: USB first, phone QR fallback.")
        usb_source = USBCameraSource()
        if usb_source.start():
            self._replace_active_source(usb_source)
            self._log_event("Selected USB_CAMERA because a working USB camera returned frames.")
            return

        usb_source.stop()
        self._log_event("No working USB camera detected. Falling back to PHONE_QR mode.")
        self.force_phone()

    def restart_detection(self) -> None:
        self._log_event("Restarting camera detection from dashboard request.")
        self.stop()
        self.start_auto()

    def force_phone(self) -> None:
        self._log_event("Forcing PHONE_QR camera mode.")
        if self.phone_source is None:
            self.phone_source = PhoneWebSocketCameraSource(
                event_log=self.event_log,
                host=self.server_host,
                port=self.server_port,
                public_host=self.public_host,
                use_https=self.use_https,
                ssl_certfile=self.ssl_certfile,
                ssl_keyfile=self.ssl_keyfile,
            )

        if self.phone_source.start():
            self._replace_active_source(self.phone_source, stop_old=True)
        else:
            self._log_event("PHONE_QR mode could not start. Dashboard will continue without frames.", logging.ERROR)

    def force_usb(self) -> None:
        self._log_event("Forcing USB_CAMERA mode.")
        usb_source = USBCameraSource()
        if usb_source.start():
            self._replace_active_source(usb_source)
            self._log_event("USB_CAMERA mode active from dashboard request.")
        else:
            usb_source.stop()
            self._log_event("USB_CAMERA force request failed: no working USB camera found.", logging.ERROR)

    def read(self) -> np.ndarray | None:
        if self.active_source is None:
            return None

        frame = self.active_source.read()
        if (
            frame is None
            and self.active_source.source_type == config.SOURCE_USB
            and not self.active_source.is_active()
        ):
            self._log_event(
                "USB_CAMERA became inactive during runtime. Falling back to PHONE_QR mode.",
                logging.ERROR,
            )
            self.force_phone()
        return frame

    def get_info(self) -> dict[str, Any]:
        if self.active_source is None:
            return {
                "source_type": config.SOURCE_NONE,
                "active": False,
                "connection_status": "NO_SOURCE",
                "fps": 0.0,
                "frame_size": None,
                "timestamp": "",
            }
        return self.active_source.get_info()

    def get_qr_image(self) -> np.ndarray | None:
        if self.active_source and self.active_source.source_type == config.SOURCE_PHONE:
            assert self.phone_source is not None
            return self.phone_source.qr_image
        return None

    def get_phone_url(self) -> str:
        if self.phone_source is None:
            return ""
        return self.phone_source.connection_url

    def stop(self) -> None:
        if self.active_source is not None:
            self.active_source.stop()
        if self.phone_source is not None and self.phone_source is not self.active_source:
            self.phone_source.stop()
        self.active_source = None

    def _replace_active_source(self, new_source: CameraSource, stop_old: bool = True) -> None:
        if self.active_source is not None and self.active_source is not new_source and stop_old:
            self.active_source.stop()
        self.active_source = new_source
        self.logger.info("Active camera source is now %s", new_source.source_type)

    def _log_event(self, message: str, level: int = logging.INFO) -> None:
        if self.event_log is not None:
            self.event_log.add(message, level=level)
        else:
            self.logger.log(level, message)
