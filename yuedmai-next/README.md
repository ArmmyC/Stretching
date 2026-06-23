# YUEDMAI Next

Server-hosted, gamified successor to the original YUEDMAI Arduino kiosk prototype.

This starter intentionally removes the old runtime constraint that required Arduino UNO Q as the server and Arduino Nano 33 BLE Sense Lite as an optional wearable sensor. The new product direction is camera-first, web/PWA-first, and hosted on an Ubuntu server.

## Product Direction

YUEDMAI Next is a gamified stretching companion:

- Uses the user's notebook camera through the browser.
- Sends frames or pose signals to a server-hosted model.
- Gives live stretch guidance and form feedback.
- Rewards sessions with XP, streaks, quests, badges, and cosmetic progression.
- Can become an installable PWA with reminders and notifications.
- Keeps hardware support as a future adapter, not a current dependency.

## Repository Layout

```text
backend/     FastAPI API, session engine, scoring, quests, notifications, pose service adapter
frontend/    Browser/PWA starter using laptop camera and WebSocket pose stream
docs/        Migration and architecture notes
```

## Current Starter Scope

This branch is a clean starting point, not a full replacement yet.

Included now:

- FastAPI app skeleton.
- Session and scoring endpoints.
- Mock server-side pose stream over WebSocket.
- Basic quest and XP logic.
- PWA manifest and service worker starter.
- Browser camera proof-of-concept page.
- Notification permission UI stub.

Not included yet:

- Real MediaPipe server inference.
- Auth and user accounts.
- Database persistence.
- Production push notification backend.
- Deployment config.

## Local Backend

```bash
cd yuedmai-next/backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Local Frontend

```bash
cd yuedmai-next/frontend
npm install
npm run dev
```

The frontend expects the backend at `http://localhost:8000` by default.

## Migration Note

The old project remains valuable as legacy reference, especially its pose tracking, stretch routines, and session scoring logic. Do not copy Arduino/Nano code into this product path unless adding it later through a `SensorAdapter` interface.
