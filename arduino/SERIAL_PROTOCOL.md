# StretchSense Serial Protocol

All firmware messages are newline-delimited. Use `115200` baud for both sketches. Lines starting with `#` are human-readable logs or acknowledgements and can be ignored by receivers.

## Nano Output

Direction: Nano wearable to UNO Q or Linux/Python app.

Rate: compact JSON is 20 Hz. Full dashboard JSON and plotter output are 10 Hz to leave serial bandwidth for the larger payload.

Compact `OUTPUT_JSON` includes the stretch fields needed by UNO Q. Full `OUTPUT_FULL_JSON` includes those plus the optional sensor fields shown below.

Full format:

```json
{
  "type": "nano_imu",
  "t": 12345,
  "ax": 0.12,
  "ay": 0.03,
  "az": 0.98,
  "gx": 1.4,
  "gy": 2.0,
  "gz": 0.4,
  "pitch": 62.1,
  "roll": 4.2,
  "relative_pitch": 58.3,
  "gyro_mag": 8.4,
  "gyro_avg": 7.9,
  "stability_score": 61,
  "arm_threshold": 55.0,
  "stability_threshold": 20.0,
  "mx": 12.4,
  "my": -3.1,
  "mz": 40.2,
  "mag_mag": 42.2,
  "heading_deg": 346.0,
  "proximity": 18,
  "red": 76,
  "green": 89,
  "blue": 102,
  "ambient": 204,
  "gesture_code": -1,
  "gesture": "none",
  "pressure_kpa": 100.84,
  "pressure_hpa": 1008.4,
  "temperature_c": 29.2,
  "humidity": 54.0,
  "mic_rms": 410.2,
  "mic_peak": 1220,
  "mic_dbfs": -38.0,
  "mic_level": 2.8,
  "stable": true,
  "arm_raised": true,
  "state_code": 2,
  "state": "NANO_HOLD_STABLE"
}
```

Nano states:

- `NANO_ARM_LOW`
- `NANO_ARM_RAISED`
- `NANO_HOLD_STABLE`
- `NANO_UNSTABLE`
- `NANO_CALIBRATING`
- `NANO_ERROR`

## Nano Commands

Send as plain newline-delimited text:

```text
CALIBRATE
STATUS
SET_ARM_THRESHOLD 55
SET_STABILITY_THRESHOLD 20
PLOTTER_ON
PLOTTER_OFF
OUTPUT_JSON
OUTPUT_FULL_JSON
OUTPUT_PLOTTER
```

`OUTPUT_JSON` is the compact UNO-compatible stream. `OUTPUT_FULL_JSON` adds optional dashboard fields for magnetometer, APDS9960 proximity/light/color/gesture, LPS22HB barometer, HTS221/HS300x temperature and humidity, and PDM microphone level. Fields for unavailable libraries or sensors remain at default values and publish companion booleans such as `apds_ok`, `baro_ok`, `env_ok`, and `mic_ok`.

`PLOTTER_ON` and `OUTPUT_PLOTTER` switch the Nano from JSON to labelled numeric output for Arduino Serial Plotter:

```text
pitch:61.8	roll:4.0	relative_pitch:57.9	arm_threshold:55.0	gyro_mag:8.3	gyro_avg:7.8	stability_threshold:20.0	stability_score:61	mx:12.4	my:-3.1	mz:40.2	mag_mag:42.2	heading_deg:346.0	proximity:18	ambient:204	red:76	green:89	blue:102	pressure_hpa:1008.4	temperature_c:29.2	humidity:54.0	mic_level:2.8	mic_rms:410.2	mic_dbfs:-38.0	gesture_code:-1	arm_raised:100	stable:100	state_band:40
```

Use `PLOTTER_OFF` or `OUTPUT_JSON` before connecting the Nano to the UNO Q sketch or the browser dashboard.

## UNO Q Inputs

UNO Q accepts plain commands and JSON messages over USB Serial. It can also read Nano JSON from `Serial1` when `USE_NANO_ON_SERIAL1` is enabled.

### Plain Commands

```text
START
PAUSE
NEXT
RESET
CALIBRATE_NANO
SET_MODE before
SET_MODE after
SET_BODY_FOCUS upper
SET_BODY_FOCUS lower
SET_BODY_FOCUS full
SET_TARGET_HOLD 8
SET_DISTANCE_MIN 80
SET_DISTANCE_MAX 220
STATUS
```

Extra test helper:

```text
SET_MOCK_DISTANCE 140
```

### Camera Pose JSON

Camera pose comes from the UNO Q Linux/Python app. The Arduino sketch does not run pose estimation.

```json
{"type":"camera_pose","t":12345,"user_visible":true,"full_body_visible":true,"arm_raised":true,"torso_centered":true,"confidence":0.82}
```

Fields:

- `user_visible`: camera sees a user.
- `full_body_visible`: camera sees enough body framing for the stretch check.
- `arm_raised`: camera pose model says the target arm is raised.
- `torso_centered`: torso is reasonably centered for the overhead shoulder stretch.
- `confidence`: `0.0` to `1.0` confidence from the external app.

### Nano IMU JSON Forwarded Over USB Serial

If the Linux/Python app forwards wearable data instead of wiring Nano to `Serial1`, send:

```json
{"type":"nano_imu","relative_pitch":62.0,"gyro_mag":7.0,"stable":true,"arm_raised":true,"state":"NANO_HOLD_STABLE"}
```

### Session Command JSON

```json
{"type":"session_command","command":"START"}
```

`command` can be `START`, `PAUSE`, `NEXT`, `RESET`, `CALIBRATE_NANO`, or `STATUS`.

### Config JSON

```json
{"type":"config","mode":"after","body_focus":"full","duration_min":5}
```

Config fields are stored for app-level behavior and future routines. The MVP firmware uses `SET_TARGET_HOLD` for the active hold duration.

## UNO Q Output

Direction: UNO Q sketch to Linux/Python dashboard/debug tools.

Rate: 10 Hz.

Format:

```json
{
  "type": "stretch_state",
  "t": 12345,
  "state": "HOLD_STEADY",
  "instruction": "Hold the stretch",
  "score": 72,
  "distance_cm": 132.0,
  "nano_angle": 61.2,
  "gyro_mag": 8.1,
  "camera_arm_raised": true,
  "nano_arm_raised": true,
  "hold_sec": 4.3,
  "source_ok": true,
  "nano_ok": true,
  "camera_ok": true,
  "distance_ok": true,
  "session_started": true
}
```

Final states:

- `NO_USER`
- `STEP_BACK`
- `STEP_CLOSER`
- `READY`
- `RAISE_ARM`
- `HOLD_STEADY`
- `UNSTABLE`
- `GOOD`
- `DONE`
- `SENSOR_ERROR`

Instructions:

- `NO_USER`: `Step into view`
- `STEP_BACK`: `Step back`
- `STEP_CLOSER`: `Step closer`
- `READY`: `Get ready` or `Move into frame`
- `RAISE_ARM`: `Raise your arm`
- `HOLD_STEADY`: `Hold the stretch`
- `UNSTABLE`: `Keep steady`
- `GOOD`: `Good hold`
- `DONE`: `Stretch complete`
- `SENSOR_ERROR`: `Sensor check needed`

## Example Session

Serial Monitor input:

```text
START
{"type":"camera_pose","user_visible":true,"full_body_visible":true,"arm_raised":true,"torso_centered":true,"confidence":0.9}
{"type":"nano_imu","relative_pitch":62.0,"gyro_mag":7.0,"stable":true,"arm_raised":true,"state":"NANO_HOLD_STABLE"}
```

Expected output sequence:

```json
{"type":"stretch_state","state":"READY",...}
{"type":"stretch_state","state":"HOLD_STEADY",...}
{"type":"stretch_state","state":"GOOD",...}
{"type":"stretch_state","state":"DONE",...}
```

## Error Handling

- Malformed JSON is ignored.
- Unknown JSON fields are ignored.
- Unknown commands produce `# WARN unknown command`.
- Nano data older than 1000 ms makes `nano_ok:false`.
- Camera data older than 1000 ms makes `camera_ok:false`.
- Distance data older than 1000 ms makes `distance_ok:false`.
- The dashboard should use `source_ok`, `nano_ok`, `camera_ok`, and `distance_ok` for debug indicators.

## Score

Score is only emitted during a started, unpaused session. It is `null` during setup. The placeholder scoring model is:

- 40 points if user is visible and distance is okay.
- 30 points if the Nano says the arm is raised.
- 20 points if the camera says the arm is raised.
- 10 points if the Nano says the hold is stable.

Clamp range: `0` to `100`. This is prototype wellness feedback, not a medical assessment.
