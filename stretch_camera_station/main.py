from __future__ import annotations

import argparse
import logging
import os
import platform
import sys
import time

from app import config
from app.camera.camera_manager import CameraManager
from app.logging_setup import setup_logging
from app.processing.pipeline import ProcessingPipeline
from app.utils.diagnostics import RuntimeEventLog, log_startup_diagnostics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smart Stretch Coach camera station for Arduino UNO Q."
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "usb", "phone"],
        default="auto",
        help="Startup camera mode. auto tries USB first, then phone QR.",
    )
    parser.add_argument(
        "--host",
        default=config.SERVER_HOST,
        help="Phone camera web server bind host.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=config.SERVER_PORT,
        help="Phone camera web server port.",
    )
    parser.add_argument(
        "--public-host",
        default=config.PUBLIC_HOST,
        help="Host/IP advertised to phones. Use this for Tailscale, for example 100.x.y.z.",
    )
    parser.add_argument(
        "--https",
        action="store_true",
        default=config.USE_HTTPS,
        help="Enable HTTPS for phone camera mode when cert and key are provided.",
    )
    parser.add_argument(
        "--ssl-cert",
        default=config.SSL_CERTFILE,
        help="Path to a TLS certificate file for HTTPS phone camera mode.",
    )
    parser.add_argument(
        "--ssl-key",
        default=config.SSL_KEYFILE,
        help="Path to a TLS private key file for HTTPS phone camera mode.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=config.HEADLESS,
        help="Run without the OpenCV GUI dashboard. Useful for Arduino App Lab.",
    )
    return parser.parse_args()


def run_headless_loop(
    manager: CameraManager,
    pipeline: ProcessingPipeline,
    event_log: RuntimeEventLog,
) -> None:
    """Run the camera and processing loop without opening an OpenCV window."""
    logger = logging.getLogger(__name__)
    event_log.add("Headless station loop started. No OpenCV dashboard window will open.")

    if manager.get_info().get("source_type") == config.SOURCE_PHONE:
        phone_url = manager.get_phone_url()
        if phone_url:
            event_log.add(f"Phone camera URL: {phone_url}")

    last_status_time = 0.0
    while True:
        frame = manager.read()
        result = pipeline.process(frame)
        now = time.monotonic()

        if now - last_status_time >= 5.0:
            info = manager.get_info()
            frame_size = info.get("frame_size")
            resolution = f"{frame_size[0]}x{frame_size[1]}" if frame_size else "N/A"
            logger.info(
                "Headless status source=%s status=%s fps=%.1f resolution=%s stretch_state=%s message=%s",
                info.get("source_type", config.SOURCE_NONE),
                info.get("connection_status", "UNKNOWN"),
                float(info.get("fps") or 0.0),
                resolution,
                result.get("stretch_state"),
                result.get("message"),
            )
            last_status_time = now

        time.sleep(0.02 if frame is not None else 0.08)


def should_run_headless(requested_headless: bool, event_log: RuntimeEventLog) -> bool:
    if requested_headless:
        return True

    if platform.system().lower() != "linux":
        return False

    has_display = bool(os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"))
    if has_display:
        return False

    event_log.add(
        "No DISPLAY or WAYLAND_DISPLAY found. Running headless instead of opening the OpenCV dashboard.",
        level=logging.WARNING,
    )
    return True


def main() -> int:
    args = parse_args()
    log_path = setup_logging()
    logger = logging.getLogger(__name__)
    event_log = RuntimeEventLog()

    log_startup_diagnostics(event_log, log_path)

    manager = CameraManager(
        event_log=event_log,
        server_host=args.host,
        server_port=args.port,
        public_host=args.public_host,
        use_https=args.https,
        ssl_certfile=args.ssl_cert,
        ssl_keyfile=args.ssl_key,
    )
    pipeline = ProcessingPipeline(event_log=event_log)
    dashboard = None

    try:
        if args.mode == "usb":
            manager.force_usb()
        elif args.mode == "phone":
            manager.force_phone()
        else:
            manager.start_auto()

        run_headless = should_run_headless(args.headless, event_log)
        if run_headless:
            manager.start_status_web_server()
            run_headless_loop(manager, pipeline, event_log)
        else:
            from app.dashboard.opencv_dashboard import OpenCVDashboard

            dashboard = OpenCVDashboard(
                camera_manager=manager,
                pipeline=pipeline,
                event_log=event_log,
            )
            dashboard.run()
        return 0
    except KeyboardInterrupt:
        event_log.add("Keyboard interrupt received. Shutting down.")
        return 0
    except Exception:
        logger.exception("Fatal error in Smart Stretch Coach station.")
        event_log.add(
            "Fatal error occurred. See log file for stack trace.",
            level=logging.ERROR,
        )
        return 1
    finally:
        try:
            if dashboard is not None:
                dashboard.stop()
        finally:
            manager.stop()
            event_log.add("Smart Stretch Coach station stopped.")


if __name__ == "__main__":
    sys.exit(main())
