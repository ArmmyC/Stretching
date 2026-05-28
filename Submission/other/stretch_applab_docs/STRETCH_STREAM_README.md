# YUEDMAI

YUEDMAI is a local kiosk-style web app for a Smart Stretch Coach running on Arduino UNO Q Linux. It helps gym beginners quickly choose a before-workout or after-workout stretching routine without needing to remember what to do.

The UNO Q hosts the site locally. There is no external hosting, database, authentication, cloud service, or public web server. This keeps latency low and makes the prototype reliable inside a small room or gym.

This is a wellness awareness prototype. It is not a medical system.

## What It Does

- Hosts a local FastAPI web app on the UNO Q.
- Uses USB camera automatically when available.
- Falls back to phone camera pairing by QR code when USB is not available.
- Streams the selected camera to the browser through `/video_feed`.
- Shows a kiosk flow:
  - `/` landing page
  - `/setup` mode, focus, and duration setup
  - `/session` camera-first stretching session
  - `/phone` phone camera sender page
- Includes a fake stretch-session state machine for demo and UI testing.
- Keeps a clear future inference hook in `app/inference.py`.

## Why Local Hosting

The station is meant to run in one gym room. Hosting locally on the UNO Q avoids cloud latency, internet dependency, and privacy issues from sending camera frames to an external server. Phones and laptops only need to reach the UNO Q over local Wi-Fi, Ethernet, or a private network such as Tailscale.

## Installation

```bash
cd ~/Stretching/stretch_stream
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
cd ~/Stretching/stretch_stream
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open the dashboard from another device:

```text
http://<UNO_Q_IP>:8000/
```

If using Tailscale or HTTPS proxying, set:

```bash
export PUBLIC_BASE_URL="https://your-uno-q-name.your-tailnet.ts.net"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Environment Variables

```bash
export APP_HOST=0.0.0.0
export APP_PORT=8000
export PUBLIC_BASE_URL=
export FORCE_CAMERA_MODE=auto
```

Camera modes:

```bash
FORCE_CAMERA_MODE=auto uvicorn app.main:app --host 0.0.0.0 --port 8000
FORCE_CAMERA_MODE=usb uvicorn app.main:app --host 0.0.0.0 --port 8000
FORCE_CAMERA_MODE=phone uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- `auto`: USB camera is preferred. If USB is missing or disconnects, phone QR mode is used.
- `usb`: only USB camera is used.
- `phone`: only phone camera is used.

## Kiosk Flow

Landing page:

```text
/
```

Choose `Before Workout` or `After Workout`.

Setup page:

```text
/setup
```

Choose:

- Mode: Before Workout or After Workout
- Body focus: Upper Body, Lower Body, Full Body
- Time: 3 min, 5 min, 8 min

Session page:

```text
/session
```

The session screen is camera-first and shows:

- Live camera stream
- Current stretch name
- Current instruction
- Countdown
- Session mode and body focus
- State
- Score placeholder
- Camera source badge
- Start, Pause, Next, Reset

Debug mode:

```text
/session?debug=1
```

## Camera Testing

Test USB camera:

```bash
FORCE_CAMERA_MODE=usb uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open:

```text
http://<UNO_Q_IP>:8000/session?debug=1
```

Test phone QR mode:

```bash
FORCE_CAMERA_MODE=phone uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open:

```text
http://<UNO_Q_IP>:8000/setup
```

Scan the QR code with the phone. The phone page is only a camera sender and should say:

- Phone Camera Connected
- Place your phone facing your body
- Keep this screen open

## API Routes

- `GET /`
- `GET /setup`
- `GET /session`
- `GET /phone`
- `GET /video_feed`
- `GET /qr.png`
- `GET /api/status`
- `GET /api/health`
- `POST /api/rescan_usb`
- `POST /api/session/start`
- `POST /api/session/pause`
- `POST /api/session/next`
- `POST /api/session/reset`
- `POST /api/session/config`

## Logs

Runtime logs are written to:

```text
logs/app.log
```

The log includes startup details, selected camera mode, USB detection, phone connect/disconnect, source switching, session actions, API errors, camera read failures, QR URL, forced camera mode, and inference hook errors.

Codex implementation notes are in:

```text
docs/CODEX_WORKLOG.md
```

## Future Inference

Add future pose estimation or stretch scoring in:

```text
app/inference.py
```

The current hook is:

```python
process_frame(frame: np.ndarray, context: dict) -> tuple[np.ndarray, dict]
```

For now it draws camera source, FPS, timestamp, session state, and a placeholder score.

## Troubleshooting

Phone and UNO Q are not on the same Wi-Fi:

- Put both devices on the same local network.
- Or use Tailscale and set `PUBLIC_BASE_URL`.

Browser camera permission denied:

- Phone camera access usually requires HTTPS or localhost.
- Use Tailscale Serve or another local HTTPS option.
- Confirm the browser has camera permission.

QR opens but camera does not start:

- Check whether the URL is HTTP. Many phones block `getUserMedia` on plain HTTP IP addresses.
- Use HTTPS with `PUBLIC_BASE_URL`.
- Keep the phone screen awake.

`/dev/video0` not found:

- Try another USB port.
- Check `ls /dev/video*`.
- Use `FORCE_CAMERA_MODE=phone` to continue the demo.

Low FPS:

- Prefer USB camera.
- Reduce other load on the UNO Q.
- Keep phone and UNO Q close to the Wi-Fi access point.

HDMI monitor shows page but no camera:

- Open `/api/status` and check `selected_camera_source`.
- Use `/session?debug=1`.
- Try `POST /api/rescan_usb` or restart the server.

USB camera disconnects:

- In `auto` mode, the app falls back to phone QR mode.
- Plug USB back in and the manager will periodically rescan and switch back to USB.
