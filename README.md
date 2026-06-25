<!-- prettier-ignore -->
<div align="center">

# YUEDMAI Smart Stretch Coach

*Local-first stretch guidance with Arduino UNO Q, camera tracking, and optional wearable sensing.*

![Python](https://img.shields.io/badge/Python-3.x-3776ab?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![Arduino](https://img.shields.io/badge/Arduino-UNO_Q-00979d?style=flat-square&logo=arduino&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-camera-5c3ee8?style=flat-square&logo=opencv&logoColor=white)
![MediaPipe](https://img.shields.io/badge/MediaPipe-pose-ff6f00?style=flat-square)

[Overview](#overview) • [Features](#features) • [Get started](#get-started) • [Firmware](#firmware) • [Configuration](#configuration) • [Diagnostics](#diagnostics)

</div>

YUEDMAI is a local-first stretching guidance prototype built around an Arduino UNO Q, a camera, and an optional Arduino Nano 33 BLE Sense Lite wearable. It serves a kiosk-style web app, streams camera input, runs coarse pose checks, manages timed stretching routines, stores session captures in memory, and can fuse camera, IMU, distance, button, light, and buzzer feedback.

> [!IMPORTANT]
> YUEDMAI is a wellness and demonstration prototype. It is not a medical device and does not diagnose mobility, prevent injury, or provide clinical biomechanics assessment.

## Overview

The maintained starting point is [`stretch_applab/`](./stretch_applab). It packages the local FastAPI kiosk app for Arduino App Lab while keeping the Python app runnable on a normal development machine.

```text
Browser kiosk
  Landing, setup, live session, dashboard, phone camera, summaries

FastAPI app
  Camera source manager, MJPEG stream, session state, pose status, QR routes

Pose layer
  MediaPipe by default, MoveNet fallback, experimental NCNN/Vulkan backend

Arduino firmware
  Nano wearable IMU node and UNO Q hardware hub for optional sensor fusion
```

The app is intentionally local-first. It does not require a cloud service or database for the current prototype.

## Features

- **Kiosk web app**: landing, setup, stretch session, dashboard, phone-camera, and summary pages.
- **Flexible camera input**: automatic USB camera selection with QR-based phone camera fallback.
- **Local pose tracking**: MediaPipe Pose Landmarker, MoveNet TFLite fallback, and experimental YOLO pose through NCNN/Vulkan.
- **Stretch session engine**: before-workout and after-workout routines with body-focus and duration settings.
- **Capture sharing**: in-memory session photos, QR summary pages, individual image serving, and ZIP download.
- **Hardware bridge**: optional UNO Q hardware events for controls, distance sensing, pixels, buzzer feedback, and fused stretch state.
- **Wearable telemetry**: optional Nano 33 BLE Sense Lite IMU output over BLE or serial JSON.
- **Developer tools**: Nano signal dashboard, camera test script, pose model benchmark script, and hardware smoke-test documentation.

> [!NOTE]
> The repo also contains older prototypes and experiments. Treat `stretch_applab/` as the primary integration package unless you are intentionally exploring legacy code.

## Project structure

```text
.
├── stretch_applab/          Primary Arduino App Lab package
│   ├── python/              FastAPI app, templates, static assets, tools, models
│   ├── sketch/              Minimal App Lab MCU sketch placeholder
│   └── docs/                System architecture and technical documentation
├── arduino/                 Nano wearable and UNO Q hub firmware
├── dashboard/               Standalone browser dashboard prototype
├── stretch_stream/          Earlier local FastAPI application package
├── stretch_camera_station/  Camera-station prototype
├── stretchsense/            Additional web prototype
├── tracking_model/          Stretch-tracking experiments
├── yolo_export/             YOLO and NCNN model exports
└── Submission/              Review-friendly submission materials
```

## Get started

### Prerequisites

- Python 3 with virtual environment support
- A USB camera, or a phone that can reach the host over the local network
- Arduino IDE for firmware work
- Optional: Arduino UNO Q, Nano 33 BLE Sense Lite, and Modulino hardware

Camera access and model support depend on the host, browser, Python version, and board image. The camera stream remains available when a pose backend cannot be loaded.

### Run locally

From the repository root:

```bash
cd stretch_applab/python
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

Open the kiosk:

```text
http://localhost:8000/
```

From another device on the same network, replace `localhost` with the host or UNO Q IP address.

### Run with MediaPipe support

The App Lab package includes a default MediaPipe model path at `models/pose_landmarker.task`. Install the compatible MediaPipe environment when your Python version and platform support it:

```bash
cd stretch_applab/python
source .venv/bin/activate
pip install -r requirements-mediapipe.txt
python main.py
```

> [!TIP]
> Run commands from `stretch_applab/python` so relative model paths, templates, static assets, and tooling resolve correctly.

### Deploy with Arduino App Lab

Create an App Lab application on the UNO Q, then copy the contents of `stretch_applab/` into the generated app folder.

```bash
cd ~/ArduinoApps
arduino-app-cli app new "SmartStretchCoach"
arduino-app-cli app start user:smartstretchcoach
arduino-app-cli app logs user:smartstretchcoach --all
```

Open the kiosk at:

```text
http://<UNO_Q_IP>:8000/
```

Set `PUBLIC_BASE_URL` when QR codes should point to a specific IP address, Tailscale name, or HTTPS URL.

## Main routes and API

| Type | Path | Purpose |
| --- | --- | --- |
| Page | `/` | Landing page |
| Page | `/setup` | Routine setup |
| Page | `/session` | Live stretch session |
| Page | `/dashboard` | Runtime dashboard |
| Page | `/phone` | Phone camera streamer |
| Page | `/summary/{session_id}` | Capture summary page |
| Stream | `/video_feed` | MJPEG camera stream |
| WebSocket | `/ws/phone-frame` | Phone camera frame input |
| WebSocket | `/ws/hardware` | Browser hardware events |
| API | `/api/health` | Server and camera health |
| API | `/api/status` | Camera, pose, session, hardware, Nano, and capture status |
| API | `/api/session/start` | Start session |
| API | `/api/session/pause` | Pause session |
| API | `/api/session/next` | Advance stretch |
| API | `/api/session/reset` | Reset session |
| API | `/api/session/config` | Configure routine settings |
| API | `/api/session/captures` | Upload session capture |

## Firmware

The [`arduino/`](./arduino) directory contains the firmware pieces for optional hardware sensing and feedback.

| Sketch | Role |
| --- | --- |
| `arduino/NanoStretchNode/NanoStretchNode.ino` | Wearable forearm IMU node with calibration, angle/stability classification, BLE, and serial JSON output |
| `arduino/UnoQStretchHub/UnoQStretchHub.ino` | UNO Q hardware hub for distance, buttons, buzzer, pixels, camera/Nano fusion, and stretch-state output |

Both sketches use `115200` baud for serial monitoring. Wiring options, library requirements, upload steps, calibration, command references, and smoke tests are documented in [`arduino/README_ARDUINO.md`](./arduino/README_ARDUINO.md).

For live Nano inspection, open [`arduino/tools/nano_signal_dashboard.html`](./arduino/tools/nano_signal_dashboard.html) in Chrome or Edge and connect through the Web Serial prompt.

## Configuration

### App server

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_HOST` | `0.0.0.0` | Web server bind address |
| `APP_PORT` | `8000` | Web server port |
| `PUBLIC_BASE_URL` | empty | Public or local URL encoded into camera and summary QR codes |
| `FORCE_CAMERA_MODE` | `auto` | Camera mode: `auto`, `usb`, or `phone` |

### Pose tracking

| Variable | Default | Purpose |
| --- | --- | --- |
| `POSE_TRACKING_ENABLED` | `true` | Enables pose processing when a backend is available |
| `POSE_BACKEND` | `mediapipe` | Pose backend: `mediapipe`, `movenet`, or `ncnn_pose` |
| `POSE_MODEL_PATH` | `models/pose_landmarker.task` | MediaPipe model path |
| `POSE_DELEGATE` | `cpu` | Requested MediaPipe delegate: `cpu` or `gpu` |
| `POSE_INFERENCE_WIDTH` | `192` from the App Lab launcher | Width used for pose inference |
| `POSE_FRAME_STRIDE` | `1` | Runs inference every Nth frame |
| `POSE_ASYNC_ENABLED` | `true` | Runs pose inference in a background worker |
| `POSE_MAX_ASYNC_FPS` | `4` from the App Lab launcher | Limits background inference submissions |
| `POSE_FALLBACK_BACKEND` | `movenet` | Fallback backend attempted by the launcher |

### Nano wearable

| Variable | Default | Purpose |
| --- | --- | --- |
| `NANO_BLE_ENABLED` | `true` | Enables Nano BLE discovery and subscription |
| `NANO_BLE_NAME` | `YUEDMAI-NanoIMU` | BLE device name to discover |

See [`stretch_applab/python/docs/POSE_TRACKING.md`](./stretch_applab/python/docs/POSE_TRACKING.md) and [`stretch_applab/python/models/README_MODELS.md`](./stretch_applab/python/models/README_MODELS.md) for backend-specific tuning and model setup.

## Diagnostics

The repository does not currently include an automated unit-test suite. It includes runtime diagnostics, model benchmarks, and hardware smoke-test procedures.

Test a camera and pose backend:

```bash
cd stretch_applab/python
source .venv/bin/activate
python tools/test_pose_camera.py --backend mediapipe --camera 0
```

Benchmark local pose models:

```bash
cd stretch_applab/python
source .venv/bin/activate
python tools/benchmark_pose_models.py --image sample.jpg --no-ncnn
```

Health and runtime status are available from the running app:

```text
http://localhost:8000/api/health
http://localhost:8000/api/status
```

Firmware-level smoke tests and expected serial JSON messages are covered in [`arduino/README_ARDUINO.md`](./arduino/README_ARDUINO.md) and [`arduino/SERIAL_PROTOCOL.md`](./arduino/SERIAL_PROTOCOL.md).

## Documentation

- [App Lab package guide](./stretch_applab/README.md)
- [System architecture](./stretch_applab/docs/SYSTEM_ARCHITECTURE.md)
- [Technical report](./stretch_applab/docs/YUEDMAI_Technical_Report.md)
- [Pose tracking and tuning](./stretch_applab/python/docs/POSE_TRACKING.md)
- [Model setup](./stretch_applab/python/models/README_MODELS.md)
- [Arduino firmware guide](./arduino/README_ARDUINO.md)
- [Serial protocol](./arduino/SERIAL_PROTOCOL.md)
- [Submission package](./Submission/README.md)

## Known limitations

- Pose tracking is 2D and is affected by lighting, clothing, framing, camera angle, and occlusion.
- Pose flags and scores are coarse prototype feedback, not clinical measurements.
- Session captures are stored in process memory and are cleared when the app restarts.
- Phone camera access may require HTTPS or localhost depending on browser security rules.
- Hardware integration and GPU backends depend on the exact UNO Q image, libraries, drivers, and connected modules.
