from __future__ import annotations

from fastapi import APIRouter

from app.models.domain import DailyQuest
from app.services.quest_engine import daily_quests_for_user

router = APIRouter(prefix="/api/quests", tags=["quests"])


@router.get("/daily")
def get_daily_quests() -> list[DailyQuest]:
    return daily_quests_for_user("demo")
