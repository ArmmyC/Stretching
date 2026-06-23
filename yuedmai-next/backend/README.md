# YUEDMAI Next Backend

FastAPI starter for the server-hosted YUEDMAI product.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Endpoints

- `GET /api/health`
- `POST /api/sessions`
- `GET /api/sessions/{session_id}`
- `POST /api/sessions/{session_id}/score`
- `POST /api/sessions/{session_id}/advance`
- `GET /api/quests/daily`
- `GET /api/notifications/preview`
- `WS /ws/pose-stream`

## Design Notes

The current backend is intentionally in-memory. This lets the game loop and camera contract move quickly before adding database migrations, auth, and production notifications.

The pose stream currently returns mock pose signals. Replace `app/services/pose_service.py` with a real MediaPipe or MoveNet server-side implementation when the frontend contract is stable.
