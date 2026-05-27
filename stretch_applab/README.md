# StretchSense App Lab Package

This folder is a packaging copy for Arduino App Lab. It keeps the main FastAPI app from `stretch_stream` intact and adds only an App Lab launcher.

## What To Put Into App Lab

Copy the contents of this folder into an Arduino App Lab app folder, for example:

```text
~/ArduinoApps/SmartStretchCoach/
  python/
  sketch/
  docs/
  README.md
```

The important files are:

- `python/app/`: the FastAPI StretchSense app, templates, CSS, JavaScript, camera manager, QR phone streaming, and inference hook.
- `python/main.py`: App Lab launcher that starts Uvicorn on `0.0.0.0:8000` by default.
- `python/requirements.txt`: Python dependencies for the App Lab virtual environment.
- `sketch/sketch.ino`: minimal MCU sketch placeholder.

## What Changed Compared With `stretch_stream`

The app logic is not changed. Camera streaming, QR streaming, source manager, and inference files are copied as-is.

The only added file is `python/main.py`, which starts the existing FastAPI app under App Lab.

## Run In App Lab

Inside the UNO Q:

```bash
cd ~/ArduinoApps
arduino-app-cli app new "SmartStretchCoach"
```

Then copy this package contents into:

```text
~/ArduinoApps/SmartStretchCoach/
```

Start it:

```bash
arduino-app-cli app start user:smartstretchcoach
arduino-app-cli app logs user:smartstretchcoach --all
```

Open the kiosk UI:

```text
http://<UNO_Q_IP>:8000/
```

## Environment Variables

Optional:

```bash
export APP_HOST=0.0.0.0
export APP_PORT=8000
export FORCE_CAMERA_MODE=auto
export PUBLIC_BASE_URL=http://<UNO_Q_IP>:8000
```

Use `PUBLIC_BASE_URL` when QR should point to a specific IP, Tailscale name, or HTTPS URL.
