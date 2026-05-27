# Codex Work Log

## 2026-05-27

### Summary

Created a new local kiosk web app named `stretch_stream` for the Smart Stretch Coach / StretchSense prototype.

### Files Created

- `stretch_stream/README.md`
- `stretch_stream/requirements.txt`
- `stretch_stream/.gitignore`
- `stretch_stream/docs/CODEX_WORKLOG.md`
- `stretch_stream/logs/.gitkeep`
- `stretch_stream/app/__init__.py`
- `stretch_stream/app/main.py`
- `stretch_stream/app/camera_sources.py`
- `stretch_stream/app/source_manager.py`
- `stretch_stream/app/session_manager.py`
- `stretch_stream/app/inference.py`
- `stretch_stream/app/utils.py`
- `stretch_stream/app/templates/landing.html`
- `stretch_stream/app/templates/setup.html`
- `stretch_stream/app/templates/session.html`
- `stretch_stream/app/templates/phone.html`
- `stretch_stream/app/static/style.css`
- `stretch_stream/app/static/session.js`

### Files Modified

- None outside the new `stretch_stream` project during this upgrade.

### Features Added

- Local FastAPI kiosk app hosted by Arduino UNO Q.
- Landing page at `/`.
- Setup page at `/setup`.
- Camera-first session page at `/session`.
- Phone camera sender page at `/phone`.
- MJPEG selected camera stream at `/video_feed`.
- QR code image route at `/qr.png`.
- JSON status route at `/api/status`.
- JSON health route at `/api/health`.
- Session control APIs:
  - `POST /api/session/start`
  - `POST /api/session/pause`
  - `POST /api/session/next`
  - `POST /api/session/reset`
  - `POST /api/session/config`
- USB rescan API:
  - `POST /api/rescan_usb`
- USB camera priority in `auto` mode.
- Forced camera mode through `FORCE_CAMERA_MODE=auto|usb|phone`.
- Phone camera WebSocket sender route at `/ws/phone-frame`.
- Fake stretch-session state machine with `IDLE`, `READY`, `HOLD`, `GOOD`, `DONE`, `NO_CAMERA`, and `WAITING_FOR_PHONE`.
- Placeholder stretch routines for before workout, after workout, upper body, lower body, and full body.
- Future inference hook in `app/inference.py`.
- Runtime logs to `logs/app.log` and console.
- Local CSS and JavaScript only, with no CDN or external dependencies.

### Important Design Decisions

- UNO Q hosts the web app locally to prioritize low latency, privacy, and reliability inside a gym room.
- USB camera is preferred in `auto` mode because it is lower latency and more reliable for a kiosk.
- Phone camera page is only a sender page. The monitor/browser session page remains the main user interface.
- The session page is camera-first, with the camera occupying most of the screen and instructions/timer beside it.
- The current inference implementation is intentionally a placeholder so the hackathon team can insert MediaPipe, TensorFlow Lite, ONNX, or custom scoring later.
- No database, authentication, cloud service, or public hosting was added.

### Commands Run

- Read current workspace files with `Get-ChildItem` and `rg --files`.
- Created files with `apply_patch`.
- Generated one visual reference image for the kiosk session screen using the local image generation tool.
- Ran Python source compile check:
  - `python -B -c "from pathlib import Path; [compile(p.read_text(encoding='utf-8'), str(p), 'exec') for p in Path('.').rglob('*.py')]; print('python source compile ok')"`
- Ran ASCII check:
  - `rg --pcre2 "[^\x00-\x7F]"`
- Ran core import smoke test:
  - `python -B -c "from app.session_manager import SessionManager; from app.source_manager import SourceManager; import app.inference; print('core imports ok')"`
- Attempted Uvicorn smoke start:
  - `python -m uvicorn app.main:app --host 127.0.0.1 --port 8010`
- Attempted FastAPI app module import:
  - `python -B -c "from app.main import app; print(app.title)"`

### Tests Performed

- Python source compile check passed.
- ASCII check passed with no non-ASCII matches.
- Core imports for `SessionManager`, `SourceManager`, and `inference` passed.
- Full FastAPI app import could not run in this Windows workspace because `fastapi` is not installed here.
- Uvicorn start smoke test could not run in this Windows workspace because `uvicorn` is not installed here.
- No browser rendering test was performed because the local environment is missing the required FastAPI/Uvicorn dependencies.

### Errors Encountered

- The Windows sandbox required escalated execution for read-only PowerShell commands.
- Local Uvicorn smoke test failed with `No module named uvicorn`.
- Local FastAPI app import failed with `No module named fastapi`.

### Assumptions Made

- The new app should live beside the previous prototype under `stretch_stream`.
- The app will be run from the `stretch_stream` directory using `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- `opencv-python-headless` is appropriate because the new app is browser-based and does not need OpenCV GUI windows.
- Phone camera streaming may require HTTPS depending on browser security rules.

### Known Limitations

- No real pose estimation or stretch form scoring is implemented yet.
- Phone camera access may fail on plain HTTP URLs in mobile browsers.
- The fake session timeline is timer-based and does not react to body pose yet.
- `/video_feed` is MJPEG, which is simple and reliable for a prototype but not as bandwidth-efficient as WebRTC.
- Full runtime test still needs to be run on the UNO Q after installing `requirements.txt`.

### Recommended Next Steps

- Run on UNO Q with a USB camera and verify `/session?debug=1`.
- Verify phone camera mode through HTTPS or Tailscale Serve.
- Add a simple persistence-free routine summary screen if time allows.
- Insert a real pose estimation model inside `app/inference.py`.
