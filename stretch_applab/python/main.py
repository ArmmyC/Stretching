from __future__ import annotations

import logging
import os
import threading
import time

import uvicorn

APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))


def _run_uvicorn() -> None:
    logging.getLogger(__name__).info("Starting StretchSense FastAPI server on %s:%s", APP_HOST, APP_PORT)
    uvicorn.run("app.main:app", host=APP_HOST, port=APP_PORT, log_level="info")


def _run_with_app_lab() -> bool:
    try:
        from arduino.app_utils import App
    except ImportError:
        return False

    print(f"StretchSense App Lab launcher starting server on http://{APP_HOST}:{APP_PORT}")
    server_thread = threading.Thread(target=_run_uvicorn, name="stretchsense-fastapi", daemon=True)
    server_thread.start()

    def heartbeat() -> None:
        if not server_thread.is_alive():
            print("StretchSense FastAPI server stopped.")
        time.sleep(1.0)

    App.run(user_loop=heartbeat)
    return True


if __name__ == "__main__":
    if not _run_with_app_lab():
        _run_uvicorn()
