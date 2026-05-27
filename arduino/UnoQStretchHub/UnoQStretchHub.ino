/*
  StretchSense - UnoQStretchHub

  UNO Q Arduino sketch responsibilities:
  - Read hardware sensors and buttons.
  - Receive Nano wearable IMU JSON.
  - Receive camera pose flags from the UNO Q Linux/Python app.
  - Fuse those inputs into simple wellness guidance states.
  - Drive pixels, buzzer, optional LCD, and dashboard/debug JSON.

  Camera pose estimation is intentionally not implemented here. The Linux/Python
  side sends compact camera_pose JSON messages into this sketch.
*/

#include <Arduino.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

#define USE_NANO_ON_SERIAL1 1
#define USE_NANO_FORWARD_FROM_USB_SERIAL 1

#define USE_MODULINO_DISTANCE 1
#define USE_MODULINO_PIXELS 1
#define USE_MODULINO_BUZZER 1
#define USE_MODULINO_BUTTONS 1
#define USE_LCD 0
#define USE_MOCK_DISTANCE 0

// Keeps serial-only tests useful when the Modulino library is not installed.
#define AUTO_MOCK_DISTANCE_IF_LIBRARY_MISSING 1

// Arduino docs currently show Arduino_Modulino.h. Some tutorials still show Modulino.h.
#if defined(__has_include)
  #if __has_include(<Arduino_Modulino.h>)
    #include <Arduino_Modulino.h>
    #define HAS_MODULINO_LIBRARY 1
  #elif __has_include(<Modulino.h>)
    #include <Modulino.h>
    #define HAS_MODULINO_LIBRARY 1
  #else
    #define HAS_MODULINO_LIBRARY 0
  #endif
#else
  #define HAS_MODULINO_LIBRARY 0
#endif

#if defined(__has_include)
  #if __has_include(<ArduinoJson.h>)
    #include <ArduinoJson.h>
    #define HAS_ARDUINOJSON 1
  #else
    #define HAS_ARDUINOJSON 0
  #endif
#else
  #define HAS_ARDUINOJSON 0
#endif

const unsigned long USB_SERIAL_BAUD = 115200;
const unsigned long NANO_SERIAL_BAUD = 115200;
const unsigned long OUTPUT_INTERVAL_MS = 100;      // 10 Hz stretch_state JSON
const unsigned long DISTANCE_INTERVAL_MS = 100;
const unsigned long NANO_STALE_MS = 1000;
const unsigned long CAMERA_STALE_MS = 1000;
const unsigned long DISTANCE_STALE_MS = 1000;
const unsigned long STATE_DEBOUNCE_MS = 300;
const unsigned long BAD_FORM_RESET_MS = 1200;
const unsigned long GOOD_TO_DONE_MS = 1500;

const float DEFAULT_DISTANCE_MIN_CM = 80.0;
const float DEFAULT_DISTANCE_MAX_CM = 220.0;
const float DISTANCE_NO_USER_MAX_CM = 300.0;
const float DEFAULT_CAMERA_CONFIDENCE_MIN = 0.50;
const float DEFAULT_STABILITY_THRESHOLD_DPS = 20.0;
const float DEFAULT_TARGET_HOLD_SEC = 8.0;

// Set to 1 if your installed distance API returns millimeters instead of centimeters.
#define MODULINO_DISTANCE_RETURNS_MM 0

enum FinalState {
  FINAL_NO_USER,
  FINAL_STEP_BACK,
  FINAL_STEP_CLOSER,
  FINAL_READY,
  FINAL_RAISE_ARM,
  FINAL_HOLD_STEADY,
  FINAL_UNSTABLE,
  FINAL_GOOD,
  FINAL_DONE,
  FINAL_SENSOR_ERROR
};

struct NanoData {
  bool valid;
  bool stable;
  bool armRaised;
  float relativePitch;
  float gyroMag;
  char state[24];
  unsigned long lastMs;
};

struct CameraPose {
  bool valid;
  bool userVisible;
  bool fullBodyVisible;
  bool armRaised;
  bool torsoCentered;
  float confidence;
  unsigned long lastMs;
};

struct DistanceData {
  bool valid;
  bool available;
  float cm;
  unsigned long lastMs;
};

NanoData nanoData = {false, false, false, 0.0, 0.0, "", 0};
CameraPose cameraPose = {false, false, false, false, false, 0.0, 0};
DistanceData distanceData = {false, false, 0.0, 0};

bool nanoOk = false;
bool cameraOk = false;
bool distanceOk = false;
bool sessionStarted = false;
bool sessionPaused = false;
bool stepGood = false;
bool routineDone = false;

float distanceMinCm = DEFAULT_DISTANCE_MIN_CM;
float distanceMaxCm = DEFAULT_DISTANCE_MAX_CM;
float cameraConfidenceMin = DEFAULT_CAMERA_CONFIDENCE_MIN;
float stabilityThresholdDps = DEFAULT_STABILITY_THRESHOLD_DPS;
float targetHoldSec = DEFAULT_TARGET_HOLD_SEC;
float mockDistanceCm = 140.0;
float sessionDurationMin = 5.0;

char modeName[12] = "before";
char bodyFocusName[12] = "upper";

FinalState currentState = FINAL_NO_USER;
FinalState candidateState = FINAL_NO_USER;
unsigned long candidateSinceMs = 0;
unsigned long lastOutputMs = 0;
unsigned long lastDistanceMs = 0;
unsigned long lastHoldTickMs = 0;
unsigned long badFormSinceMs = 0;
unsigned long goodSinceMs = 0;
unsigned long holdElapsedMs = 0;

char usbLine[512];
size_t usbLineLength = 0;
char nanoLine[512];
size_t nanoLineLength = 0;

#if HAS_MODULINO_LIBRARY
ModulinoDistance modulinoDistance;
ModulinoPixels modulinoPixels;
ModulinoBuzzer modulinoBuzzer;
ModulinoButtons modulinoButtons;
#endif

bool pixelsAvailable = false;
bool buzzerAvailable = false;
bool buttonsAvailable = false;

const char *stateName(FinalState state) {
  switch (state) {
    case FINAL_NO_USER: return "NO_USER";
    case FINAL_STEP_BACK: return "STEP_BACK";
    case FINAL_STEP_CLOSER: return "STEP_CLOSER";
    case FINAL_READY: return "READY";
    case FINAL_RAISE_ARM: return "RAISE_ARM";
    case FINAL_HOLD_STEADY: return "HOLD_STEADY";
    case FINAL_UNSTABLE: return "UNSTABLE";
    case FINAL_GOOD: return "GOOD";
    case FINAL_DONE: return "DONE";
    case FINAL_SENSOR_ERROR: return "SENSOR_ERROR";
    default: return "SENSOR_ERROR";
  }
}

void safeCopy(char *dest, size_t destSize, const char *src) {
  if (destSize == 0) return;
  if (src == NULL) src = "";
  strncpy(dest, src, destSize - 1);
  dest[destSize - 1] = '\0';
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
  while (*start == ' ' || *start == '\t') start++;
  if (start != line) memmove(line, start, strlen(start) + 1);
}

bool distanceMockActive() {
#if USE_MOCK_DISTANCE
  return true;
#elif AUTO_MOCK_DISTANCE_IF_LIBRARY_MISSING
  #if HAS_MODULINO_LIBRARY && USE_MODULINO_DISTANCE
    return false;
  #else
    return true;
  #endif
#else
  return false;
#endif
}

bool acceptNanoInput(bool fromNanoPort) {
  if (fromNanoPort) {
    return true;
  }

#if USE_NANO_FORWARD_FROM_USB_SERIAL
  return true;
#else
  return false;
#endif
}

bool distanceInUserRange() {
  return distanceOk && distanceData.cm > 0.0 && distanceData.cm <= DISTANCE_NO_USER_MAX_CM;
}

bool distanceGood() {
  return distanceInUserRange() && distanceData.cm >= distanceMinCm && distanceData.cm <= distanceMaxCm;
}

bool cameraFrameGood() {
  return cameraOk && cameraPose.userVisible && cameraPose.fullBodyVisible && cameraPose.confidence >= cameraConfidenceMin;
}

const char *instructionForState(FinalState state) {
  if (state == FINAL_READY && cameraOk && cameraPose.userVisible &&
      (!cameraPose.fullBodyVisible || cameraPose.confidence < cameraConfidenceMin)) {
    return "Move into frame";
  }

  switch (state) {
    case FINAL_NO_USER: return "Step into view";
    case FINAL_STEP_BACK: return "Step back";
    case FINAL_STEP_CLOSER: return "Step closer";
    case FINAL_READY: return "Get ready";
    case FINAL_RAISE_ARM: return "Raise your arm";
    case FINAL_HOLD_STEADY: return "Hold the stretch";
    case FINAL_UNSTABLE: return "Keep steady";
    case FINAL_GOOD: return "Good hold";
    case FINAL_DONE: return "Stretch complete";
    case FINAL_SENSOR_ERROR: return "Sensor check needed";
    default: return "Sensor check needed";
  }
}

void refreshSourceStatus() {
  unsigned long now = millis();
  nanoOk = nanoData.valid && (now - nanoData.lastMs <= NANO_STALE_MS) && strcmp(nanoData.state, "NANO_ERROR") != 0;
  cameraOk = cameraPose.valid && (now - cameraPose.lastMs <= CAMERA_STALE_MS);
  distanceOk = distanceData.valid && (now - distanceData.lastMs <= DISTANCE_STALE_MS);
}

bool holdConditionRaw() {
  return sessionStarted &&
         !sessionPaused &&
         nanoOk &&
         cameraFrameGood() &&
         distanceGood() &&
         nanoData.stable &&
         nanoData.armRaised &&
         cameraPose.armRaised &&
         cameraPose.torsoCentered &&
         nanoData.gyroMag < stabilityThresholdDps;
}

void updateHoldTimer() {
  unsigned long now = millis();
  if (lastHoldTickMs == 0) {
    lastHoldTickMs = now;
    return;
  }

  unsigned long dt = now - lastHoldTickMs;
  lastHoldTickMs = now;

  if (!sessionStarted || sessionPaused || routineDone) {
    badFormSinceMs = 0;
    return;
  }

  if (holdConditionRaw()) {
    holdElapsedMs += dt;
    badFormSinceMs = 0;
  } else {
    if (badFormSinceMs == 0) badFormSinceMs = now;
    if (!stepGood && now - badFormSinceMs >= BAD_FORM_RESET_MS) {
      holdElapsedMs = 0;
    }
  }

  if (!stepGood && holdElapsedMs >= (unsigned long)(targetHoldSec * 1000.0)) {
    stepGood = true;
    goodSinceMs = now;
  }

  if (stepGood && !routineDone && now - goodSinceMs >= GOOD_TO_DONE_MS) {
    routineDone = true;
  }
}

FinalState computeWantedState() {
  if (nanoOk && strcmp(nanoData.state, "NANO_ERROR") == 0) {
    return FINAL_SENSOR_ERROR;
  }

  if (!distanceInUserRange()) {
    return FINAL_NO_USER;
  }

  if (distanceData.cm < distanceMinCm) {
    return FINAL_STEP_BACK;
  }

  if (distanceData.cm > distanceMaxCm && distanceData.cm <= DISTANCE_NO_USER_MAX_CM) {
    return FINAL_STEP_CLOSER;
  }

  if (!cameraOk || !cameraPose.userVisible) {
    return FINAL_NO_USER;
  }

  if (cameraPose.confidence < cameraConfidenceMin || !cameraPose.fullBodyVisible) {
    return FINAL_READY;
  }

  if (!sessionStarted || sessionPaused) {
    return FINAL_READY;
  }

  if (!nanoOk) {
    return FINAL_SENSOR_ERROR;
  }

  if (routineDone) {
    return FINAL_DONE;
  }

  if (stepGood) {
    return FINAL_GOOD;
  }

  if (!nanoData.armRaised && !cameraPose.armRaised) {
    return FINAL_RAISE_ARM;
  }

  if (nanoData.gyroMag >= stabilityThresholdDps) {
    return FINAL_UNSTABLE;
  }

  if (nanoData.armRaised && cameraPose.armRaised && cameraPose.torsoCentered && nanoData.stable) {
    return FINAL_HOLD_STEADY;
  }

  return FINAL_RAISE_ARM;
}

void playStateTone(FinalState state) {
#if HAS_MODULINO_LIBRARY && USE_MODULINO_BUZZER
  if (!buzzerAvailable) return;

  if (state == FINAL_UNSTABLE) {
    modulinoBuzzer.tone(880, 80);
  } else if (state == FINAL_GOOD) {
    modulinoBuzzer.tone(1320, 120);
  } else if (state == FINAL_DONE) {
    modulinoBuzzer.tone(1040, 80);
  } else if (state == FINAL_SENSOR_ERROR) {
    modulinoBuzzer.tone(220, 120);
  }
#else
  (void)state;
#endif
}

void updateDisplay(FinalState state, const char *instruction) {
#if USE_LCD
  // TODO: Add the selected LCD library here. Line 1: stateName(state). Line 2:
  // instruction or hold seconds while holding.
  (void)state;
  (void)instruction;
#else
  (void)state;
  (void)instruction;
#endif
}

void setState(FinalState nextState) {
  if (currentState == nextState) {
    return;
  }

  currentState = nextState;
  playStateTone(nextState);
  updateDisplay(nextState, instructionForState(nextState));
}

void updateStateMachine() {
  refreshSourceStatus();
  updateHoldTimer();

  FinalState wanted = computeWantedState();
  unsigned long now = millis();

  if (wanted != candidateState) {
    candidateState = wanted;
    candidateSinceMs = now;
  }

  bool immediate = wanted == FINAL_GOOD || wanted == FINAL_DONE || wanted == FINAL_SENSOR_ERROR;
  if (currentState != candidateState && (immediate || now - candidateSinceMs >= STATE_DEBOUNCE_MS)) {
    setState(candidateState);
  }
}

int computeScore() {
  if (!sessionStarted || sessionPaused) {
    return -1;
  }

  int score = 0;
  if (cameraOk && cameraPose.userVisible && distanceGood()) score += 40;
  if (nanoOk && nanoData.armRaised) score += 30;
  if (cameraOk && cameraPose.armRaised) score += 20;
  if (nanoOk && nanoData.stable) score += 10;
  if (score < 0) score = 0;
  if (score > 100) score = 100;
  return score;
}

void outputStatusJson(bool force) {
  unsigned long now = millis();
  if (!force && now - lastOutputMs < OUTPUT_INTERVAL_MS) {
    return;
  }
  lastOutputMs = now;

  const char *instruction = instructionForState(currentState);
  int score = computeScore();
  bool sourceOk = nanoOk && cameraOk && distanceOk;

  Serial.print("{\"type\":\"stretch_state\",\"t\":");
  Serial.print(now);
  Serial.print(",\"state\":\"");
  Serial.print(stateName(currentState));
  Serial.print("\",\"instruction\":\"");
  Serial.print(instruction);
  Serial.print("\",\"score\":");
  if (score >= 0) Serial.print(score);
  else Serial.print("null");
  Serial.print(",\"distance_cm\":");
  if (distanceOk) Serial.print(distanceData.cm, 1);
  else Serial.print("null");
  Serial.print(",\"nano_angle\":");
  if (nanoOk) Serial.print(nanoData.relativePitch, 1);
  else Serial.print("null");
  Serial.print(",\"gyro_mag\":");
  if (nanoOk) Serial.print(nanoData.gyroMag, 1);
  else Serial.print("null");
  Serial.print(",\"camera_arm_raised\":");
  Serial.print(cameraOk && cameraPose.armRaised ? "true" : "false");
  Serial.print(",\"nano_arm_raised\":");
  Serial.print(nanoOk && nanoData.armRaised ? "true" : "false");
  Serial.print(",\"hold_sec\":");
  Serial.print((float)holdElapsedMs / 1000.0, 1);
  Serial.print(",\"source_ok\":");
  Serial.print(sourceOk ? "true" : "false");
  Serial.print(",\"nano_ok\":");
  Serial.print(nanoOk ? "true" : "false");
  Serial.print(",\"camera_ok\":");
  Serial.print(cameraOk ? "true" : "false");
  Serial.print(",\"distance_ok\":");
  Serial.print(distanceOk ? "true" : "false");
  Serial.print(",\"session_started\":");
  Serial.print(sessionStarted ? "true" : "false");
  Serial.println("}");
}

void resetSession() {
  sessionStarted = false;
  sessionPaused = false;
  stepGood = false;
  routineDone = false;
  holdElapsedMs = 0;
  badFormSinceMs = 0;
  goodSinceMs = 0;
  lastHoldTickMs = millis();
}

void startSession() {
  sessionStarted = true;
  sessionPaused = false;
  stepGood = false;
  routineDone = false;
  holdElapsedMs = 0;
  badFormSinceMs = 0;
  goodSinceMs = 0;
  lastHoldTickMs = millis();
}

void nextStep() {
  stepGood = true;
  routineDone = true;
  goodSinceMs = millis();
}

void sendNanoCalibrationCommand() {
#if USE_NANO_ON_SERIAL1
  Serial1.println("CALIBRATE");
#endif
  Serial.println("# OK CALIBRATE_NANO requested");
}

void processCommand(const char *rawLine) {
  char line[128];
  safeCopy(line, sizeof(line), rawLine);
  trimLine(line);
  if (line[0] == '\0') return;

  if (strcmp(line, "START") == 0) {
    startSession();
    Serial.println("# OK START");
  } else if (strcmp(line, "PAUSE") == 0) {
    sessionPaused = !sessionPaused;
    Serial.println("# OK PAUSE");
  } else if (strcmp(line, "NEXT") == 0) {
    nextStep();
    Serial.println("# OK NEXT");
  } else if (strcmp(line, "RESET") == 0) {
    resetSession();
    Serial.println("# OK RESET");
  } else if (strcmp(line, "CALIBRATE_NANO") == 0) {
    sendNanoCalibrationCommand();
  } else if (strcmp(line, "STATUS") == 0) {
    outputStatusJson(true);
  } else if (startsWith(line, "SET_MODE ")) {
    safeCopy(modeName, sizeof(modeName), line + strlen("SET_MODE "));
    Serial.println("# OK SET_MODE");
  } else if (startsWith(line, "SET_BODY_FOCUS ")) {
    safeCopy(bodyFocusName, sizeof(bodyFocusName), line + strlen("SET_BODY_FOCUS "));
    Serial.println("# OK SET_BODY_FOCUS");
  } else if (startsWith(line, "SET_TARGET_HOLD ")) {
    float value = atof(line + strlen("SET_TARGET_HOLD "));
    if (value >= 1.0 && value <= 120.0) {
      targetHoldSec = value;
      Serial.println("# OK SET_TARGET_HOLD");
    } else {
      Serial.println("# ERROR SET_TARGET_HOLD out of range");
    }
  } else if (startsWith(line, "SET_DISTANCE_MIN ")) {
    float value = atof(line + strlen("SET_DISTANCE_MIN "));
    if (value > 0.0 && value < distanceMaxCm) {
      distanceMinCm = value;
      Serial.println("# OK SET_DISTANCE_MIN");
    } else {
      Serial.println("# ERROR SET_DISTANCE_MIN out of range");
    }
  } else if (startsWith(line, "SET_DISTANCE_MAX ")) {
    float value = atof(line + strlen("SET_DISTANCE_MAX "));
    if (value > distanceMinCm && value <= DISTANCE_NO_USER_MAX_CM) {
      distanceMaxCm = value;
      Serial.println("# OK SET_DISTANCE_MAX");
    } else {
      Serial.println("# ERROR SET_DISTANCE_MAX out of range");
    }
  } else if (startsWith(line, "SET_MOCK_DISTANCE ")) {
    mockDistanceCm = atof(line + strlen("SET_MOCK_DISTANCE "));
    Serial.println("# OK SET_MOCK_DISTANCE");
  } else {
    Serial.println("# WARN unknown command");
  }
}

const char *findJsonValue(const char *json, const char *key) {
  char pattern[40];
  snprintf(pattern, sizeof(pattern), "\"%s\"", key);
  const char *p = strstr(json, pattern);
  if (p == NULL) return NULL;
  p = strchr(p, ':');
  if (p == NULL) return NULL;
  p++;
  while (*p == ' ' || *p == '\t') p++;
  return p;
}

bool jsonGetBool(const char *json, const char *key, bool *out) {
  const char *p = findJsonValue(json, key);
  if (p == NULL) return false;
  if (strncmp(p, "true", 4) == 0) {
    *out = true;
    return true;
  }
  if (strncmp(p, "false", 5) == 0) {
    *out = false;
    return true;
  }
  return false;
}

bool jsonGetFloat(const char *json, const char *key, float *out) {
  const char *p = findJsonValue(json, key);
  if (p == NULL) return false;
  *out = atof(p);
  return true;
}

bool jsonGetString(const char *json, const char *key, char *out, size_t outSize) {
  const char *p = findJsonValue(json, key);
  if (p == NULL || *p != '"') return false;
  p++;

  size_t i = 0;
  while (*p != '\0' && *p != '"' && i < outSize - 1) {
    out[i++] = *p++;
  }
  out[i] = '\0';
  return i > 0;
}

void markNanoUpdated() {
  nanoData.valid = true;
  nanoData.lastMs = millis();
  if (nanoData.state[0] == '\0') {
    safeCopy(nanoData.state, sizeof(nanoData.state), nanoData.stable ? "NANO_HOLD_STABLE" : "NANO_ARM_RAISED");
  }
}

void markCameraUpdated() {
  cameraPose.valid = true;
  cameraPose.lastMs = millis();
}

void processJsonLine(const char *line, bool fromNanoPort) {
#if HAS_ARDUINOJSON
  StaticJsonDocument<640> doc;
  DeserializationError error = deserializeJson(doc, line);
  if (error) {
    return;
  }

  const char *type = doc["type"] | "";

  if (strcmp(type, "nano_imu") == 0) {
    if (!acceptNanoInput(fromNanoPort)) return;
    if (!doc["relative_pitch"].isNull()) nanoData.relativePitch = doc["relative_pitch"];
    if (!doc["gyro_mag"].isNull()) nanoData.gyroMag = doc["gyro_mag"];
    if (!doc["stable"].isNull()) nanoData.stable = doc["stable"];
    if (!doc["arm_raised"].isNull()) nanoData.armRaised = doc["arm_raised"];
    const char *state = doc["state"] | "";
    if (state[0] != '\0') safeCopy(nanoData.state, sizeof(nanoData.state), state);
    markNanoUpdated();
  } else if (strcmp(type, "camera_pose") == 0) {
    if (!doc["user_visible"].isNull()) cameraPose.userVisible = doc["user_visible"];
    if (!doc["full_body_visible"].isNull()) cameraPose.fullBodyVisible = doc["full_body_visible"];
    if (!doc["arm_raised"].isNull()) cameraPose.armRaised = doc["arm_raised"];
    if (!doc["torso_centered"].isNull()) cameraPose.torsoCentered = doc["torso_centered"];
    if (!doc["confidence"].isNull()) cameraPose.confidence = doc["confidence"];
    markCameraUpdated();
  } else if (strcmp(type, "session_command") == 0) {
    const char *command = doc["command"] | "";
    if (command[0] != '\0') processCommand(command);
  } else if (strcmp(type, "config") == 0) {
    const char *mode = doc["mode"] | "";
    const char *bodyFocus = doc["body_focus"] | "";
    if (mode[0] != '\0') safeCopy(modeName, sizeof(modeName), mode);
    if (bodyFocus[0] != '\0') safeCopy(bodyFocusName, sizeof(bodyFocusName), bodyFocus);
    if (!doc["duration_min"].isNull()) sessionDurationMin = doc["duration_min"];
    Serial.println("# OK config");
  }
#else
  char type[32];
  if (!jsonGetString(line, "type", type, sizeof(type))) {
    return;
  }

  if (strcmp(type, "nano_imu") == 0) {
    if (!acceptNanoInput(fromNanoPort)) return;
    bool boolValue;
    float floatValue;
    char stateValue[24];
    if (jsonGetFloat(line, "relative_pitch", &floatValue)) nanoData.relativePitch = floatValue;
    if (jsonGetFloat(line, "gyro_mag", &floatValue)) nanoData.gyroMag = floatValue;
    if (jsonGetBool(line, "stable", &boolValue)) nanoData.stable = boolValue;
    if (jsonGetBool(line, "arm_raised", &boolValue)) nanoData.armRaised = boolValue;
    if (jsonGetString(line, "state", stateValue, sizeof(stateValue))) safeCopy(nanoData.state, sizeof(nanoData.state), stateValue);
    markNanoUpdated();
  } else if (strcmp(type, "camera_pose") == 0) {
    bool boolValue;
    float floatValue;
    if (jsonGetBool(line, "user_visible", &boolValue)) cameraPose.userVisible = boolValue;
    if (jsonGetBool(line, "full_body_visible", &boolValue)) cameraPose.fullBodyVisible = boolValue;
    if (jsonGetBool(line, "arm_raised", &boolValue)) cameraPose.armRaised = boolValue;
    if (jsonGetBool(line, "torso_centered", &boolValue)) cameraPose.torsoCentered = boolValue;
    if (jsonGetFloat(line, "confidence", &floatValue)) cameraPose.confidence = floatValue;
    markCameraUpdated();
  } else if (strcmp(type, "session_command") == 0) {
    char command[32];
    if (jsonGetString(line, "command", command, sizeof(command))) processCommand(command);
  } else if (strcmp(type, "config") == 0) {
    char value[16];
    float durationValue;
    if (jsonGetString(line, "mode", value, sizeof(value))) safeCopy(modeName, sizeof(modeName), value);
    if (jsonGetString(line, "body_focus", value, sizeof(value))) safeCopy(bodyFocusName, sizeof(bodyFocusName), value);
    if (jsonGetFloat(line, "duration_min", &durationValue)) sessionDurationMin = durationValue;
    Serial.println("# OK config");
  }
#endif
}

void handleInputLine(char *line, bool fromNanoPort) {
  trimLine(line);
  if (line[0] == '\0' || line[0] == '#') return;

  if (line[0] == '{') {
    processJsonLine(line, fromNanoPort);
  } else if (!fromNanoPort) {
    processCommand(line);
  }
}

void readSerialLines(Stream &stream, char *buffer, size_t *length, bool fromNanoPort) {
  while (stream.available() > 0) {
    char c = (char)stream.read();
    if (c == '\n' || c == '\r') {
      if (*length > 0) {
        buffer[*length] = '\0';
        handleInputLine(buffer, fromNanoPort);
        *length = 0;
      }
    } else if (*length < 511) {
      buffer[(*length)++] = c;
    } else {
      *length = 0;
      if (!fromNanoPort) Serial.println("# WARN input line too long");
    }
  }
}

void parseSerial() {
  readSerialLines(Serial, usbLine, &usbLineLength, false);

#if USE_NANO_ON_SERIAL1
  readSerialLines(Serial1, nanoLine, &nanoLineLength, true);
#endif
}

void initDistanceSensor() {
  if (distanceMockActive()) {
    distanceData.available = true;
    distanceData.valid = true;
    distanceData.cm = mockDistanceCm;
    distanceData.lastMs = millis();
    Serial.println("# Distance: mock mode active");
    return;
  }

#if HAS_MODULINO_LIBRARY && USE_MODULINO_DISTANCE
  // TODO: Confirm the installed Modulino library version on the hackathon laptop.
  // Arduino_Modulino docs show ModulinoDistance distance; distance.begin(); distance.get();
  modulinoDistance.begin();
  distanceData.available = true;
  Serial.println("# Distance: ModulinoDistance enabled");
#else
  distanceData.available = false;
  distanceData.valid = false;
  Serial.println("# Distance: no library and mock disabled");
#endif
}

bool readDistanceCm(float *outCm) {
  if (distanceMockActive()) {
    *outCm = mockDistanceCm;
    return true;
  }

#if HAS_MODULINO_LIBRARY && USE_MODULINO_DISTANCE
  if (!distanceData.available) return false;
  float raw = modulinoDistance.get();
  #if MODULINO_DISTANCE_RETURNS_MM
    raw = raw / 10.0;
  #endif
  if (isnan(raw) || raw <= 0.0) return false;
  *outCm = raw;
  return true;
#else
  (void)outCm;
  return false;
#endif
}

void updateDistance() {
  unsigned long now = millis();
  if (now - lastDistanceMs < DISTANCE_INTERVAL_MS) {
    return;
  }
  lastDistanceMs = now;

  float cm = 0.0;
  if (readDistanceCm(&cm)) {
    distanceData.cm = cm;
    distanceData.valid = true;
    distanceData.lastMs = now;
  } else {
    distanceData.valid = false;
  }
}

void initFeedback() {
#if HAS_MODULINO_LIBRARY && (USE_MODULINO_DISTANCE || USE_MODULINO_PIXELS || USE_MODULINO_BUZZER || USE_MODULINO_BUTTONS)
  Modulino.begin();
#endif

#if HAS_MODULINO_LIBRARY && USE_MODULINO_PIXELS
  modulinoPixels.begin();
  pixelsAvailable = true;
#endif

#if HAS_MODULINO_LIBRARY && USE_MODULINO_BUZZER
  modulinoBuzzer.begin();
  buzzerAvailable = true;
#endif

#if HAS_MODULINO_LIBRARY && USE_MODULINO_BUTTONS
  modulinoButtons.begin();
  buttonsAvailable = true;
#endif
}

void setAllPixels(uint8_t r, uint8_t g, uint8_t b) {
#if HAS_MODULINO_LIBRARY && USE_MODULINO_PIXELS
  if (!pixelsAvailable) return;
  for (int i = 0; i < 8; i++) {
    modulinoPixels.set(i, ModulinoColor(r, g, b));
  }
  modulinoPixels.show();
#else
  (void)r;
  (void)g;
  (void)b;
#endif
}

uint8_t pulseValue(unsigned long periodMs, uint8_t minValue, uint8_t maxValue) {
  unsigned long phase = millis() % periodMs;
  float normalized = (phase < periodMs / 2) ? (float)phase / (float)(periodMs / 2) : (float)(periodMs - phase) / (float)(periodMs / 2);
  return minValue + (uint8_t)((maxValue - minValue) * normalized);
}

void updateFeedback() {
  static unsigned long lastPixelMs = 0;
  unsigned long now = millis();
  if (now - lastPixelMs < 50) return;
  lastPixelMs = now;

  switch (currentState) {
    case FINAL_NO_USER:
      setAllPixels(8, 8, 8);
      break;
    case FINAL_STEP_BACK:
    case FINAL_STEP_CLOSER: {
      uint8_t v = pulseValue(900, 20, 160);
      setAllPixels(v, v, 0);
      break;
    }
    case FINAL_READY:
      setAllPixels(0, 120, 140);
      break;
    case FINAL_RAISE_ARM:
      setAllPixels(0, 40, 180);
      break;
    case FINAL_HOLD_STEADY:
      setAllPixels(0, 150, 40);
      break;
    case FINAL_UNSTABLE: {
      uint8_t v = pulseValue(500, 20, 180);
      setAllPixels(v, 0, 0);
      break;
    }
    case FINAL_GOOD:
      setAllPixels(0, 220, 80);
      break;
    case FINAL_DONE: {
      uint8_t v = pulseValue(700, 80, 220);
      setAllPixels(0, v, v);
      break;
    }
    case FINAL_SENSOR_ERROR: {
      uint8_t v = pulseValue(1400, 0, 150);
      setAllPixels(v, 0, 0);
      break;
    }
  }
}

void readButtons() {
#if HAS_MODULINO_LIBRARY && USE_MODULINO_BUTTONS
  if (!buttonsAvailable) return;

  static bool lastPressed[3] = {false, false, false};
  if (!modulinoButtons.update()) return;

  for (int i = 0; i < 3; i++) {
    bool pressed = modulinoButtons.isPressed(i);
    if (pressed && !lastPressed[i]) {
      if (i == 0) {
        if (!sessionStarted || sessionPaused) startSession();
        else sessionPaused = true;
      } else if (i == 1) {
        nextStep();
      } else if (i == 2) {
        resetSession();
      }
    }
    lastPressed[i] = pressed;
  }
#endif
}

void readInputs() {
  parseSerial();
  updateDistance();
  readButtons();
}

void initDisplay() {
#if USE_LCD
  // TODO: Initialize the chosen LCD library here.
#endif
}

void setup() {
  Serial.begin(USB_SERIAL_BAUD);
  unsigned long waitStart = millis();
  while (!Serial && millis() - waitStart < 1500) {
    // Bounded wait for Serial Monitor or UNO Q Linux app attach.
  }

#if USE_NANO_ON_SERIAL1
  Serial1.begin(NANO_SERIAL_BAUD);
#endif

  Serial.println("# StretchSense UnoQStretchHub boot");
  Serial.println("# Camera inference is external; send camera_pose JSON over USB Serial.");

  initFeedback();
  initDistanceSensor();
  initDisplay();
  resetSession();
}

void loop() {
  readInputs();
  updateStateMachine();
  updateFeedback();
  outputStatusJson(false);
}
