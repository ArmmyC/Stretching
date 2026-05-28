from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
import time
from typing import Any

logger = logging.getLogger(__name__)

try:
    from bleak import BleakClient, BleakScanner
except Exception:  # pragma: no cover - optional on UNO Q image.
    BleakClient = None  # type: ignore[assignment]
    BleakScanner = None  # type: ignore[assignment]


NANO_BLE_ENABLED = os.getenv("NANO_BLE_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
NANO_BLE_NAME = os.getenv("NANO_BLE_NAME", "YUEDMAI-NanoIMU")
NANO_BLE_SERVICE_UUID = os.getenv("NANO_BLE_SERVICE_UUID", "19b10000-e8f2-537e-4f6c-d104768a1214")
NANO_BLE_IMU_CHAR_UUID = os.getenv("NANO_BLE_IMU_CHAR_UUID", "19b10001-e8f2-537e-4f6c-d104768a1214")
NANO_BLE_SCAN_TIMEOUT_SEC = float(os.getenv("NANO_BLE_SCAN_TIMEOUT_SEC", "5"))
NANO_BLE_RETRY_SEC = float(os.getenv("NANO_BLE_RETRY_SEC", "3"))
BLUEZ_SYSTEM_BUS_SOCKET = Path(os.getenv("DBUS_SYSTEM_BUS_SOCKET", "/run/dbus/system_bus_socket"))


class NanoBleManager:
    def __init__(self) -> None:
        self.enabled = bool(NANO_BLE_ENABLED)
        self.available = BleakClient is not None and BleakScanner is not None
        self.bridge: Any = None
        self._task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event | None = None
        self._state = "stopped"
        self._device_address = ""
        self._last_error = ""
        self._last_packet_at: float | None = None

    def start(self, bridge: Any) -> None:
        self.bridge = bridge
        if self._task and not self._task.done():
            return
        if not self.enabled:
            self._state = "disabled"
            logger.info("Nano BLE disabled by NANO_BLE_ENABLED=false.")
            return
        if not self.available:
            self._state = "missing_bleak"
            logger.warning("Nano BLE unavailable; install bleak to enable Python BLE subscription.")
            return
        if not BLUEZ_SYSTEM_BUS_SOCKET.exists() and not os.getenv("DBUS_SYSTEM_BUS_ADDRESS"):
            self._state = "missing_dbus"
            self._last_error = f"BlueZ D-Bus socket not visible at {BLUEZ_SYSTEM_BUS_SOCKET}."
            logger.warning("Nano BLE unavailable: %s", self._last_error)
            return

        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._run(), name="nano-ble-manager")
        logger.info("Nano BLE manager started.")

    async def stop(self) -> None:
        if self._stop_event:
            self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self._state = "stopped"

    def status(self) -> dict[str, Any]:
        age = None
        if self._last_packet_at is not None:
            age = round(max(0.0, time.time() - self._last_packet_at), 2)
        return {
            "enabled": self.enabled,
            "available": self.available,
            "state": self._state,
            "device_name": NANO_BLE_NAME,
            "device_address": self._device_address,
            "last_packet_age_sec": age,
            "last_error": self._last_error,
        }

    async def _run(self) -> None:
        assert self._stop_event is not None
        while not self._stop_event.is_set():
            try:
                device = await self._find_device()
                if device is None:
                    await asyncio.sleep(NANO_BLE_RETRY_SEC)
                    continue
                await self._connect_and_subscribe(device)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self._state = "error"
                self._last_error = str(error)
                logger.exception("Nano BLE loop error.")
                await asyncio.sleep(NANO_BLE_RETRY_SEC)

    async def _find_device(self) -> Any | None:
        assert BleakScanner is not None
        self._state = "scanning"
        self._last_error = ""
        logger.info("Scanning for Nano BLE device name=%s service=%s", NANO_BLE_NAME, NANO_BLE_SERVICE_UUID)
        devices = await BleakScanner.discover(timeout=NANO_BLE_SCAN_TIMEOUT_SEC, service_uuids=[NANO_BLE_SERVICE_UUID])
        for device in devices:
            name = device.name or ""
            details_name = str(getattr(device, "metadata", {}).get("local_name") or "")
            if name == NANO_BLE_NAME or details_name == NANO_BLE_NAME:
                self._device_address = str(device.address)
                logger.info("Found Nano BLE device address=%s name=%s", device.address, name or details_name)
                return device

        # Some BLE stacks omit service UUIDs in discovery results, so retry by name.
        devices = await BleakScanner.discover(timeout=NANO_BLE_SCAN_TIMEOUT_SEC)
        for device in devices:
            name = device.name or ""
            details_name = str(getattr(device, "metadata", {}).get("local_name") or "")
            if name == NANO_BLE_NAME or details_name == NANO_BLE_NAME:
                self._device_address = str(device.address)
                logger.info("Found Nano BLE device by name address=%s", device.address)
                return device

        self._last_error = f"Nano BLE device '{NANO_BLE_NAME}' not found."
        logger.info(self._last_error)
        return None

    async def _connect_and_subscribe(self, device: Any) -> None:
        assert BleakClient is not None
        assert self._stop_event is not None

        self._state = "connecting"
        async with BleakClient(device) as client:
            self._state = "connected"
            self._device_address = str(device.address)
            logger.info("Connected to Nano BLE address=%s", self._device_address)

            def handle_packet(_: int, data: bytearray) -> None:
                text = bytes(data).decode("utf-8", errors="ignore").strip("\x00\r\n ")
                if not text:
                    return
                self._last_packet_at = time.time()
                if self.bridge is not None:
                    self.bridge.publish_nano_imu(text, source="python_ble")

            await client.start_notify(NANO_BLE_IMU_CHAR_UUID, handle_packet)
            self._state = "subscribed"
            logger.info("Subscribed to Nano IMU characteristic.")

            while not self._stop_event.is_set() and client.is_connected:
                await asyncio.sleep(0.5)

            try:
                await client.stop_notify(NANO_BLE_IMU_CHAR_UUID)
            except Exception:
                pass
        self._state = "disconnected"


nano_ble_manager = NanoBleManager()
