from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.movenet_pose import DEFAULT_MOVENET_INPUT_SIZE, DEFAULT_MOVENET_MODEL_PATH, DEFAULT_MOVENET_NUM_THREADS  # noqa: E402
from app.pose_tracker import DEFAULT_MODEL_PATH, PoseTracker  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Test YUEDMAI camera pose tracking.")
    parser.add_argument("--camera", type=int, default=0, help="OpenCV camera index.")
    parser.add_argument("--width", type=int, default=640, help="Requested frame width.")
    parser.add_argument("--height", type=int, default=480, help="Requested frame height.")
    parser.add_argument("--backend", choices=("mediapipe", "ncnn_pose", "movenet"), default=None, help="Pose backend to test.")
    parser.add_argument("--model", default=DEFAULT_MODEL_PATH, help="Path to MediaPipe pose_landmarker.task.")
    parser.add_argument("--delegate", choices=("cpu", "gpu"), default=None, help="MediaPipe delegate to request. GPU falls back to CPU if unavailable.")
    parser.add_argument("--ncnn-model-dir", default=None, help="Directory containing model.ncnn.param and model.ncnn.bin.")
    parser.add_argument("--ncnn-input-size", type=int, default=None, help="Square NCNN pose input size, for example 320.")
    parser.add_argument("--ncnn-cpu", action="store_true", help="Disable NCNN Vulkan and run NCNN on CPU.")
    parser.add_argument("--ncnn-gpu-index", type=int, default=None, help="NCNN Vulkan GPU index. Use 0 for Adreno on UNO Q.")
    parser.add_argument("--movenet-model", default=DEFAULT_MOVENET_MODEL_PATH, help="Path to MoveNet SinglePose .tflite model.")
    parser.add_argument("--movenet-input-size", type=int, default=DEFAULT_MOVENET_INPUT_SIZE, help="MoveNet square input size, usually 192 for Lightning.")
    parser.add_argument("--movenet-threads", type=int, default=DEFAULT_MOVENET_NUM_THREADS, help="CPU threads for the TFLite/LiteRT interpreter.")
    parser.add_argument("--pose-width", type=int, default=None, help="Resize frame to this width for pose inference. Use 0 for source size.")
    parser.add_argument("--pose-stride", type=int, default=None, help="Run pose every Nth frame and reuse the last skeleton between runs.")
    parser.add_argument("--sync-pose", action="store_true", help="Run pose synchronously for debugging. Default uses a background worker.")
    parser.add_argument("--max-async-fps", type=int, default=None, help="Limit async pose worker submissions per second. Use 0 for unlimited.")
    args = parser.parse_args()

    _setup_logging()
    if args.ncnn_model_dir:
        os.environ["NCNN_MODEL_DIR"] = args.ncnn_model_dir
    if args.ncnn_input_size is not None:
        os.environ["NCNN_INPUT_SIZE"] = str(args.ncnn_input_size)
    if args.ncnn_cpu:
        os.environ["NCNN_USE_VULKAN"] = "false"
    if args.ncnn_gpu_index is not None:
        os.environ["NCNN_GPU_INDEX"] = str(args.ncnn_gpu_index)
    if args.movenet_model:
        os.environ["MOVENET_MODEL_PATH"] = args.movenet_model
    if args.movenet_input_size is not None:
        os.environ["MOVENET_INPUT_SIZE"] = str(args.movenet_input_size)
    if args.movenet_threads is not None:
        os.environ["MOVENET_NUM_THREADS"] = str(args.movenet_threads)

    tracker = PoseTracker(
        model_path=args.model,
        enabled=True,
        inference_width=args.pose_width,
        frame_stride=args.pose_stride,
        async_enabled=not args.sync_pose,
        max_async_fps=args.max_async_fps,
        delegate=args.delegate,
        backend=args.backend,
    )
    status = tracker.get_status()
    print(f"model_loaded={status.get('model_loaded')} backend={status.get('pose_backend')} model_path={status.get('model_path')}")
    if status.get("last_error"):
        print(f"pose_error={status['last_error']}")

    cap = cv2.VideoCapture(args.camera)
    print(f"camera_opened={cap.isOpened()} camera_index={args.camera}")
    if not cap.isOpened():
        return 1

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    last_print = 0.0
    last_frame_time = time.perf_counter()
    camera_fps = 0.0
    window_available = True

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                print("camera_read=false")
                time.sleep(0.1)
                continue

            now = time.perf_counter()
            camera_fps = 1.0 / max(now - last_frame_time, 1e-6)
            last_frame_time = now

            output, metrics = tracker.process(frame, {"draw_landmarks": True})
            cv2.putText(
                output,
                f"Camera FPS: {camera_fps:.1f}",
                (18, output.shape[0] - 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.62,
                (230, 245, 248),
                2,
                cv2.LINE_AA,
            )

            if now - last_print >= 1.0:
                print(json.dumps(_compact_metrics(metrics, tracker.get_status(), camera_fps), sort_keys=True))
                last_print = now

            if window_available:
                try:
                    cv2.imshow("YUEDMAI Pose Test", output)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (27, ord("q")):
                        break
                except cv2.error as exc:
                    print(f"opencv_window_unavailable={exc}")
                    print("Continuing print-only. Press Ctrl+C to exit.")
                    window_available = False
    except KeyboardInterrupt:
        print("interrupted=true")
    finally:
        cap.release()
        if window_available:
            cv2.destroyAllWindows()

    return 0


def _compact_metrics(metrics: dict[str, Any], status: dict[str, Any], camera_fps: float) -> dict[str, Any]:
    keys = (
        "pose_enabled",
        "pose_backend",
        "pose_delegate_requested",
        "pose_delegate_active",
        "pose_ok",
        "user_visible",
        "upper_body_visible",
        "full_body_visible",
        "arm_raised",
        "torso_centered",
        "confidence",
        "fps_pose",
        "pose_reused",
        "pose_async_enabled",
        "pose_worker_busy",
        "pose_pending",
        "pose_dropped_frames",
        "pose_inference_width",
        "pose_frame_stride",
        "ncnn_model_dir",
        "ncnn_output_shapes",
        "movenet_model_path",
        "movenet_output_shapes",
    )
    compact = {key: metrics.get(key) for key in keys}
    compact["model_loaded"] = status.get("model_loaded")
    compact["camera_fps"] = round(camera_fps, 2)
    return compact


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
