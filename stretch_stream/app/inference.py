from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import numpy as np


def process_frame(frame: np.ndarray, context: dict[str, Any]) -> tuple[np.ndarray, dict[str, Any]]:
    """Process one camera frame and return a clean frame plus metrics.

    Future model insertion point:
    - Load a pose model in a module-level service or injected class.
    - Run pose estimation here using the incoming frame.
    - Replace the placeholder score with real stretch form scoring.
    - Add landmarks, warnings, and confidence to the returned metrics.
    """
    logger = logging.getLogger(__name__)
    try:
        output = frame.copy()
        score = int(context.get("score") or 0)
        timestamp = datetime.now().strftime("%H:%M:%S")

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
