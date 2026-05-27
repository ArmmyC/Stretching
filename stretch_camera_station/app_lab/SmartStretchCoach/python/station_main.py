from __future__ import annotations

import argparse
import logging
import sys

from app import config
from app.camera.camera_manager import CameraManager
from app.dashboard.opencv_dashboard import OpenCVDashboard
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
    return parser.parse_args()


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
        use_https=args.https,
        ssl_certfile=args.ssl_cert,
        ssl_keyfile=args.ssl_key,
    )
    pipeline = ProcessingPipeline(event_log=event_log)
    dashboard = OpenCVDashboard(
        camera_manager=manager,
        pipeline=pipeline,
        event_log=event_log,
    )

    try:
        if args.mode == "usb":
            manager.force_usb()
        elif args.mode == "phone":
            manager.force_phone()
        else:
            manager.start_auto()

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
            dashboard.stop()
        finally:
            manager.stop()
            event_log.add("Smart Stretch Coach station stopped.")


if __name__ == "__main__":
    sys.exit(main())
