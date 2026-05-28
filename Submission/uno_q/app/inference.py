from __future__ import annotations

import logging
import os
import threading
from datetime import datetime
from typing import Any

import cv2
import numpy as np

from app.pose_tracker import DEFAULT_MODEL_PATH, PoseTracker

logger = logging.getLogger(__name__)

POSE_TRACKING_ENABLED = os.getenv("POSE_TRACKING_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
POSE_MODEL_PATH = os.getenv("POSE_MODEL_PATH", DEFAULT_MODEL_PATH)
POSE_DRAW_LANDMARKS = os.getenv("POSE_DRAW_LANDMARKS", "true").strip().lower() in {"1", "true", "yes", "on"}
POSE_BACKEND = os.getenv("POSE_BACKEND", "mediapipe").strip().lower() or "mediapipe"

_pose_tracker: PoseTracker | None = None
_pose_tracker_lock = threading.Lock()
_last_pose_metrics: dict[str, Any] = {}
_pose_disabled_logged = False


def process_frame(frame: np.ndarray, context: dict[str, Any] | None = None) -> tuple[np.ndarray, dict[str, Any]]:
    """Process one camera frame and return a clean frame plus metrics.

    This is still not a scoring layer. It only adds camera pose flags that can
    later be fused with Nano IMU and UNO Q hardware feedback.
    """
    global _last_pose_metrics

    context = context or {}
    try:
        output = frame.copy()
        score = int(context.get("score") or 0)
        timestamp = datetime.now().strftime("%H:%M:%S")

        if POSE_TRACKING_ENABLED:
            pose_context = {**context, "draw_landmarks": POSE_DRAW_LANDMARKS}
            output, pose_metrics = get_pose_tracker().process(output, pose_context)
        else:
            pose_metrics = _pose_disabled_metrics()

        if bool(context.get("draw_frame_labels", True)):
            _draw_frame_labels(output, context, pose_metrics)

        metrics = {
            **pose_metrics,
            "pose_landmarks": pose_metrics.get("landmarks") or None,
            "score": score,
            "message": "Pose tracking active" if pose_metrics.get("pose_enabled") else "Pose tracking unavailable",
            "timestamp": timestamp,
        }
        _last_pose_metrics = metrics
        return output, metrics
    except Exception:
        logger.exception("Inference hook processing error")
        metrics = {
            **_pose_disabled_metrics(),
            "score": 0,
            "pose_landmarks": None,
            "message": "Inference hook error; raw stream preserved",
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }
        _last_pose_metrics = metrics
        return frame, metrics


def get_pose_status(debug: bool = False) -> dict[str, Any]:
    if POSE_TRACKING_ENABLED:
        status = get_pose_tracker().get_status()
    else:
        status = {
            **_pose_disabled_metrics(),
            "model_path": POSE_MODEL_PATH,
            "model_loaded": False,
        }

    if debug and _last_pose_metrics.get("landmarks"):
        status["landmarks"] = _last_pose_metrics["landmarks"]
    return status


def get_pose_tracker() -> PoseTracker:
    global _pose_tracker

    with _pose_tracker_lock:
        if _pose_tracker is None:
            _pose_tracker = PoseTracker(model_path=POSE_MODEL_PATH, enabled=POSE_TRACKING_ENABLED)
        return _pose_tracker


def _pose_disabled_metrics() -> dict[str, Any]:
    global _pose_disabled_logged

    if not POSE_TRACKING_ENABLED and not _pose_disabled_logged:
        logger.info("Pose tracking disabled by POSE_TRACKING_ENABLED=false.")
        _pose_disabled_logged = True

    return {
        "pose_enabled": False,
        "pose_backend": POSE_BACKEND,
        "pose_ok": False,
        "user_visible": False,
        "upper_body_visible": False,
        "full_body_visible": False,
        "arm_raised": False,
        "torso_centered": False,
        "confidence": 0.0,
        "fps_pose": 0.0,
        "last_pose_timestamp": None,
        "landmarks": {},
    }


def _draw_frame_labels(frame: np.ndarray, context: dict[str, Any], pose_metrics: dict[str, Any]) -> None:
    h, w = frame.shape[:2]
    panel_w = min(430, max(300, w - 20))
    panel_h = 148
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (10 + panel_w, min(h - 10, 10 + panel_h)), (10, 18, 22), -1)
    cv2.addWeighted(overlay, 0.68, frame, 0.32, 0, frame)

    source_name = str(context.get("source_label") or "Camera")
    session_state = str(context.get("session_state") or "READY")
    fps_pose = float(pose_metrics.get("fps_pose") or 0.0)

    y = 34
    cv2.putText(frame, source_name, (22, y), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (238, 246, 248), 2, cv2.LINE_AA)
    y += 28
    cv2.putText(frame, f"Session: {session_state}", (22, y), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (190, 205, 212), 1, cv2.LINE_AA)
    y += 28
    cv2.putText(frame, _flag_line("User", pose_metrics.get("user_visible")), (22, y), cv2.FONT_HERSHEY_SIMPLEX, 0.52, _flag_color(pose_metrics.get("user_visible")), 1, cv2.LINE_AA)
    y += 24
    cv2.putText(frame, _flag_line("Arm raised", pose_metrics.get("arm_raised")), (22, y), cv2.FONT_HERSHEY_SIMPLEX, 0.52, _flag_color(pose_metrics.get("arm_raised")), 1, cv2.LINE_AA)
    y += 24
    cv2.putText(frame, _flag_line("Torso centered", pose_metrics.get("torso_centered")), (22, y), cv2.FONT_HERSHEY_SIMPLEX, 0.52, _flag_color(pose_metrics.get("torso_centered")), 1, cv2.LINE_AA)
    cv2.putText(frame, f"Pose FPS: {fps_pose:.1f}", (220, y), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (210, 225, 232), 1, cv2.LINE_AA)


def _flag_line(label: str, value: Any) -> str:
    return f"{label}: {'yes' if bool(value) else 'no'}"


def _flag_color(value: Any) -> tuple[int, int, int]:
    return (95, 240, 135) if bool(value) else (90, 170, 245)
