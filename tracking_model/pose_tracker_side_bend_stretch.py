#!/usr/bin/env python3
"""
Standing Side Bend / Overhead Side Stretch Coach built on pose_tracker.py.

Run:
    conda run -n ai_env python pose_tracker_side_bend_stretch.py

This standalone prototype does not modify pose_tracker.py. It uses the same
PoseTracker/fallback chain as pose_tracker_hamstring_reach.py, then scores:
  - wrist(s) raised overhead
  - torso laterally tilted
  - arm(s) mostly extended
  - reach drifting to the same side as the bend
"""

from __future__ import annotations

import argparse
import logging
import math
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from pose_tracker_hamstring_reach import (
    EPSILON,
    MODEL_PATH,
    build_tracker,
    clamp01,
    ema_metrics,
    ema_value,
    open_camera,
    put_text,
)


HOLD_SECONDS_REQUIRED = 3.0
SUCCESS_SCORE_THRESHOLD = 75.0
DEFAULT_SMOOTHING_ALPHA = 0.25


@dataclass(frozen=True)
class SideBendHyperparameters:
    overhead_good_widths: float = 0.75
    overhead_bad_widths: float = 0.10
    tilt_good_deg: float = 15.0
    tilt_bad_deg: float = 3.0
    elbow_good_deg: float = 150.0
    elbow_bad_deg: float = 105.0
    side_reach_good_widths: float = 0.28
    side_reach_bad_widths: float = 0.02
    overhead_weight: float = 0.35
    tilt_weight: float = 0.35
    elbow_weight: float = 0.20
    side_reach_weight: float = 0.10

    def normalized_weights(self) -> dict[str, float]:
        weights = {
            "overhead": max(0.0, self.overhead_weight),
            "tilt": max(0.0, self.tilt_weight),
            "elbow": max(0.0, self.elbow_weight),
            "side_reach": max(0.0, self.side_reach_weight),
        }
        total = sum(weights.values())
        if total < EPSILON:
            return {"overhead": 0.35, "tilt": 0.35, "elbow": 0.20, "side_reach": 0.10}
        return {key: value / total for key, value in weights.items()}


DEFAULT_HYPERPARAMS = SideBendHyperparameters()


def point(landmarks: dict[str, dict[str, float]], name: str) -> Optional[np.ndarray]:
    lm = landmarks.get(name)
    if not lm:
        return None
    return np.asarray([float(lm.get("x", 0.0)), float(lm.get("y", 0.0)), float(lm.get("z", 0.0))], dtype=np.float32)


def vector_angle_degrees(v1: np.ndarray, v2: np.ndarray) -> float:
    denom = float(np.linalg.norm(v1) * np.linalg.norm(v2))
    if denom < EPSILON:
        return float("nan")
    cos_theta = float(np.dot(v1, v2) / denom)
    return math.degrees(math.acos(float(np.clip(cos_theta, -1.0, 1.0))))


def angle_degrees(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    return vector_angle_degrees(a - b, c - b)


def normalize_score(value: float, good: float, bad: float, higher_is_better: bool = True) -> float:
    if not np.isfinite(value):
        return 0.0
    if higher_is_better:
        return 100.0 * clamp01((value - bad) / max(good - bad, EPSILON))
    return 100.0 * clamp01((bad - value) / max(bad - good, EPSILON))


def mean_visible(points: list[np.ndarray]) -> Optional[np.ndarray]:
    if not points:
        return None
    return np.mean(np.vstack(points), axis=0)


def score_side_bend(
    landmarks: dict[str, dict[str, float]],
    hp: SideBendHyperparameters,
) -> tuple[Optional[float], Optional[dict]]:
    left_shoulder = point(landmarks, "left_shoulder")
    right_shoulder = point(landmarks, "right_shoulder")
    left_hip = point(landmarks, "left_hip")
    right_hip = point(landmarks, "right_hip")
    if left_shoulder is None or right_shoulder is None or left_hip is None or right_hip is None:
        return None, None

    shoulder_width = float(np.linalg.norm(left_shoulder[:2] - right_shoulder[:2]))
    if shoulder_width < EPSILON:
        return None, None

    shoulder_mid = (left_shoulder + right_shoulder) / 2.0
    hip_mid = (left_hip + right_hip) / 2.0
    spine = shoulder_mid - hip_mid
    lateral_tilt = math.degrees(math.atan2(abs(float(spine[0])), max(abs(float(spine[1])), EPSILON)))
    bend_side = "left" if float(spine[0]) < 0.0 else "right"

    wrist_points = [p for p in (point(landmarks, "left_wrist"), point(landmarks, "right_wrist")) if p is not None]
    wrist_mid = mean_visible(wrist_points)
    if wrist_mid is None:
        return None, None

    overhead = (float(shoulder_mid[1]) - float(wrist_mid[1])) / shoulder_width
    side_reach = abs(float(wrist_mid[0] - shoulder_mid[0])) / shoulder_width
    reach_same_side = (float(wrist_mid[0] - shoulder_mid[0]) < 0.0 and bend_side == "left") or (
        float(wrist_mid[0] - shoulder_mid[0]) > 0.0 and bend_side == "right"
    )
    if not reach_same_side:
        side_reach *= 0.55

    elbow_angles: list[float] = []
    left_elbow = point(landmarks, "left_elbow")
    left_wrist = point(landmarks, "left_wrist")
    right_elbow = point(landmarks, "right_elbow")
    right_wrist = point(landmarks, "right_wrist")
    if left_elbow is not None and left_wrist is not None:
        elbow_angles.append(angle_degrees(left_shoulder, left_elbow, left_wrist))
    if right_elbow is not None and right_wrist is not None:
        elbow_angles.append(angle_degrees(right_shoulder, right_elbow, right_wrist))
    elbow_extension = float(np.nanmean(elbow_angles)) if elbow_angles else float("nan")

    overhead_score = normalize_score(overhead, hp.overhead_good_widths, hp.overhead_bad_widths)
    tilt_score = normalize_score(lateral_tilt, hp.tilt_good_deg, hp.tilt_bad_deg)
    elbow_score = normalize_score(elbow_extension, hp.elbow_good_deg, hp.elbow_bad_deg)
    side_reach_score = normalize_score(side_reach, hp.side_reach_good_widths, hp.side_reach_bad_widths)
    weights = hp.normalized_weights()
    total = (
        weights["overhead"] * overhead_score
        + weights["tilt"] * tilt_score
        + weights["elbow"] * elbow_score
        + weights["side_reach"] * side_reach_score
    )

    return float(np.clip(total, 0.0, 100.0)), {
        "bend_side": bend_side,
        "overhead": overhead,
        "lateral_tilt": lateral_tilt,
        "elbow_extension": elbow_extension,
        "side_reach": side_reach,
        "reach_same_side": reach_same_side,
        "overhead_score": overhead_score,
        "tilt_score": tilt_score,
        "elbow_score": elbow_score,
        "side_reach_score": side_reach_score,
    }


def score_color(score: float) -> tuple[int, int, int]:
    if score >= SUCCESS_SCORE_THRESHOLD:
        return (40, 210, 70)
    if score >= 55.0:
        return (0, 215, 255)
    return (45, 45, 230)


def draw_bar(image: np.ndarray, label: str, score: float, x: int, y: int, width: int = 210) -> None:
    color = score_color(score)
    cv2.rectangle(image, (x, y), (x + width, y + 12), (70, 70, 70), -1)
    cv2.rectangle(image, (x, y), (x + int(width * clamp01(score / 100.0)), y + 12), color, -1)
    put_text(image, f"{label}: {score:4.0f}", (x + width + 12, y + 13), 0.42, (230, 230, 230), 1)


def draw_panel(
    image: np.ndarray,
    score: Optional[float],
    metrics: Optional[dict],
    hold_seconds: float,
    camera_fps: float,
    pose_metrics: dict,
) -> None:
    panel_color = score_color(score or 0.0) if score is not None else (190, 190, 190)
    cv2.rectangle(image, (18, 18), (720, 318), (20, 20, 20), -1)
    cv2.rectangle(image, (18, 18), (720, 318), panel_color, 3)
    put_text(image, "PoseTracker Side Bend Coach", (36, 54), 0.72, (245, 245, 245), 2)
    backend = pose_metrics.get("pose_backend", "pose_tracker")
    pose_fps = float(pose_metrics.get("fps_pose", 0.0) or 0.0)
    put_text(image, f"Standing side bend / overhead side stretch | backend {backend}", (36, 86), 0.48, (210, 235, 255), 1)

    if score is None or metrics is None:
        note = "Waiting for shoulders, hips, and wrist landmarks..."
        if pose_metrics.get("last_error"):
            note = str(pose_metrics["last_error"])[:72]
        put_text(image, note, (36, 140), 0.56, (80, 180, 255), 2)
        put_text(image, f"Camera FPS: {camera_fps:4.1f}   Pose FPS: {pose_fps:4.1f}", (36, 188), 0.50, (230, 230, 230), 1)
        return

    same_side = "yes" if metrics["reach_same_side"] else "no"
    put_text(image, f"Form Score: {score:5.1f}%", (36, 130), 0.82, panel_color, 2)
    put_text(image, f"Bend side: {metrics['bend_side']}   reach same side: {same_side}", (36, 166), 0.52, (235, 235, 235), 1)
    put_text(image, f"Wrists overhead: {metrics['overhead']:4.2f} shoulder widths", (36, 194), 0.52, (235, 235, 235), 1)
    put_text(image, f"Lateral trunk tilt: {metrics['lateral_tilt']:5.1f} deg", (36, 222), 0.52, (235, 235, 235), 1)
    put_text(image, f"Elbow extension: {metrics['elbow_extension']:5.1f} deg", (36, 250), 0.52, (235, 235, 235), 1)
    put_text(
        image,
        f"Hold: {min(hold_seconds, HOLD_SECONDS_REQUIRED):3.1f}s / {HOLD_SECONDS_REQUIRED:.0f}s   Camera FPS: {camera_fps:4.1f}   Pose FPS: {pose_fps:4.1f}",
        (36, 284),
        0.48,
        (235, 235, 235),
        1,
    )

    draw_bar(image, "overhead", float(metrics["overhead_score"]), 410, 146)
    draw_bar(image, "tilt", float(metrics["tilt_score"]), 410, 182)
    draw_bar(image, "elbows", float(metrics["elbow_score"]), 410, 218)
    draw_bar(image, "side", float(metrics["side_reach_score"]), 410, 254)


def draw_success_banner(image: np.ndarray) -> None:
    height, width = image.shape[:2]
    text = "SIDE BEND STRETCH SUCCESSFUL!"
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 1.18, 4)
    x = max(24, (width - tw) // 2)
    y = max(110, height // 2)
    cv2.rectangle(image, (x - 26, y - th - 28), (x + tw + 26, y + 22), (30, 150, 55), -1)
    cv2.rectangle(image, (x - 26, y - th - 28), (x + tw + 26, y + 22), (255, 255, 255), 3)
    put_text(image, text, (x, y), 1.18, (255, 255, 255), 4)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PoseTracker Standing Side Bend Stretch Coach")
    parser.add_argument("--backend", default="mediapipe")
    parser.add_argument("--model-path", default=str(MODEL_PATH))
    parser.add_argument("--delegate", default="cpu", choices=["cpu", "gpu"])
    parser.add_argument("--inference-width", type=int, default=320)
    parser.add_argument("--frame-stride", type=int, default=1)
    parser.add_argument("--async-enabled", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--max-async-fps", type=int, default=12)
    parser.add_argument("--smoothing-alpha", type=float, default=DEFAULT_SMOOTHING_ALPHA)
    parser.add_argument("--success-threshold", type=float, default=SUCCESS_SCORE_THRESHOLD)
    parser.add_argument("--overhead-good", type=float, default=DEFAULT_HYPERPARAMS.overhead_good_widths)
    parser.add_argument("--overhead-bad", type=float, default=DEFAULT_HYPERPARAMS.overhead_bad_widths)
    parser.add_argument("--tilt-good", type=float, default=DEFAULT_HYPERPARAMS.tilt_good_deg)
    parser.add_argument("--tilt-bad", type=float, default=DEFAULT_HYPERPARAMS.tilt_bad_deg)
    parser.add_argument("--elbow-good", type=float, default=DEFAULT_HYPERPARAMS.elbow_good_deg)
    parser.add_argument("--elbow-bad", type=float, default=DEFAULT_HYPERPARAMS.elbow_bad_deg)
    parser.add_argument("--side-reach-good", type=float, default=DEFAULT_HYPERPARAMS.side_reach_good_widths)
    parser.add_argument("--side-reach-bad", type=float, default=DEFAULT_HYPERPARAMS.side_reach_bad_widths)
    return parser.parse_args()


def hyperparameters_from_args(args: argparse.Namespace) -> SideBendHyperparameters:
    return SideBendHyperparameters(
        overhead_good_widths=args.overhead_good,
        overhead_bad_widths=args.overhead_bad,
        tilt_good_deg=args.tilt_good,
        tilt_bad_deg=args.tilt_bad,
        elbow_good_deg=args.elbow_good,
        elbow_bad_deg=args.elbow_bad,
        side_reach_good_widths=args.side_reach_good,
        side_reach_bad_widths=args.side_reach_bad,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    args = parse_args()
    smoothing_alpha = float(np.clip(args.smoothing_alpha, 0.05, 1.0))
    success_threshold = float(np.clip(args.success_threshold, 1.0, 100.0))
    hp = hyperparameters_from_args(args)
    tracker = build_tracker(args)
    cap = open_camera()
    window_name = "PoseTracker Side Bend Stretch Coach"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    hold_started_at: Optional[float] = None
    success = False
    camera_fps = 0.0
    prev_time = time.perf_counter()
    smoothed_score: Optional[float] = None
    smoothed_metrics: Optional[dict] = None

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Camera frame grab failed; exiting.")
            break

        now = time.perf_counter()
        dt = max(now - prev_time, EPSILON)
        prev_time = now
        camera_fps = (0.9 * camera_fps) + (0.1 * (1.0 / dt)) if camera_fps > 0.0 else (1.0 / dt)

        frame = cv2.flip(frame, 1)
        annotated, pose_metrics = tracker.process(frame, context={"draw_landmarks": True})
        landmarks = pose_metrics.get("landmarks", {}) if isinstance(pose_metrics, dict) else {}
        raw_score, raw_metrics = score_side_bend(landmarks, hp)

        if raw_score is None or raw_metrics is None:
            smoothed_score = None
            smoothed_metrics = None
            score = None
            metrics = None
        else:
            smoothed_score = ema_value(smoothed_score, raw_score, smoothing_alpha)
            smoothed_metrics = ema_metrics(smoothed_metrics, raw_metrics, smoothing_alpha)
            score = smoothed_score
            metrics = smoothed_metrics

        hold_seconds = 0.0
        if score is not None and score >= success_threshold:
            if hold_started_at is None:
                hold_started_at = now
            hold_seconds = now - hold_started_at
            success = hold_seconds >= HOLD_SECONDS_REQUIRED
        else:
            hold_started_at = None
            success = False

        draw_panel(annotated, score, metrics, hold_seconds, camera_fps, pose_metrics)
        if score is not None:
            cv2.rectangle(annotated, (0, 0), (annotated.shape[1] - 1, annotated.shape[0] - 1), score_color(score), 8)
        if success:
            draw_success_banner(annotated)

        put_text(annotated, "Press r to restart hold | q or Esc to quit", (24, annotated.shape[0] - 28), 0.58, (245, 245, 245), 1)
        cv2.imshow(window_name, annotated)

        key = cv2.waitKey(1) & 0xFF
        if key in (27, ord("q")):
            break
        if key == ord("r"):
            hold_started_at = None
            success = False
            smoothed_score = None
            smoothed_metrics = None

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
