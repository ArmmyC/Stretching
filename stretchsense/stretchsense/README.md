# StretchSense — Kiosk UI

Drop-in frontend for an existing FastAPI / Jinja project running on Arduino UNO Q Linux.
No CDN, no external fonts, no JS framework, no icons library.

## Files

```
templates/
  landing.html   ->  GET /
  setup.html     ->  GET /setup
  session.html   ->  GET /session
  phone.html     ->  GET /phone
static/
  style.css
  session.js
```

## FastAPI mount (example)

```python
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/",        response_class=HTMLResponse)
def landing(req: Request): return templates.TemplateResponse("landing.html", {"request": req})
@app.get("/setup",   response_class=HTMLResponse)
def setup(req: Request):   return templates.TemplateResponse("setup.html",   {"request": req})
@app.get("/session", response_class=HTMLResponse)
def session(req: Request): return templates.TemplateResponse("session.html", {"request": req})
@app.get("/phone",   response_class=HTMLResponse)
def phone(req: Request):   return templates.TemplateResponse("phone.html",   {"request": req})
```

## Expected backend endpoints (already provided by your app)

- `GET /video_feed` — MJPEG stream
- `GET /qr.png` — phone-pair QR
- `GET /api/status` — JSON: `{ camera, state, stretch:{name,step_label,instruction}, remaining_s, progress, score, stability, config:{mode,focus,duration}, fps, frame_w, frame_h, frame_ts, elapsed_s, forced_camera, local_url, position_ok }`
- `POST /api/session/start | /pause | /next | /reset`
- `POST /api/session/config` — form-encoded `mode, focus, duration`

All UI polling is **fail-safe** — if the endpoint is missing, the page degrades quietly.

## Conventions

- Score, FPS, debug never appear on landing / setup.
- Setup camera frame says "Setup preview only · No score yet".
- Debug panel only visible at `/session?debug=1`.
- QR area on setup is hidden when USB camera is active.
- Wellness language only — no medical/diagnostic claims.

## Look & feel

- Near-black background, lime (`#b8ff3a`) + cyan (`#36e0ff`) glow accents
- System font stack — no online fonts
- Designed first for 1920×1080 and ultrawide 2048×900
- Responsive fallback for smaller screens
