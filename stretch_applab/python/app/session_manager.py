from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

from app.stretch_models import evaluate_stretch_model


READY_SECONDS = 5
STRETCH_SECONDS = 30
REST_SECONDS = 10


@dataclass(frozen=True)
class StretchDefinition:
    name: str
    score_hint: str = "steady_hold"
    needs_arm_raised: bool = False
    needs_full_body: bool = False
    model_key: str | None = None


ROUTINES = {
    "before": ["Arm circles", "Hip opener", StretchDefinition("Hamstring sweep", "hamstring_reach", needs_full_body=True, model_key="hamstring_reach")],
    "after": [
        StretchDefinition("Hamstring reach", "hamstring_reach", needs_full_body=True, model_key="hamstring_reach"),
        StretchDefinition("Overhead reach hold", "overhead_hold", needs_arm_raised=True),
        StretchDefinition("Standing side bend stretch", "side_bend", needs_arm_raised=True, model_key="side_bend"),
        StretchDefinition("Doorway chest opener", "open_chest"),
    ],
    "after_upper": [
        StretchDefinition("Wall slides", "overhead_control", needs_arm_raised=True),
        StretchDefinition("Overhead reach hold", "overhead_hold", needs_arm_raised=True),
        StretchDefinition("Standing side bend stretch", "side_bend", needs_arm_raised=True, model_key="side_bend"),
        StretchDefinition("Doorway chest opener", "open_chest"),
        StretchDefinition("Shoulder external rotation", "controlled_rotation"),
    ],
    "upper": [
        StretchDefinition("Arm circles", "controlled_rotation"),
        StretchDefinition("Wall slides", "overhead_control", needs_arm_raised=True),
        StretchDefinition("Standing side bend stretch", "side_bend", needs_arm_raised=True, model_key="side_bend"),
        StretchDefinition("Overhead reach hold", "overhead_hold", needs_arm_raised=True),
        StretchDefinition("Doorway chest opener", "open_chest"),
    ],
    "lower": ["Quad stretch", StretchDefinition("Hamstring stretch", "hamstring_reach", needs_full_body=True, model_key="hamstring_reach"), "Calf stretch"],
    "full": ["Shoulder stretch", "Hip opener", StretchDefinition("Hamstring stretch", "hamstring_reach", needs_full_body=True, model_key="hamstring_reach")],
}


def _safe_float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None

INSTRUCTIONS = {
    "IDLE": "Press Start",
    "READY": "Get ready",
    "REST": "Rest",
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
        self._current_step = 0
        self._phase = "ready"
        self._complete = False

    def start(self) -> dict[str, Any]:
        with self._lock:
            if not self._running:
                self._started_at = time.monotonic()
                self._paused_elapsed = 0.0
                self._running = True
                self._paused = False
                if self._complete:
                    self._current_step = 0
                    self._current_index = 0
                    self._phase = "ready"
                    self._complete = False
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
            self._complete = False
            self._current_step = min(self._current_step + 1, max(0, self._target_stretches_locked() - 1))
            self._current_index = self._current_step % max(1, len(routine))
            self._phase = "stretch"
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
            self._current_step = 0
            self._phase = "ready"
            self._complete = False
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
            routine = self._routine_locked()
            self._current_step = min(self._current_step, max(0, self._target_stretches_locked() - 1))
            self._current_index = self._current_step % max(1, len(routine))
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

    def _target_stretches_locked(self) -> int:
        return max(1, int((self.config.duration * 60 + STRETCH_SECONDS - 1) // STRETCH_SECONDS))

    def _advance_phase_locked(self) -> None:
        if not self._running or self._paused or self._complete:
            return

        routine = self._routine_locked()
        target_stretches = self._target_stretches_locked()

        while self._running and not self._paused and not self._complete:
            elapsed = self._elapsed_locked()
            if self._phase == "ready":
                if elapsed < READY_SECONDS:
                    break
                self._phase = "stretch"
                self._started_at = time.monotonic() - max(0.0, elapsed - READY_SECONDS)
                self._paused_elapsed = 0.0
                continue

            if self._phase == "stretch":
                if elapsed < STRETCH_SECONDS:
                    break
                if self._current_step >= target_stretches - 1:
                    self._complete = True
                    self._running = False
                    self._paused = False
                    self._started_at = None
                    self._paused_elapsed = 0.0
                    break
                self._current_step += 1
                self._current_index = self._current_step % max(1, len(routine))
                self._phase = "rest"
                self._started_at = time.monotonic() - max(0.0, elapsed - STRETCH_SECONDS)
                self._paused_elapsed = 0.0
                continue

            if self._phase == "rest":
                if elapsed < REST_SECONDS:
                    break
                self._phase = "stretch"
                self._started_at = time.monotonic() - max(0.0, elapsed - REST_SECONDS)
                self._paused_elapsed = 0.0
                continue

            break

    def _state_for_elapsed(self, elapsed: float) -> str:
        if self._complete:
            return "DONE"
        if not self._running:
            return "IDLE"
        if self._phase == "ready":
            return "READY"
        if self._phase == "rest":
            return "REST"
        if elapsed < 20:
            return "HOLD"
        if elapsed < STRETCH_SECONDS:
            return "GOOD"
        return "DONE"

    def _score_locked(
        self,
        state: str,
        elapsed: float,
        stretch: StretchDefinition | str,
        pose_metrics: dict[str, Any] | None = None,
        nano_metrics: dict[str, Any] | None = None,
        stretch_model: dict[str, Any] | None = None,
    ) -> int:
        if state in {"IDLE", "READY"}:
            return 0
        if state == "REST":
            return 0

        if state == "HOLD":
            base = 64 + min(16, int(max(0.0, elapsed) * 0.8))
        elif state == "GOOD":
            base = 84 + min(12, int(max(0.0, elapsed - 20.0) * 1.2))
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

        if stretch_model and stretch_model.get("available"):
            model_score = _safe_float(stretch_model.get("score"))
            if model_score is not None:
                form_multiplier += max(-0.22, min(0.08, (model_score - 68.0) / 260.0))

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
        self._advance_phase_locked()
        routine = self._routine_locked()
        current_stretch = routine[self._current_index]
        current_stretch_name = self._stretch_name(current_stretch)
        elapsed = self._elapsed_locked()
        state = self._state_for_elapsed(elapsed)
        if self._complete:
            elapsed = float(STRETCH_SECONDS)
        phase_limit = READY_SECONDS if state == "READY" else REST_SECONDS if state == "REST" else STRETCH_SECONDS
        remaining = max(0, phase_limit - int(elapsed))
        stretch_model = evaluate_stretch_model(
            current_stretch.model_key if isinstance(current_stretch, StretchDefinition) else None,
            pose_metrics,
            nano_metrics,
        )
        score = self._score_locked(state, elapsed, current_stretch, pose_metrics, nano_metrics, stretch_model)
        total_stretches = self._target_stretches_locked()
        completed_stretch_seconds = min(
            self.config.duration * 60,
            (self._current_step * STRETCH_SECONDS) + (
                STRETCH_SECONDS if self._complete else elapsed if state in {"HOLD", "GOOD", "DONE"} else 0
            ),
        )
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
            "current_step": self._current_step,
            "total_stretches": total_stretches,
            "current_stretch": current_stretch_name,
            "state": state,
            "instruction": INSTRUCTIONS[state],
            "elapsed_time": round(elapsed, 1),
            "remaining_time": remaining,
            "segment_seconds": phase_limit,
            "stretch_seconds": STRETCH_SECONDS,
            "rest_seconds": REST_SECONDS,
            "stretch_time_goal": self.config.duration * 60,
            "stretch_time_completed": round(completed_stretch_seconds, 1),
            "complete": self._complete,
            "stretch_model": stretch_model,
            "score": score,
            "running": self._running,
            "paused": self._paused,
        }
