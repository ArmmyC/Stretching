# Smart Stretch Coach Test Plan

## Test 1: HDMI/monitor dashboard opens

Steps:

1. Connect the UNO Q to an HDMI monitor.
2. Install requirements.
3. Run `python main.py`.

Pass criteria:

- An OpenCV window titled `Smart Stretch Coach Station` appears.
- The dashboard shows source, status, FPS, resolution, placeholder inference, stretch state, and controls.

Fail criteria:

- No window appears.
- The app exits with an OpenCV GUI error.

## Test 2: USB camera detected

Steps:

1. Connect a USB webcam.
2. Run `python main.py --mode auto`.

Pass criteria:

- Logs show attempts for camera indexes 0 to 5 until a working camera is found.
- Dashboard source is `USB_CAMERA`.
- Live video appears.
- QR pairing is not shown.

Fail criteria:

- A working USB camera is ignored.
- QR mode appears while USB frames are available.

## Test 3: USB camera unplugged, QR mode appears

Steps:

1. Start in USB mode with live video.
2. Unplug the USB webcam.
3. Wait for repeated read failures.

Pass criteria:

- Logs show USB read failures.
- The manager switches to `PHONE_QR`.
- The dashboard displays a QR code and phone URL.

Fail criteria:

- The app crashes.
- The dashboard freezes permanently.

## Test 4: phone scans QR and connects

Steps:

1. Start with no USB camera connected.
2. Scan the dashboard QR code using a phone on the same network.
3. Allow camera permission.

Pass criteria:

- Phone page opens.
- Phone status changes to streaming or connected.
- Station logs a phone connection event.
- Dashboard status changes from waiting to connected.

Fail criteria:

- Phone cannot reach the station URL.
- WebSocket never connects.

## Test 5: frames stream from phone to UNO Q

Steps:

1. Complete Test 4.
2. Point the phone camera at a moving scene.

Pass criteria:

- Dashboard shows live phone frames.
- FPS is around 10 FPS on a stable network.
- Frame resolution appears as 640x480.
- Logs show received frames without repeated decode errors.

Fail criteria:

- Dashboard remains on waiting screen.
- Decode errors increase continuously.

## Test 6: force mode switching

Steps:

1. Run `python main.py`.
2. Press `p`.
3. Press `u`.
4. Press `r`.

Pass criteria:

- `p` starts phone QR mode.
- `u` starts USB mode if a valid USB camera is connected, or logs a clean failure if not.
- `r` restarts automatic detection.
- The app does not crash during switches.

Fail criteria:

- Mode switch crashes the app.
- The dashboard no longer updates after a switch.

## Test 7: save debug frame

Steps:

1. Start either USB or phone mode with live video.
2. Press `s`.

Pass criteria:

- A JPEG is saved under `debug_frames/`.
- Logs show the saved file path.

Fail criteria:

- No file is saved while frames are available.
- The app crashes when saving.

## Test 8: 5-minute stability test

Steps:

1. Run either USB or phone mode.
2. Leave the dashboard running for 5 minutes.
3. Move occasionally in front of the camera.

Pass criteria:

- Dashboard remains responsive.
- FPS remains visible.
- Logs do not show repeated unhandled exceptions.
- Pressing `q` exits cleanly.

Fail criteria:

- Memory or CPU growth makes the station unusable.
- The WebSocket thread blocks the dashboard.
- The dashboard becomes unresponsive.
