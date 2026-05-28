# Nano Signal Dashboard

The Nano firmware shows these signal lines for pattern finding:

| Signal | Meaning | Use while testing |
| --- | --- | --- |
| `ax`, `ay`, `az` | Raw accelerometer axes in g | Check strap orientation and sudden motion |
| `gx`, `gy`, `gz` | Raw gyro axes in deg/s | See which rotation axis spikes during wobble |
| `pitch` | Smoothed accelerometer pitch estimate | General forearm angle trend |
| `roll` | Accelerometer roll estimate | Strap twist and side rotation |
| `relative_pitch` | `pitch - baselinePitch` | Main arm-raised signal |
| `gyro_mag` | Raw rotation magnitude | Instant shakiness |
| `gyro_avg` | Smoothed rotation magnitude | Main stability signal |
| `stability_score` | Prototype 0-100 stillness score | Quick visual quality check |
| `mx`, `my`, `mz` | Magnetometer axes in microtesla | Find magnetic disturbances, board yaw patterns |
| `mag_mag` | Magnetic field magnitude | Watch for nearby metal, magnets, or wiring |
| `heading_deg` | Simple X/Y magnetic heading | Rough compass-like trend, not tilt-compensated |
| `proximity` | APDS9960 proximity value | Hand/object nearness to the sensor |
| `ambient` | APDS9960 clear/ambient light | Room lighting and shadows |
| `red`, `green`, `blue` | APDS9960 color channels | Reflected color/light changes |
| `gesture_code`, `gesture` | APDS9960 gesture result | Hand swipe direction near the board |
| `pressure_kpa`, `pressure_hpa` | LPS22HB barometric pressure | Ambient pressure trend |
| `mic_rms`, `mic_peak` | PDM microphone loudness values | Noise/activity pattern only, not audio recording |
| `mic_avg_abs` | Mean absolute microphone sample value | Quick check that PDM callbacks are delivering non-zero samples |
| `mic_dbfs`, `mic_level` | Derived microphone level | Easier sound activity lines for charts |
| `mic_samples` | Number of samples in latest PDM callback | Should usually be above 0 when the mic is running |
| `mag_ok`, `apds_ok`, `baro_ok`, `mic_ok` | Optional sensor health flags | Check whether the library initialized on this board |
| `arm_threshold` | Current arm-raised threshold | Compare against `relative_pitch` |
| `stability_threshold` | Current stability threshold | Compare against `gyro_avg` |
| `arm_raised` | Boolean classification | Should switch when arm crosses threshold |
| `stable` | Boolean classification | Should stay true during a steady hold |
| `state_code` | Numeric state for plotting | `-1` error, `0` low, `1` raised, `2` hold stable, `3` unstable, `4` calibrating |
| `state` | Text state | Human-readable Nano classification |

## Browser Dashboard

Open this file in Chrome or Edge:

```text
arduino/tools/nano_signal_dashboard.html
```

Then:

1. Upload `NanoStretchNode.ino`.
2. Close Arduino Serial Monitor so the browser can claim the serial port.
3. Open the dashboard.
4. Click `Connect Nano`.
5. Choose the Nano serial port.
6. Move the forearm through the stretch.
7. Toggle signal lines on/off and export CSV if needed.

The dashboard now sends `OUTPUT_FULL_JSON` after connecting. For Nano 33 BLE Sense Lite this includes IMU, magnetometer, APDS9960 proximity/light/color/gesture, barometer, and PDM microphone metrics. Temperature and humidity are intentionally hidden because the Lite board does not include that sensor. Use `Compact JSON` in the dashboard or send `OUTPUT_JSON` when returning to the UNO Q fusion pipeline.

## Arduino Serial Plotter Mode

For a very quick plot inside Arduino IDE:

1. Open Serial Monitor at `115200`.
2. Send:

```text
PLOTTER_ON
```

3. Close Serial Monitor.
4. Open Serial Plotter at `115200`.

Plotter mode outputs labelled numeric series:

```text
pitch:61.8	roll:4.0	relative_pitch:57.9	arm_threshold:55.0	gyro_mag:8.3	gyro_avg:7.8	stability_threshold:20.0	stability_score:61	mx:12.4	my:-3.1	mz:40.2	mag_mag:42.2	heading_deg:346.0	proximity:18	ambient:204	red:76	green:89	blue:102	pressure_hpa:1008.4	mic_level:28.0	mic_rms:410.2	mic_avg_abs:260.0	mic_dbfs:-38.0	mic_samples:256	gesture_code:-1	arm_raised:100	stable:100	state_band:40
```

To return to normal dashboard/UNO-compatible JSON:

```text
PLOTTER_OFF
```

or:

```text
OUTPUT_JSON
```

## Pattern Tips

- During a clean overhead raise, `relative_pitch` should move past `arm_threshold` and stay there.
- During a steady hold, `gyro_avg` should stay below `stability_threshold`.
- If `relative_pitch` looks inverted, keep the code the same and swap the Nano strap orientation or recalibrate in the chosen orientation.
- If `gyro_mag` spikes but `gyro_avg` stays low, that is a short movement, not sustained instability.
- If `mag_mag` jumps suddenly, something magnetic or metallic is close to the board.
- If `proximity` rises during a stretch, your hand, strap, or clothing may be covering the APDS9960 window.
- If `mic_samples` stays at `0`, the PDM callback is not firing; check the board profile and `PDM.h` library.
- If `mic_samples` is non-zero but `mic_level` is flat, clap near the board and watch `mic_rms`, `mic_avg_abs`, and `mic_dbfs`.
- If `mic_level` follows room noise, the microphone is working; use it as context, not as stretch quality.
- If `stable` flickers during a good hold, raise `SET_STABILITY_THRESHOLD` slightly.
- If `arm_raised` never turns true, lower `SET_ARM_THRESHOLD` or check the baseline calibration pose.
