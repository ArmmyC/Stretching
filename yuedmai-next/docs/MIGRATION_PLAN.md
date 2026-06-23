# Migration Plan

## Decision

Create YUEDMAI Next as a clean server-hosted product path instead of continuing the Arduino-first architecture.

The original repo remains the legacy reference for:

- pose tracking experiments
- routine definitions
- scoring heuristics
- old kiosk UI ideas
- Arduino and Nano firmware

## Phase 1: Browser Camera Prototype

- Use browser `getUserMedia` for notebook camera access.
- Keep frontend and backend separate.
- Connect frontend to backend pose stream over WebSocket.
- Use mock pose signals first.
- Keep all sensor code out of the critical path.

## Phase 2: Server Pose Inference

- Port useful logic from the old `inference.py` and pose model setup.
- Decide frame transport format.
- Add frame validation and rate limiting.
- Add confidence smoothing.
- Add calibration and boundary checks.

## Phase 3: Game Loop

- Add XP, stars, daily quests, and streaks.
- Add result screen with earned rewards.
- Reward consistency, completion, and safe camera visibility.
- Avoid scoring body shape or extreme flexibility.

## Phase 4: Persistence

- Add database models.
- Store users, sessions, session segments, quests, achievements, and notification subscriptions.
- Replace in-memory session engine.

## Phase 5: PWA Reminders

- Add install prompt.
- Add push subscription API.
- Add scheduled reminders.
- Add notification preferences.

## Phase 6: Future Hardware Adapter

- Define a small optional `SensorAdapter` interface.
- Keep Arduino/Nano as future plugin packages only.
- Do not make sensors required for the main app.

## Files Worth Porting From Legacy

Potentially useful:

```text
stretch_applab/python/app/inference.py
stretch_applab/python/app/session_manager.py
stretch_applab/python/app/stretch_models.py
stretch_applab/python/models/
stretch_applab/python/app/static/PoseGuideline/
```

Avoid porting directly:

```text
arduino/
stretch_applab/sketch/
hardware_bridge.py
nano_ble.py
UNO Q deployment docs
```
