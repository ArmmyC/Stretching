# Codex Worklog: Pose Tracking

Date/time: 2026-05-28 00:14 Asia/Bangkok

## Files Created

- `app/pose_tracker.py`
- `tools/test_pose_camera.py`
- `models/README_MODELS.md`
- `docs/POSE_TRACKING.md`
- `docs/CODEX_WORKLOG_POSE.md`

## Files Modified

- `app/inference.py`
- `app/main.py`
- `app/utils.py`

The same code was mirrored into `stretch_applab/python` for the Arduino App Lab package copy.

## Backend Chosen

- Primary backend: MediaPipe Pose Landmarker.
- Model path: `models/pose_landmarker.task`.
- Runtime mode: MediaPipe video mode with increasing frame timestamps.
- `num_poses=1`.
- Segmentation masks disabled.
- Default confidence thresholds: `0.5`.

MoveNet Lightning remains the planned fallback if MediaPipe is unavailable or too slow. It was not implemented in this pass because no local MoveNet model/runtime was already present, and the MVP must avoid downloads and cloud services.

## Assumptions

- The active source app is `stretch_stream`.
- The UNO Q package copy is `stretch_applab/python`, so it should stay in sync with the source app.
- MediaPipe and `pose_landmarker.task` may be installed manually later.
- If MediaPipe or the model is missing, raw camera streaming should continue.

## Environment Variables Added

- `POSE_TRACKING_ENABLED=true`
- `POSE_MODEL_PATH=models/pose_landmarker.task`
- `POSE_DRAW_LANDMARKS=true`
- `POSE_BACKEND=mediapipe`
- `POSE_DELEGATE=cpu`
- `POSE_INFERENCE_WIDTH=320`
- `POSE_FRAME_STRIDE=1`
- `POSE_ASYNC_ENABLED=true`
- `POSE_MAX_ASYNC_FPS=8`
- `NCNN_MODEL_DIR=models/yolov8n-pose_ncnn_model`
- `NCNN_INPUT_SIZE=320`
- `NCNN_USE_VULKAN=true`
- `NCNN_GPU_INDEX=0`

## Tests Run

- `python -m compileall app tools` in `stretch_stream`: passed.
- `python -m compileall app tools` in `stretch_applab/python`: passed.
- Blank-frame `inference.process_frame(...)` smoke test in `stretch_stream`: passed, returned safe false pose flags with missing model.
- Blank-frame `inference.process_frame(...)` smoke test in `stretch_applab/python`: passed, returned safe false pose flags with missing model.
- `/api/status` shape smoke via `stretch_stream/.venv/Scripts/python.exe`: passed, pose status included and landmarks omitted by default.
- Synthetic `compute_pose_flags(...)` rule check: passed for `user_visible`, `arm_raised`, and `torso_centered`.

## Errors Encountered

- Global Python did not have FastAPI installed, so a direct `from app.main import full_status` status smoke failed with `ModuleNotFoundError: No module named 'fastapi'`.
- Retried the status smoke with `stretch_stream/.venv/Scripts/python.exe`, which passed.
- No local `models/pose_landmarker.task` file is present yet, so `model_loaded=false` was expected and verified.
- No physical camera test was run during this pass.

## Known Limitations

- Current implementation only supports MediaPipe at runtime.
- Missing MediaPipe or missing model disables pose tracking gracefully.
- 2D pose cannot reliably detect depth, rotation, or occluded joints.
- No stretch scoring is implemented.
- No Nano IMU fusion is implemented yet.

## Next Steps

- Place `pose_landmarker.task` in `models/`.
- Run `python tools/test_pose_camera.py --camera 0 --width 640 --height 480`.
- Try `320x240` if pose FPS is low on the UNO Q.
- Add Nano IMU fusion later using `camera_arm_raised + nano_arm_raised + nano_stable + distance_ok`.
- Add MoveNet Lightning fallback only if MediaPipe is unavailable or too slow on target hardware.

## Follow-up: Low FPS Tuning

Added performance knobs after UNO Q reported about 5-6 FPS:

- `POSE_INFERENCE_WIDTH`: resize frame before MediaPipe inference; default `320`, use `0` for source size.
- `POSE_FRAME_STRIDE`: run pose every Nth frame and reuse the last landmarks between inference frames; default `1`.
- `tools/test_pose_camera.py --pose-width` and `--pose-stride` for quick board-side tests.

## Follow-up: Smooth Stream With Lagging Skeleton

Added async pose mode so `/video_feed` no longer blocks on MediaPipe:

- `POSE_ASYNC_ENABLED=true` starts a background pose worker.
- `POSE_MAX_ASYNC_FPS` throttles pose submissions.
- New frames replace older pending pose frames, so the worker always processes the latest available camera image.
- Display frames draw the last completed skeleton and return immediately.
- `tools/test_pose_camera.py --sync-pose` can still force blocking mode for debugging.

## Follow-up: MediaPipe Delegate Switch

Added a delegate experiment knob for UNO Q:

- `POSE_DELEGATE=cpu` keeps the known-good XNNPACK CPU path.
- `POSE_DELEGATE=gpu` requests `python.BaseOptions.Delegate.GPU`.
- If GPU initialization fails, the loader logs the error and falls back to CPU.
- `/api/status` and test metrics report `pose_delegate_requested` and `pose_delegate_active`.
- `tools/test_pose_camera.py --delegate gpu` tests the GPU path directly.

## Follow-up: NCNN Vulkan Backend

Added experimental `POSE_BACKEND=ncnn_pose` after UNO Q confirmed Vulkan sees `Turnip Adreno (TM) 702`.

- New file: `app/ncnn_pose.py`.
- Loads `model.ncnn.param`/`model.ncnn.bin` or `model.param`/`model.bin`.
- Uses NCNN Vulkan by default with `NCNN_GPU_INDEX=0`.
- Maps YOLO COCO keypoints to YUEDMAI shoulders/elbows/wrists/hips/knees/ankles.
- Reuses the same async worker, overlay, status, and pose-rule logic as MediaPipe.
- Reports `ncnn_output_shapes` if the NCNN export layout needs decoder adjustment.

## Follow-up: Model Benchmark Helper

Added `tools/benchmark_pose_models.py` to compare local pose models/backends with a shared frame source.

- Tests MediaPipe at multiple inference widths.
- Auto-discovers `models/*_ncnn_model`.
- Tests NCNN at multiple input sizes.
- Runs synchronously to measure actual inference FPS, independent of async stream smoothing.
- Prints JSON rows plus a compact summary.

## Follow-up: MoveNet TFLite Backend

Added a local MoveNet fallback after YOLO/NCNN measured around 1-2 FPS on UNO Q.

- New file: `app/movenet_pose.py`.
- New backend: `POSE_BACKEND=movenet`.
- Default model path: `models/movenet_lightning.tflite`.
- Environment variables:
  - `MOVENET_MODEL_PATH=models/movenet_lightning.tflite`
  - `MOVENET_INPUT_SIZE=192`
  - `MOVENET_NUM_THREADS=2`
- Runtime priority inside the backend: `ai-edge-litert`, then `tflite-runtime`, then `tensorflow`.
- Maps MoveNet's 17 COCO keypoints to YUEDMAI shoulders/elbows/wrists/hips/knees/ankles.
- Reuses the same overlay, async worker, status JSON, and pose flags.
- Updated `tools/test_pose_camera.py` with `--backend movenet`, `--movenet-model`, `--movenet-input-size`, and `--movenet-threads`.
- Updated `tools/benchmark_pose_models.py` to auto-discover `models/movenet*.tflite` and to extract the first JPEG from an MJPEG dump saved from `/video_feed`.

Assumption: MoveNet is CPU-only in this Python path. It is expected to be lighter than YOLO pose, not a GPU acceleration solution.
