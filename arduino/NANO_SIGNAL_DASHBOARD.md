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

The dashboard sends `OUTPUT_JSON` after connecting, so the Nano stays in JSON mode.

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
pitch:61.8	roll:4.0	relative_pitch:57.9	arm_threshold:55.0	gyro_mag:8.3	gyro_avg:7.8	stability_threshold:20.0	stability_score:61	arm_raised:100	stable:100	state_band:40
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
- If `stable` flickers during a good hold, raise `SET_STABILITY_THRESHOLD` slightly.
- If `arm_raised` never turns true, lower `SET_ARM_THRESHOLD` or check the baseline calibration pose.
