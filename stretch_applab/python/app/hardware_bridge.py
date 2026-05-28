from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

try:
    from arduino.app_utils import Bridge as ArduinoBridge
except Exception:  # pragma: no cover - only available on UNO Q App Lab.
    ArduinoBridge = None  # type: ignore[assignment]


ACTION_ALIASES = {
    "KNOB_LEFT": "PREV",
    "KNOB_RIGHT": "NEXT",
    "KNOB_PRESS": "CONFIRM",
    "KNOB_PRESS_LONG": "CONFIRM_LONG",
    "BUTTON_A": "CONFIRM",
    "BUTTON_B": "BACK",
    "BUTTON_C": "ALT",
    "BUTTON_A_LONG": "CONFIRM_LONG",
    "BUTTON_B_LONG": "BACK_LONG",
    "BUTTON_C_LONG": "ALT_LONG",
}


class HardwareBridge:
    """UNO Q Bridge event fanout for the kiosk web pages."""

    def __init__(self) -> None:
        self.available = ArduinoBridge is not None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._clients: set[asyncio.Queue[dict[str, Any]]] = set()
        self._history: deque[dict[str, Any]] = deque(maxlen=80)
        self._next_id = 0
        self._last_feedback: dict[str, Any] = {}
        self._last_nano_imu: dict[str, Any] = {}

    def start(self) -> None:
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

        if not self.available:
            logger.info("UNO Q hardware bridge unavailable in this Python environment.")
            return

        try:
            ArduinoBridge.provide("hardware_event", self._bridge_hardware_event)
            logger.info("UNO Q hardware bridge registered hardware_event callback.")
            ArduinoBridge.provide("nano_imu", self._bridge_nano_imu)
            logger.info("UNO Q hardware bridge registered nano_imu callback.")
        except Exception:
            logger.exception("UNO Q hardware bridge callback registration failed.")

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=30)
        self._clients.add(queue)
        try:
            await websocket.send_json({"type": "hardware_status", "hardware": self.status()})
            while True:
                event = await queue.get()
                try:
                    await websocket.send_json(event)
                except WebSocketDisconnect:
                    break
                except Exception:
                    logger.info("Hardware WebSocket client disconnected while sending event.")
                    break
        finally:
            self._clients.discard(queue)

    def status(self) -> dict[str, Any]:
        return {
            "bridge_available": self.available,
            "client_count": len(self._clients),
            "last_event_id": self._next_id - 1,
            "last_feedback": self._last_feedback,
            "last_nano_imu": self.latest_nano_imu(),
        }

    def feedback(self, payload: dict[str, Any]) -> dict[str, Any]:
        clean = self._clean_feedback(payload)
        self._last_feedback = clean
        if self.available:
            try:
                ArduinoBridge.call(
                    "set_feedback",
                    clean["page"],
                    clean["state"],
                    clean["selection"],
                    int(clean["value"]),
                )
            except Exception:
                logger.exception("UNO Q hardware feedback call failed.")
        return {"ok": True, "hardware": self.status()}

    def publish(self, raw_action: str, value: int = 0, source: str = "bridge") -> dict[str, Any]:
        raw = str(raw_action or "").strip().upper()
        action = ACTION_ALIASES.get(raw, raw)
        self._next_id += 1
        event = {
            "type": "hardware_event",
            "id": self._next_id,
            "action": action,
            "raw_action": raw,
            "value": int(value or 0),
            "source": source,
            "timestamp": time.time(),
        }
        self._history.append(event)
        logger.info(
            "UNO Q hardware event raw=%s action=%s value=%s clients=%s",
            raw,
            action,
            event["value"],
            len(self._clients),
        )
        self._fanout(event)
        return event

    def publish_nano_imu(self, payload: str | dict[str, Any], source: str = "uno_q_ble") -> dict[str, Any]:
        self._next_id += 1
        nano = self._clean_nano_imu(payload)
        nano["received_at"] = time.time()
        self._last_nano_imu = nano
        event = {
            "type": "nano_imu",
            "id": self._next_id,
            "source": source,
            "nano_imu": nano,
            "timestamp": nano["received_at"],
        }
        self._history.append(event)
        logger.info(
            "Nano IMU update state=%s stable=%s arm=%s angle=%s score=%s clients=%s",
            nano.get("state"),
            nano.get("stable"),
            nano.get("arm_raised"),
            nano.get("relative_pitch"),
            nano.get("stability_score"),
            len(self._clients),
        )
        self._fanout(event)
        return event

    def latest_nano_imu(self) -> dict[str, Any]:
        nano = dict(self._last_nano_imu)
        received_at = nano.get("received_at")
        if isinstance(received_at, (int, float)):
            nano["age_sec"] = round(max(0.0, time.time() - float(received_at)), 2)
            nano["fresh"] = nano["age_sec"] <= 2.0
        else:
            nano["fresh"] = False
        return nano

    def _bridge_hardware_event(self, action: str, value: int = 0) -> str:
        if isinstance(action, str) and action.strip().startswith("{"):
            try:
                payload = json.loads(action)
                self.publish(
                    str(payload.get("action") or ""),
                    value=int(float(payload.get("value") or 0)),
                    source="uno_q",
                )
                return "ok"
            except (TypeError, ValueError, json.JSONDecodeError):
                logger.warning("Invalid hardware_event payload: %s", action[:160])
        self.publish(action, value=value, source="uno_q")
        return "ok"

    def _bridge_nano_imu(self, payload: str) -> str:
        self.publish_nano_imu(payload, source="uno_q_ble")
        return "ok"

    def _fanout(self, event: dict[str, Any]) -> None:
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._queue_event, event)
        else:
            self._queue_event(event)

    def _queue_event(self, event: dict[str, Any]) -> None:
        for queue in list(self._clients):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    @staticmethod
    def _clean_feedback(payload: dict[str, Any]) -> dict[str, Any]:
        def short(value: Any, default: str = "") -> str:
            text = str(value if value is not None else default)
            return text[:32]

        return {
            "page": short(payload.get("page"), "unknown"),
            "state": short(payload.get("state"), ""),
            "selection": short(payload.get("selection"), ""),
            "value": max(0, min(100, int(float(payload.get("value") or 0)))),
        }

    @staticmethod
    def _clean_nano_imu(payload: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(payload, str):
            try:
                raw: dict[str, Any] = json.loads(payload)
            except json.JSONDecodeError:
                logger.warning("Invalid nano_imu payload: %s", payload[:160])
                raw = {"raw": payload[:220], "valid": False}
        else:
            raw = dict(payload)

        def maybe_float(name: str) -> float | None:
            try:
                value = raw.get(name)
                return None if value is None else round(float(value), 3)
            except (TypeError, ValueError):
                return None

        def maybe_bool(name: str) -> bool | None:
            value = raw.get(name)
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {"1", "true", "yes", "on"}:
                    return True
                if lowered in {"0", "false", "no", "off"}:
                    return False
            return None

        cleaned: dict[str, Any] = {
            "valid": bool(raw.get("valid", True)),
            "state": str(raw.get("state") or "")[:32],
            "t": maybe_float("t"),
            "ax": maybe_float("ax"),
            "ay": maybe_float("ay"),
            "az": maybe_float("az"),
            "gx": maybe_float("gx"),
            "gy": maybe_float("gy"),
            "gz": maybe_float("gz"),
            "roll": maybe_float("roll"),
            "pitch": maybe_float("pitch"),
            "relative_pitch": maybe_float("relative_pitch"),
            "gyro_mag": maybe_float("gyro_mag"),
            "gyro_avg": maybe_float("gyro_avg"),
            "stability_score": maybe_float("stability_score"),
            "arm_threshold": maybe_float("arm_threshold"),
            "stability_threshold": maybe_float("stability_threshold"),
            "mx": maybe_float("mx"),
            "my": maybe_float("my"),
            "mz": maybe_float("mz"),
            "heading_deg": maybe_float("heading_deg"),
            "mag_mag": maybe_float("mag_mag"),
            "proximity": maybe_float("proximity"),
            "red": maybe_float("red"),
            "green": maybe_float("green"),
            "blue": maybe_float("blue"),
            "ambient": maybe_float("ambient"),
            "gesture_code": maybe_float("gesture_code"),
            "pressure_kpa": maybe_float("pressure_kpa"),
            "pressure_hpa": maybe_float("pressure_hpa"),
            "temperature_c": maybe_float("temperature_c"),
            "humidity": maybe_float("humidity"),
            "mic_rms": maybe_float("mic_rms"),
            "mic_peak": maybe_float("mic_peak"),
            "mic_avg_abs": maybe_float("mic_avg_abs"),
            "mic_dbfs": maybe_float("mic_dbfs"),
            "mic_level": maybe_float("mic_level"),
            "mic_samples": maybe_float("mic_samples"),
            "state_code": maybe_float("state_code"),
            "gesture": str(raw.get("gesture") or "")[:24],
            "arm_raised": maybe_bool("arm_raised"),
            "stable": maybe_bool("stable"),
            "mag_ok": maybe_bool("mag_ok"),
            "apds_ok": maybe_bool("apds_ok"),
            "baro_ok": maybe_bool("baro_ok"),
            "env_ok": maybe_bool("env_ok"),
            "mic_ok": maybe_bool("mic_ok"),
        }
        return {key: value for key, value in cleaned.items() if value is not None}


hardware_bridge = HardwareBridge()
