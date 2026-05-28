from __future__ import annotations

import logging
import math
import os
import threading
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.movenet_pose import (
    DEFAULT_MOVENET_INPUT_SIZE,
    DEFAULT_MOVENET_MODEL_PATH,
    DEFAULT_MOVENET_NUM_THREADS,
    MoveNetPose,
)
from app.ncnn_pose import (
    DEFAULT_NCNN_CONFIDENCE,
    DEFAULT_NCNN_GPU_INDEX,
    DEFAULT_NCNN_INPUT_SIZE,
    DEFAULT_NCNN_IOU,
    DEFAULT_NCNN_MODEL_DIR,
    NcnnYoloPose,
)

ARM_RAISE_MARGIN = 0.08
TORSO_CENTER_MARGIN = 0.12
MIN_LANDMARK_CONFIDENCE = 0.5

DEFAULT_MODEL_PATH = "models/pose_landmarker.task"
DEFAULT_INFERENCE_WIDTH = 320
DEFAULT_FRAME_STRIDE = 1
DEFAULT_ASYNC_ENABLED = True
DEFAULT_MAX_ASYNC_FPS = 8
DEFAULT_DELEGATE = "cpu"
FPS_LOG_INTERVAL_SEC = 5.0
NCNN_BACKENDS = {"ncnn", "ncnn_pose", "ncnn_yolo_pose"}
MOVENET_BACKENDS = {"movenet", "movenet_tflite"}

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

UPPER_BODY_NAMES = (
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
)

FULL_BODY_NAMES = (
    "left_shoulder",
    "right_shoulder",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
)

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

logger = logging.getLogger(__name__)


def normalized_distance(a: dict[str, float], b: dict[str, float]) -> float:
    return math.hypot(float(a["x"]) - float(b["x"]), float(a["y"]) - float(b["y"]))


def extract_required_landmarks(result: Any) -> dict[str, dict[str, float]]:
    """Extract the landmarks needed for the MVP stretch flags."""
    pose_landmarks = getattr(result, "pose_landmarks", None)
    if not pose_landmarks:
        return {}

    first_pose = pose_landmarks[0]
    extracted: dict[str, dict[str, float]] = {}
    for name, index in LANDMARK_INDEXES.items():
        if index >= len(first_pose):
            continue
        landmark = first_pose[index]
        visibility = _landmark_score(landmark)
        extracted[name] = {
            "x": float(getattr(landmark, "x", 0.0)),
            "y": float(getattr(landmark, "y", 0.0)),
            "z": float(getattr(landmark, "z", 0.0)),
            "visibility": visibility,
        }
        presence = getattr(landmark, "presence", None)
        if presence is not None:
            extracted[name]["presence"] = float(presence)
    return extracted


def compute_pose_flags(landmarks: dict[str, dict[str, float]]) -> dict[str, Any]:
    def visible(name: str) -> bool:
        landmark = landmarks.get(name)
        return bool(landmark and float(landmark.get("visibility", 0.0)) >= MIN_LANDMARK_CONFIDENCE)

    shoulders_visible = visible("left_shoulder") and visible("right_shoulder")
    hips_visible = visible("left_hip") and visible("right_hip")
    elbows_visible = visible("left_elbow") or visible("right_elbow")
    wrists_visible = visible("left_wrist") or visible("right_wrist")

    user_visible = shoulders_visible and hips_visible
    upper_body_visible = shoulders_visible and elbows_visible and wrists_visible
    full_body_visible = all(visible(name) for name in FULL_BODY_NAMES)

    left_arm_raised = (
        visible("left_wrist")
        and visible("left_shoulder")
        and landmarks["left_wrist"]["y"] < landmarks["left_shoulder"]["y"] - ARM_RAISE_MARGIN
    )
    right_arm_raised = (
        visible("right_wrist")
        and visible("right_shoulder")
        and landmarks["right_wrist"]["y"] < landmarks["right_shoulder"]["y"] - ARM_RAISE_MARGIN
    )
    arm_raised = left_arm_raised or right_arm_raised

    torso_centered = False
    if user_visible:
        shoulder_center_x = (landmarks["left_shoulder"]["x"] + landmarks["right_shoulder"]["x"]) / 2.0
        hip_center_x = (landmarks["left_hip"]["x"] + landmarks["right_hip"]["x"]) / 2.0
        torso_centered = abs(shoulder_center_x - hip_center_x) < TORSO_CENTER_MARGIN

    confidence_values = [
        float(landmarks[name].get("visibility", 0.0))
        for name in UPPER_BODY_NAMES
        if name in landmarks
    ]
    confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0.0

    return {
        "pose_ok": bool(landmarks) and confidence > 0.0,
        "user_visible": user_visible,
        "upper_body_visible": upper_body_visible,
        "full_body_visible": full_body_visible,
        "arm_raised": arm_raised,
        "torso_centered": torso_centered,
        "confidence": round(float(confidence), 4),
    }


def draw_pose_overlay(
    frame: np.ndarray,
    landmarks: dict[str, dict[str, float]],
    flags: dict[str, Any],
) -> np.ndarray:
    if not landmarks:
        return frame

    h, w = frame.shape[:2]

    def point(name: str) -> tuple[int, int] | None:
        landmark = landmarks.get(name)
        if not landmark or landmark.get("visibility", 0.0) < MIN_LANDMARK_CONFIDENCE:
            return None
        x = int(max(0.0, min(1.0, float(landmark["x"]))) * w)
        y = int(max(0.0, min(1.0, float(landmark["y"]))) * h)
        return x, y

    line_color = (60, 220, 255) if flags.get("arm_raised") else (80, 180, 240)
    dot_color = (70, 255, 120) if flags.get("user_visible") else (80, 180, 240)

    for start_name, end_name in POSE_CONNECTIONS:
        start = point(start_name)
        end = point(end_name)
        if start and end:
            cv2.line(frame, start, end, line_color, 2, cv2.LINE_AA)

    for name in LANDMARK_INDEXES:
        pt = point(name)
        if pt:
            cv2.circle(frame, pt, 5, dot_color, -1, cv2.LINE_AA)
            cv2.circle(frame, pt, 7, (15, 25, 30), 1, cv2.LINE_AA)

    return frame


class PoseTracker:
    def __init__(
        self,
        model_path: str | None = None,
        enabled: bool = True,
        inference_width: int | None = None,
        frame_stride: int | None = None,
        async_enabled: bool | None = None,
        max_async_fps: int | None = None,
        delegate: str | None = None,
        backend: str | None = None,
    ):
        self.requested_enabled = bool(enabled)
        self.backend = (backend or os.getenv("POSE_BACKEND", "mediapipe")).strip().lower() or "mediapipe"
        self.model_path = _resolve_model_path(model_path or os.getenv("POSE_MODEL_PATH", DEFAULT_MODEL_PATH))
        self.requested_delegate = _resolve_delegate(delegate, os.getenv("POSE_DELEGATE", DEFAULT_DELEGATE))
        self.active_delegate = "none"
        self.ncnn_model_dir = _resolve_model_path(os.getenv("NCNN_MODEL_DIR", DEFAULT_NCNN_MODEL_DIR))
        self.ncnn_input_size = _resolve_int(None, os.getenv("NCNN_INPUT_SIZE"), DEFAULT_NCNN_INPUT_SIZE, minimum=64)
        self.ncnn_use_vulkan = _resolve_bool(None, os.getenv("NCNN_USE_VULKAN"), True)
        self.ncnn_gpu_index = _resolve_int(None, os.getenv("NCNN_GPU_INDEX"), DEFAULT_NCNN_GPU_INDEX, minimum=0)
        self.ncnn_confidence = _resolve_float(os.getenv("NCNN_CONFIDENCE"), DEFAULT_NCNN_CONFIDENCE, minimum=0.0)
        self.ncnn_iou = _resolve_float(os.getenv("NCNN_IOU"), DEFAULT_NCNN_IOU, minimum=0.0)
        self.movenet_model_path = _resolve_model_path(os.getenv("MOVENET_MODEL_PATH", DEFAULT_MOVENET_MODEL_PATH))
        self.movenet_input_size = _resolve_int(
            None,
            os.getenv("MOVENET_INPUT_SIZE"),
            DEFAULT_MOVENET_INPUT_SIZE,
            minimum=64,
        )
        self.movenet_num_threads = _resolve_int(
            None,
            os.getenv("MOVENET_NUM_THREADS"),
            DEFAULT_MOVENET_NUM_THREADS,
            minimum=1,
        )
        self.inference_width = _resolve_int(
            inference_width,
            os.getenv("POSE_INFERENCE_WIDTH"),
            DEFAULT_INFERENCE_WIDTH,
            minimum=0,
        )
        self.frame_stride = _resolve_int(
            frame_stride,
            os.getenv("POSE_FRAME_STRIDE"),
            DEFAULT_FRAME_STRIDE,
            minimum=1,
        )
        self.async_enabled = _resolve_bool(async_enabled, os.getenv("POSE_ASYNC_ENABLED"), DEFAULT_ASYNC_ENABLED)
        self.max_async_fps = _resolve_int(
            max_async_fps,
            os.getenv("POSE_MAX_ASYNC_FPS"),
            DEFAULT_MAX_ASYNC_FPS,
            minimum=0,
        )
        self.model_loaded = False
        self.enabled = False
        self.last_error: str | None = None
        self.last_warning: str | None = None
        self.last_pose_timestamp: float | None = None
        self.fps_pose = 0.0

        self._mp: Any = None
        self._landmarker: Any = None
        self._ncnn_pose: NcnnYoloPose | None = None
        self._movenet_pose: MoveNetPose | None = None
        self._last_timestamp_ms = 0
        self._landmarker_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._worker_condition = threading.Condition()
        self._worker_thread: threading.Thread | None = None
        self._worker_stop = False
        self._worker_busy = False
        self._pending_frame: np.ndarray | None = None
        self._dropped_frames = 0
        self._submitted_frames = 0
        self._completed_frames = 0
        self._last_async_submit = 0.0
        self._last_status = self._empty_status()
        self._last_landmarks: dict[str, dict[str, float]] = {}
        self._last_metrics = self._empty_metrics()
        self._frame_count = 0
        self._fps_log_started = time.monotonic()
        self._fps_log_total = 0.0
        self._fps_log_count = 0

        logger.info("Pose tracker init. enabled=%s backend=%s", self.requested_enabled, self.backend)
        logger.info("Pose model path: %s", self.model_path)
        logger.info(
            "Pose performance config. delegate=%s inference_width=%s frame_stride=%s async=%s max_async_fps=%s",
            self.requested_delegate,
            self.inference_width or "source",
            self.frame_stride,
            self.async_enabled,
            self.max_async_fps or "unlimited",
        )
        logger.info(
            "MoveNet config. model_path=%s input_size=%s threads=%s",
            self.movenet_model_path,
            self.movenet_input_size,
            self.movenet_num_threads,
        )

        if not self.requested_enabled:
            self.last_error = "Pose tracking disabled by configuration."
            logger.info("Pose tracking disabled by configuration.")
            self._last_status = self._empty_status()
            return

        if self.backend == "mediapipe":
            self._load_mediapipe()
        elif self.backend in NCNN_BACKENDS:
            self._load_ncnn()
        elif self.backend in MOVENET_BACKENDS:
            self._load_movenet()
        else:
            self.last_error = f"Pose backend '{self.backend}' is not implemented."
            logger.error("%s Supported: mediapipe, ncnn_pose, movenet.", self.last_error)
            self._last_status = self._empty_status()

    def process(self, frame: np.ndarray, context: dict | None = None) -> tuple[np.ndarray, dict]:
        output = frame.copy()
        context = context or {}

        if not self.enabled or not self._backend_ready():
            metrics = self._empty_metrics()
            self._last_status = self._status_from_metrics(metrics)
            return output, metrics

        self._frame_count += 1
        if self.async_enabled:
            return self._process_async(output, frame, context)

        if self._should_reuse_previous_pose():
            metrics = dict(self._last_metrics)
            metrics["pose_reused"] = True
            metrics["pose_frame_stride"] = self.frame_stride
            metrics["pose_inference_width"] = self._active_inference_width()
            if context.get("draw_landmarks", True):
                draw_pose_overlay(output, self._last_landmarks, metrics)
            self._last_status = self._status_from_metrics(metrics)
            return output, metrics

        try:
            metrics, landmarks = self._detect_pose(frame)
            if context.get("draw_landmarks", True):
                draw_pose_overlay(output, landmarks, metrics)

            with self._state_lock:
                self._last_landmarks = landmarks
                self._last_metrics = dict(metrics)
                self._last_status = self._status_from_metrics(metrics)
            self._log_average_fps(self.fps_pose)
            return output, metrics
        except Exception as exc:
            self.last_error = str(exc)
            logger.exception("Pose process error; returning raw frame.")
            metrics = self._empty_metrics()
            metrics["pose_enabled"] = True
            metrics["last_error"] = self.last_error
            self._last_status = self._status_from_metrics(metrics)
            return output, metrics

    def _detect_pose(self, frame: np.ndarray) -> tuple[dict[str, Any], dict[str, dict[str, float]]]:
        if self.backend in NCNN_BACKENDS:
            return self._detect_ncnn_pose(frame)
        if self.backend in MOVENET_BACKENDS:
            return self._detect_movenet_pose(frame)
        return self._detect_mediapipe_pose(frame)

    def _detect_mediapipe_pose(self, frame: np.ndarray) -> tuple[dict[str, Any], dict[str, dict[str, float]]]:
        start = time.perf_counter()
        inference_frame = self._resize_for_inference(frame)
        rgb = cv2.cvtColor(inference_frame, cv2.COLOR_BGR2RGB)
        mp_image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        timestamp_ms = self._next_timestamp_ms()

        with self._landmarker_lock:
            result = self._landmarker.detect_for_video(mp_image, timestamp_ms)

        landmarks = extract_required_landmarks(result)
        flags = compute_pose_flags(landmarks)
        elapsed = max(time.perf_counter() - start, 1e-6)
        self.fps_pose = 1.0 / elapsed
        self.last_pose_timestamp = time.time()

        metrics = {
            "pose_enabled": True,
            "pose_backend": self.backend,
            "pose_delegate_requested": self.requested_delegate,
            "pose_delegate_active": self.active_delegate,
            "fps_pose": round(self.fps_pose, 2),
            "last_pose_timestamp": self.last_pose_timestamp,
            "pose_reused": False,
            "pose_async_enabled": self.async_enabled,
            "pose_worker_busy": self._worker_busy,
            "pose_pending": self._pending_frame is not None,
            "pose_dropped_frames": self._dropped_frames,
            "pose_submitted_frames": self._submitted_frames,
            "pose_completed_frames": self._completed_frames,
            "pose_inference_width": self._active_inference_width(),
            "pose_frame_stride": self.frame_stride,
            "landmarks": landmarks,
            **flags,
        }
        return metrics, landmarks

    def _detect_ncnn_pose(self, frame: np.ndarray) -> tuple[dict[str, Any], dict[str, dict[str, float]]]:
        if self._ncnn_pose is None:
            raise RuntimeError("NCNN pose backend is not loaded.")

        start = time.perf_counter()
        landmarks, detection_confidence = self._ncnn_pose.detect(frame)
        flags = compute_pose_flags(landmarks)
        elapsed = max(time.perf_counter() - start, 1e-6)
        self.fps_pose = 1.0 / elapsed
        self.last_pose_timestamp = time.time()

        confidence = max(float(flags.get("confidence", 0.0)), float(detection_confidence))
        metrics = {
            "pose_enabled": True,
            "pose_backend": self.backend,
            "pose_delegate_requested": "vulkan" if self.ncnn_use_vulkan else "cpu",
            "pose_delegate_active": self.active_delegate,
            "fps_pose": round(self.fps_pose, 2),
            "last_pose_timestamp": self.last_pose_timestamp,
            "pose_reused": False,
            "pose_async_enabled": self.async_enabled,
            "pose_worker_busy": self._worker_busy,
            "pose_pending": self._pending_frame is not None,
            "pose_dropped_frames": self._dropped_frames,
            "pose_submitted_frames": self._submitted_frames,
            "pose_completed_frames": self._completed_frames,
            "pose_inference_width": self.ncnn_input_size,
            "pose_frame_stride": self.frame_stride,
            "ncnn_model_dir": str(self.ncnn_model_dir),
            "ncnn_output_shapes": self._ncnn_pose.last_output_shapes,
            "landmarks": landmarks,
            **flags,
        }
        metrics["confidence"] = round(confidence, 4)
        return metrics, landmarks

    def _detect_movenet_pose(self, frame: np.ndarray) -> tuple[dict[str, Any], dict[str, dict[str, float]]]:
        if self._movenet_pose is None:
            raise RuntimeError("MoveNet pose backend is not loaded.")

        start = time.perf_counter()
        landmarks, detection_confidence = self._movenet_pose.detect(frame)
        flags = compute_pose_flags(landmarks)
        elapsed = max(time.perf_counter() - start, 1e-6)
        self.fps_pose = 1.0 / elapsed
        self.last_pose_timestamp = time.time()

        confidence = max(float(flags.get("confidence", 0.0)), float(detection_confidence))
        if confidence < MIN_LANDMARK_CONFIDENCE:
            flags.update(
                {
                    "pose_ok": False,
                    "user_visible": False,
                    "upper_body_visible": False,
                    "full_body_visible": False,
                    "arm_raised": False,
                    "torso_centered": False,
                }
            )

        metrics = {
            "pose_enabled": True,
            "pose_backend": self.backend,
            "pose_delegate_requested": "tflite_cpu",
            "pose_delegate_active": self.active_delegate,
            "fps_pose": round(self.fps_pose, 2),
            "last_pose_timestamp": self.last_pose_timestamp,
            "pose_reused": False,
            "pose_async_enabled": self.async_enabled,
            "pose_worker_busy": self._worker_busy,
            "pose_pending": self._pending_frame is not None,
            "pose_dropped_frames": self._dropped_frames,
            "pose_submitted_frames": self._submitted_frames,
            "pose_completed_frames": self._completed_frames,
            "pose_inference_width": self.movenet_input_size,
            "pose_frame_stride": self.frame_stride,
            "movenet_model_path": str(self.movenet_model_path),
            "movenet_output_shapes": self._movenet_pose.output_shapes,
            "landmarks": landmarks,
            **flags,
        }
        metrics["confidence"] = round(confidence, 4)
        return metrics, landmarks

    def _process_async(self, output: np.ndarray, frame: np.ndarray, context: dict[str, Any]) -> tuple[np.ndarray, dict]:
        submitted = self._submit_async_frame(frame)

        with self._state_lock:
            metrics = dict(self._last_metrics)
            landmarks = dict(self._last_landmarks)

        metrics.update(
            {
                "pose_enabled": True,
                "pose_delegate_requested": self._requested_runtime_delegate(),
                "pose_delegate_active": self.active_delegate,
                "pose_reused": True,
                "pose_async_enabled": True,
                "pose_worker_busy": self._worker_busy,
                "pose_pending": submitted or self._pending_frame is not None,
                "pose_dropped_frames": self._dropped_frames,
                "pose_submitted_frames": self._submitted_frames,
                "pose_completed_frames": self._completed_frames,
                "pose_inference_width": self._active_inference_width(),
                "pose_frame_stride": self.frame_stride,
            }
        )

        if context.get("draw_landmarks", True):
            draw_pose_overlay(output, landmarks, metrics)

        with self._state_lock:
            self._last_status = self._status_from_metrics(metrics)
        return output, metrics

    def get_status(self) -> dict:
        status = dict(self._last_status)
        status.update(
            {
                "pose_enabled": bool(self.enabled and self.model_loaded),
                "pose_backend": self.backend,
                "fps_pose": round(float(self.fps_pose), 2),
                "last_pose_timestamp": self.last_pose_timestamp,
                "model_path": str(self.model_path),
                "model_loaded": self.model_loaded,
                "pose_delegate_requested": self._requested_runtime_delegate(),
                "pose_delegate_active": self.active_delegate,
                "pose_async_enabled": self.async_enabled,
                "pose_worker_busy": self._worker_busy,
                "pose_pending": self._pending_frame is not None,
                "pose_dropped_frames": self._dropped_frames,
                "pose_submitted_frames": self._submitted_frames,
                "pose_completed_frames": self._completed_frames,
                "pose_inference_width": self._active_inference_width(),
                "pose_frame_stride": self.frame_stride,
            }
        )
        if self.last_error:
            status["last_error"] = self.last_error
        if self.last_warning:
            status["last_warning"] = self.last_warning
        return status

    def _backend_ready(self) -> bool:
        if self.backend == "mediapipe":
            return self._landmarker is not None
        if self.backend in NCNN_BACKENDS:
            return self._ncnn_pose is not None
        if self.backend in MOVENET_BACKENDS:
            return self._movenet_pose is not None
        return False

    def _load_mediapipe(self) -> None:
        if not self.model_path.exists():
            self.last_error = f"MediaPipe pose model missing: {self.model_path}"
            logger.error("%s. Place pose_landmarker.task there; pose tracking will stay disabled.", self.last_error)
            self._last_status = self._empty_status()
            return

        try:
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            try:
                self._landmarker = self._create_landmarker(python, vision, self.requested_delegate)
            except Exception as exc:
                if self.requested_delegate != "gpu":
                    raise
                self.last_warning = f"GPU delegate failed: {exc}; using CPU fallback."
                logger.exception("MediaPipe GPU delegate failed; falling back to CPU.")
                self._landmarker = self._create_landmarker(python, vision, "cpu")

            self._mp = mp
            self.model_loaded = True
            self.enabled = True
            self.last_error = None
            self._last_status = self._empty_status()
            self._last_metrics = self._empty_metrics()
            logger.info("MediaPipe Pose Landmarker loaded successfully. delegate=%s", self.active_delegate)
            self._start_async_worker()
        except Exception as exc:
            self.last_error = f"MediaPipe Pose Landmarker load failed: {exc}"
            self.model_loaded = False
            self.enabled = False
            self.active_delegate = "none"
            self._landmarker = None
            self._mp = None
            self._last_status = self._empty_status()
            logger.exception("MediaPipe import/model load failure; pose tracking disabled.")

    def _load_ncnn(self) -> None:
        try:
            self._ncnn_pose = NcnnYoloPose(
                model_dir=self.ncnn_model_dir,
                input_size=self.ncnn_input_size,
                use_vulkan=self.ncnn_use_vulkan,
                gpu_index=self.ncnn_gpu_index,
                confidence_threshold=self.ncnn_confidence,
                iou_threshold=self.ncnn_iou,
            )
            self.model_path = self._ncnn_pose.param_path
            self._ncnn_pose.load()
            self.model_loaded = True
            self.enabled = True
            self.last_error = None
            self.active_delegate = self._ncnn_pose.active_device
            self._last_status = self._empty_status()
            self._last_metrics = self._empty_metrics()
            logger.info("NCNN pose backend loaded successfully. device=%s", self.active_delegate)
            self._start_async_worker()
        except Exception as exc:
            self.last_error = f"NCNN pose backend load failed: {exc}"
            self.model_loaded = False
            self.enabled = False
            self.active_delegate = "none"
            self._ncnn_pose = None
            self._last_status = self._empty_status()
            logger.exception("NCNN pose backend load failure; pose tracking disabled.")

    def _load_movenet(self) -> None:
        if not self.movenet_model_path.exists():
            self.last_error = f"MoveNet model missing: {self.movenet_model_path}"
            logger.error("%s. Place movenet_lightning.tflite there; pose tracking will stay disabled.", self.last_error)
            self.model_path = self.movenet_model_path
            self._last_status = self._empty_status()
            return

        try:
            self._movenet_pose = MoveNetPose(
                model_path=self.movenet_model_path,
                input_size=self.movenet_input_size,
                num_threads=self.movenet_num_threads,
            )
            self.model_path = self.movenet_model_path
            self._movenet_pose.load()
            self.movenet_input_size = self._movenet_pose.input_size
            self.model_loaded = True
            self.enabled = True
            self.last_error = None
            self.active_delegate = self._movenet_pose.runtime_name
            self._last_status = self._empty_status()
            self._last_metrics = self._empty_metrics()
            logger.info("MoveNet pose backend loaded successfully. runtime=%s", self.active_delegate)
            self._start_async_worker()
        except Exception as exc:
            self.last_error = f"MoveNet pose backend load failed: {exc}"
            self.model_loaded = False
            self.enabled = False
            self.active_delegate = "none"
            self._movenet_pose = None
            self._last_status = self._empty_status()
            logger.exception("MoveNet pose backend load failure; pose tracking disabled.")

    def _create_landmarker(self, python: Any, vision: Any, delegate_name: str) -> Any:
        delegate_container = getattr(python.BaseOptions, "Delegate", None)
        delegate_enum = getattr(delegate_container, delegate_name.upper(), None) if delegate_container else None
        if delegate_enum is None:
            if delegate_name != "cpu":
                raise RuntimeError(f"MediaPipe delegate enum is unavailable for {delegate_name}.")
            logger.warning("MediaPipe delegate enum unavailable; using default CPU delegate.")
            base_options = python.BaseOptions(model_asset_path=str(self.model_path))
            options = self._pose_landmarker_options(vision, base_options)
            landmarker = vision.PoseLandmarker.create_from_options(options)
            self.active_delegate = "cpu"
            return landmarker

        try:
            base_options = python.BaseOptions(model_asset_path=str(self.model_path), delegate=delegate_enum)
        except TypeError:
            if delegate_name != "cpu":
                raise
            logger.warning("MediaPipe BaseOptions delegate argument unavailable; using default CPU delegate.")
            base_options = python.BaseOptions(model_asset_path=str(self.model_path))

        options = self._pose_landmarker_options(vision, base_options)
        landmarker = vision.PoseLandmarker.create_from_options(options)
        self.active_delegate = delegate_name
        return landmarker

    def _pose_landmarker_options(self, vision: Any, base_options: Any) -> Any:
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=MIN_LANDMARK_CONFIDENCE,
            min_pose_presence_confidence=MIN_LANDMARK_CONFIDENCE,
            min_tracking_confidence=MIN_LANDMARK_CONFIDENCE,
            output_segmentation_masks=False,
        )
        return options

    def _next_timestamp_ms(self) -> int:
        timestamp_ms = int(time.monotonic() * 1000)
        if timestamp_ms <= self._last_timestamp_ms:
            timestamp_ms = self._last_timestamp_ms + 1
        self._last_timestamp_ms = timestamp_ms
        return timestamp_ms

    def _resize_for_inference(self, frame: np.ndarray) -> np.ndarray:
        if self.inference_width <= 0:
            return frame

        h, w = frame.shape[:2]
        if w <= self.inference_width:
            return frame

        target_h = max(1, int(h * (self.inference_width / float(w))))
        return cv2.resize(frame, (self.inference_width, target_h), interpolation=cv2.INTER_AREA)

    def _should_reuse_previous_pose(self) -> bool:
        if self.frame_stride <= 1:
            return False
        if not self._last_landmarks:
            return False
        return (self._frame_count - 1) % self.frame_stride != 0

    def _submit_async_frame(self, frame: np.ndarray) -> bool:
        if self._should_reuse_previous_pose():
            return False

        now = time.monotonic()
        if self.max_async_fps > 0 and now - self._last_async_submit < 1.0 / float(self.max_async_fps):
            return False

        frame_copy = frame.copy()
        with self._worker_condition:
            if self._pending_frame is not None:
                self._dropped_frames += 1
            self._pending_frame = frame_copy
            self._submitted_frames += 1
            self._last_async_submit = now
            self._worker_condition.notify()
        return True

    def _start_async_worker(self) -> None:
        if not self.async_enabled or self._worker_thread is not None:
            return
        self._worker_thread = threading.Thread(target=self._async_worker_loop, name="pose-tracker-worker", daemon=True)
        self._worker_thread.start()
        logger.info("Async pose worker started.")

    def _async_worker_loop(self) -> None:
        while True:
            with self._worker_condition:
                while self._pending_frame is None and not self._worker_stop:
                    self._worker_condition.wait(timeout=0.5)
                if self._worker_stop:
                    return
                frame = self._pending_frame
                self._pending_frame = None
                self._worker_busy = True

            try:
                if frame is None:
                    continue
                metrics, landmarks = self._detect_pose(frame)
                with self._state_lock:
                    self._completed_frames += 1
                    metrics["pose_completed_frames"] = self._completed_frames
                    metrics["pose_worker_busy"] = False
                    metrics["pose_pending"] = self._pending_frame is not None
                    metrics["pose_dropped_frames"] = self._dropped_frames
                    self._last_landmarks = landmarks
                    self._last_metrics = dict(metrics)
                    self._last_status = self._status_from_metrics(metrics)
                self._log_average_fps(self.fps_pose)
            except Exception as exc:
                self.last_error = str(exc)
                logger.exception("Async pose process error; keeping last good pose.")
            finally:
                with self._worker_condition:
                    self._worker_busy = False

    def _empty_metrics(self) -> dict[str, Any]:
        return {
            "pose_enabled": bool(self.enabled and self.model_loaded),
            "pose_backend": self.backend,
            "pose_delegate_requested": self._requested_runtime_delegate(),
            "pose_delegate_active": self.active_delegate,
            "pose_ok": False,
            "user_visible": False,
            "upper_body_visible": False,
            "full_body_visible": False,
            "arm_raised": False,
            "torso_centered": False,
            "confidence": 0.0,
            "fps_pose": round(float(self.fps_pose), 2),
            "last_pose_timestamp": self.last_pose_timestamp,
            "pose_reused": False,
            "pose_async_enabled": self.async_enabled,
            "pose_worker_busy": self._worker_busy,
            "pose_pending": self._pending_frame is not None,
            "pose_dropped_frames": self._dropped_frames,
            "pose_submitted_frames": self._submitted_frames,
            "pose_completed_frames": self._completed_frames,
            "pose_inference_width": self._active_inference_width(),
            "pose_frame_stride": self.frame_stride,
            "landmarks": {},
        }

    def _empty_status(self) -> dict[str, Any]:
        return {
            "pose_enabled": bool(self.enabled and self.model_loaded),
            "pose_backend": self.backend,
            "pose_delegate_requested": self._requested_runtime_delegate(),
            "pose_delegate_active": self.active_delegate,
            "pose_ok": False,
            "fps_pose": round(float(self.fps_pose), 2),
            "last_pose_timestamp": self.last_pose_timestamp,
            "user_visible": False,
            "arm_raised": False,
            "torso_centered": False,
            "confidence": 0.0,
            "pose_reused": False,
            "pose_async_enabled": self.async_enabled,
            "pose_worker_busy": self._worker_busy,
            "pose_pending": self._pending_frame is not None,
            "pose_dropped_frames": self._dropped_frames,
            "pose_submitted_frames": self._submitted_frames,
            "pose_completed_frames": self._completed_frames,
            "model_path": str(self.model_path),
            "model_loaded": self.model_loaded,
            "pose_inference_width": self._active_inference_width(),
            "pose_frame_stride": self.frame_stride,
        }

    def _status_from_metrics(self, metrics: dict[str, Any]) -> dict[str, Any]:
        status = self._empty_status()
        for key in (
            "pose_enabled",
            "pose_backend",
            "pose_delegate_requested",
            "pose_delegate_active",
            "pose_ok",
            "fps_pose",
            "last_pose_timestamp",
            "user_visible",
            "arm_raised",
            "torso_centered",
            "confidence",
            "pose_reused",
            "pose_async_enabled",
            "pose_worker_busy",
            "pose_pending",
            "pose_dropped_frames",
            "pose_submitted_frames",
            "pose_completed_frames",
            "pose_inference_width",
            "pose_frame_stride",
        ):
            status[key] = metrics.get(key, status[key])
        return status

    def _log_average_fps(self, fps: float) -> None:
        self._fps_log_total += fps
        self._fps_log_count += 1
        now = time.monotonic()
        if now - self._fps_log_started < FPS_LOG_INTERVAL_SEC:
            return
        average = self._fps_log_total / max(1, self._fps_log_count)
        logger.info("Average pose FPS over %.1fs: %.2f", now - self._fps_log_started, average)
        self._fps_log_started = now
        self._fps_log_total = 0.0
        self._fps_log_count = 0

    def _requested_runtime_delegate(self) -> str:
        if self.backend in NCNN_BACKENDS:
            return "vulkan" if self.ncnn_use_vulkan else "cpu"
        if self.backend in MOVENET_BACKENDS:
            return "tflite_cpu"
        return self.requested_delegate

    def _active_inference_width(self) -> int:
        if self.backend in NCNN_BACKENDS:
            return self.ncnn_input_size
        if self.backend in MOVENET_BACKENDS:
            return self.movenet_input_size
        return self.inference_width


def _landmark_score(landmark: Any) -> float:
    visibility = getattr(landmark, "visibility", None)
    if visibility is not None:
        return float(visibility)
    presence = getattr(landmark, "presence", None)
    if presence is not None:
        return float(presence)
    return 1.0


def _resolve_model_path(model_path: str) -> Path:
    path = Path(model_path).expanduser()
    if path.is_absolute():
        return path
    project_root = Path(__file__).resolve().parents[1]
    return project_root / path


def _resolve_int(value: int | None, env_value: str | None, default: int, minimum: int) -> int:
    raw: Any = value if value is not None else env_value
    if raw is None or raw == "":
        return default
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        logger.warning("Invalid pose integer value %r. Using %s.", raw, default)
        return default
    return max(minimum, parsed)


def _resolve_bool(value: bool | None, env_value: str | None, default: bool) -> bool:
    if value is not None:
        return bool(value)
    if env_value is None or env_value == "":
        return default
    return env_value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_float(env_value: str | None, default: float, minimum: float) -> float:
    if env_value is None or env_value == "":
        return default
    try:
        parsed = float(env_value)
    except (TypeError, ValueError):
        logger.warning("Invalid pose float value %r. Using %s.", env_value, default)
        return default
    return max(minimum, parsed)


def _resolve_delegate(value: str | None, env_value: str | None) -> str:
    raw = (value if value is not None else env_value) or DEFAULT_DELEGATE
    delegate = raw.strip().lower()
    if delegate in {"cpu", "gpu"}:
        return delegate
    logger.warning("Invalid POSE_DELEGATE=%r. Using %s.", raw, DEFAULT_DELEGATE)
    return DEFAULT_DELEGATE
