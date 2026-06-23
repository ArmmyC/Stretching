# YUEDMAI Next Architecture

## Goal

Move from an Arduino-constrained local kiosk to a server-hosted gamified web/PWA product.

## Runtime Split

```text
Browser / PWA
  - notebook camera
  - game UI
  - notification permission
  - session controls
  - optional installable app shell

Ubuntu Server
  - FastAPI API
  - pose inference service
  - scoring and session engine
  - quest and achievement engine
  - notification scheduler later

Database later
  - users
  - sessions
  - segments
  - quests
  - achievements
  - notification subscriptions
```

## Current Starter Flow

```text
User opens frontend
→ starts camera
→ frontend opens /ws/pose-stream
→ backend returns mock pose signal
→ frontend posts signal to /api/sessions/{id}/score
→ backend updates score and stars
→ user advances stretch
→ completed session earns XP
```

## Near-Term Replacement Points

### Pose Service

Replace `backend/app/services/pose_service.py` with real server inference.

Input options:

1. Send compressed frames to the backend over WebSocket.
2. Send browser-side landmarks to the backend and keep model client-side.
3. Use WebRTC if low latency becomes important.

For the current project direction, option 1 is the intended path.

### Session Persistence

Replace the in-memory `SessionEngine` with a database-backed service.

Start with SQLite for local development, then move to PostgreSQL when deploying with accounts.

### Notifications

The current notification helper only requests browser permission and displays a local preview notification. Production reminders need service worker push subscriptions, a push provider, and a scheduled backend job.

## Hardware Policy

No sensors are used in the main product path.

Future hardware should connect through a narrow adapter:

```python
class SensorAdapter:
    def status(self) -> dict: ...
    def latest_signal(self) -> dict | None: ...
```

Arduino, Nano BLE, serial, and wearable integrations should remain optional plugins.
