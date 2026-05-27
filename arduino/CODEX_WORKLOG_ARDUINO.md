# Codex Worklog - Arduino Firmware

## Date/Time

- 2026-05-27 20:44:48 +07:00, Asia/Bangkok workspace context.

## Files Created

- `arduino/NanoStretchNode/NanoStretchNode.ino`
- `arduino/UnoQStretchHub/UnoQStretchHub.ino`
- `arduino/tools/nano_signal_dashboard.html`
- `arduino/NANO_SIGNAL_DASHBOARD.md`
- `arduino/README_ARDUINO.md`
- `arduino/SERIAL_PROTOCOL.md`
- `arduino/CODEX_WORKLOG_ARDUINO.md`

## Design Decisions

- Kept camera pose estimation outside Arduino firmware. UNO Q only accepts `camera_pose` flags from the Linux/Python app.
- Nano performs first-pass IMU processing and sends compact JSON at 20 Hz.
- UNO Q performs phase 2 to phase 4 fusion and sends `stretch_state` JSON at 10 Hz.
- Nano now has JSON output for app/dashboard use and labelled plotter output for Arduino Serial Plotter.
- Added a dependency-free Web Serial dashboard that plots individual Nano signal lines in Chrome or Edge.
- Used non-blocking `millis()` timing for calibration, serial parsing, output, distance reads, feedback, debounce, and hold timing.
- Added 300 ms state debounce to reduce flicker into `HOLD_STEADY` and `UNSTABLE`.
- Hold time resets only after sustained bad form for 1200 ms.
- `GOOD` appears once the target hold is reached, then transitions to `DONE` after a short success window.
- Score is explicitly documented as prototype wellness feedback, not a medical assessment.

## Libraries Assumed

- Nano IMU:
  - `Arduino_LSM9DS1` for `IMU_BACKEND_LSM9DS1`.
  - `Arduino_BMI270_BMM150` for `IMU_BACKEND_BMI270`.
- UNO Q optional:
  - `Arduino_Modulino` for `ModulinoDistance`, `ModulinoPixels`, `ModulinoBuzzer`, and `ModulinoButtons`.
  - `ArduinoJson` for robust JSON parsing.

## Compile-Time Flags Added

Nano:

- `IMU_BACKEND_LSM9DS1`
- `IMU_BACKEND_BMI270`
- `DEFAULT_PLOTTER_MODE`

UNO Q:

- `USE_NANO_ON_SERIAL1`
- `USE_NANO_FORWARD_FROM_USB_SERIAL`
- `USE_MODULINO_DISTANCE`
- `USE_MODULINO_PIXELS`
- `USE_MODULINO_BUZZER`
- `USE_MODULINO_BUTTONS`
- `USE_LCD`
- `USE_MOCK_DISTANCE`
- `AUTO_MOCK_DISTANCE_IF_LIBRARY_MISSING`
- `MODULINO_DISTANCE_RETURNS_MM`

## Known Uncertain APIs

- Modulino APIs were isolated in small functions. Current Arduino documentation shows:
  - `#include <Arduino_Modulino.h>`
  - `Modulino.begin()`
  - `ModulinoDistance distance; distance.begin(); distance.get();`
  - `ModulinoPixels leds; leds.set(index, ModulinoColor(...)); leds.show();`
  - `ModulinoBuzzer buzzer; buzzer.tone(freq, duration);`
  - `ModulinoButtons buttons; buttons.update(); buttons.isPressed(index);`
- Some tutorials still show `#include <Modulino.h>`, so the sketch checks both headers.
- LCD support is stubbed because no exact LCD library or wiring was specified.
- `Serial1` is enabled for the Nano UART path; set `USE_NANO_ON_SERIAL1 0` if the selected UNO Q board profile does not expose `Serial1`.

## Tests Performed

- Created firmware and documentation files in the workspace.
- Reviewed sketches for missing semicolons, obvious malformed conditionals, and stale-data logic.
- Ran a local static file sanity check for balanced braces, parentheses, and brackets after stripping comments and strings.
- Added a self-contained HTML dashboard and reviewed it for local-only Web Serial usage with no external assets or packages.
- Parsed the dashboard JavaScript with Node's `Function` constructor to catch syntax errors.
- Added fallback JSON parsing so UNO Q can still accept simple messages when `ArduinoJson` is not installed.
- Added automatic mock distance when the Modulino library is absent, enabling manual Serial Monitor testing without sensors.
- Checked for `arduino-cli`; it is not installed in this workspace.

## Commands Run

- Listed workspace contents.
- Checked git status.
- Created `arduino/NanoStretchNode` and `arduino/UnoQStretchHub` directories.

## Could Not Compile Here

- Actual Arduino compilation was not run in this environment because board cores and hardware libraries are not installed in the workspace.
- `arduino-cli` was not available on PATH.
- Modulino hardware behavior must be verified on the actual UNO Q with the installed `Arduino_Modulino` library.
- IMU backend must be selected against the exact Nano 33 BLE Sense Lite variant.

## Manual Test Messages

UNO Q Serial Monitor:

```text
START
{"type":"camera_pose","user_visible":true,"full_body_visible":true,"arm_raised":true,"torso_centered":true,"confidence":0.9}
{"type":"nano_imu","relative_pitch":62.0,"gyro_mag":7.0,"stable":true,"arm_raised":true,"state":"NANO_HOLD_STABLE"}
```

Expected: `HOLD_STEADY`, then `GOOD` after `SET_TARGET_HOLD` seconds, then `DONE`.

Nano Serial Monitor:

```text
CALIBRATE
STATUS
SET_ARM_THRESHOLD 55
SET_STABILITY_THRESHOLD 20
PLOTTER_ON
OUTPUT_JSON
```

## Known Limitations

- Accelerometer-only pitch works for a stable MVP but is sensitive to strap orientation and fast movement.
- The prototype assumes one MVP stretch: overhead shoulder stretch.
- Camera flags are trusted inputs; bad pose inference upstream can produce bad guidance downstream.
- The fallback JSON parser is intentionally small and only supports the flat JSON messages documented here.
- Buttons are mapped to three Modulino buttons: A start/pause, B next, C reset. Separate start and pause remain available as serial commands.

## Recommended Next Steps

- Compile both sketches in Arduino IDE with the exact board profiles.
- Verify whether `ModulinoDistance.get()` returns centimeters or millimeters, then set `MODULINO_DISTANCE_RETURNS_MM` accordingly.
- Confirm UNO Q `Serial1` pins and Nano voltage-level compatibility.
- Tune `SET_ARM_THRESHOLD`, `SET_STABILITY_THRESHOLD`, and distance thresholds with real users.
- Add the selected LCD library implementation if the display is included in the demo.
- Have the Linux/Python app ignore `#` lines and consume only `type:"stretch_state"` JSON for the dashboard.
