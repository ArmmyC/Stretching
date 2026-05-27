# StretchSense Model Files

StretchSense expects a local MediaPipe Pose Landmarker model at:

```text
models/pose_landmarker.task
```

The app does not download model files at runtime. Place the `.task` file there manually before starting FastAPI or running the standalone camera test.

MediaPipe must also be installed in the Python environment if your UNO Q/Linux image has a compatible wheel. If it is not installed, the app logs the import failure and keeps the raw camera stream alive.

Recommended first test settings:

- Start with `640x480`.
- If pose FPS is low on the UNO Q, try `320x240`.
- Keep `POSE_MODEL_PATH=models/pose_landmarker.task` unless you intentionally place the model somewhere else.

If MediaPipe is unavailable or too slow on the UNO Q, keep the camera stream running and use the documented fallback path later. The current MVP disables pose tracking gracefully when the model or MediaPipe runtime is missing.
