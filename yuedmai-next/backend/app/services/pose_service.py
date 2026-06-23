from __future__ import annotations

import random
from dataclasses import dataclass

from app.services.scoring import PoseSignal


@dataclass(frozen=True)
class PoseResult:
    signal: PoseSignal
    message: str


class PoseService:
    """Server-side pose adapter.

    The starter uses mock values so the frontend/backend contract can be built first.
    Replace `evaluate_frame` with MediaPipe, MoveNet, or another server-hosted model.
    """

    def evaluate_frame(self, frame_hint: dict | None = None) -> PoseResult:
        confidence = random.uniform(0.55, 0.92)
        signal = PoseSignal(
            visible=True,
            centered=confidence > 0.62,
            confidence=confidence,
            steady=confidence > 0.68,
            hold_seconds=float((frame_hint or {}).get("holdSeconds") or 0),
        )
        message = "Hold steady" if signal.steady else "Center yourself and slow down"
        return PoseResult(signal=signal, message=message)


pose_service = PoseService()
