# StretchSense Arduino Firmware

This folder contains the Arduino IDE firmware for the StretchSense hackathon prototype. The sketches focus on stable wellness guidance for an overhead shoulder stretch. They do not diagnose, treat, or guarantee injury prevention.

## Hardware Roles

- `NanoStretchNode`: wearable forearm IMU node on Arduino Nano 33 BLE Sense Lite.
- `UnoQStretchHub`: UNO Q hardware hub for distance, buttons, buzzer, pixels, optional LCD, serial input, and fusion state.
- UNO Q Linux/Python app: camera streaming, QR phone streaming, dashboard, and future pose inference. Camera inference does not run in `.ino` files.

## Folder Layout

```text
arduino/
  NanoStretchNode/
    NanoStretchNode.ino
  UnoQStretchHub/
    UnoQStretchHub.ino
  README_ARDUINO.md
  SERIAL_PROTOCOL.md
  CODEX_WORKLOG_ARDUINO.md
```

## Wiring Options

- Nano to UNO Q direct UART: Nano `TX` to UNO Q `RX1`, Nano `RX` to UNO Q `TX1`, common `GND`. Keep voltage compatibility in mind for the exact boards in use.
- Nano to UNO Q Linux/Python app: Nano USB connects to Linux side, and the app forwards Nano JSON to the UNO Q sketch over USB Serial.
- Modulino modules: connect over Qwiic/I2C. The sketch isolates all Modulino-specific calls in `initDistanceSensor()`, `readDistanceCm()`, `initFeedback()`, `readButtons()`, and pixel/buzzer helpers.

## Forearm Strap Setup

Strap the Nano firmly to the forearm so the board moves with the arm. Keep the orientation consistent between calibration and use. A simple rule for the prototype is: USB connector points toward the wrist or toward the elbow, but do not switch orientation after calibration.

## Uploading `NanoStretchNode.ino`

1. Open `arduino/NanoStretchNode/NanoStretchNode.ino` in Arduino IDE.
2. Select the Nano 33 BLE Sense Lite board profile.
3. At the top of the sketch, choose one IMU backend:
   - `#define IMU_BACKEND_LSM9DS1`
   - or `#define IMU_BACKEND_BMI270`
4. Install the matching IMU library if needed.
5. Upload.
6. Open Serial Monitor at `115200` baud.

## Uploading `UnoQStretchHub.ino`

1. Open `arduino/UnoQStretchHub/UnoQStretchHub.ino` in Arduino IDE.
2. Select the UNO Q board profile.
3. Install optional libraries as needed.
4. Confirm top-level flags:
   - `USE_NANO_ON_SERIAL1`
   - `USE_NANO_FORWARD_FROM_USB_SERIAL`
   - `USE_MODULINO_DISTANCE`
   - `USE_MODULINO_PIXELS`
   - `USE_MODULINO_BUZZER`
   - `USE_MODULINO_BUTTONS`
   - `USE_LCD`
   - `USE_MOCK_DISTANCE`
5. Upload.
6. Open Serial Monitor at `115200` baud.

## Required Libraries

- Nano:
  - `Arduino_LSM9DS1` for LSM9DS1 boards.
  - `Arduino_BMI270_BMM150` for Rev2-style BMI270/BMM150 boards.
- UNO Q:
  - No hard dependency for serial-only mock testing.
  - `ArduinoJson` is recommended for robust JSON parsing. A small fallback parser is included for the simple messages in this prototype.

## Optional Libraries

- `Arduino_Modulino` for Modulino Distance, Pixels, Buzzer, and Buttons. The sketch also checks for older `Modulino.h` examples.
- An LCD library of your choice if `USE_LCD` is set to `1`; display functions are stubbed until a specific LCD is chosen.

Arduino's current Modulino library documentation shows `#include <Arduino_Modulino.h>`, `Modulino.begin()`, `ModulinoDistance`, `ModulinoPixels`, `ModulinoBuzzer`, and `ModulinoButtons`.

## Test Nano Alone

Open Serial Monitor at `115200` baud. Keep the forearm still for the first two seconds while baseline calibration runs. You should see `#` startup logs followed by JSON:

```json
{"type":"nano_imu","t":12345,"pitch":62.1,"roll":4.2,"relative_pitch":58.3,"gyro_mag":8.4,"stable":true,"arm_raised":true,"state":"NANO_HOLD_STABLE"}
```

Useful commands:

```text
CALIBRATE
STATUS
SET_ARM_THRESHOLD 55
SET_STABILITY_THRESHOLD 20
```

## Test UNO Q Alone

If the Modulino library is missing, the UNO Q sketch automatically uses mock distance so the serial state machine can still be tested. If the library is installed but no sensor is connected, set `USE_MOCK_DISTANCE 1` before upload.

Send these lines in Serial Monitor at `115200` baud:

```text
START
{"type":"camera_pose","user_visible":true,"full_body_visible":true,"arm_raised":true,"torso_centered":true,"confidence":0.9}
{"type":"nano_imu","relative_pitch":62.0,"gyro_mag":7.0,"stable":true,"arm_raised":true,"state":"NANO_HOLD_STABLE"}
```

Expected behavior: UNO Q outputs `HOLD_STEADY`, then `GOOD` after the target hold time, then `DONE`.

## Camera App Integration

The Linux/Python camera app should send newline-delimited JSON to the UNO Q sketch:

```json
{"type":"camera_pose","t":12345,"user_visible":true,"full_body_visible":true,"arm_raised":true,"torso_centered":true,"confidence":0.82}
```

Keep the camera message rate at roughly 10 to 30 Hz. The sketch marks camera data stale after 1000 ms.

## Dashboard Integration

The dashboard reads newline-delimited `stretch_state` JSON from UNO Q:

```json
{"type":"stretch_state","t":12345,"state":"HOLD_STEADY","instruction":"Hold the stretch","score":72,"distance_cm":132,"nano_angle":61.2,"gyro_mag":8.1,"camera_arm_raised":true,"nano_arm_raised":true,"hold_sec":4.3,"source_ok":true}
```

Ignore lines starting with `#`; those are human-readable logs and command acknowledgements.

## Calibration Procedure

1. Put the Nano on the forearm.
2. Relax the arm in the baseline position.
3. Power or reset the Nano.
4. Hold still for two seconds while baseline pitch is collected.
5. Recalibrate any time with `CALIBRATE` on the Nano or `CALIBRATE_NANO` through the UNO Q sketch.

## Threshold Tuning Guide

- `SET_ARM_THRESHOLD 55`: increase if normal movement falsely counts as raised; decrease if the user cannot reach the target angle.
- `SET_STABILITY_THRESHOLD 20`: increase if the prototype is too strict; decrease if it allows shaky holds.
- `SET_TARGET_HOLD 8`: changes the hold duration in seconds.
- `SET_DISTANCE_MIN 80` and `SET_DISTANCE_MAX 220`: tune setup guidance for the camera field of view and room layout.

## Known Limitations

- The pitch estimate is accelerometer-based and simple; it is good enough for a hackathon prototype, not biomechanics-grade measurement.
- The score is a prototype wellness feedback score, not a medical assessment.
- Modulino APIs are isolated, but hardware behavior still needs verification on the exact UNO Q and library version used at the event.
- LCD support is intentionally stubbed until the exact display is selected.
- Camera pose flags are trusted as external inputs; no MediaPipe, OpenCV, or ML inference runs in the Arduino sketches.
