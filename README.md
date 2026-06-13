# YUEDMAI Smart Stretch Coach

YUEDMAI is a local-first stretching guidance prototype built around Arduino UNO Q, a camera, and an optional Arduino Nano 33 BLE Sense wearable. It serves a kiosk-style web app, tracks coarse body-position signals, manages timed stretching routines, and can combine camera, IMU, distance, button, light, and buzzer feedback.

The project is intended for wellness guidance and demonstrations. It is not a medical device and does not diagnose mobility, prevent injury, or assess biomechanics.

## Features

- Local FastAPI kiosk with landing, setup, session, dashboard, phone-camera, and session-summary pages.
- Automatic USB-camera selection with QR-based phone camera fallback.
- Local pose tracking through MediaPipe, MoveNet, or an experimental NCNN/Vulkan backend.
- Before-workout and after-workout routines with body-focus and duration settings.
- In-memory session captures with QR sharing and ZIP download.
- Optional Arduino Nano IMU telemetry over BLE or serial.
- Optional UNO Q hardware events for buttons, distance sensing, pixels, buzzer feedback, and fused stretch state.
- Browser tools for inspecting Nano sensor output and standalone dashboard data.

## Tech Stack

- Python, FastAPI, Uvicorn, Jinja2, and WebSockets
- OpenCV and NumPy
- MediaPipe Pose Landmarker, LiteRT/MoveNet, and optional NCNN pose inference
- Arduino sketches for UNO Q and Nano 33 BLE Sense Lite
- HTML, CSS, and JavaScript kiosk/dashboard interfaces
- BLE through `bleak` and newline-delimited JSON for serial integration

## Repository Layout

```text
.
|-- stretch_applab/          # Primary Arduino App Lab package
|   |-- python/              # FastAPI app, models, tools, and launcher
|   |-- sketch/              # Minimal App Lab MCU sketch
|   `-- docs/                # Architecture and technical documentation
|-- arduino/                 # Nano wearable and UNO Q hub firmware
|-- dashboard/               # Standalone browser dashboard
|-- stretch_stream/          # Earlier/local FastAPI application package
|-- stretch_camera_station/  # Camera-station prototype
|-- stretchsense/            # Additional web prototype
|-- tracking_model/          # Standalone stretch-tracking experiments
|-- yolo_export/             # YOLO and NCNN model exports
`-- Submission/              # Review-friendly copy of submission materials
```

The maintained integration package and recommended starting point is [`stretch_applab`](stretch_applab/README.md). Some other directories preserve earlier prototypes, experiments, or packaging copies.

## Getting Started

### Prerequisites

- Python 3 with virtual environment support
- A USB camera, or a phone that can reach the host over the local network
- Arduino IDE for the firmware components
- Optional: Arduino UNO Q, Nano 33 BLE Sense Lite, and Modulino hardware

MediaPipe availability depends on the Python version and target platform. The camera stream remains available when a pose backend cannot be loaded.

### Run the Web App

From the repository root:

```bash
cd stretch_applab/python
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

Open the kiosk on the host at:

```text
http://localhost:8000/
```

From another device on the same network, replace `localhost` with the host or UNO Q IP address.

For the included MediaPipe model, install the compatible MediaPipe environment instead of only the base requirements:

```bash
pip install -r requirements-mediapipe.txt
python main.py
```

The launcher defaults to `models/pose_landmarker.task`, which is included in the App Lab package. MoveNet and NCNN require their respective local model files and runtime support; see the [model guide](stretch_applab/python/models/README_MODELS.md).

### Deploy with Arduino App Lab

Create an App Lab application on the UNO Q and copy the contents of `stretch_applab/` into its app folder:

```bash
cd ~/ArduinoApps
arduino-app-cli app new "SmartStretchCoach"
arduino-app-cli app start user:smartstretchcoach
arduino-app-cli app logs user:smartstretchcoach --all
```

See the [`stretch_applab` deployment guide](stretch_applab/README.md) for the expected folder layout and launcher behavior.

## Configuration

Run commands from `stretch_applab/python` so relative model paths resolve correctly.

| Variable | Default | Purpose |
|---|---|---|
| `APP_HOST` | `0.0.0.0` | Web server bind address |
| `APP_PORT` | `8000` | Web server port |
| `PUBLIC_BASE_URL` | empty | Public/local URL encoded into camera and summary QR codes |
| `FORCE_CAMERA_MODE` | `auto` | Camera mode: `auto`, `usb`, or `phone` |
| `POSE_TRACKING_ENABLED` | `true` | Enables pose processing when a backend is available |
| `POSE_BACKEND` | `mediapipe` | Pose backend: `mediapipe`, `movenet`, or `ncnn_pose` |
| `POSE_MODEL_PATH` | `models/pose_landmarker.task` | MediaPipe model path |
| `POSE_DELEGATE` | `cpu` | Requested MediaPipe delegate: `cpu` or `gpu` |
| `POSE_INFERENCE_WIDTH` | `192` from the App Lab launcher | Width used for pose inference |
| `POSE_FRAME_STRIDE` | `1` | Runs inference every Nth frame |
| `POSE_ASYNC_ENABLED` | `true` | Runs pose inference in a background worker |
| `POSE_MAX_ASYNC_FPS` | `4` from the App Lab launcher | Limits background inference submissions |
| `NANO_BLE_ENABLED` | `true` | Enables Nano BLE discovery and subscription |
| `NANO_BLE_NAME` | `YUEDMAI-NanoIMU` | BLE device name to discover |

Backend-specific variables and tuning guidance are documented in [`POSE_TRACKING.md`](stretch_applab/python/docs/POSE_TRACKING.md).

## Firmware

The [`arduino`](arduino/README_ARDUINO.md) directory contains:

- `NanoStretchNode/NanoStretchNode.ino`: wearable IMU calibration, angle/stability classification, optional sensor telemetry, BLE, and serial JSON output.
- `UnoQStretchHub/UnoQStretchHub.ino`: distance and control inputs, feedback outputs, camera/Nano fusion, and the stretch-state machine.

Both sketches use `115200` baud for serial monitoring. Library requirements, wiring options, calibration, upload instructions, and mock-hardware testing are covered in the [firmware guide](arduino/README_ARDUINO.md). The message contract is documented in [`SERIAL_PROTOCOL.md`](arduino/SERIAL_PROTOCOL.md).

For live Nano inspection, open `arduino/tools/nano_signal_dashboard.html` in Chrome or Edge and connect through the Web Serial prompt.

## Verification and Diagnostics

The repository does not currently contain an automated unit-test suite. It includes runtime diagnostics and hardware smoke-test procedures.

Test a camera and pose backend:

```bash
cd stretch_applab/python
source .venv/bin/activate
python tools/test_pose_camera.py --backend mediapipe --camera 0
```

Benchmark available local pose models:

```bash
python tools/benchmark_pose_models.py --image sample.jpg --no-ncnn
```

The app also exposes `/api/health` and `/api/status` for camera, pose, session, hardware bridge, and Nano BLE diagnostics. Firmware smoke tests and expected JSON messages are in the [Arduino guide](arduino/README_ARDUINO.md).

## Documentation

- [System architecture](stretch_applab/docs/SYSTEM_ARCHITECTURE.md)
- [Technical report](stretch_applab/docs/YUEDMAI_Technical_Report.md)
- [Pose tracking and tuning](stretch_applab/python/docs/POSE_TRACKING.md)
- [Model setup](stretch_applab/python/models/README_MODELS.md)
- [Arduino firmware guide](arduino/README_ARDUINO.md)
- [Serial protocol](arduino/SERIAL_PROTOCOL.md)
- [Submission package](Submission/README.md)

## Known Limitations

- Pose tracking is 2D and is affected by lighting, clothing, framing, camera angle, and occlusion.
- Pose flags and scores provide coarse prototype feedback, not clinical or biomechanics-grade measurements.
- Session captures are stored in process memory and are cleared when the app restarts.
- Phone camera access may require HTTPS or localhost depending on browser security rules.
- Hardware integration and GPU backends depend on the exact UNO Q image, libraries, drivers, and connected modules.

## License

This project is licensed under the [MIT License](LICENSE).
