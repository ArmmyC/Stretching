from __future__ import annotations

from app.models.domain import DailyQuest, StretchSession


def daily_quests_for_user(user_id: str = "demo") -> list[DailyQuest]:
    """Demo quest list. Replace with persisted per-user quests later."""
    return [
        DailyQuest(
            code="daily_3min",
            title="Complete one 3-minute stretch quest",
            target=1,
            progress=0,
            reward_xp=80,
        ),
        DailyQuest(
            code="steady_hold",
            title="Earn 2 stars on any stretch",
            target=1,
            progress=0,
            reward_xp=40,
        ),
    ]


def completed_quest_codes(session: StretchSession) -> list[str]:
    codes: list[str] = []
    if session.state == "complete":
        codes.append("daily_3min")
    if any(segment.stars >= 2 for segment in session.segments):
        codes.append("steady_hold")
    return codes
