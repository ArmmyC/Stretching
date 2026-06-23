from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NotificationPreference:
    enabled: bool
    reminder_time: str = "18:00"


class NotificationService:
    """Placeholder for PWA push subscriptions and scheduled reminders."""

    def preview_daily_reminder(self) -> dict[str, str]:
        return {
            "title": "Your stretch quest is ready",
            "body": "Complete a short YUEDMAI quest to keep your streak alive.",
        }


notification_service = NotificationService()
