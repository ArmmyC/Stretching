from __future__ import annotations

import logging
import os
import sys
import threading
import time

os.environ.setdefault("STRETCH_HEADLESS", "1")

from station_main import main as run_station


def _run_station_thread() -> None:
    try:
        exit_code = run_station()
        logging.getLogger(__name__).info("Station thread exited with code %s", exit_code)
    except Exception:
        logging.getLogger(__name__).exception("Station thread crashed.")


def _run_with_app_lab() -> bool:
    """Start the station under Arduino App Lab when its runtime is available."""
    try:
        from arduino.app_utils import App
    except ImportError:
        return False

    print("Arduino App Lab runtime detected. Starting Smart Stretch Coach station.")
    station_thread = threading.Thread(
        target=_run_station_thread,
        name="smart-stretch-station",
        daemon=True,
    )
    station_thread.start()

    def heartbeat() -> None:
        if not station_thread.is_alive():
            print("Smart Stretch Coach station thread has stopped.")
        time.sleep(1.0)

    App.run(user_loop=heartbeat)
    return True


if __name__ == "__main__":
    if not _run_with_app_lab():
        sys.exit(run_station())
