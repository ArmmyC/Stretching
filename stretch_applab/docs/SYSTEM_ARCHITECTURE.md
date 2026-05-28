# YUEDMAI System Architecture

Editable diagram: `docs/YUEDMAI_system_architecture.drawio`

## System Role

`stretch_applab` packages the YUEDMAI Smart Stretch Coach for Arduino App Lab. The app runs a local FastAPI kiosk server on the UNO Q or a local Python runtime, serves the browser UI, streams camera frames, runs pose inference, manages a stretch-session state machine, and exposes optional UNO Q hardware input through a bridge.

## Deployment Context

- `python/main.py` is the App Lab launcher. It sets pose-related defaults and starts `uvicorn` with `app.main:app`.
- `python/app/main.py` owns the FastAPI application, routes, lifecycle hooks, status aggregation, MJPEG stream, QR endpoints, and capture summaries.
- `python/app/templates/` and `python/app/static/` provide the kiosk pages and client-side behavior.
- `sketch/sketch.ino` is currently a minimal MCU placeholder for future hardware behavior.
- `python/models/pose_landmarker.task` is the default MediaPipe pose model asset.

## Main Runtime Components

- `SourceManager`: chooses the active camera source using `FORCE_CAMERA_MODE` (`auto`, `usb`, or `phone`), keeps a background loop running, and exposes camera status plus the latest frame.
- `USBCameraSource`: scans OpenCV camera indexes `0-5`, validates frames, reads from `cv2.VideoCapture`, and marks repeated failures as disconnection.
- `PhoneCameraSource`: accepts JPEG frames from `/ws/phone-frame`, decodes them with OpenCV, tracks connected phone clients, and updates frame stats.
- `LatestFrameStore`: thread-safe latest-frame buffer shared by camera sources.
- `inference.py`: processes frames for `/video_feed`, overlays labels, invokes pose tracking, and caches pose metrics for `/api/status`.
- `PoseTracker`: loads MediaPipe by default, can fall back to MoveNet or NCNN, supports async inference, frame stride, and pose readiness flags.
- `SessionManager`: tracks routine configuration, session state, elapsed time, current stretch, remaining time, and score.
- `CaptureStore`: stores per-session photos in memory, validates base64 uploads, serves summary pages, QR codes, images, and ZIP downloads.
- `HardwareBridge`: adapts optional `arduino.app_utils.Bridge` events to browser WebSocket events and sends feedback back to the UNO Q bridge when available.

## Browser Flows

- Landing/setup/session pages are served by FastAPI templates.
- `setup.js` manages routine configuration and hardware navigation on the setup page.
- `session.js` polls `/api/status` every 500 ms, drives boundary precheck, posts session actions, captures photos from the MJPEG image element, and uploads captures.
- `hardware.js` connects to `/ws/hardware`, emits normalized `YUEDMAI:hardware` DOM events, provides keyboard fallback controls, and sends feedback through `/api/hardware/feedback`.
- `phone.html` captures phone camera frames and streams JPEG bytes to `/ws/phone-frame`.

## Key API Surface

- Pages: `/`, `/setup`, `/session`, `/phone`, `/summary/{session_id}`
- Status and health: `/api/status`, `/api/health`, `/api/hardware`
- Session controls: `/api/session/start`, `/api/session/pause`, `/api/session/next`, `/api/session/reset`, `/api/session/config`
- Capture upload and sharing: `/api/session/captures`, `/summary/{session_id}/image/{index}.{ext}`, `/summary/{session_id}/download.zip`
- Camera and hardware streams: `/video_feed`, `/ws/phone-frame`, `/ws/hardware`
- QR images: `/qr.png`, `/summary_qr/{session_id}.png`

## Important Runtime Notes

- The app is local-first and does not require a cloud service or database.
- Captures are stored in process memory; restarting the app clears active summary photos.
- The MJPEG camera stream and `/api/status` polling are separate browser flows.
- Boundary readiness depends on active camera state, fresh pose status, full-body visibility, torso centering, and confidence.
- Hardware integration is optional. Browser keyboard controls still drive the same normalized action path.
