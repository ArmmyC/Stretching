from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import cv2
import numpy as np


def process_frame(frame: np.ndarray, context: dict[str, Any]) -> tuple[np.ndarray, dict[str, Any]]:
    """Process one camera frame and return an annotated frame plus metrics.

    Future model insertion point:
    - Load a pose model in a module-level service or injected class.
    - Run pose estimation here using the incoming frame.
    - Replace the placeholder score with real stretch form scoring.
    - Add landmarks, warnings, and confidence to the returned metrics.
    """
    logger = logging.getLogger(__name__)
    try:
        output = frame.copy()
        source_name = context.get("source_label", "No Camera")
        fps = float(context.get("fps") or 0.0)
        session_state = context.get("session_state", "IDLE")
        score = int(context.get("score") or 0)
        timestamp = datetime.now().strftime("%H:%M:%S")

        draw_overlay(output, source_name, fps, timestamp, session_state, score)
        metrics = {
            "pose_landmarks": None,
            "score": score,
            "confidence": 0.0,
            "message": "Inference model not loaded yet",
            "timestamp": timestamp,
        }
        return output, metrics
    except Exception:
        logger.exception("Inference hook processing error")
        return frame, {
            "pose_landmarks": None,
            "score": 0,
            "confidence": 0.0,
            "message": "Inference hook error",
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }


def draw_overlay(
    frame: np.ndarray,
    source_name: str,
    fps: float,
    timestamp: str,
    session_state: str,
    score: int,
) -> None:
    h, w = frame.shape[:2]
    panel_h = 92
    cv2.rectangle(frame, (0, 0), (w, panel_h), (8, 12, 16), thickness=-1)
    cv2.addWeighted(frame[:panel_h, :], 0.72, np.zeros_like(frame[:panel_h, :]), 0.28, 0, frame[:panel_h, :])

    lines = [
        f"{source_name}  |  {fps:.1f} FPS  |  {timestamp}",
        f"State: {session_state}  |  Score: {score}",
    ]
    y = 32
    for text in lines:
        cv2.putText(frame, text, (24, y), cv2.FONT_HERSHEY_SIMPLEX, 0.78, (245, 250, 252), 2, cv2.LINE_AA)
        y += 36

    cv2.rectangle(frame, (0, h - 8), (int(w * min(score, 100) / 100), h), (141, 245, 33), thickness=-1)
