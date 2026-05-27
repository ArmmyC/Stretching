# Smart Stretch Coach Architecture

## What the system does

Smart Stretch Coach is a hackathon MVP for an Arduino UNO Q based indoor stretching guidance station. It creates a visible input to processing to state to dashboard to feedback loop for beginners who need reminders about warm-up and cool-down stretching.

The current implementation captures camera frames, routes them through a placeholder processing pipeline, and displays live station state on an OpenCV dashboard. It is a wellness awareness prototype only. It is not a medical system, diagnostic tool, or substitute for professional advice.

## Libraries used

- `opencv-python`: USB camera capture, JPEG decode, frame resize, dashboard rendering, keyboard controls, debug frame saving.
- `fastapi`: HTTP page and WebSocket endpoint for phone camera mode.
- `uvicorn`: ASGI server used to run the FastAPI phone camera service.
- `numpy`: frame array storage and image buffer handling.
- `qrcode`: QR code generation for phone pairing.
- `pillow`: image backend used by `qrcode`.
- `jinja2`: HTML template rendering for the phone camera page.
- `websockets` / Starlette WebSocket support: WebSocket transport used by FastAPI.
- `psutil`: optional startup diagnostics for CPU and memory.

## Runtime flow

1. `main.py` configures logging and records startup diagnostics.
2. `CameraManager.start_auto()` tries USB camera mode first.
3. If a USB camera returns valid frames, it becomes the active source.
4. If no USB camera works, the manager starts phone QR mode.
5. `OpenCVDashboard` reads frames only through the `CameraSource` interface.
6. Frames are passed to `ProcessingPipeline.process()`.
7. The dashboard displays source, connection status, FPS, resolution, timestamp, placeholder inference state, and latest event.

## Camera source interface

All camera implementations inherit from `CameraSource`:

```python
start() -> bool
read() -> np.ndarray | None
stop() -> None
is_active() -> bool
get_info() -> dict[str, Any]
```

This keeps camera logic out of the dashboard and keeps future inference code independent of the input device.

## USB camera mode

`USBCameraSource` uses OpenCV `VideoCapture`.

- Tries camera indexes 0 through 5.
- Requests 640x480 at 15 FPS.
- Confirms a camera only after it returns a real frame.
- Tracks observed FPS, resolution, timestamp, and read failures.
- Marks the source inactive after repeated runtime failures.

USB is prioritized because it is lower latency, simpler to judge in a demo, and does not depend on phone browser camera security rules.

## QR phone camera mode

`PhoneWebSocketCameraSource` owns a `PhoneWebServer` and `PhoneFrameBuffer`.

- The server binds to `0.0.0.0` and displays the UNO Q LAN IP in the QR URL.
- The phone page requests the rear camera when available.
- A canvas captures frames at about 10 FPS.
- JPEG frames are sent as binary WebSocket messages.
- The server decodes JPEG bytes into OpenCV BGR frames.
- `PhoneFrameBuffer` stores the latest frame behind a thread lock.
- The dashboard and processing pipeline read the latest frame through the same `CameraSource` interface used by USB.

## Future inference insertion points

Add model loading in `app/processing/pipeline.py` inside `ProcessingPipeline.__init__()`.

Examples:

- MediaPipe pose graph setup.
- TensorFlow Lite interpreter load and tensor allocation.
- ONNX Runtime session creation.
- Custom stretch classifier loading.

Add per-frame inference inside `ProcessingPipeline.process()`.

The result object already contains the fields expected by the dashboard:

- `pose_landmarks`
- `stretch_state`
- `confidence`
- `message`

Future sensor fusion can be inserted in the same processing class or in a sibling service that enriches the result object before it reaches the dashboard.

## Logging

Logging goes to console and a timestamped file under `logs/`.

The system logs startup diagnostics, library versions and reasons, camera detection attempts, selected source, frame sizes, FPS, phone connect and disconnect events, WebSocket errors, frame decode errors, mode switches, dashboard lifecycle, placeholder inference calls, and exceptions with stack traces.

The dashboard shows a compact event count and latest event.

## Limitations and known risks

- Phone browser camera access usually requires HTTPS unless the page is loaded from localhost. A LAN IP is not localhost.
- Self-signed certificates may require accepting a browser warning on the phone.
- Some mobile browsers throttle JavaScript or camera capture when battery saver is active.
- USB camera indexes vary by OS and connected devices.
- OpenCV GUI windows require a desktop session and may not work over a headless SSH session.
- The current inference result is a placeholder. No pose estimation or stretch classification is implemented yet.
- This is not a medical device.
