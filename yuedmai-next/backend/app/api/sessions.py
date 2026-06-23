from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.domain import StretchSession
from app.services.quest_engine import completed_quest_codes
from app.services.scoring import PoseSignal
from app.services.session_engine import session_engine

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    routine: list[str] | None = None


class PoseScoreRequest(BaseModel):
    visible: bool = True
    centered: bool = True
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    steady: bool = True
    hold_seconds: float = Field(default=0.0, ge=0.0)


@router.post("")
def create_session(payload: CreateSessionRequest) -> StretchSession:
    return session_engine.create_session(payload.routine)


@router.get("/{session_id}")
def get_session(session_id: str) -> StretchSession:
    session = session_engine.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/{session_id}/score")
def score_session(session_id: str, payload: PoseScoreRequest) -> StretchSession:
    session = session_engine.score_current(session_id, PoseSignal(**payload.model_dump()))
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/{session_id}/advance")
def advance_session(session_id: str) -> dict:
    session = session_engine.advance(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session": session,
        "completed_quests": completed_quest_codes(session),
    }
