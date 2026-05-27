/*
  StretchSense - NanoStretchNode

  Wear the Arduino Nano 33 BLE Sense Lite on the forearm with the USB connector
  pointing consistently toward the wrist or elbow. Keep the strap snug so the
  board follows the forearm instead of sliding around during the hold.

  IMU backend selection:
  - Use IMU_BACKEND_LSM9DS1 for original Nano 33 BLE Sense-style boards.
  - Use IMU_BACKEND_BMI270 for Rev2-style boards.
  - Do not enable both at once.
*/

#define IMU_BACKEND_LSM9DS1
// #define IMU_BACKEND_BMI270

#include <Arduino.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

#if defined(IMU_BACKEND_LSM9DS1) && defined(IMU_BACKEND_BMI270)
#error "Select only one IMU backend."
#endif

#if defined(IMU_BACKEND_LSM9DS1)
#include <Arduino_LSM9DS1.h>
#elif defined(IMU_BACKEND_BMI270)
#include <Arduino_BMI270_BMM150.h>
#else
#error "Select an IMU backend at the top of this file."
#endif

const unsigned long SERIAL_BAUD = 115200;
const unsigned long OUTPUT_INTERVAL_MS = 50;       // 20 Hz JSON stream
const unsigned long CALIBRATION_DURATION_MS = 2000;
const unsigned long IMU_STALE_MS = 1000;
const unsigned long HOLD_STABLE_DWELL_MS = 300;
const bool DEFAULT_PLOTTER_MODE = false;           // true starts in Arduino Serial Plotter-friendly mode

float armRaisedThresholdDeg = 55.0;
float stabilityThresholdDps = 20.0;
const float EMA_ALPHA = 0.18;

enum NanoState {
  NANO_ARM_LOW,
  NANO_ARM_RAISED,
  NANO_HOLD_STABLE,
  NANO_UNSTABLE,
  NANO_CALIBRATING,
  NANO_ERROR
};

enum OutputMode {
  OUTPUT_JSON,
  OUTPUT_PLOTTER
};

float ax = 0.0;
float ay = 0.0;
float az = 0.0;
float gx = 0.0;
float gy = 0.0;
float gz = 0.0;

float pitchDeg = 0.0;
float rollDeg = 0.0;
float smoothedPitchDeg = 0.0;
float gyroMagDps = 0.0;
float smoothedGyroMagDps = 0.0;
float relativePitchDeg = 0.0;
float stabilityScore = 0.0;

float baselinePitchDeg = 0.0;
float calibrationPitchSum = 0.0;
unsigned int calibrationSamples = 0;

bool imuHealthy = false;
bool haveAccel = false;
bool haveGyro = false;
bool emaReady = false;
bool calibrating = false;
bool armRaised = false;
bool stableHold = false;

unsigned long calibrationStartedMs = 0;
unsigned long lastImuReadMs = 0;
unsigned long lastOutputMs = 0;
unsigned long stableCandidateSinceMs = 0;

NanoState nanoState = NANO_CALIBRATING;
OutputMode outputMode = DEFAULT_PLOTTER_MODE ? OUTPUT_PLOTTER : OUTPUT_JSON;

char commandBuffer[96];
size_t commandLength = 0;

const char *nanoStateName(NanoState state) {
  switch (state) {
    case NANO_ARM_LOW: return "NANO_ARM_LOW";
    case NANO_ARM_RAISED: return "NANO_ARM_RAISED";
    case NANO_HOLD_STABLE: return "NANO_HOLD_STABLE";
    case NANO_UNSTABLE: return "NANO_UNSTABLE";
    case NANO_CALIBRATING: return "NANO_CALIBRATING";
    case NANO_ERROR: return "NANO_ERROR";
    default: return "NANO_ERROR";
  }
}

int nanoStateCode(NanoState state) {
  switch (state) {
    case NANO_ARM_LOW: return 0;
    case NANO_ARM_RAISED: return 1;
    case NANO_HOLD_STABLE: return 2;
    case NANO_UNSTABLE: return 3;
    case NANO_CALIBRATING: return 4;
    case NANO_ERROR: return -1;
    default: return -1;
  }
}

bool startsWith(const char *text, const char *prefix) {
  return strncmp(text, prefix, strlen(prefix)) == 0;
}

void trimLine(char *line) {
  size_t len = strlen(line);
  while (len > 0 && (line[len - 1] == '\r' || line[len - 1] == '\n' || line[len - 1] == ' ' || line[len - 1] == '\t')) {
    line[--len] = '\0';
  }

  char *start = line;
  while (*start == ' ' || *start == '\t') {
    start++;
  }
  if (start != line) {
    memmove(line, start, strlen(start) + 1);
  }
}

void beginCalibration() {
  calibrating = true;
  calibrationStartedMs = millis();
  calibrationPitchSum = 0.0;
  calibrationSamples = 0;
  nanoState = NANO_CALIBRATING;
  stableCandidateSinceMs = 0;
  Serial.println("# Nano calibration started. Keep the forearm relaxed in the baseline position.");
}

void finishCalibrationIfReady() {
  if (!calibrating) {
    return;
  }

  unsigned long now = millis();
  if (now - calibrationStartedMs < CALIBRATION_DURATION_MS) {
    return;
  }

  if (calibrationSamples == 0) {
    imuHealthy = false;
    nanoState = NANO_ERROR;
    Serial.println("# ERROR: IMU produced no calibration samples.");
    return;
  }

  baselinePitchDeg = calibrationPitchSum / (float)calibrationSamples;
  calibrating = false;
  Serial.print("# Nano calibration complete. baseline_pitch=");
  Serial.println(baselinePitchDeg, 2);
}

void updateStabilityScore() {
  float ratio = smoothedGyroMagDps / stabilityThresholdDps;
  stabilityScore = 100.0 - (ratio * 100.0);
  if (stabilityScore < 0.0) stabilityScore = 0.0;
  if (stabilityScore > 100.0) stabilityScore = 100.0;
}

void updateNanoState() {
  unsigned long now = millis();

  if (!imuHealthy || (lastImuReadMs > 0 && now - lastImuReadMs > IMU_STALE_MS)) {
    nanoState = NANO_ERROR;
    return;
  }

  if (calibrating) {
    nanoState = NANO_CALIBRATING;
    return;
  }

  armRaised = fabs(relativePitchDeg) >= armRaisedThresholdDeg;
  stableHold = smoothedGyroMagDps < stabilityThresholdDps;

  if (!armRaised) {
    nanoState = NANO_ARM_LOW;
    stableCandidateSinceMs = 0;
    return;
  }

  if (!stableHold) {
    nanoState = NANO_UNSTABLE;
    stableCandidateSinceMs = 0;
    return;
  }

  if (stableCandidateSinceMs == 0) {
    stableCandidateSinceMs = now;
  }

  nanoState = (now - stableCandidateSinceMs >= HOLD_STABLE_DWELL_MS) ? NANO_HOLD_STABLE : NANO_ARM_RAISED;
}

void updateImu() {
  if (!imuHealthy) {
    return;
  }

  bool readSomething = false;

  if (IMU.accelerationAvailable()) {
    IMU.readAcceleration(ax, ay, az);
    haveAccel = true;
    readSomething = true;
  }

  if (IMU.gyroscopeAvailable()) {
    IMU.readGyroscope(gx, gy, gz);
    haveGyro = true;
    readSomething = true;
  }

  if (!readSomething || !haveAccel || !haveGyro) {
    finishCalibrationIfReady();
    updateNanoState();
    return;
  }

  lastImuReadMs = millis();

  pitchDeg = atan2(ax, sqrt((ay * ay) + (az * az))) * 180.0 / PI;
  rollDeg = atan2(ay, sqrt((ax * ax) + (az * az))) * 180.0 / PI;
  gyroMagDps = sqrt((gx * gx) + (gy * gy) + (gz * gz));

  if (!emaReady) {
    smoothedPitchDeg = pitchDeg;
    smoothedGyroMagDps = gyroMagDps;
    emaReady = true;
  } else {
    smoothedPitchDeg = (EMA_ALPHA * pitchDeg) + ((1.0 - EMA_ALPHA) * smoothedPitchDeg);
    smoothedGyroMagDps = (EMA_ALPHA * gyroMagDps) + ((1.0 - EMA_ALPHA) * smoothedGyroMagDps);
  }

  if (calibrating) {
    calibrationPitchSum += smoothedPitchDeg;
    calibrationSamples++;
  }

  relativePitchDeg = smoothedPitchDeg - baselinePitchDeg;
  updateStabilityScore();
  finishCalibrationIfReady();
  updateNanoState();
}

void outputStatusJson(bool force) {
  unsigned long now = millis();
  if (!force && now - lastOutputMs < OUTPUT_INTERVAL_MS) {
    return;
  }
  lastOutputMs = now;

  Serial.print("{\"type\":\"nano_imu\",\"t\":");
  Serial.print(now);
  Serial.print(",\"ax\":");
  Serial.print(ax, 3);
  Serial.print(",\"ay\":");
  Serial.print(ay, 3);
  Serial.print(",\"az\":");
  Serial.print(az, 3);
  Serial.print(",\"gx\":");
  Serial.print(gx, 2);
  Serial.print(",\"gy\":");
  Serial.print(gy, 2);
  Serial.print(",\"gz\":");
  Serial.print(gz, 2);
  Serial.print(",\"pitch\":");
  Serial.print(smoothedPitchDeg, 1);
  Serial.print(",\"roll\":");
  Serial.print(rollDeg, 1);
  Serial.print(",\"relative_pitch\":");
  Serial.print(relativePitchDeg, 1);
  Serial.print(",\"gyro_mag\":");
  Serial.print(gyroMagDps, 1);
  Serial.print(",\"gyro_avg\":");
  Serial.print(smoothedGyroMagDps, 1);
  Serial.print(",\"stability_score\":");
  Serial.print(stabilityScore, 0);
  Serial.print(",\"arm_threshold\":");
  Serial.print(armRaisedThresholdDeg, 1);
  Serial.print(",\"stability_threshold\":");
  Serial.print(stabilityThresholdDps, 1);
  Serial.print(",\"stable\":");
  Serial.print(stableHold ? "true" : "false");
  Serial.print(",\"arm_raised\":");
  Serial.print(armRaised ? "true" : "false");
  Serial.print(",\"state_code\":");
  Serial.print(nanoStateCode(nanoState));
  Serial.print(",\"state\":\"");
  Serial.print(nanoStateName(nanoState));
  Serial.println("\"}");
}

void outputStatusPlotter(bool force) {
  unsigned long now = millis();
  if (!force && now - lastOutputMs < OUTPUT_INTERVAL_MS) {
    return;
  }
  lastOutputMs = now;

  Serial.print("pitch:");
  Serial.print(smoothedPitchDeg, 1);
  Serial.print("\troll:");
  Serial.print(rollDeg, 1);
  Serial.print("\trelative_pitch:");
  Serial.print(relativePitchDeg, 1);
  Serial.print("\tarm_threshold:");
  Serial.print(armRaisedThresholdDeg, 1);
  Serial.print("\tgyro_mag:");
  Serial.print(gyroMagDps, 1);
  Serial.print("\tgyro_avg:");
  Serial.print(smoothedGyroMagDps, 1);
  Serial.print("\tstability_threshold:");
  Serial.print(stabilityThresholdDps, 1);
  Serial.print("\tstability_score:");
  Serial.print(stabilityScore, 0);
  Serial.print("\tarm_raised:");
  Serial.print(armRaised ? 100 : 0);
  Serial.print("\tstable:");
  Serial.print(stableHold ? 100 : 0);
  Serial.print("\tstate_band:");
  Serial.println(nanoStateCode(nanoState) * 20);
}

void outputStatus(bool force) {
  if (outputMode == OUTPUT_PLOTTER) {
    outputStatusPlotter(force);
  } else {
    outputStatusJson(force);
  }
}

void processCommand(char *line) {
  trimLine(line);
  if (line[0] == '\0') {
    return;
  }

  if (strcmp(line, "CALIBRATE") == 0) {
    beginCalibration();
    Serial.println("# OK CALIBRATE");
  } else if (strcmp(line, "STATUS") == 0) {
    outputStatus(true);
  } else if (strcmp(line, "PLOTTER_ON") == 0 || strcmp(line, "OUTPUT_PLOTTER") == 0) {
    outputMode = OUTPUT_PLOTTER;
    Serial.println("# OK PLOTTER_ON");
  } else if (strcmp(line, "PLOTTER_OFF") == 0 || strcmp(line, "OUTPUT_JSON") == 0) {
    outputMode = OUTPUT_JSON;
    Serial.println("# OK OUTPUT_JSON");
  } else if (startsWith(line, "SET_ARM_THRESHOLD ")) {
    float value = atof(line + strlen("SET_ARM_THRESHOLD "));
    if (value > 5.0 && value < 170.0) {
      armRaisedThresholdDeg = value;
      Serial.println("# OK SET_ARM_THRESHOLD");
    } else {
      Serial.println("# ERROR SET_ARM_THRESHOLD out of range");
    }
  } else if (startsWith(line, "SET_STABILITY_THRESHOLD ")) {
    float value = atof(line + strlen("SET_STABILITY_THRESHOLD "));
    if (value > 1.0 && value < 300.0) {
      stabilityThresholdDps = value;
      Serial.println("# OK SET_STABILITY_THRESHOLD");
    } else {
      Serial.println("# ERROR SET_STABILITY_THRESHOLD out of range");
    }
  } else {
    Serial.println("# WARN unknown command");
  }
}

void parseSerialCommands() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (commandLength > 0) {
        commandBuffer[commandLength] = '\0';
        processCommand(commandBuffer);
        commandLength = 0;
      }
    } else if (commandLength < sizeof(commandBuffer) - 1) {
      commandBuffer[commandLength++] = c;
    } else {
      commandLength = 0;
      Serial.println("# WARN command too long");
    }
  }
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  unsigned long waitStart = millis();
  while (!Serial && millis() - waitStart < 1500) {
    // Keep boot bounded; the wearable should also run when not attached to Serial Monitor.
  }

  Serial.println("# StretchSense NanoStretchNode boot");
  Serial.println("# Output: newline-delimited JSON at 20 Hz after startup.");
  Serial.println("# Plotter mode commands: PLOTTER_ON, PLOTTER_OFF, OUTPUT_JSON, OUTPUT_PLOTTER.");

  if (!IMU.begin()) {
    imuHealthy = false;
    nanoState = NANO_ERROR;
    Serial.println("# ERROR: IMU.begin() failed. Check board type and IMU_BACKEND selection.");
  } else {
    imuHealthy = true;
    beginCalibration();
  }
}

void loop() {
  parseSerialCommands();
  updateImu();
  outputStatus(false);
}
