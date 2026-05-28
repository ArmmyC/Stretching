from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Any

from fastapi import WebSocket

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
                await websocket.send_json(event)
        finally:
            self._clients.discard(queue)

    def status(self) -> dict[str, Any]:
        return {
            "bridge_available": self.available,
            "client_count": len(self._clients),
            "last_event_id": self._next_id - 1,
            "last_feedback": self._last_feedback,
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

    def _bridge_hardware_event(self, action: str, value: int = 0) -> str:
        self.publish(action, value=value, source="uno_q")
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


hardware_bridge = HardwareBridge()
