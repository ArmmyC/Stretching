from __future__ import annotations

import io
import logging
import os
import platform
import socket
import sys
from pathlib import Path

import qrcode

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = PROJECT_ROOT / "logs"
APP_LOG = LOG_DIR / "app.log"


def setup_logging() -> None:
    """Log to console and logs/app.log for every kiosk run."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    console.setLevel(logging.INFO)

    file_handler = logging.FileHandler(APP_LOG, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    root.addHandler(console)
    root.addHandler(file_handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def log_startup_details(force_camera_mode: str, public_base_url: str) -> None:
    logger = logging.getLogger(__name__)
    logger.info("YUEDMAI app startup")
    logger.info("OS/platform: %s", platform.platform())
    logger.info("Python version: %s", sys.version.replace("\n", " "))
    logger.info("APP_HOST=%s", os.getenv("APP_HOST", "0.0.0.0"))
    logger.info("APP_PORT=%s", os.getenv("APP_PORT", "8000"))
    logger.info("FORCE_CAMERA_MODE=%s", force_camera_mode)
    logger.info("PUBLIC_BASE_URL=%s", public_base_url or "<auto local IP>")
    logger.info("POSE_TRACKING_ENABLED=%s", os.getenv("POSE_TRACKING_ENABLED", "true"))
    logger.info("POSE_BACKEND=%s", os.getenv("POSE_BACKEND", "mediapipe"))
    logger.info("POSE_DELEGATE=%s", os.getenv("POSE_DELEGATE", "cpu"))
    logger.info("POSE_MODEL_PATH=%s", os.getenv("POSE_MODEL_PATH", "models/pose_landmarker.task"))
    logger.info("POSE_DRAW_LANDMARKS=%s", os.getenv("POSE_DRAW_LANDMARKS", "true"))
    logger.info("POSE_INFERENCE_WIDTH=%s", os.getenv("POSE_INFERENCE_WIDTH", "320"))
    logger.info("POSE_FRAME_STRIDE=%s", os.getenv("POSE_FRAME_STRIDE", "1"))
    logger.info("POSE_ASYNC_ENABLED=%s", os.getenv("POSE_ASYNC_ENABLED", "true"))
    logger.info("POSE_MAX_ASYNC_FPS=%s", os.getenv("POSE_MAX_ASYNC_FPS", "8"))
    logger.info("POSE_FALLBACK_BACKEND=%s", os.getenv("POSE_FALLBACK_BACKEND", "movenet"))
    logger.info("NCNN_MODEL_DIR=%s", os.getenv("NCNN_MODEL_DIR", "models/yolov8n-pose_ncnn_model"))
    logger.info("NCNN_INPUT_SIZE=%s", os.getenv("NCNN_INPUT_SIZE", "320"))
    logger.info("NCNN_USE_VULKAN=%s", os.getenv("NCNN_USE_VULKAN", "true"))
    logger.info("NCNN_GPU_INDEX=%s", os.getenv("NCNN_GPU_INDEX", "0"))
    logger.info("MOVENET_MODEL_PATH=%s", os.getenv("MOVENET_MODEL_PATH", "models/movenet_lightning.tflite"))
    logger.info("MOVENET_INPUT_SIZE=%s", os.getenv("MOVENET_INPUT_SIZE", "192"))
    logger.info("MOVENET_NUM_THREADS=%s", os.getenv("MOVENET_NUM_THREADS", "2"))


def get_env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        logging.getLogger(__name__).warning("Invalid integer for %s. Using %s.", name, default)
        return default


def get_local_ip() -> str:
    """Find the LAN IP that another device in the room can usually reach."""
    logger = logging.getLogger(__name__)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip_address = sock.getsockname()[0]
            logger.info("Detected local IP: %s", ip_address)
            return ip_address
    except Exception:
        logger.exception("Primary local IP detection failed.")

    try:
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        logger.info("Detected local IP from hostname %s: %s", hostname, ip_address)
        return ip_address
    except Exception:
        logger.exception("Hostname IP detection failed. Falling back to 127.0.0.1.")
        return "127.0.0.1"


def build_base_url() -> str:
    public_base_url = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if public_base_url:
        return public_base_url

    port = get_env_int("APP_PORT", 8000)
    return f"http://{get_local_ip()}:{port}"


def make_qr_png_bytes(url: str) -> bytes:
    image = qrcode.make(url)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
