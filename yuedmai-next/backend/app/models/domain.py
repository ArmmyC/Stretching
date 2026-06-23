from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


SessionState = Literal["idle", "ready", "active", "rest", "complete"]


@dataclass
class StretchSegment:
    name: str
    score: int = 0
    stars: int = 0
    feedback_tags: list[str] = field(default_factory=list)


@dataclass
class StretchSession:
    id: str
    routine: list[str]
    state: SessionState = "idle"
    current_index: int = 0
    total_score: int = 0
    xp_earned: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    segments: list[StretchSegment] = field(default_factory=list)


@dataclass(frozen=True)
class DailyQuest:
    code: str
    title: str
    target: int
    progress: int
    reward_xp: int
