from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from statistics import mean
from typing import Any

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.movenet_pose import DEFAULT_MOVENET_INPUT_SIZE, DEFAULT_MOVENET_MODEL_PATH, DEFAULT_MOVENET_NUM_THREADS  # noqa: E402
from app.pose_tracker import DEFAULT_MODEL_PATH, PoseTracker  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark StretchSense pose models/backends.")
    parser.add_argument("--camera", type=int, default=None, help="Optional OpenCV camera index.")
    parser.add_argument("--image", default=None, help="Optional image path. Used when no camera is set.")
    parser.add_argument("--width", type=int, default=320, help="Camera width or generated frame width.")
    parser.add_argument("--height", type=int, default=240, help="Camera height or generated frame height.")
    parser.add_argument("--frames", type=int, default=60, help="Measured frames per model.")
    parser.add_argument("--warmup", type=int, default=5, help="Warmup frames per model.")
    parser.add_argument("--mediapipe-widths", default="192,256,320", help="Comma-separated MediaPipe inference widths.")
    parser.add_argument("--ncnn-sizes", default="192,224,320", help="Comma-separated NCNN input sizes.")
    parser.add_argument("--ncnn-model-dir", action="append", default=[], help="NCNN model directory. Can be repeated.")
    parser.add_argument("--movenet-model", action="append", default=[], help="MoveNet .tflite path. Can be repeated.")
    parser.add_argument("--movenet-sizes", default=str(DEFAULT_MOVENET_INPUT_SIZE), help="Comma-separated MoveNet input sizes.")
    parser.add_argument("--movenet-threads", type=int, default=DEFAULT_MOVENET_NUM_THREADS, help="MoveNet TFLite/LiteRT CPU thread count.")
    parser.add_argument("--no-mediapipe", action="store_true", help="Skip MediaPipe tests.")
    parser.add_argument("--no-ncnn", action="store_true", help="Skip NCNN tests.")
    parser.add_argument("--no-movenet", action="store_true", help="Skip MoveNet tests.")
    parser.add_argument("--ncnn-cpu", action="store_true", help="Run NCNN on CPU instead of Vulkan.")
    parser.add_argument("--ncnn-gpu-index", type=int, default=0, help="NCNN Vulkan GPU index.")
    args = parser.parse_args()

    _setup_logging()
    frames = _load_frames(args)
    configs = _build_configs(args)
    if not configs:
        print("No benchmark configs found.")
        return 1

    results = []
    for config in configs:
        result = _run_config(config, frames, warmup=max(0, args.warmup), measured=max(1, args.frames))
        results.append(result)
        print(json.dumps(result, sort_keys=True))

    print("\nSummary")
    for result in results:
        label = result["label"]
        status = "ok" if result.get("model_loaded") else "skip"
        fps = result.get("fps_mean", 0.0)
        device = result.get("pose_delegate_active") or "none"
        confidence = result.get("confidence_last", 0.0)
        print(f"{label:36s} {status:4s} fps={fps:6.2f} device={device:10s} conf={confidence:.2f}")

    return 0


def _build_configs(args: argparse.Namespace) -> list[dict[str, Any]]:
    configs: list[dict[str, Any]] = []

    if not args.no_mediapipe:
        model_path = PROJECT_ROOT / DEFAULT_MODEL_PATH
        for width in _parse_int_list(args.mediapipe_widths):
            configs.append(
                {
                    "label": f"mediapipe_w{width}",
                    "backend": "mediapipe",
                    "model_path": str(model_path),
                    "pose_width": width,
                    "env": {
                        "POSE_BACKEND": "mediapipe",
                        "POSE_DELEGATE": "cpu",
                    },
                }
            )

    if not args.no_ncnn:
        ncnn_dirs = [Path(value) for value in args.ncnn_model_dir]
        ncnn_dirs.extend(sorted((PROJECT_ROOT / "models").glob("*_ncnn_model")))
        unique_dirs = []
        seen = set()
        for model_dir in ncnn_dirs:
            resolved = _resolve_path(model_dir)
            if resolved in seen:
                continue
            seen.add(resolved)
            unique_dirs.append(resolved)

        for model_dir in unique_dirs:
            for size in _parse_int_list(args.ncnn_sizes):
                configs.append(
                    {
                        "label": f"{model_dir.name}_ncnn{size}",
                        "backend": "ncnn_pose",
                        "model_path": str(PROJECT_ROOT / DEFAULT_MODEL_PATH),
                        "pose_width": 0,
                        "env": {
                            "POSE_BACKEND": "ncnn_pose",
                            "NCNN_MODEL_DIR": str(model_dir),
                            "NCNN_INPUT_SIZE": str(size),
                            "NCNN_USE_VULKAN": "false" if args.ncnn_cpu else "true",
                            "NCNN_GPU_INDEX": str(args.ncnn_gpu_index),
                        },
                    }
                )

    if not args.no_movenet:
        movenet_paths = [Path(value) for value in args.movenet_model]
        default_movenet = PROJECT_ROOT / DEFAULT_MOVENET_MODEL_PATH
        if default_movenet.exists():
            movenet_paths.append(default_movenet)
        movenet_paths.extend(sorted((PROJECT_ROOT / "models").glob("movenet*.tflite")))

        unique_paths = []
        seen_paths = set()
        for model_path in movenet_paths:
            resolved = _resolve_path(model_path)
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            unique_paths.append(resolved)

        for model_path in unique_paths:
            for size in _parse_int_list(args.movenet_sizes):
                configs.append(
                    {
                        "label": f"{model_path.stem}_movenet{size}",
                        "backend": "movenet",
                        "model_path": str(PROJECT_ROOT / DEFAULT_MODEL_PATH),
                        "pose_width": 0,
                        "env": {
                            "POSE_BACKEND": "movenet",
                            "MOVENET_MODEL_PATH": str(model_path),
                            "MOVENET_INPUT_SIZE": str(size),
                            "MOVENET_NUM_THREADS": str(args.movenet_threads),
                        },
                    }
                )

    return configs


def _run_config(config: dict[str, Any], frames: list[np.ndarray], warmup: int, measured: int) -> dict[str, Any]:
    old_env = {key: os.environ.get(key) for key in config["env"]}
    os.environ.update(config["env"])
    try:
        tracker = PoseTracker(
            model_path=config["model_path"],
            enabled=True,
            inference_width=config["pose_width"],
            async_enabled=False,
            max_async_fps=0,
            backend=config["backend"],
        )
        status = tracker.get_status()
        result = {
            "label": config["label"],
            "backend": config["backend"],
            "model_loaded": bool(status.get("model_loaded")),
            "model_path": status.get("model_path"),
            "pose_delegate_requested": status.get("pose_delegate_requested"),
            "pose_delegate_active": status.get("pose_delegate_active"),
            "last_error": status.get("last_error"),
        }
        if not status.get("model_loaded"):
            return result

        total = warmup + measured
        timings: list[float] = []
        last_metrics: dict[str, Any] = {}
        for index in range(total):
            frame = frames[index % len(frames)]
            start = time.perf_counter()
            _, metrics = tracker.process(frame, {"draw_landmarks": False})
            elapsed = time.perf_counter() - start
            if index >= warmup:
                timings.append(elapsed)
                last_metrics = metrics

        fps_values = [1.0 / max(value, 1e-6) for value in timings]
        result.update(
            {
                "fps_mean": round(mean(fps_values), 2) if fps_values else 0.0,
                "fps_last_reported": last_metrics.get("fps_pose", 0.0),
                "pose_ok_last": last_metrics.get("pose_ok", False),
                "confidence_last": last_metrics.get("confidence", 0.0),
                "user_visible_last": last_metrics.get("user_visible", False),
                "arm_raised_last": last_metrics.get("arm_raised", False),
                "torso_centered_last": last_metrics.get("torso_centered", False),
                "ncnn_output_shapes": last_metrics.get("ncnn_output_shapes"),
                "movenet_output_shapes": last_metrics.get("movenet_output_shapes"),
            }
        )
        return result
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _load_frames(args: argparse.Namespace) -> list[np.ndarray]:
    if args.camera is not None:
        cap = cv2.VideoCapture(args.camera)
        if not cap.isOpened():
            raise RuntimeError(f"Camera {args.camera} did not open.")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
        frames = []
        try:
            for _ in range(10):
                ok, frame = cap.read()
                if ok and frame is not None:
                    frames.append(frame)
            if not frames:
                raise RuntimeError(f"Camera {args.camera} returned no frames.")
            return frames
        finally:
            cap.release()

    if args.image:
        image = cv2.imread(args.image)
        if image is None:
            image = _read_jpeg_from_mjpeg_dump(args.image)
        if image is None:
            raise RuntimeError(f"Could not read image: {args.image}")
        return [image]

    frame = np.zeros((args.height, args.width, 3), dtype=np.uint8)
    cv2.putText(frame, "StretchSense", (20, args.height // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (220, 220, 220), 2)
    return [frame]


def _parse_int_list(value: str) -> list[int]:
    parsed = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        parsed.append(int(item))
    return parsed


def _resolve_path(path: Path) -> Path:
    path = path.expanduser()
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _read_jpeg_from_mjpeg_dump(path: str) -> np.ndarray | None:
    data = Path(path).read_bytes()
    start = data.find(b"\xff\xd8")
    end = data.find(b"\xff\xd9", start + 2)
    if start < 0 or end < 0:
        return None
    jpg = np.frombuffer(data[start : end + 2], dtype=np.uint8)
    return cv2.imdecode(jpg, cv2.IMREAD_COLOR)


def _setup_logging() -> None:
    try:
        from app.utils import setup_logging

        setup_logging()
    except Exception:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        )


if __name__ == "__main__":
    raise SystemExit(main())
