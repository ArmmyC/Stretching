# StretchSense Pose Tracking

StretchSense uses camera pose tracking to produce simple, local-only body-position flags for the stretching station. The camera layer is not a medical assessment, does not diagnose mobility, and does not make claims about injury prevention or treatment. It only helps the kiosk understand whether the user appears framed and whether the overhead shoulder stretch is roughly in position.

## Current Backend

The MVP uses MediaPipe Pose Landmarker when available:

- Local model path: `models/pose_landmarker.task`
- No runtime model downloads
- `num_poses=1`
- Segmentation masks disabled
- Confidence thresholds near `0.5`
- Delegate requested with `POSE_DELEGATE=cpu` or `POSE_DELEGATE=gpu`
- Pose inference resized to `POSE_INFERENCE_WIDTH=320` by default
- Async pose worker enabled by default so streaming stays responsive

If MediaPipe or the model file is missing, pose tracking is disabled and `/video_feed` continues showing the raw camera stream with status text. MoveNet Lightning is now available as a local TFLite fallback if MediaPipe is unavailable or too slow. ArUco or visible body markers can remain a future backup for tightly controlled demos.

## MoveNet TFLite Backend

MoveNet SinglePose Lightning is the lightweight fallback to try before heavier YOLO pose models:

```bash
curl -L -o models/movenet_lightning.tflite "https://tfhub.dev/google/lite-model/movenet/singlepose/lightning/tflite/float16/4?lite-format=tflite"
python -m pip install ai-edge-litert

export POSE_BACKEND=movenet
export MOVENET_MODEL_PATH=models/movenet_lightning.tflite
export MOVENET_INPUT_SIZE=192
export MOVENET_NUM_THREADS=2
export POSE_ASYNC_ENABLED=true
export POSE_MAX_ASYNC_FPS=10
python tools/test_pose_camera.py --backend movenet --camera 0 --width 320 --height 240
```

The backend maps MoveNet's 17 COCO keypoints into the same StretchSense landmarks and flags. It runs on the CPU through `ai-edge-litert`, `tflite-runtime`, or `tensorflow` if one of those interpreters is installed. It does not use the Adreno GPU directly, but it should be much lighter than YOLO pose on NCNN for this MVP.

## NCNN Vulkan Backend

UNO Q exposes the Adreno 702 through Vulkan/Turnip, so StretchSense includes an experimental NCNN YOLO pose backend:

```bash
export POSE_BACKEND=ncnn_pose
export NCNN_MODEL_DIR=models/yolov8n-pose_ncnn_model
export NCNN_USE_VULKAN=true
export NCNN_GPU_INDEX=0
export NCNN_INPUT_SIZE=320
python tools/test_pose_camera.py --backend ncnn_pose --camera 0 --width 320 --height 240
```

The backend expects a YOLO pose NCNN export with 17 COCO keypoints. It maps shoulders, elbows, wrists, hips, knees, and ankles into the same StretchSense landmark dictionary used by MediaPipe.

If the export has a different output layout, the backend logs `ncnn_output_shapes` so the decoder can be adjusted without changing the camera source manager.

## Flags

`user_visible`

True when both shoulders and both hips are detected with enough confidence.

`upper_body_visible`

True when both shoulders are detected and at least one elbow plus one wrist are detected.

`full_body_visible`

True when shoulders, hips, knees, and ankles are detected. This can be false for the MVP and should not block the overhead shoulder demo.

`arm_raised`

True when either wrist is above the same-side shoulder by the tuned margin:

```text
wrist.y < shoulder.y - 0.08
```

Image coordinates use smaller `y` values higher in the frame.

`torso_centered`

True when the shoulder center and hip center are close on the x-axis:

```text
abs(shoulder_center_x - hip_center_x) < 0.12
```

`confidence`

Average visibility or presence score over the upper-body landmarks used by the MVP.

## Future Nano IMU Fusion

The camera flags are designed to fuse with Nano IMU and UNO Q hardware feedback later:

```text
camera_arm_raised + nano_arm_raised + nano_stable + distance_ok
```

The camera can say whether the stretch appears visible and roughly raised. The Nano can add angle and stability. Distance or setup sensors can help ensure the user is in a usable capture zone.

## Limitations

This is 2D pose tracking. It cannot perfectly detect depth, torso rotation, occluded joints, or whether a stretch is being performed with good form. Lighting, clothing, camera angle, and partial framing all affect the flags.

Recommended demo stretch: overhead shoulder stretch.

## Performance Tuning

On UNO Q, start with the Lite model and a smaller inference frame:

```bash
export POSE_INFERENCE_WIDTH=320
export POSE_FRAME_STRIDE=1
python tools/test_pose_camera.py --camera 0 --width 640 --height 480
```

If pose is still around 5-6 FPS, try:

```bash
export POSE_INFERENCE_WIDTH=256
export POSE_FRAME_STRIDE=2
python tools/test_pose_camera.py --camera 0 --width 320 --height 240 --pose-width 256 --pose-stride 2
```

`POSE_FRAME_STRIDE=2` runs inference every other frame and reuses the last skeleton overlay between runs. This is usually good enough for the overhead shoulder demo because the motion is slow.

For the smoothest camera stream, leave async pose enabled:

```bash
export POSE_ASYNC_ENABLED=true
export POSE_MAX_ASYNC_FPS=6
export POSE_INFERENCE_WIDTH=256
export POSE_FRAME_STRIDE=1
python main.py
```

In async mode, `/video_feed` does not wait for MediaPipe. Each displayed frame draws the most recent completed skeleton, so the camera can feel smooth while the skeleton trails slightly behind.

To test the UNO Q GPU path:

```bash
export POSE_DELEGATE=gpu
python tools/test_pose_camera.py --camera 0 --width 320 --height 240 --pose-width 192 --delegate gpu
```

If the MediaPipe GPU delegate is unavailable in the installed Python wheel or board driver stack, StretchSense logs the GPU failure and falls back to CPU. Check `/api/status` for `pose_delegate_requested` and `pose_delegate_active`.

For NCNN/Vulkan, prefer:

```bash
export POSE_BACKEND=ncnn_pose
export MESA_VK_DEVICE_SELECT=5143:7000200
export NCNN_USE_VULKAN=true
export NCNN_GPU_INDEX=0
```

## Model Benchmark Matrix

Use `tools/benchmark_pose_models.py` to compare every local model with the same frame source:

```bash
cd ~/ArduinoApps/stretchcoach/python
source .venv-mediapipe/bin/activate
python tools/benchmark_pose_models.py --image sample.jpg --no-ncnn
```

For NCNN models:

```bash
source .venv-ncnn/bin/activate
export MESA_VK_DEVICE_SELECT=5143:7000200
python tools/benchmark_pose_models.py --image sample.jpg --no-mediapipe --ncnn-sizes 192,224,320
```

For MoveNet:

```bash
source .venv-movenet/bin/activate
python tools/benchmark_pose_models.py --image sample.jpg --no-mediapipe --no-ncnn --movenet-sizes 192
```

If a USB camera is available, replace `--image sample.jpg` with:

```bash
--camera 0 --width 320 --height 240
```

Suggested model folders to try:

```text
models/yolov8n-pose_ncnn_model
models/yolo11n-pose_ncnn_model
models/yolo26n-pose_ncnn_model
```

Use the model with the best mix of `fps_mean`, `confidence_last`, and visible stable landmarks. For the live phone-camera app, the smoothness still comes mostly from `POSE_ASYNC_ENABLED=true`.
