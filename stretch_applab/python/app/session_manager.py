from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StretchDefinition:
    name: str
    score_hint: str = "steady_hold"
    needs_arm_raised: bool = False
    needs_full_body: bool = False


ROUTINES = {
    "before": ["Arm circles", "Hip opener", "Hamstring sweep"],
    "after": [
        StretchDefinition("Cross-body shoulder stretch", "steady_hold"),
        StretchDefinition("Overhead triceps stretch", "overhead_hold", needs_arm_raised=True),
        StretchDefinition("Doorway chest opener", "open_chest"),
        StretchDefinition("Shoulder external rotation", "controlled_rotation"),
    ],
    "after_upper": [
        StretchDefinition("Cross-body shoulder stretch", "steady_hold"),
        StretchDefinition("Overhead triceps stretch", "overhead_hold", needs_arm_raised=True),
        StretchDefinition("Doorway chest opener", "open_chest"),
        StretchDefinition("Shoulder external rotation", "controlled_rotation"),
    ],
    "upper": [
        StretchDefinition("Arm circles", "controlled_rotation"),
        StretchDefinition("Wall slides", "overhead_control", needs_arm_raised=True),
        StretchDefinition("Cross-body shoulder stretch", "steady_hold"),
        StretchDefinition("Overhead triceps stretch", "overhead_hold", needs_arm_raised=True),
    ],
    "lower": ["Quad stretch", "Hamstring stretch", "Calf stretch"],
    "full": ["Shoulder stretch", "Hip opener", "Hamstring stretch"],
}


def _safe_float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None

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
            self.logger.info("Session next stretch index=%s stretch=%s", self._current_index, self._stretch_name(routine[self._current_index]))
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

    def get_status(
        self,
        camera_state: str | None = None,
        pose_metrics: dict[str, Any] | None = None,
        nano_metrics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            status = self._status_locked(pose_metrics=pose_metrics, nano_metrics=nano_metrics)
            if camera_state == "NO_CAMERA":
                status["state"] = "NO_CAMERA"
                status["instruction"] = INSTRUCTIONS["NO_CAMERA"]
            elif camera_state == "WAITING_FOR_PHONE":
                status["state"] = "WAITING_FOR_PHONE"
                status["instruction"] = INSTRUCTIONS["WAITING_FOR_PHONE"]
            return status

    def _routine_locked(self) -> list[StretchDefinition | str]:
        if self.config.body_focus == "upper":
            if self.config.mode == "after":
                return ROUTINES["after_upper"]
            return ROUTINES["upper"]
        if self.config.body_focus == "lower":
            return ROUTINES["lower"]
        if self.config.mode == "before":
            return ROUTINES["before"]
        if self.config.mode == "after":
            return ROUTINES["after"]
        return ROUTINES["full"]

    @staticmethod
    def _stretch_name(stretch: StretchDefinition | str) -> str:
        return stretch.name if isinstance(stretch, StretchDefinition) else stretch

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

    def _score_locked(
        self,
        state: str,
        elapsed: float,
        stretch: StretchDefinition | str,
        pose_metrics: dict[str, Any] | None = None,
        nano_metrics: dict[str, Any] | None = None,
    ) -> int:
        if state in {"IDLE", "READY"}:
            return 0

        if state == "HOLD":
            base = 64 + min(16, int(max(0.0, elapsed - 5.0) * 1.6))
        elif state == "GOOD":
            base = 88 + min(7, int(max(0.0, elapsed - 15.0) * 1.4))
        else:
            base = 100

        if not isinstance(stretch, StretchDefinition) or not pose_metrics:
            form_multiplier = 1.0
        else:
            form_multiplier = 1.0

            pose_ready = bool(pose_metrics.get("pose_enabled") and pose_metrics.get("model_loaded"))
            if pose_ready:
                confidence = float(pose_metrics.get("confidence") or 0.0)
                user_visible = bool(pose_metrics.get("user_visible"))
                torso_centered = bool(pose_metrics.get("torso_centered"))
                full_body_visible = bool(pose_metrics.get("full_body_visible"))
                arm_raised = bool(pose_metrics.get("arm_raised"))

                if confidence < 0.45 or not user_visible:
                    form_multiplier -= 0.32
                if not torso_centered:
                    form_multiplier -= 0.14
                if stretch.needs_full_body and not full_body_visible:
                    form_multiplier -= 0.18
                if stretch.needs_arm_raised and not arm_raised:
                    form_multiplier -= 0.18
                if stretch.score_hint in {"controlled_rotation", "overhead_control"} and confidence >= 0.65:
                    form_multiplier += 0.04

        if nano_metrics and nano_metrics.get("fresh"):
            az = _safe_float(nano_metrics.get("az"))
            roll = _safe_float(nano_metrics.get("roll"))
            top_raise = az is not None and az <= -0.55
            side_raise = roll is not None and 55.0 <= abs(roll) <= 125.0
            nano_arm_raised = bool(nano_metrics.get("arm_raised")) or top_raise or side_raise
            nano_stable = bool(nano_metrics.get("stable"))
            stability_score = _safe_float(nano_metrics.get("stability_score")) or 0.0
            gyro_mag = _safe_float(nano_metrics.get("gyro_mag")) or 0.0
            if isinstance(stretch, StretchDefinition) and stretch.needs_arm_raised and not nano_arm_raised:
                form_multiplier -= 0.18
            if isinstance(stretch, StretchDefinition) and stretch.needs_arm_raised and top_raise:
                form_multiplier += 0.04
            if isinstance(stretch, StretchDefinition) and stretch.score_hint in {"controlled_rotation", "overhead_control"} and side_raise:
                form_multiplier += 0.03
            if state in {"HOLD", "GOOD"}:
                if nano_stable:
                    form_multiplier += 0.06
                else:
                    form_multiplier -= 0.14
                if stability_score > 0:
                    form_multiplier += max(-0.12, min(0.08, (stability_score - 70.0) / 400.0))
                if gyro_mag >= 35.0:
                    form_multiplier -= 0.12

        return max(0, min(100, int(round(base * max(0.45, min(1.04, form_multiplier))))))

    def _status_locked(
        self,
        pose_metrics: dict[str, Any] | None = None,
        nano_metrics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        routine = self._routine_locked()
        current_stretch = routine[self._current_index]
        current_stretch_name = self._stretch_name(current_stretch)
        elapsed = self._elapsed_locked()
        state = self._state_for_elapsed(elapsed)
        remaining = max(0, 20 - int(elapsed))
        score = self._score_locked(state, elapsed, current_stretch, pose_metrics, nano_metrics)
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
            "routine": [self._stretch_name(stretch) for stretch in routine],
            "current_index": self._current_index,
            "current_stretch": current_stretch_name,
            "state": state,
            "instruction": INSTRUCTIONS[state],
            "elapsed_time": round(elapsed, 1),
            "remaining_time": remaining,
            "score": score,
            "running": self._running,
            "paused": self._paused,
        }
