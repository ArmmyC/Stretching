from __future__ import annotations

import logging
import socket


def get_local_ip() -> str:
    """Return the LAN IP address phones should use to reach the station."""
    logger = logging.getLogger(__name__)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip_address = sock.getsockname()[0]
            logger.info("Detected local IP address for QR page: %s", ip_address)
            return ip_address
    except Exception:
        logger.exception("Primary local IP detection failed. Falling back to hostname lookup.")

    try:
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        logger.info("Detected local IP from hostname %s: %s", hostname, ip_address)
        return ip_address
    except Exception:
        logger.exception("Hostname IP detection failed. Falling back to 127.0.0.1.")
        return "127.0.0.1"
