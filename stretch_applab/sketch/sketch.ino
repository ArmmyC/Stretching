/*
  YUEDMAI App Lab sketch

  Reads Modulino Knob and Modulino Buttons on the UNO Q MCU side, sends
  abstract navigation actions to Python through Arduino_RouterBridge, and
  receives lightweight feedback for Modulino Pixels / button LEDs.

  Also scans for the Nano 33 BLE Sense Lite wearable named YUEDMAI-NanoIMU,
  subscribes to its compact IMU characteristic, and forwards that JSON payload
  to Python as nano_imu for scoring/dashboard use.
*/

#include <Arduino.h>

// Keep this off for the App Lab control sketch unless Nano BLE has been
// verified. Continuous BLE central scanning can stall RouterBridge/button
// handling on UNO Q, which breaks kiosk navigation.
#define USE_NANO_BLE_IMU 0

#if defined(__has_include)
  #if __has_include(<Arduino_RouterBridge.h>)
    #include <Arduino_RouterBridge.h>
    #define HAS_ROUTER_BRIDGE 1
  #else
    #define HAS_ROUTER_BRIDGE 0
  #endif

  #if __has_include(<Arduino_Modulino.h>)
    #include <Arduino_Modulino.h>
    #define HAS_MODULINO_LIBRARY 1
  #elif __has_include(<Modulino.h>)
    #include <Modulino.h>
    #define HAS_MODULINO_LIBRARY 1
  #else
    #define HAS_MODULINO_LIBRARY 0
  #endif

  #if __has_include(<ArduinoBLE.h>)
    #include <ArduinoBLE.h>
    #define HAS_ARDUINOBLE 1
  #else
    #define HAS_ARDUINOBLE 0
  #endif
#else
  #define HAS_ROUTER_BRIDGE 0
  #define HAS_MODULINO_LIBRARY 0
  #define HAS_ARDUINOBLE 0
#endif

const unsigned long INPUT_POLL_MS = 25;
const unsigned long LONG_PRESS_MS = 850;
const unsigned long FEEDBACK_REFRESH_MS = 80;
const unsigned long BUTTON_DEBUG_MS = 1000;
const unsigned long BLE_POLL_INTERVAL_MS = 250;
const unsigned long BLE_SCAN_RETRY_MS = 10000;
const unsigned long SERIAL_BAUD = 115200;
const int PIXEL_COUNT = 8;
const char NANO_BLE_NAME[] = "YUEDMAI-NanoIMU";
const char NANO_BLE_SERVICE_UUID[] = "19b10000-e8f2-537e-4f6c-d104768a1214";
const char NANO_BLE_IMU_CHAR_UUID[] = "19b10001-e8f2-537e-4f6c-d104768a1214";

#if HAS_MODULINO_LIBRARY
ModulinoKnob modulinoKnob;
ModulinoButtons modulinoButtons;
ModulinoPixels modulinoPixels;
#endif

#if HAS_ARDUINOBLE && USE_NANO_BLE_IMU
BLEDevice nanoBlePeripheral;
BLECharacteristic nanoBleImuCharacteristic;
#endif

bool knobAvailable = false;
bool buttonsAvailable = false;
bool pixelsAvailable = false;
bool nanoBleHealthy = false;
bool nanoBleConnected = false;
bool nanoBleSubscribed = false;

bool knobPressed = false;
bool knobLongSent = false;
unsigned long knobPressedAt = 0;
int16_t lastKnobValue = 0;
bool haveKnobValue = false;

bool buttonPressed[3] = {false, false, false};
bool buttonLongSent[3] = {false, false, false};
bool buttonIdleState[3] = {false, false, false};
bool buttonIdleCalibrated = false;
unsigned long buttonPressedAt[3] = {0, 0, 0};

String feedbackPage = "boot";
String feedbackState = "";
String feedbackSelection = "";
int feedbackValue = 0;
String lastFeedbackDebug = "";
unsigned long lastInputMs = 0;
unsigned long lastFeedbackMs = 0;
unsigned long lastButtonDebugMs = 0;
unsigned long lastBleScanMs = 0;
unsigned long lastBleReadMs = 0;
unsigned long lastBlePollMs = 0;
char nanoBleLine[256];

const char *buttonAction(int index) {
  switch (index) {
    case 0: return "BUTTON_A";
    case 1: return "BUTTON_B";
    case 2: return "BUTTON_C";
    default: return "BUTTON_A";
  }
}

const char *buttonLongAction(int index) {
  switch (index) {
    case 0: return "BUTTON_A_LONG";
    case 1: return "BUTTON_B_LONG";
    case 2: return "BUTTON_C_LONG";
    default: return "BUTTON_A_LONG";
  }
}

void notifyAction(const char *action, int value = 0) {
  String payload = String("{\"action\":\"") + action + "\",\"value\":" + String(value) + "}";
  Serial.print("# notify hardware_event action=");
  Serial.print(action);
  Serial.print(" value=");
  Serial.print(value);
  Serial.print(" bridge=");
  Serial.println(HAS_ROUTER_BRIDGE ? "yes" : "no");
#if HAS_ROUTER_BRIDGE
  Bridge.notify("hardware_event", payload);
#else
  Serial.print("# hardware_event ");
  Serial.println(payload);
#endif
}

void notifyNanoImu(const char *payload) {
  if (payload == NULL || payload[0] == '\0') return;

  Serial.print("# notify nano_imu bridge=");
  Serial.print(HAS_ROUTER_BRIDGE ? "yes" : "no");
  Serial.print(" payload=");
  Serial.println(payload);
#if HAS_ROUTER_BRIDGE
  Bridge.notify("nano_imu", payload);
#else
  Serial.print("# nano_imu ");
  Serial.println(payload);
#endif
}

void startNanoBleScan() {
#if HAS_ARDUINOBLE && USE_NANO_BLE_IMU
  BLE.stopScan();
  BLE.scanForName(NANO_BLE_NAME);
  lastBleScanMs = millis();
  Serial.println("# BLE scanning for Nano IMU by name");
#endif
}

void initNanoBle() {
#if HAS_ARDUINOBLE && USE_NANO_BLE_IMU
  if (!BLE.begin()) {
    nanoBleHealthy = false;
    Serial.println("# WARN ArduinoBLE begin failed; Nano BLE disabled");
    return;
  }
  nanoBleHealthy = true;
  startNanoBleScan();
#else
  nanoBleHealthy = false;
  Serial.println("# WARN ArduinoBLE library not installed; Nano BLE disabled");
#endif
}

void disconnectNanoBle() {
#if HAS_ARDUINOBLE && USE_NANO_BLE_IMU
  if (nanoBlePeripheral && nanoBlePeripheral.connected()) {
    nanoBlePeripheral.disconnect();
  }
  nanoBleConnected = false;
  nanoBleSubscribed = false;
  startNanoBleScan();
#endif
}

bool connectAvailableNanoBle() {
#if HAS_ARDUINOBLE && USE_NANO_BLE_IMU
  BLEDevice peripheral = BLE.available();
  if (!peripheral) {
    return false;
  }

  String localName = peripheral.localName();
  if (localName != NANO_BLE_NAME) {
    return false;
  }

  Serial.print("# BLE Nano candidate ");
  Serial.println(peripheral.address());
  BLE.stopScan();

  if (!peripheral.connect()) {
    Serial.println("# WARN BLE Nano connect failed");
    startNanoBleScan();
    return false;
  }

  if (!peripheral.discoverService(NANO_BLE_SERVICE_UUID)) {
    Serial.println("# WARN BLE Nano service discovery failed");
    peripheral.disconnect();
    startNanoBleScan();
    return false;
  }

  BLECharacteristic imuChar = peripheral.characteristic(NANO_BLE_IMU_CHAR_UUID);
  if (!imuChar) {
    Serial.println("# WARN BLE Nano IMU characteristic missing");
    peripheral.disconnect();
    startNanoBleScan();
    return false;
  }

  nanoBlePeripheral = peripheral;
  nanoBleImuCharacteristic = imuChar;
  nanoBleSubscribed = nanoBleImuCharacteristic.canSubscribe() && nanoBleImuCharacteristic.subscribe();
  nanoBleConnected = true;
  lastBleReadMs = 0;

  Serial.print("# BLE Nano connected name=");
  Serial.print(peripheral.localName());
  Serial.print(" notify=");
  Serial.println(nanoBleSubscribed ? "yes" : "no");
  return true;
#else
  return false;
#endif
}

void readNanoBlePacket() {
#if HAS_ARDUINOBLE && USE_NANO_BLE_IMU
  if (!nanoBleConnected || !nanoBleImuCharacteristic) return;

  int valueLength = nanoBleImuCharacteristic.valueLength();
  if (valueLength <= 0) return;

  int readLength = min(valueLength, (int)sizeof(nanoBleLine) - 1);
  int actualLength = nanoBleImuCharacteristic.readValue((uint8_t *)nanoBleLine, readLength);
  if (actualLength <= 0) return;

  nanoBleLine[actualLength] = '\0';
  notifyNanoImu(nanoBleLine);
#endif
}

void updateNanoBle() {
#if HAS_ARDUINOBLE && USE_NANO_BLE_IMU
  if (!nanoBleHealthy) return;

  unsigned long now = millis();
  if (now - lastBlePollMs < BLE_POLL_INTERVAL_MS) {
    return;
  }
  lastBlePollMs = now;

  BLE.poll();

  if (nanoBleConnected) {
    if (!nanoBlePeripheral.connected()) {
      Serial.println("# BLE Nano disconnected");
      disconnectNanoBle();
      return;
    }

    if (nanoBleSubscribed) {
      if (nanoBleImuCharacteristic.valueUpdated()) {
        readNanoBlePacket();
      }
    } else if (now - lastBleReadMs >= BLE_POLL_INTERVAL_MS) {
      lastBleReadMs = now;
      readNanoBlePacket();
    }
    return;
  }

  if (connectAvailableNanoBle()) {
    return;
  }

  if (now - lastBleScanMs >= BLE_SCAN_RETRY_MS) {
    startNanoBleScan();
  }
#endif
}

uint8_t scaleColor(uint8_t value, uint8_t brightness) {
  return (uint8_t)((uint16_t)value * (uint16_t)brightness / 31);
}

void setPixel(int index, uint8_t r, uint8_t g, uint8_t b, uint8_t brightness = 18) {
#if HAS_MODULINO_LIBRARY
  modulinoPixels.set(index, ModulinoColor(scaleColor(r, brightness), scaleColor(g, brightness), scaleColor(b, brightness)));
#else
  (void)index;
  (void)r;
  (void)g;
  (void)b;
  (void)brightness;
#endif
}

void setAllPixels(uint8_t r, uint8_t g, uint8_t b, uint8_t brightness = 12) {
#if HAS_MODULINO_LIBRARY
  if (!pixelsAvailable) return;
  for (int i = 0; i < PIXEL_COUNT; i++) {
    setPixel(i, r, g, b, brightness);
  }
  modulinoPixels.show();
#else
  (void)r;
  (void)g;
  (void)b;
  (void)brightness;
#endif
}

void setProgressPixels(uint8_t r, uint8_t g, uint8_t b, int percent, uint8_t brightness = 16) {
#if HAS_MODULINO_LIBRARY
  if (!pixelsAvailable) return;
  int lit = constrain(map(percent, 0, 100, 0, PIXEL_COUNT), 0, PIXEL_COUNT);
  modulinoPixels.clear();
  for (int i = 0; i < lit; i++) {
    setPixel(i, r, g, b, brightness);
  }
  modulinoPixels.show();
#else
  (void)r;
  (void)g;
  (void)b;
  (void)percent;
  (void)brightness;
#endif
}

uint8_t pulse(unsigned long periodMs, uint8_t low, uint8_t high) {
  unsigned long phase = millis() % periodMs;
  unsigned long half = periodMs / 2;
  float t = phase < half ? (float)phase / (float)half : (float)(periodMs - phase) / (float)half;
  return low + (uint8_t)((high - low) * t);
}

void updateButtonLeds() {
#if HAS_MODULINO_LIBRARY
  if (!buttonsAvailable) return;
  bool a = feedbackPage == "landing" || feedbackPage == "setup" || feedbackPage == "session";
  bool b = feedbackPage == "setup" || feedbackPage == "session";
  bool c = feedbackPage == "setup" || feedbackPage == "session";
  modulinoButtons.setLeds(buttonPressed[0] || a, buttonPressed[1] || b, buttonPressed[2] || c);
#endif
}

void updatePixels() {
  if (feedbackPage == "landing") {
    if (feedbackSelection == "after") setAllPixels(0, 120, 160, 16);
    else setAllPixels(120, 220, 20, 16);
    return;
  }

  if (feedbackPage == "setup") {
#if HAS_MODULINO_LIBRARY
    if (!pixelsAvailable) return;
    int selected = constrain(feedbackValue % PIXEL_COUNT, 0, PIXEL_COUNT - 1);
    modulinoPixels.clear();
    for (int i = 0; i < PIXEL_COUNT; i++) {
      if (i == selected) setPixel(i, 184, 255, 58, 22);
      else setPixel(i, 16, 24, 32, 4);
    }
    modulinoPixels.show();
#endif
    return;
  }

  if (feedbackPage == "session") {
    if (feedbackState == "READY") {
      int countdownPercent = constrain((6 - feedbackValue) * 20, 0, 100);
      setProgressPixels(184, 255, 58, countdownPercent, 20);
    } else if (feedbackState == "HOLD" || feedbackState == "GOOD") {
      setProgressPixels(0, 220, 90, feedbackValue, 18);
    } else if (feedbackState == "DONE") {
      uint8_t v = pulse(750, 70, 220);
      setAllPixels(0, v, v, 18);
    } else if (feedbackState == "NO_CAMERA" || feedbackState == "WAITING_FOR_PHONE") {
      uint8_t v = pulse(900, 20, 190);
      setAllPixels(v, 120, 0, 14);
    } else {
      setAllPixels(20, 30, 40, 8);
    }
    return;
  }

  setAllPixels(8, 8, 8, 4);
}

String setFeedback(String page, String state, String selection, int value) {
  feedbackPage = page;
  feedbackState = state;
  feedbackSelection = selection;
  feedbackValue = constrain(value, 0, 100);
  String feedbackDebug = page + "|" + state + "|" + selection + "|" + String(feedbackValue);
  if (feedbackDebug != lastFeedbackDebug) {
    lastFeedbackDebug = feedbackDebug;
    Serial.print("# feedback page=");
    Serial.print(feedbackPage);
    Serial.print(" state=");
    Serial.print(feedbackState);
    Serial.print(" selection=");
    Serial.print(feedbackSelection);
    Serial.print(" value=");
    Serial.println(feedbackValue);
  }
  updateButtonLeds();
  updatePixels();
  return "{\"ok\":true}";
}

void handlePressState(bool pressed, bool &lastPressed, bool &longSent, unsigned long &pressedAt, const char *shortAction, const char *longAction) {
  unsigned long now = millis();
  if (pressed && !lastPressed) {
    Serial.print("# input down action=");
    Serial.println(shortAction);
    pressedAt = now;
    longSent = false;
  }

  if (pressed && !longSent && now - pressedAt >= LONG_PRESS_MS) {
    Serial.print("# input long action=");
    Serial.println(longAction);
    notifyAction(longAction);
    longSent = true;
  }

  if (!pressed && lastPressed && !longSent) {
    Serial.print("# input short action=");
    Serial.println(shortAction);
    notifyAction(shortAction);
  }

  if (!pressed && lastPressed && longSent) {
    Serial.print("# input release after long action=");
    Serial.println(longAction);
  }

  lastPressed = pressed;
}

void readKnob() {
#if HAS_MODULINO_LIBRARY
  if (!knobAvailable) return;

  int16_t value = modulinoKnob.get();
  if (!haveKnobValue) {
    lastKnobValue = value;
    haveKnobValue = true;
  }

  int16_t delta = value - lastKnobValue;
  if (delta != 0) {
    notifyAction(delta > 0 ? "KNOB_RIGHT" : "KNOB_LEFT", delta);
    lastKnobValue = value;
  }

  bool pressed = modulinoKnob.isPressed() == HIGH;
  handlePressState(pressed, knobPressed, knobLongSent, knobPressedAt, "KNOB_PRESS", "KNOB_PRESS_LONG");
#endif
}

void readButtons() {
#if HAS_MODULINO_LIBRARY
  if (!buttonsAvailable) return;
  modulinoButtons.update();
  bool rawNow[3] = {false, false, false};
  bool pressedNow[3] = {false, false, false};
  for (int i = 0; i < 3; i++) {
    rawNow[i] = modulinoButtons.isPressed(i) == HIGH;
    pressedNow[i] = buttonIdleCalibrated ? rawNow[i] != buttonIdleState[i] : rawNow[i];
  }

  unsigned long now = millis();
  if (now - lastButtonDebugMs >= BUTTON_DEBUG_MS) {
    lastButtonDebugMs = now;
    Serial.print("# buttons raw A=");
    Serial.print(rawNow[0]);
    Serial.print(" B=");
    Serial.print(rawNow[1]);
    Serial.print(" C=");
    Serial.print(rawNow[2]);
    Serial.print(" pressed A=");
    Serial.print(pressedNow[0]);
    Serial.print(" B=");
    Serial.print(pressedNow[1]);
    Serial.print(" C=");
    Serial.println(pressedNow[2]);
  }

  for (int i = 0; i < 3; i++) {
    handlePressState(pressedNow[i], buttonPressed[i], buttonLongSent[i], buttonPressedAt[i], buttonAction(i), buttonLongAction(i));
  }
  updateButtonLeds();
#endif
}

void initHardware() {
  Serial.print("# compile HAS_ROUTER_BRIDGE=");
  Serial.println(HAS_ROUTER_BRIDGE);
  Serial.print("# compile HAS_MODULINO_LIBRARY=");
  Serial.println(HAS_MODULINO_LIBRARY);
  Serial.print("# compile HAS_ARDUINOBLE=");
  Serial.println(HAS_ARDUINOBLE);

#if HAS_ROUTER_BRIDGE
  Serial.println("# Bridge.begin");
  Bridge.begin();
  Serial.println("# Bridge.provide set_feedback");
  Bridge.provide("set_feedback", setFeedback);
  Serial.println("# Arduino_RouterBridge ready.");
#endif

#if HAS_MODULINO_LIBRARY
  Serial.println("# Modulino.begin");
  Modulino.begin();
  Serial.println("# ModulinoKnob.begin");
  modulinoKnob.begin();
  Serial.println("# ModulinoButtons.begin");
  modulinoButtons.begin();
  modulinoButtons.update();
  for (int i = 0; i < 3; i++) {
    buttonIdleState[i] = modulinoButtons.isPressed(i) == HIGH;
  }
  buttonIdleCalibrated = true;
  Serial.print("# button idle raw A=");
  Serial.print(buttonIdleState[0]);
  Serial.print(" B=");
  Serial.print(buttonIdleState[1]);
  Serial.print(" C=");
  Serial.println(buttonIdleState[2]);
  Serial.println("# ModulinoPixels.begin");
  modulinoPixels.begin();
  knobAvailable = true;
  buttonsAvailable = true;
  pixelsAvailable = true;
  Serial.println("# Arduino_Modulino ready: knob/buttons/pixels enabled.");
  setFeedback("boot", "", "", 0);
#else
  Serial.println("# Arduino_Modulino library unavailable.");
#endif

#if !HAS_ROUTER_BRIDGE
  Serial.println("# Arduino_RouterBridge library unavailable.");
#endif

  initNanoBle();
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  unsigned long waitStart = millis();
  while (!Serial && millis() - waitStart < 1500) {
    delay(10);
  }
  Serial.println("# YUEDMAI App Lab hardware bridge boot");
  initHardware();
}

void loop() {
  unsigned long now = millis();
  if (now - lastInputMs >= INPUT_POLL_MS) {
    lastInputMs = now;
    readKnob();
    readButtons();
  }

  if (now - lastFeedbackMs >= FEEDBACK_REFRESH_MS) {
    lastFeedbackMs = now;
    updatePixels();
  }

  updateNanoBle();
}
