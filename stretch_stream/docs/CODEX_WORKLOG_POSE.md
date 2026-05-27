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
