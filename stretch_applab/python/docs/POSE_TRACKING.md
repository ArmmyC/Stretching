# StretchSense Pose Tracking

StretchSense uses camera pose tracking to produce simple, local-only body-position flags for the stretching station. The camera layer is not a medical assessment, does not diagnose mobility, and does not make claims about injury prevention or treatment. It only helps the kiosk understand whether the user appears framed and whether the overhead shoulder stretch is roughly in position.

## Current Backend

The MVP uses MediaPipe Pose Landmarker when available:

- Local model path: `models/pose_landmarker.task`
- No runtime model downloads
- `num_poses=1`
- Segmentation masks disabled
- Confidence thresholds near `0.5`
- Pose inference resized to `POSE_INFERENCE_WIDTH=320` by default

If MediaPipe or the model file is missing, pose tracking is disabled and `/video_feed` continues showing the raw camera stream with status text. MoveNet Lightning is the planned fallback if MediaPipe is unavailable or too slow. ArUco or visible body markers can remain a future backup for tightly controlled demos.

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
