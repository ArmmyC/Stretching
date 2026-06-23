from __future__ import annotations

from fastapi import APIRouter

from app.services.notification_service import notification_service

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/preview")
def preview_notification() -> dict[str, str]:
    return notification_service.preview_daily_reminder()
