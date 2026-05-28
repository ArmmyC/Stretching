#!/usr/bin/env python3
"""
Standing Hamstring Stretch Coach built on pose_tracker.py.

Run:
    conda run -n ai_env python pose_tracker_hamstring_reach.py

This file intentionally does not modify pose_tracker.py. It imports the
PoseTracker class, uses its normalized landmark output, then applies the same
standing hamstring reach scoring idea from hamstring_v_sit_reach.py:
  - front knee close to straight
  - torso folded forward from the hips
  - wrists reaching toward the front ankle/shin
"""

from __future__ import annotations

import argparse
import logging
import math
import os
import sys
import time
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np


APP_DIR = Path(__file__).resolve().parent
MPL_CACHE_DIR = APP_DIR / ".cache" / "matplotlib"
MPL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE_DIR))
MODEL_PATH = APP_DIR / "pose_landmarker.task"
CAMERA_INDEX = 0
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
TARGET_FPS = 30
HOLD_SECONDS_REQUIRED = 3.0
SUCCESS_SCORE_THRESHOLD = 75.0
DEFAULT_SMOOTHING_ALPHA = 0.25
EPSILON = 1e-8


@dataclass(frozen=True)
class ScoringHyperparameters:
    knee_good_deg: float = 160.0
    knee_bad_deg: float = 125.0
    fold_good_deg: float = 65.0
    fold_bad_deg: float = 125.0
    reach_good_leg_lengths: float = 0.35
    reach_bad_leg_lengths: float = 0.95
    knee_weight: float = 0.35
    fold_weight: float = 0.35
    reach_weight: float = 0.30

    def normalized_weights(self) -> dict[str, float]:
        weights = {
            "knee": max(0.0, self.knee_weight),
            "fold": max(0.0, self.fold_weight),
            "reach": max(0.0, self.reach_weight),
        }
        total = sum(weights.values())
        if total < EPSILON:
            return {"knee": 0.35, "fold": 0.35, "reach": 0.30}
        return {key: value / total for key, value in weights.items()}


DEFAULT_HYPERPARAMS = ScoringHyperparameters()


LANDMARK_INDEXES = {
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_elbow": 13,
    "right_elbow": 14,
    "left_wrist": 15,
    "right_wrist": 16,
    "left_hip": 23,
    "right_hip": 24,
    "left_knee": 25,
    "right_knee": 26,
    "left_ankle": 27,
    "right_ankle": 28,
}

POSE_CONNECTIONS = (
    ("left_shoulder", "right_shoulder"),
    ("left_shoulder", "left_elbow"),
    ("left_elbow", "left_wrist"),
    ("right_shoulder", "right_elbow"),
    ("right_elbow", "right_wrist"),
    ("left_shoulder", "left_hip"),
    ("right_shoulder", "right_hip"),
    ("left_hip", "right_hip"),
    ("left_hip", "left_knee"),
    ("left_knee", "left_ankle"),
    ("right_hip", "right_knee"),
    ("right_knee", "right_ankle"),
)


def install_pose_tracker_import_shims() -> None:
    """
    Let pose_tracker.py import in this standalone folder.

    The current pose_tracker.py imports optional app.movenet_pose and
    app.ncnn_pose modules at top level. Those modules are not present in this
    workspace snapshot. This shim supplies enough names for importing
    PoseTracker while this script forces the MediaPipe backend.
    """
    if "app.movenet_pose" in sys.modules and "app.ncnn_pose" in sys.modules:
        return

    app_module = sys.modules.setdefault("app", types.ModuleType("app"))
    movenet_module = types.ModuleType("app.movenet_pose")
    ncnn_module = types.ModuleType("app.ncnn_pose")

    class _UnavailableMoveNetPose:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("MoveNet app backend is unavailable in this workspace.")

    class _UnavailableNcnnYoloPose:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("NCNN app backend is unavailable in this workspace.")

    movenet_module.DEFAULT_MOVENET_INPUT_SIZE = 192
    movenet_module.DEFAULT_MOVENET_MODEL_PATH = "models/movenet_lightning.tflite"
    movenet_module.DEFAULT_MOVENET_NUM_THREADS = 4
    movenet_module.MoveNetPose = _UnavailableMoveNetPose

    ncnn_module.DEFAULT_NCNN_CONFIDENCE = 0.35
    ncnn_module.DEFAULT_NCNN_GPU_INDEX = 0
    ncnn_module.DEFAULT_NCNN_INPUT_SIZE = 320
    ncnn_module.DEFAULT_NCNN_IOU = 0.45
    ncnn_module.DEFAULT_NCNN_MODEL_DIR = "models/ncnn"
    ncnn_module.NcnnYoloPose = _UnavailableNcnnYoloPose

    app_module.movenet_pose = movenet_module
    app_module.ncnn_pose = ncnn_module
    sys.modules.setdefault("app.movenet_pose", movenet_module)
    sys.modules.setdefault("app.ncnn_pose", ncnn_module)


install_pose_tracker_import_shims()
os.environ.setdefault("POSE_FALLBACK_BACKEND", "none")
from pose_tracker import PoseTracker  # noqa: E402


def install_mediapipe_doc_controls_stub() -> None:
    if "tensorflow.tools.docs.doc_controls" in sys.modules:
        return

    def do_not_generate_docs(obj=None):
        return (lambda wrapped: wrapped) if obj is None else obj

    tensorflow = types.ModuleType("tensorflow")
    tools = types.ModuleType("tensorflow.tools")
    docs = types.ModuleType("tensorflow.tools.docs")
    doc_controls = types.ModuleType("tensorflow.tools.docs.doc_controls")
    doc_controls.do_not_generate_docs = do_not_generate_docs
    tensorflow.tools = tools
    tools.docs = docs
    docs.doc_controls = doc_controls
    sys.modules.setdefault("tensorflow", tensorflow)
    sys.modules.setdefault("tensorflow.tools", tools)
    sys.modules.setdefault("tensorflow.tools.docs", docs)
    sys.modules.setdefault("tensorflow.tools.docs.doc_controls", doc_controls)


class SolutionsPoseFallback:
    """Small fallback with the same process() shape as PoseTracker.process()."""

    def __init__(self) -> None:
        install_mediapipe_doc_controls_stub()
        import mediapipe as mp

        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_styles = mp.solutions.drawing_styles
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            smooth_landmarks=True,
            enable_segmentation=False,
            min_detection_confidence=0.50,
            min_tracking_confidence=0.50,
        )
        self.enabled = True
        self.model_loaded = True
        self.last_error: str | None = None
        self.fps_pose = 0.0

    def process(self, frame: np.ndarray, context: dict | None = None) -> tuple[np.ndarray, dict[str, Any]]:
        start = time.perf_counter()
        output = frame.copy()
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = self.pose.process(rgb)
        rgb.flags.writeable = True

        landmarks: dict[str, dict[str, float]] = {}
        if results.pose_landmarks:
            if (context or {}).get("draw_landmarks", True):
                self.mp_drawing.draw_landmarks(
                    output,
                    results.pose_landmarks,
                    self.mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=self.mp_styles.get_default_pose_landmarks_style(),
                )
            first_pose = results.pose_landmarks.landmark
            for name, index in LANDMARK_INDEXES.items():
                lm = first_pose[index]
                landmarks[name] = {
                    "x": float(lm.x),
                    "y": float(lm.y),
                    "z": float(lm.z),
                    "visibility": float(getattr(lm, "visibility", 1.0)),
                }

        elapsed = max(time.perf_counter() - start, EPSILON)
        self.fps_pose = 1.0 / elapsed
        metrics = {
            "pose_enabled": True,
            "pose_backend": "mediapipe_solutions_fallback",
            "fps_pose": round(self.fps_pose, 2),
            "landmarks": landmarks,
            "pose_ok": bool(landmarks),
            "full_body_visible": bool(landmarks),
            "confidence": float(np.mean([lm["visibility"] for lm in landmarks.values()])) if landmarks else 0.0,
        }
        return output, metrics


class HubMoveNetFallback:
    """Fallback through prototype_app_movenet.py, converted to PoseTracker landmarks."""

    COCO_TO_NAMES = {
        "left_shoulder": 5,
        "right_shoulder": 6,
        "left_elbow": 7,
        "right_elbow": 8,
        "left_wrist": 9,
        "right_wrist": 10,
        "left_hip": 11,
        "right_hip": 12,
        "left_knee": 13,
        "right_knee": 14,
        "left_ankle": 15,
        "right_ankle": 16,
    }

    def __init__(self) -> None:
        import prototype_app_movenet as movenet_app

        self.movenet_app = movenet_app
        self.movenet = movenet_app.load_movenet()
        self.enabled = True
        self.model_loaded = True
        self.last_error: str | None = None
        self.fps_pose = 0.0

    def process(self, frame: np.ndarray, context: dict | None = None) -> tuple[np.ndarray, dict[str, Any]]:
        start = time.perf_counter()
        output = frame.copy()
        keypoints, scores = self.movenet_app.run_movenet(frame, self.movenet)
        if (context or {}).get("draw_landmarks", True):
            self.movenet_app.draw_skeleton(output, keypoints, scores)

        height, width = frame.shape[:2]
        landmarks: dict[str, dict[str, float]] = {}
        for name, index in self.COCO_TO_NAMES.items():
            score = float(scores[index])
            if score < self.movenet_app.KEYPOINT_CONFIDENCE:
                continue
            landmarks[name] = {
                "x": float(keypoints[index, 0] / max(width, 1)),
                "y": float(keypoints[index, 1] / max(height, 1)),
                "z": 0.0,
                "visibility": score,
            }

        elapsed = max(time.perf_counter() - start, EPSILON)
        self.fps_pose = 1.0 / elapsed
        confidence = float(np.mean([lm["visibility"] for lm in landmarks.values()])) if landmarks else 0.0
        metrics = {
            "pose_enabled": True,
            "pose_backend": "movenet_tfhub_fallback",
            "fps_pose": round(self.fps_pose, 2),
            "landmarks": landmarks,
            "pose_ok": bool(landmarks),
            "full_body_visible": len(landmarks) >= 10,
            "confidence": confidence,
        }
        return output, metrics


def vector_angle_degrees(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    v1 = a - b
    v2 = c - b
    denom = float(np.linalg.norm(v1) * np.linalg.norm(v2))
    if denom < EPSILON:
        return float("nan")
    cos_theta = float(np.dot(v1, v2) / denom)
    return math.degrees(math.acos(float(np.clip(cos_theta, -1.0, 1.0))))


def dist(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


def clamp01(value: float) -> float:
    return float(np.clip(value, 0.0, 1.0))


def normalize_score(value: float, good: float, bad: float, higher_is_better: bool = True) -> float:
    if not np.isfinite(value):
        return 0.0
    if higher_is_better:
        return 100.0 * clamp01((value - bad) / max(good - bad, EPSILON))
    return 100.0 * clamp01((bad - value) / max(bad - good, EPSILON))


def ema_value(previous: Optional[float], current: float, alpha: float) -> float:
    if previous is None or not np.isfinite(previous):
        return float(current)
    return float((1.0 - alpha) * previous + alpha * current)


def ema_metrics(previous: Optional[dict], current: dict, alpha: float) -> dict:
    if previous is None:
        return dict(current)
    smoothed = {}
    for key, value in current.items():
        if isinstance(value, (int, float, np.floating)):
            smoothed[key] = ema_value(previous.get(key), float(value), alpha)
        else:
            smoothed[key] = value
    return smoothed


def landmarks_to_points(landmarks: dict[str, dict[str, float]]) -> Optional[dict[str, np.ndarray]]:
    required = (
        "left_shoulder",
        "right_shoulder",
        "left_wrist",
        "right_wrist",
        "left_hip",
        "right_hip",
        "left_knee",
        "right_knee",
        "left_ankle",
        "right_ankle",
    )
    missing = [name for name in required if name not in landmarks]
    if missing:
        return None

    points: dict[str, np.ndarray] = {}
    for name in required:
        lm = landmarks[name]
        points[name] = np.asarray(
            [float(lm.get("x", 0.0)), float(lm.get("y", 0.0)), float(lm.get("z", 0.0))],
            dtype=np.float32,
        )
    return points


def score_one_standing_side(
    points: dict[str, np.ndarray],
    side: str,
    hyperparams: ScoringHyperparameters,
) -> tuple[float, dict]:
    left_hip = points["left_hip"]
    right_hip = points["right_hip"]
    left_knee = points["left_knee"]
    right_knee = points["right_knee"]
    left_ankle = points["left_ankle"]
    right_ankle = points["right_ankle"]
    shoulder_mid = (points["left_shoulder"] + points["right_shoulder"]) / 2.0
    hip_mid = (left_hip + right_hip) / 2.0
    wrist_mid = (points["left_wrist"] + points["right_wrist"]) / 2.0

    if side == "left":
        front_hip, front_knee, front_ankle = left_hip, left_knee, left_ankle
        rear_hip, rear_knee, rear_ankle = right_hip, right_knee, right_ankle
    else:
        front_hip, front_knee, front_ankle = right_hip, right_knee, right_ankle
        rear_hip, rear_knee, rear_ankle = left_hip, left_knee, left_ankle

    front_knee_angle = vector_angle_degrees(front_hip, front_knee, front_ankle)
    rear_knee_angle = vector_angle_degrees(rear_hip, rear_knee, rear_ankle)
    hip_fold_angle = vector_angle_degrees(shoulder_mid, hip_mid, front_knee)
    leg_length = float(
        np.nanmean(
            [
                dist(front_hip, front_knee) + dist(front_knee, front_ankle),
                dist(rear_hip, rear_knee) + dist(rear_knee, rear_ankle),
            ]
        )
    )
    reach_distance = dist(wrist_mid, front_ankle) / max(leg_length, EPSILON)

    knee_score = normalize_score(front_knee_angle, hyperparams.knee_good_deg, hyperparams.knee_bad_deg)
    fold_score = normalize_score(
        hip_fold_angle,
        hyperparams.fold_good_deg,
        hyperparams.fold_bad_deg,
        higher_is_better=False,
    )
    reach_score = normalize_score(
        reach_distance,
        hyperparams.reach_good_leg_lengths,
        hyperparams.reach_bad_leg_lengths,
        higher_is_better=False,
    )
    weights = hyperparams.normalized_weights()
    total = weights["knee"] * knee_score + weights["fold"] * fold_score + weights["reach"] * reach_score
    return float(np.clip(total, 0.0, 100.0)), {
        "side": side,
        "front_knee_angle": front_knee_angle,
        "rear_knee_angle": rear_knee_angle,
        "hip_fold_angle": hip_fold_angle,
        "reach_distance": reach_distance,
        "knee_score": knee_score,
        "fold_score": fold_score,
        "reach_score": reach_score,
    }


def score_standing_hamstring(
    landmarks: dict[str, dict[str, float]],
    hyperparams: ScoringHyperparameters,
) -> tuple[Optional[float], Optional[dict]]:
    points = landmarks_to_points(landmarks)
    if points is None:
        return None, None

    left_score, left_metrics = score_one_standing_side(points, "left", hyperparams)
    right_score, right_metrics = score_one_standing_side(points, "right", hyperparams)
    if left_score >= right_score:
        left_metrics["active_side"] = "left"
        return left_score, left_metrics
    right_metrics["active_side"] = "right"
    return right_score, right_metrics


def score_color(score: float) -> tuple[int, int, int]:
    if score >= SUCCESS_SCORE_THRESHOLD:
        return (40, 210, 70)
    if score >= 55.0:
        return (0, 215, 255)
    return (45, 45, 230)


def put_text(
    image: np.ndarray,
    text: str,
    origin: tuple[int, int],
    scale: float,
    color: tuple[int, int, int],
    thickness: int = 2,
) -> None:
    cv2.putText(image, text, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thickness + 3, cv2.LINE_AA)
    cv2.putText(image, text, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)


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
    cv2.rectangle(image, (18, 18), (690, 318), (20, 20, 20), -1)
    cv2.rectangle(image, (18, 18), (690, 318), panel_color, 3)
    put_text(image, "PoseTracker Hamstring Coach", (36, 54), 0.72, (245, 245, 245), 2)
    backend = pose_metrics.get("pose_backend", "pose_tracker")
    pose_fps = float(pose_metrics.get("fps_pose", 0.0) or 0.0)
    put_text(image, f"Standing Hamstring Reach | backend {backend}", (36, 86), 0.50, (210, 235, 255), 1)

    if score is None or metrics is None:
        note = "Waiting for full-body landmarks from pose_tracker..."
        if pose_metrics.get("last_error"):
            note = str(pose_metrics["last_error"])[:68]
        put_text(image, note, (36, 140), 0.56, (80, 180, 255), 2)
        put_text(image, f"Camera FPS: {camera_fps:4.1f}   Pose FPS: {pose_fps:4.1f}", (36, 188), 0.50, (230, 230, 230), 1)
        return

    put_text(image, f"Form Score: {score:5.1f}%", (36, 130), 0.82, panel_color, 2)
    put_text(
        image,
        f"Active side: {metrics.get('active_side', 'front')}   Front knee: {metrics['front_knee_angle']:5.1f} deg",
        (36, 166),
        0.52,
        (235, 235, 235),
        1,
    )
    put_text(image, f"Hip fold: {metrics['hip_fold_angle']:5.1f} deg", (36, 194), 0.52, (235, 235, 235), 1)
    put_text(image, f"Reach gap: {metrics['reach_distance']:4.2f} leg lengths", (36, 222), 0.52, (235, 235, 235), 1)
    put_text(image, f"Back knee: {metrics['rear_knee_angle']:5.1f} deg", (36, 250), 0.52, (235, 235, 235), 1)
    put_text(
        image,
        f"Hold: {min(hold_seconds, HOLD_SECONDS_REQUIRED):3.1f}s / {HOLD_SECONDS_REQUIRED:.0f}s   Camera FPS: {camera_fps:4.1f}   Pose FPS: {pose_fps:4.1f}",
        (36, 284),
        0.48,
        (235, 235, 235),
        1,
    )

    draw_bar(image, "knees", float(metrics["knee_score"]), 392, 146)
    draw_bar(image, "fold", float(metrics["fold_score"]), 392, 182)
    draw_bar(image, "reach", float(metrics["reach_score"]), 392, 218)


def draw_success_banner(image: np.ndarray) -> None:
    height, width = image.shape[:2]
    text = "STANDING HAMSTRING SUCCESSFUL!"
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 1.25, 4)
    x = max(24, (width - tw) // 2)
    y = max(110, height // 2)
    cv2.rectangle(image, (x - 26, y - th - 28), (x + tw + 26, y + 22), (30, 150, 55), -1)
    cv2.rectangle(image, (x - 26, y - th - 28), (x + tw + 26, y + 22), (255, 255, 255), 3)
    put_text(image, text, (x, y), 1.25, (255, 255, 255), 4)


def build_tracker(args: argparse.Namespace) -> Any:
    tracker = PoseTracker(
        model_path=args.model_path,
        enabled=True,
        inference_width=args.inference_width,
        frame_stride=args.frame_stride,
        async_enabled=args.async_enabled,
        max_async_fps=args.max_async_fps,
        delegate=args.delegate,
        backend=args.backend,
    )
    if tracker.enabled:
        return tracker

    print(f"PoseTracker failed to start: {tracker.last_error}")
    print("Trying mediapipe.solutions.pose fallback...")
    try:
        return SolutionsPoseFallback()
    except Exception as exc:
        print(f"MediaPipe Solutions fallback failed: {exc}")

    print("Trying MoveNet TensorFlow Hub fallback...")
    return HubMoveNetFallback()


def open_camera() -> cv2.VideoCapture:
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_AVFOUNDATION)
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam. Check macOS camera permissions.")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PoseTracker Standing Hamstring Stretch Coach")
    parser.add_argument("--backend", default="mediapipe", help="PoseTracker backend. Use mediapipe for this standalone file.")
    parser.add_argument("--model-path", default=str(MODEL_PATH), help="Path to pose_landmarker.task")
    parser.add_argument("--delegate", default="cpu", choices=["cpu", "gpu"], help="MediaPipe delegate")
    parser.add_argument("--inference-width", type=int, default=320)
    parser.add_argument("--frame-stride", type=int, default=1)
    parser.add_argument("--async-enabled", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--max-async-fps", type=int, default=12)
    parser.add_argument("--smoothing-alpha", type=float, default=DEFAULT_SMOOTHING_ALPHA)
    parser.add_argument("--success-threshold", type=float, default=SUCCESS_SCORE_THRESHOLD)
    parser.add_argument("--knee-good-deg", type=float, default=DEFAULT_HYPERPARAMS.knee_good_deg)
    parser.add_argument("--knee-bad-deg", type=float, default=DEFAULT_HYPERPARAMS.knee_bad_deg)
    parser.add_argument("--fold-good-deg", type=float, default=DEFAULT_HYPERPARAMS.fold_good_deg)
    parser.add_argument("--fold-bad-deg", type=float, default=DEFAULT_HYPERPARAMS.fold_bad_deg)
    parser.add_argument("--reach-good", type=float, default=DEFAULT_HYPERPARAMS.reach_good_leg_lengths)
    parser.add_argument("--reach-bad", type=float, default=DEFAULT_HYPERPARAMS.reach_bad_leg_lengths)
    return parser.parse_args()


def hyperparameters_from_args(args: argparse.Namespace) -> ScoringHyperparameters:
    return ScoringHyperparameters(
        knee_good_deg=args.knee_good_deg,
        knee_bad_deg=args.knee_bad_deg,
        fold_good_deg=args.fold_good_deg,
        fold_bad_deg=args.fold_bad_deg,
        reach_good_leg_lengths=args.reach_good,
        reach_bad_leg_lengths=args.reach_bad,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    args = parse_args()
    smoothing_alpha = float(np.clip(args.smoothing_alpha, 0.05, 1.0))
    success_threshold = float(np.clip(args.success_threshold, 1.0, 100.0))
    hyperparams = hyperparameters_from_args(args)

    tracker = build_tracker(args)

    cap = open_camera()
    window_name = "PoseTracker Hamstring Stretch Coach"
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

        raw_score, raw_metrics = score_standing_hamstring(landmarks, hyperparams)
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
