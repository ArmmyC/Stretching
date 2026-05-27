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

// Optional onboard Sense sensors. Missing libraries are detected at compile time
// and reported in startup logs instead of breaking the core stretch detector.
#define USE_MAGNETOMETER 1
#define USE_APDS9960_SENSOR 1
#define USE_BAROMETER_SENSOR 1
#define USE_ENVIRONMENT_SENSOR 1
#define USE_PDM_MICROPHONE 1

// Original Nano 33 BLE Sense uses HTS221. Rev2-style boards use HS300x.
#define ENV_BACKEND_HTS221
// #define ENV_BACKEND_HS300X

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

#if defined(ENV_BACKEND_HTS221) && defined(ENV_BACKEND_HS300X)
#error "Select only one environment sensor backend."
#endif

#if defined(__has_include)
  #if __has_include(<Arduino_APDS9960.h>)
    #include <Arduino_APDS9960.h>
    #define HAS_APDS9960_LIBRARY 1
  #else
    #define HAS_APDS9960_LIBRARY 0
  #endif

  #if __has_include(<Arduino_LPS22HB.h>)
    #include <Arduino_LPS22HB.h>
    #define HAS_LPS22HB_LIBRARY 1
  #else
    #define HAS_LPS22HB_LIBRARY 0
  #endif

  #if __has_include(<Arduino_HTS221.h>)
    #include <Arduino_HTS221.h>
    #define HAS_HTS221_LIBRARY 1
  #else
    #define HAS_HTS221_LIBRARY 0
  #endif

  #if __has_include(<Arduino_HS300x.h>)
    #include <Arduino_HS300x.h>
    #define HAS_HS300X_LIBRARY 1
  #else
    #define HAS_HS300X_LIBRARY 0
  #endif

  #if __has_include(<PDM.h>)
    #include <PDM.h>
    #define HAS_PDM_LIBRARY 1
  #else
    #define HAS_PDM_LIBRARY 0
  #endif
#else
  #define HAS_APDS9960_LIBRARY 0
  #define HAS_LPS22HB_LIBRARY 0
  #define HAS_HTS221_LIBRARY 0
  #define HAS_HS300X_LIBRARY 0
  #define HAS_PDM_LIBRARY 0
#endif

const unsigned long SERIAL_BAUD = 115200;
const unsigned long OUTPUT_INTERVAL_MS = 50;       // 20 Hz JSON stream
const unsigned long FULL_OUTPUT_INTERVAL_MS = 100; // 10 Hz rich dashboard stream
const unsigned long CALIBRATION_DURATION_MS = 2000;
const unsigned long IMU_STALE_MS = 1000;
const unsigned long HOLD_STABLE_DWELL_MS = 300;
const bool DEFAULT_PLOTTER_MODE = false;           // true starts in Arduino Serial Plotter-friendly mode
const unsigned long APDS_READ_INTERVAL_MS = 100;
const unsigned long BARO_READ_INTERVAL_MS = 500;
const unsigned long ENV_READ_INTERVAL_MS = 1000;
const unsigned long MAG_READ_INTERVAL_MS = 50;
const int PDM_CHANNELS = 1;
const int PDM_SAMPLE_RATE = 16000;
const int PDM_GAIN = 20;

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
  OUTPUT_FULL_JSON,
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
float mx = 0.0;
float my = 0.0;
float mz = 0.0;
float magMagnitudeUt = 0.0;
float magHeadingDeg = 0.0;
float pressureKpa = 0.0;
float pressureHpa = 0.0;
float temperatureC = 0.0;
float humidityPercent = 0.0;
float micRms = 0.0;
float micPeak = 0.0;
float micDbfs = -90.0;
float micLevelPercent = 0.0;

int proximity = -1;
int red = 0;
int green = 0;
int blue = 0;
int ambient = 0;
int gestureCode = -1;

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
bool haveMag = false;
bool apdsHealthy = false;
bool baroHealthy = false;
bool envHealthy = false;
bool micHealthy = false;

unsigned long calibrationStartedMs = 0;
unsigned long lastImuReadMs = 0;
unsigned long lastOutputMs = 0;
unsigned long stableCandidateSinceMs = 0;
unsigned long lastMagReadMs = 0;
unsigned long lastApdsReadMs = 0;
unsigned long lastBaroReadMs = 0;
unsigned long lastEnvReadMs = 0;

NanoState nanoState = NANO_CALIBRATING;
OutputMode outputMode = DEFAULT_PLOTTER_MODE ? OUTPUT_PLOTTER : OUTPUT_JSON;

char commandBuffer[96];
size_t commandLength = 0;
char gestureName[12] = "none";

#if HAS_PDM_LIBRARY && USE_PDM_MICROPHONE
short pdmSampleBuffer[256];
volatile int pdmSamplesRead = 0;
#endif

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

const char *gestureCodeName(int gesture) {
#if HAS_APDS9960_LIBRARY && USE_APDS9960_SENSOR
  switch (gesture) {
    #ifdef GESTURE_UP
    case GESTURE_UP: return "up";
    #endif
    #ifdef GESTURE_DOWN
    case GESTURE_DOWN: return "down";
    #endif
    #ifdef GESTURE_LEFT
    case GESTURE_LEFT: return "left";
    #endif
    #ifdef GESTURE_RIGHT
    case GESTURE_RIGHT: return "right";
    #endif
    default: return "none";
  }
#else
  (void)gesture;
  return "none";
#endif
}

float clampFloat(float value, float low, float high) {
  if (value < low) return low;
  if (value > high) return high;
  return value;
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

#if HAS_PDM_LIBRARY && USE_PDM_MICROPHONE
void onPDMdata() {
  int bytesAvailable = PDM.available();
  if (bytesAvailable > (int)sizeof(pdmSampleBuffer)) {
    bytesAvailable = sizeof(pdmSampleBuffer);
  }
  PDM.read((void *)pdmSampleBuffer, bytesAvailable);
  pdmSamplesRead = bytesAvailable / (int)sizeof(short);
}
#endif

void initOptionalSensors() {
#if USE_APDS9960_SENSOR
  #if HAS_APDS9960_LIBRARY
    apdsHealthy = APDS.begin();
    Serial.println(apdsHealthy ? "# APDS9960 proximity/light/color/gesture ready" : "# WARN APDS9960 begin failed");
  #else
    Serial.println("# WARN Arduino_APDS9960 library not installed; APDS9960 signals disabled");
  #endif
#endif

#if USE_BAROMETER_SENSOR
  #if HAS_LPS22HB_LIBRARY
    baroHealthy = BARO.begin();
    Serial.println(baroHealthy ? "# LPS22HB barometer ready" : "# WARN LPS22HB begin failed");
  #else
    Serial.println("# WARN Arduino_LPS22HB library not installed; pressure signals disabled");
  #endif
#endif

#if USE_ENVIRONMENT_SENSOR
  #if defined(ENV_BACKEND_HTS221)
    #if HAS_HTS221_LIBRARY
      envHealthy = HTS.begin();
      Serial.println(envHealthy ? "# HTS221 temperature/humidity ready" : "# WARN HTS221 begin failed");
    #else
      Serial.println("# WARN Arduino_HTS221 library not installed; temperature/humidity disabled");
    #endif
  #elif defined(ENV_BACKEND_HS300X)
    #if HAS_HS300X_LIBRARY
      envHealthy = HS300x.begin();
      Serial.println(envHealthy ? "# HS300x temperature/humidity ready" : "# WARN HS300x begin failed");
    #else
      Serial.println("# WARN Arduino_HS300x library not installed; temperature/humidity disabled");
    #endif
  #else
    Serial.println("# WARN no environment backend selected; temperature/humidity disabled");
  #endif
#endif

#if USE_PDM_MICROPHONE
  #if HAS_PDM_LIBRARY
    PDM.onReceive(onPDMdata);
    PDM.setGain(PDM_GAIN);
    micHealthy = PDM.begin(PDM_CHANNELS, PDM_SAMPLE_RATE);
    Serial.println(micHealthy ? "# PDM microphone ready" : "# WARN PDM microphone begin failed");
  #else
    Serial.println("# WARN PDM library not installed; microphone signals disabled");
  #endif
#endif
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
  unsigned long now = millis();

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

#if USE_MAGNETOMETER
  #if defined(IMU_BACKEND_LSM9DS1)
    if (IMU.magneticFieldAvailable()) {
      IMU.readMagneticField(mx, my, mz);
      haveMag = true;
      lastMagReadMs = now;
    }
  #elif defined(IMU_BACKEND_BMI270)
    if (now - lastMagReadMs >= MAG_READ_INTERVAL_MS) {
      IMU.readMagneticField(mx, my, mz);
      haveMag = true;
      lastMagReadMs = now;
    }
  #endif

  if (haveMag) {
    magMagnitudeUt = sqrt((mx * mx) + (my * my) + (mz * mz));
    magHeadingDeg = atan2(my, mx) * 180.0 / PI;
    if (magHeadingDeg < 0.0) magHeadingDeg += 360.0;
  }
#endif

  if (!readSomething || !haveAccel || !haveGyro) {
    finishCalibrationIfReady();
    updateNanoState();
    return;
  }

  lastImuReadMs = now;

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

void updateApds9960() {
#if HAS_APDS9960_LIBRARY && USE_APDS9960_SENSOR
  if (!apdsHealthy) return;
  unsigned long now = millis();
  if (now - lastApdsReadMs < APDS_READ_INTERVAL_MS) return;
  lastApdsReadMs = now;

  if (APDS.proximityAvailable()) {
    proximity = APDS.readProximity();
  }

  if (APDS.colorAvailable()) {
    APDS.readColor(red, green, blue, ambient);
  }

  if (APDS.gestureAvailable()) {
    gestureCode = APDS.readGesture();
    strncpy(gestureName, gestureCodeName(gestureCode), sizeof(gestureName) - 1);
    gestureName[sizeof(gestureName) - 1] = '\0';
  }
#endif
}

void updateBarometer() {
#if HAS_LPS22HB_LIBRARY && USE_BAROMETER_SENSOR
  if (!baroHealthy) return;
  unsigned long now = millis();
  if (now - lastBaroReadMs < BARO_READ_INTERVAL_MS) return;
  lastBaroReadMs = now;

  // Arduino_LPS22HB examples report readPressure() in kPa.
  pressureKpa = BARO.readPressure();
  pressureHpa = pressureKpa * 10.0;
#endif
}

void updateEnvironment() {
#if USE_ENVIRONMENT_SENSOR
  if (!envHealthy) return;
  unsigned long now = millis();
  if (now - lastEnvReadMs < ENV_READ_INTERVAL_MS) return;
  lastEnvReadMs = now;

  #if defined(ENV_BACKEND_HTS221) && HAS_HTS221_LIBRARY
    temperatureC = HTS.readTemperature();
    humidityPercent = HTS.readHumidity();
  #elif defined(ENV_BACKEND_HS300X) && HAS_HS300X_LIBRARY
    temperatureC = HS300x.readTemperature();
    humidityPercent = HS300x.readHumidity();
  #endif
#endif
}

void updateMicrophone() {
#if HAS_PDM_LIBRARY && USE_PDM_MICROPHONE
  if (!micHealthy) return;

  short localSamples[256];
  int count = 0;

  noInterrupts();
  count = pdmSamplesRead;
  if (count > 0) {
    if (count > 256) count = 256;
    memcpy(localSamples, pdmSampleBuffer, count * sizeof(short));
    pdmSamplesRead = 0;
  }
  interrupts();

  if (count <= 0) return;

  double sumSquares = 0.0;
  long sumAbs = 0;
  int peak = 0;
  for (int i = 0; i < count; i++) {
    int sample = localSamples[i];
    int absSample = abs(sample);
    if (absSample > peak) peak = absSample;
    sumAbs += absSample;
    sumSquares += (double)sample * (double)sample;
  }

  micRms = sqrt(sumSquares / (double)count);
  micPeak = peak;
  micDbfs = 20.0 * log10(max(micRms, 1.0f) / 32768.0);
  micLevelPercent = clampFloat(((float)sumAbs / (float)count) / 32768.0 * 100.0, 0.0, 100.0);
#endif
}

void updateOptionalSensors() {
  updateApds9960();
  updateBarometer();
  updateEnvironment();
  updateMicrophone();
}

void outputStatusJson(bool force) {
  unsigned long now = millis();
  unsigned long interval = (outputMode == OUTPUT_FULL_JSON) ? FULL_OUTPUT_INTERVAL_MS : OUTPUT_INTERVAL_MS;
  if (!force && now - lastOutputMs < interval) {
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
  if (outputMode == OUTPUT_FULL_JSON) {
    Serial.print(",\"mx\":");
    Serial.print(mx, 2);
    Serial.print(",\"my\":");
    Serial.print(my, 2);
    Serial.print(",\"mz\":");
    Serial.print(mz, 2);
    Serial.print(",\"mag_mag\":");
    Serial.print(magMagnitudeUt, 2);
    Serial.print(",\"heading_deg\":");
    Serial.print(magHeadingDeg, 1);
    Serial.print(",\"mag_ok\":");
    Serial.print(haveMag ? "true" : "false");
    Serial.print(",\"proximity\":");
    Serial.print(proximity);
    Serial.print(",\"red\":");
    Serial.print(red);
    Serial.print(",\"green\":");
    Serial.print(green);
    Serial.print(",\"blue\":");
    Serial.print(blue);
    Serial.print(",\"ambient\":");
    Serial.print(ambient);
    Serial.print(",\"gesture_code\":");
    Serial.print(gestureCode);
    Serial.print(",\"gesture\":\"");
    Serial.print(gestureName);
    Serial.print("\",\"apds_ok\":");
    Serial.print(apdsHealthy ? "true" : "false");
    Serial.print(",\"pressure_kpa\":");
    Serial.print(pressureKpa, 2);
    Serial.print(",\"pressure_hpa\":");
    Serial.print(pressureHpa, 1);
    Serial.print(",\"baro_ok\":");
    Serial.print(baroHealthy ? "true" : "false");
    Serial.print(",\"temperature_c\":");
    Serial.print(temperatureC, 1);
    Serial.print(",\"humidity\":");
    Serial.print(humidityPercent, 1);
    Serial.print(",\"env_ok\":");
    Serial.print(envHealthy ? "true" : "false");
    Serial.print(",\"mic_rms\":");
    Serial.print(micRms, 1);
    Serial.print(",\"mic_peak\":");
    Serial.print(micPeak, 0);
    Serial.print(",\"mic_dbfs\":");
    Serial.print(micDbfs, 1);
    Serial.print(",\"mic_level\":");
    Serial.print(micLevelPercent, 1);
    Serial.print(",\"mic_ok\":");
    Serial.print(micHealthy ? "true" : "false");
  }
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
  if (!force && now - lastOutputMs < FULL_OUTPUT_INTERVAL_MS) {
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
  Serial.print("\tmx:");
  Serial.print(mx, 1);
  Serial.print("\tmy:");
  Serial.print(my, 1);
  Serial.print("\tmz:");
  Serial.print(mz, 1);
  Serial.print("\tmag_mag:");
  Serial.print(magMagnitudeUt, 1);
  Serial.print("\theading_deg:");
  Serial.print(magHeadingDeg, 1);
  Serial.print("\tproximity:");
  Serial.print(proximity);
  Serial.print("\tambient:");
  Serial.print(ambient);
  Serial.print("\tred:");
  Serial.print(red);
  Serial.print("\tgreen:");
  Serial.print(green);
  Serial.print("\tblue:");
  Serial.print(blue);
  Serial.print("\tpressure_hpa:");
  Serial.print(pressureHpa, 1);
  Serial.print("\ttemperature_c:");
  Serial.print(temperatureC, 1);
  Serial.print("\thumidity:");
  Serial.print(humidityPercent, 1);
  Serial.print("\tmic_level:");
  Serial.print(micLevelPercent, 1);
  Serial.print("\tmic_rms:");
  Serial.print(micRms, 1);
  Serial.print("\tmic_dbfs:");
  Serial.print(micDbfs, 1);
  Serial.print("\tgesture_code:");
  Serial.print(gestureCode);
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
  } else if (strcmp(line, "OUTPUT_FULL_JSON") == 0 || strcmp(line, "SENSORS_ON") == 0) {
    outputMode = OUTPUT_FULL_JSON;
    Serial.println("# OK OUTPUT_FULL_JSON");
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
  Serial.println("# Output: compact newline-delimited JSON at 20 Hz after startup.");
  Serial.println("# Dashboard command: OUTPUT_FULL_JSON at 10 Hz. UNO/default command: OUTPUT_JSON.");
  Serial.println("# Plotter mode commands: PLOTTER_ON, PLOTTER_OFF, OUTPUT_JSON, OUTPUT_PLOTTER.");

  if (!IMU.begin()) {
    imuHealthy = false;
    nanoState = NANO_ERROR;
    Serial.println("# ERROR: IMU.begin() failed. Check board type and IMU_BACKEND selection.");
  } else {
    imuHealthy = true;
    beginCalibration();
  }

  initOptionalSensors();
}

void loop() {
  parseSerialCommands();
  updateImu();
  updateOptionalSensors();
  outputStatus(false);
}
