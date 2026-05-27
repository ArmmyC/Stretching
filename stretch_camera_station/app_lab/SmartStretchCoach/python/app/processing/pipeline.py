from __future__ import annotations

import logging
from typing import Any

import numpy as np


class ProcessingPipeline:
    """Frame processing boundary for future pose, ML, and sensor fusion logic."""

    def __init__(self, event_log: Any | None = None) -> None:
        self.logger = logging.getLogger(__name__)
        self.event_log = event_log
        self._processed_frames = 0
        self._log_event("Processing pipeline initialized with placeholder inference.")

        # Future model loading goes here.
        # Examples:
        # - MediaPipe pose graph initialization
        # - TensorFlow Lite interpreter load and tensor allocation
        # - ONNX Runtime session creation
        # - Calibration state for extra sensors fused with camera inference
        self.model = None

    def process(self, frame: np.ndarray | None) -> dict[str, Any]:
        self._processed_frames += 1

        if self._processed_frames == 1 or self._processed_frames % 120 == 0:
            self.logger.debug(
                "Inference placeholder call. frame_available=%s processed_frames=%s",
                frame is not None,
                self._processed_frames,
            )

        # Future per-frame inference goes here.
        # Convert/resize frame, run the model, smooth landmarks, classify stretch
        # state, then return the same field names with real values.
        return {
            "pose_landmarks": None,
            "stretch_state": "NO_MODEL",
            "confidence": 0.0,
            "message": "Inference model not loaded yet",
            "processed_frames": self._processed_frames,
        }

    def _log_event(self, message: str, level: int = logging.INFO) -> None:
        if self.event_log is not None:
            self.event_log.add(message, level=level)
        else:
            self.logger.log(level, message)
