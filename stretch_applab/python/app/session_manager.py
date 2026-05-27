from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any


ROUTINES = {
    "before": ["Arm circles", "Hip opener", "Hamstring sweep"],
    "after": ["Shoulder stretch", "Quad stretch", "Hamstring stretch"],
    "upper": ["Shoulder stretch", "Chest opener", "Triceps stretch"],
    "lower": ["Quad stretch", "Hamstring stretch", "Calf stretch"],
    "full": ["Shoulder stretch", "Hip opener", "Hamstring stretch"],
}

INSTRUCTIONS = {
    "IDLE": "Press Start",
    "READY": "Get ready",
    "HOLD": "Hold the stretch",
    "GOOD": "Good, keep steady",
    "DONE": "Stretch complete",
    "NO_CAMERA": "No camera",
    "WAITING_FOR_PHONE": "Scan QR",
}


@dataclass
class SessionConfig:
    mode: str = "before"
    body_focus: str = "full"
    duration: int = 5


class SessionManager:
    """Small fake stretch-session state machine for the hackathon UI."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self._lock = threading.Lock()
        self.config = SessionConfig()
        self._running = False
        self._paused = False
        self._started_at: float | None = None
        self._paused_elapsed = 0.0
        self._current_index = 0

    def start(self) -> dict[str, Any]:
        with self._lock:
            if not self._running:
                self._started_at = time.monotonic()
                self._paused_elapsed = 0.0
                self._running = True
                self._paused = False
            elif self._paused:
                self._started_at = time.monotonic() - self._paused_elapsed
                self._paused = False
            self.logger.info("Session start mode=%s body_focus=%s duration=%s", self.config.mode, self.config.body_focus, self.config.duration)
            return self._status_locked()

    def pause(self) -> dict[str, Any]:
        with self._lock:
            if self._running and not self._paused:
                self._paused_elapsed = self._elapsed_locked()
                self._paused = True
            self.logger.info("Session pause elapsed=%.1f", self._paused_elapsed)
            return self._status_locked()

    def next(self) -> dict[str, Any]:
        with self._lock:
            routine = self._routine_locked()
            self._current_index = min(self._current_index + 1, max(0, len(routine) - 1))
            self._started_at = time.monotonic()
            self._paused_elapsed = 0.0
            self._running = True
            self._paused = False
            self.logger.info("Session next stretch index=%s stretch=%s", self._current_index, routine[self._current_index])
            return self._status_locked()

    def reset(self) -> dict[str, Any]:
        with self._lock:
            self._running = False
            self._paused = False
            self._started_at = None
            self._paused_elapsed = 0.0
            self._current_index = 0
            self.logger.info("Session reset")
            return self._status_locked()

    def configure(self, mode: str | None = None, body_focus: str | None = None, duration: int | None = None) -> dict[str, Any]:
        with self._lock:
            if mode in {"before", "after"}:
                self.config.mode = mode
            if body_focus in {"upper", "lower", "full"}:
                self.config.body_focus = body_focus
            if duration in {3, 5, 8}:
                self.config.duration = int(duration)
            self._current_index = min(self._current_index, len(self._routine_locked()) - 1)
            self.logger.info(
                "Session config mode=%s body_focus=%s duration=%s",
                self.config.mode,
                self.config.body_focus,
                self.config.duration,
            )
            return self._status_locked()

    def get_status(self, camera_state: str | None = None) -> dict[str, Any]:
        with self._lock:
            status = self._status_locked()
            if camera_state == "NO_CAMERA":
                status["state"] = "NO_CAMERA"
                status["instruction"] = INSTRUCTIONS["NO_CAMERA"]
            elif camera_state == "WAITING_FOR_PHONE":
                status["state"] = "WAITING_FOR_PHONE"
                status["instruction"] = INSTRUCTIONS["WAITING_FOR_PHONE"]
            return status

    def _routine_locked(self) -> list[str]:
        if self.config.body_focus == "upper":
            return ROUTINES["upper"]
        if self.config.body_focus == "lower":
            return ROUTINES["lower"]
        if self.config.mode == "before":
            return ROUTINES["before"]
        if self.config.mode == "after":
            return ROUTINES["after"]
        return ROUTINES["full"]

    def _elapsed_locked(self) -> float:
        if not self._running:
            return 0.0
        if self._paused:
            return self._paused_elapsed
        if self._started_at is None:
            return 0.0
        return max(0.0, time.monotonic() - self._started_at)

    def _state_for_elapsed(self, elapsed: float) -> str:
        if not self._running:
            return "IDLE"
        if elapsed < 5:
            return "READY"
        if elapsed < 15:
            return "HOLD"
        if elapsed < 20:
            return "GOOD"
        return "DONE"

    def _status_locked(self) -> dict[str, Any]:
        routine = self._routine_locked()
        current_stretch = routine[self._current_index]
        elapsed = self._elapsed_locked()
        state = self._state_for_elapsed(elapsed)
        remaining = max(0, 20 - int(elapsed))
        score = 0 if state in {"IDLE", "READY"} else 72 if state == "HOLD" else 88 if state == "GOOD" else 100
        return {
            "mode": self.config.mode,
            "mode_label": "Before Workout" if self.config.mode == "before" else "After Workout",
            "body_focus": self.config.body_focus,
            "body_focus_label": {
                "upper": "Upper Body",
                "lower": "Lower Body",
                "full": "Full Body",
            }[self.config.body_focus],
            "duration": self.config.duration,
            "routine": routine,
            "current_index": self._current_index,
            "current_stretch": current_stretch,
            "state": state,
            "instruction": INSTRUCTIONS[state],
            "elapsed_time": round(elapsed, 1),
            "remaining_time": remaining,
            "score": score,
            "running": self._running,
            "paused": self._paused,
        }
