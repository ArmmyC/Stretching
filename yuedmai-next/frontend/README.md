# YUEDMAI Next Frontend

Installable PWA starter for the server-hosted YUEDMAI product.

## Run

```bash
npm install
npm run dev
```

Open the Vite URL in a browser. Camera access works on localhost during development. For real deployment, use HTTPS.

## Current Features

- Browser camera preview using `getUserMedia`.
- WebSocket connection to backend pose stream.
- Daily quest board.
- XP and score HUD.
- PWA manifest.
- Service worker starter.
- Notification permission preview.

## Next Frontend Tasks

1. Replace the mock visual design with final game art direction.
2. Add calibration and boundary-check flow.
3. Send real frame data or compressed pose input to the backend.
4. Add install prompt UI.
5. Add user settings for reminders.
6. Add session result screen with badges, XP, and streaks.
