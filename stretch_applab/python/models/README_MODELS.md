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
- Pose inference now defaults to `POSE_INFERENCE_WIDTH=320`, which runs MediaPipe on a smaller copy of the frame while drawing landmarks back on the full stream.
- If FPS is still low, try `POSE_INFERENCE_WIDTH=256` and `POSE_FRAME_STRIDE=2`.
- `POSE_ASYNC_ENABLED=true` lets the video stream stay smooth while pose runs in a background worker and the last skeleton is reused.
- `POSE_MAX_ASYNC_FPS=8` limits how often the app submits frames to the pose worker.
- `POSE_DELEGATE=cpu` is the safe default. Try `POSE_DELEGATE=gpu` on UNO Q to test MediaPipe GPU delegate support; the app falls back to CPU if GPU init fails.
- Keep `POSE_MODEL_PATH=models/pose_landmarker.task` unless you intentionally place the model somewhere else.

If MediaPipe is unavailable or too slow on the UNO Q, keep the camera stream running and use the documented fallback path later. The current MVP disables pose tracking gracefully when the model or MediaPipe runtime is missing.

## MoveNet TFLite Model

MoveNet is the lightweight CPU fallback to try when MediaPipe is unavailable or the YOLO/NCNN path is too heavy. StretchSense expects this file by default:

```text
models/movenet_lightning.tflite
```

Download the model manually; the app still does not download anything at runtime:

```bash
curl -L -o models/movenet_lightning.tflite "https://tfhub.dev/google/lite-model/movenet/singlepose/lightning/tflite/float16/4?lite-format=tflite"
```

Try it with:

```bash
export POSE_BACKEND=movenet
export MOVENET_MODEL_PATH=models/movenet_lightning.tflite
export MOVENET_INPUT_SIZE=192
export MOVENET_NUM_THREADS=2
python tools/test_pose_camera.py --backend movenet --camera 0 --width 320 --height 240
```

MoveNet runs through `ai-edge-litert`, `tflite-runtime`, or `tensorflow` if one of those interpreters is installed. On UNO Q, try installing `ai-edge-litert` first in a separate venv:

```bash
python -m pip install ai-edge-litert
```

MoveNet Lightning is the first model to try. MoveNet Thunder is larger and may be more accurate, but it is usually slower and not the best first hackathon target on the UNO Q.

## NCNN Vulkan Pose Model

For GPU experiments on UNO Q, StretchSense can also load a YOLO pose model exported to NCNN:

```text
models/yolov8n-pose_ncnn_model/model.ncnn.param
models/yolov8n-pose_ncnn_model/model.ncnn.bin
```

Some exporters write these names instead:

```text
models/yolov8n-pose_ncnn_model/model.param
models/yolov8n-pose_ncnn_model/model.bin
```

Both naming styles are accepted.

The expected output layout is the common YOLO pose tensor:

```text
x, y, w, h, confidence, 17 COCO keypoints * (x, y, confidence)
```

To run it:

```bash
export POSE_BACKEND=ncnn_pose
export NCNN_MODEL_DIR=models/yolov8n-pose_ncnn_model
export NCNN_USE_VULKAN=true
export NCNN_GPU_INDEX=0
export NCNN_INPUT_SIZE=320
```

Install `ncnn` only in the venv where you want to test the NCNN backend. It currently pulls `numpy>=2`, which conflicts with `mediapipe==0.10.15`, so use separate venvs if you want both backends cleanly available.

## Benchmarking Models

Compare local model folders with:

```bash
python tools/benchmark_pose_models.py --image sample.jpg --no-mediapipe --ncnn-sizes 192,224,320
python tools/benchmark_pose_models.py --image sample.jpg --no-ncnn --no-mediapipe --movenet-sizes 192
```

The script auto-discovers `models/*_ncnn_model` and reports load status, active device, mean FPS, confidence, and NCNN output shapes.
It also auto-discovers `models/movenet*.tflite` and reports MoveNet output shapes.
