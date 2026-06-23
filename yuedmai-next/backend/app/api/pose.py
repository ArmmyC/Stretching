from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.pose_service import pose_service

router = APIRouter(tags=["pose"])


@router.websocket("/ws/pose-stream")
async def pose_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            payload = await websocket.receive_json()
            result = pose_service.evaluate_frame(payload)
            await websocket.send_json(
                {
                    "signal": {
                        "visible": result.signal.visible,
                        "centered": result.signal.centered,
                        "confidence": result.signal.confidence,
                        "steady": result.signal.steady,
                        "hold_seconds": result.signal.hold_seconds,
                    },
                    "message": result.message,
                }
            )
    except WebSocketDisconnect:
        return
