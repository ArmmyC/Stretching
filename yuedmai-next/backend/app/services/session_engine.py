from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.models.domain import StretchSegment, StretchSession
from app.services.scoring import PoseSignal, score_pose, xp_from_session


DEFAULT_ROUTINE = [
    "Neck reset",
    "Shoulder opener",
    "Standing side bend",
    "Hamstring reach",
]


class SessionEngine:
    """In-memory starter engine. Replace with database-backed service after v1 proof of concept."""

    def __init__(self) -> None:
        self._sessions: dict[str, StretchSession] = {}

    def create_session(self, routine: list[str] | None = None) -> StretchSession:
        names = routine or DEFAULT_ROUTINE
        session = StretchSession(
            id=uuid.uuid4().hex[:12],
            routine=names,
            state="ready",
            segments=[StretchSegment(name=name) for name in names],
        )
        self._sessions[session.id] = session
        return session

    def get_session(self, session_id: str) -> StretchSession | None:
        return self._sessions.get(session_id)

    def score_current(self, session_id: str, signal: PoseSignal) -> StretchSession | None:
        session = self._sessions.get(session_id)
        if session is None or session.state == "complete":
            return session

        session.state = "active"
        segment = session.segments[session.current_index]
        score, stars, tags = score_pose(signal)
        segment.score = max(segment.score, score)
        segment.stars = max(segment.stars, stars)
        segment.feedback_tags = tags
        session.total_score = sum(item.score for item in session.segments)
        return session

    def advance(self, session_id: str) -> StretchSession | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None

        if session.current_index >= len(session.routine) - 1:
            session.state = "complete"
            session.completed_at = datetime.now(timezone.utc)
            session.xp_earned = xp_from_session(
                total_score=session.total_score,
                completed_segments=len(session.segments),
                completed=True,
            )
            return session

        session.current_index += 1
        session.state = "ready"
        return session


session_engine = SessionEngine()
