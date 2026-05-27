# Smart Stretch Coach Camera Station

Hackathon MVP for an Arduino UNO Q based indoor gym stretching guidance station. It helps beginners remember what stretches to do before or after workouts by creating a visible camera input, processing, state, dashboard, and feedback loop.

This prototype is for wellness awareness and guidance only. It is not a medical device, diagnostic system, or substitute for professional advice.

## Hardware assumptions

- Arduino UNO Q or similar Linux-capable station acting as the main hub/server.
- HDMI monitor or local desktop session for the OpenCV dashboard.
- Optional USB webcam.
- Phone on the same Wi-Fi/LAN for QR camera fallback.

## Installation

```bash
cd stretch_camera_station
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

On Linux/UNO Q:

```bash
cd stretch_camera_station
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## How to run

Auto mode tries USB first, then falls back to phone QR:

```bash
python main.py
```

Force phone QR mode:

```bash
python main.py --mode phone
```

Force USB mode:

```bash
python main.py --mode usb
```

Use a custom phone server port:

```bash
python main.py --port 8080
```

Use a specific phone-facing IP or hostname, such as a Tailscale IP:

```bash
python main.py --mode phone --headless --public-host 100.85.1.123
```

The server still binds to `0.0.0.0`; `--public-host` only changes the URL shown in logs and QR/dashboard output.

## Run on Arduino UNO Q over SSH

Clone the GitHub repo directly on the UNO Q:

```bash
git clone https://github.com/ArmmyC/Stretching.git
cd Stretching/stretch_camera_station
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

If `opencv-python` is difficult to install on the UNO Q, install the system camera packages first:

```bash
sudo apt update
sudo apt install -y python3-opencv v4l-utils
```

Then run again:

```bash
python main.py
```

If you run from SSH and see `qt.qpa.xcb: could not connect to display`, the camera pipeline is working but OpenCV cannot open a dashboard window from that SSH session. Use one of these:

```bash
python main.py --headless
```

or run from the UNO Q desktop/HDMI terminal for the visible dashboard. If a desktop session is already active on the UNO Q, SSH can sometimes use it with:

```bash
DISPLAY=:0 python main.py
```

If permissions block that, start it from the local HDMI desktop terminal instead.

## Run through Arduino App Lab

This repo also includes an App Lab-ready source tree:

```text
app_lab/SmartStretchCoach/
  python/
    main.py
    station_main.py
    requirements.txt
    app/
  sketch/
    sketch.ino
  docs/
```

Arduino App Lab expects Python code under `python/main.py` and dependencies under `python/requirements.txt`. The `python/main.py` wrapper detects App Lab's runtime and starts the camera station in the background with `STRETCH_HEADLESS=1`. Headless mode avoids `cv2.imshow()` inside App Lab and prints status plus the phone URL to logs.

The App Lab requirements use `opencv-python-headless` to avoid the common `ImportError: libGL.so.1` issue inside App Lab. Use the SSH/HDMI terminal workflow when you want the full OpenCV dashboard window.

Recommended App Lab GUI workflow:

1. Open Arduino App Lab.
2. Create a new App named `SmartStretchCoach`.
3. Copy `app_lab/SmartStretchCoach/python/` into the App's `python/` folder.
4. Copy `app_lab/SmartStretchCoach/sketch/sketch.ino` into the App's `sketch/sketch.ino`.
5. Click Run.

SSH/App CLI workflow:

```bash
ssh arduino@<boardname>.local
arduino-app-cli app new "SmartStretchCoach"
exit
scp -r app_lab/SmartStretchCoach/. arduino@<boardname>.local:/home/arduino/ArduinoApps/SmartStretchCoach/
ssh arduino@<boardname>.local
arduino-app-cli app start "/home/arduino/ArduinoApps/SmartStretchCoach"
arduino-app-cli app logs "/home/arduino/ArduinoApps/SmartStretchCoach" --all
```

From Windows PowerShell, you can use the helper script:

```powershell
.\scripts\deploy_app_lab_ssh.ps1 -Board <boardname>.local
```

After changing dependencies, especially when moving from `opencv-python` to `opencv-python-headless`, use:

```powershell
.\scripts\deploy_app_lab_ssh.ps1 -Board <boardname>.local -CleanCache
```

Note: App Lab manages `app.yaml` and `sketch.yaml`. Create the App in App Lab or with `arduino-app-cli app new` first, then copy the `python/` and `sketch/` contents from this repo into the generated App directory.

If you want to run the full OpenCV dashboard from SSH and see `ImportError: libGL.so.1`, install the missing system library on the UNO Q:

```bash
sudo apt update
sudo apt install -y libgl1 libglib2.0-0
```

## USB camera mode

USB mode uses OpenCV `VideoCapture`.

- Tries camera indexes 0 to 5.
- Requests 640x480 at 15 FPS.
- Accepts a camera only after it returns real frames.
- Shows source type, connection status, FPS, frame size, timestamp, placeholder inference, stretch state, and latest event on the dashboard.
- If the camera repeatedly fails during runtime, the manager logs the failure and falls back to phone QR mode.

When USB mode works, the QR workflow is not shown.

## Phone QR mode

If no USB webcam is detected, the station starts a FastAPI server and displays a QR code. Scan it with a phone on the same network.

The phone page:

- Opens the rear camera when available.
- Captures frames with a canvas.
- Sends JPEG frames over WebSocket at about 10 FPS.
- Uses JPEG quality around 65.
- Shows connection status and sent frame count.

The station server:

- Receives binary JPEG WebSocket frames.
- Decodes them with OpenCV into NumPy frames.
- Stores the latest frame in a thread-safe buffer.
- Feeds that frame into the same processing pipeline as USB mode.

The QR URL uses the station LAN IP address, not `localhost`.

## HTTPS warning for phone cameras

Most mobile browsers allow camera access only on HTTPS pages or on `localhost`. Since your phone is visiting the UNO Q by LAN IP, plain HTTP may fail with a camera permission error.

Option A: run with a self-signed certificate.

Generate a local certificate:

```bash
openssl req -x509 -newkey rsa:2048 -nodes -keyout certs/stretch-key.pem -out certs/stretch-cert.pem -days 365 -subj "/CN=stretch-station.local"
```

Run HTTPS mode:

```bash
python main.py --mode phone --https --ssl-cert certs/stretch-cert.pem --ssl-key certs/stretch-key.pem
```

Your phone may show a certificate warning. Accept it for the hackathon demo network if appropriate.

Option B: use a phone/IP webcam app.

If the browser blocks camera access, install a phone app that exposes an MJPEG stream on the LAN. This repo does not yet include an MJPEG source class, but the architecture is ready for one: add a new `CameraSource` implementation that reads the MJPEG URL with OpenCV and register it in `CameraManager`.

## Dashboard controls

- `q`: quit
- `r`: restart automatic camera detection
- `p`: force phone QR mode
- `u`: force USB camera mode
- `s`: save current frame to `debug_frames/`

## Logs

Each run creates a timestamped log file under `logs/`.

Logs include startup time, OS/platform, Python version, OpenCV version, imported libraries and why they are used, camera detection attempts, selected source and reason, USB camera frame size/FPS, phone connect/disconnect events, WebSocket errors, frame decode errors, mode switches, dashboard start/stop, placeholder inference calls, and stack traces for exceptions.

## Troubleshooting

No USB camera detected:

- Confirm the camera works in another app.
- Try a different USB port.
- On Linux, check `ls /dev/video*`.
- Run `python main.py --mode phone` to continue the demo with phone QR mode.

Phone cannot open camera:

- Use HTTPS mode with a certificate.
- If using Tailscale, prefer a MagicDNS HTTPS hostname and pass it with `--public-host`.
- Confirm the browser has camera permission.
- Try Chrome or Safari depending on the phone.
- Disable battery saver if it throttles camera access.

Phone cannot connect to UNO Q:

- Confirm phone and UNO Q are on the same network.
- Check that the dashboard QR URL shows the LAN IP, not `127.0.0.1`.
- Try `python main.py --port 8080`.
- Check firewall rules for the selected port.

WebSocket disconnected:

- Keep the phone screen awake.
- Move closer to the Wi-Fi access point.
- Refresh the phone page.
- Watch the log file for WebSocket errors.

Low FPS:

- Use USB mode when available.
- Reduce other workload on the UNO Q.
- Keep the phone and station on strong Wi-Fi.
- Lower the phone page target FPS in `app/config.py`.

HDMI monitor works but USB camera fails:

- The dashboard display and camera device are separate subsystems.
- Check camera permissions and `/dev/video*` device availability.
- Try another webcam.
- Use phone QR mode for the demo path.

## How to add future inference

Open `app/processing/pipeline.py`.

Add model loading in `ProcessingPipeline.__init__()`:

- MediaPipe pose
- TensorFlow Lite
- ONNX Runtime
- Custom stretch classifier

Add per-frame inference in `ProcessingPipeline.process(frame)`.

Return the same fields the dashboard already expects:

- `pose_landmarks`
- `stretch_state`
- `confidence`
- `message`

## Demo checklist

- HDMI dashboard opens.
- USB camera auto-detects when connected.
- No QR screen appears when USB works.
- With no USB camera, QR screen appears.
- Phone scans QR and streams frames.
- Dashboard shows FPS, resolution, timestamp, source, placeholder inference, stretch state, and latest event.
- `p`, `u`, `r`, `s`, and `q` controls work.
- Logs are created under `logs/`.

## Implemented vs placeholder

Implemented:

- Modular `CameraSource` interface.
- USB camera source with real-frame validation.
- Phone QR WebSocket camera source.
- Thread-safe latest-frame buffer.
- FastAPI phone camera page.
- OpenCV dashboard.
- Runtime mode switching and USB fallback.
- Timestamped console and file logging.
- Architecture and test documentation.

Placeholder:

- Pose landmarks.
- Stretch classification.
- Confidence scoring.
- Sensor fusion.
- MJPEG/IP webcam source.
