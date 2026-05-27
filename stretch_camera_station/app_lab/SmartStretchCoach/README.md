# Smart Stretch Coach for Arduino App Lab

This folder is the App Lab-ready version of the Smart Stretch Coach camera station.

Use it in either of these ways:

## Option A: App Lab GUI

1. Open Arduino App Lab.
2. Create a new App named `SmartStretchCoach`.
3. Copy this folder's `python/` contents into the App's `python/` folder.
4. Copy this folder's `sketch/sketch.ino` into the App's `sketch/sketch.ino`.
5. Click Run.

App Lab should install packages from `python/requirements.txt` into the App virtual environment.

## Option B: SSH and App CLI

From your computer, copy this folder to the UNO Q:

```bash
ssh arduino@<boardname>.local
arduino-app-cli app new "SmartStretchCoach"
exit
scp -r app_lab/SmartStretchCoach/. arduino@<boardname>.local:/home/arduino/ArduinoApps/SmartStretchCoach/
ssh arduino@<boardname>.local
arduino-app-cli app start "/home/arduino/ArduinoApps/SmartStretchCoach"
arduino-app-cli app logs "/home/arduino/ArduinoApps/SmartStretchCoach" --all
```

The `app new` command lets App Lab generate `app.yaml` and `sketch/sketch.yaml`. This source folder intentionally does not overwrite those generated manifests.

## Option C: Terminal mode from this App folder

You can also run the Python side directly:

```bash
cd /home/arduino/ArduinoApps/SmartStretchCoach/python
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Notes

- The OpenCV dashboard needs an HDMI/desktop session.
- Phone camera browser access may require HTTPS when opened from a phone LAN IP.
- The MCU sketch is intentionally minimal for now. Add Bridge calls later when you wire sensors into the stretch state pipeline.
