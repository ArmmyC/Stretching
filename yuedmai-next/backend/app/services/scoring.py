from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PoseSignal:
    visible: bool
    centered: bool
    confidence: float
    steady: bool
    hold_seconds: float


def score_pose(signal: PoseSignal) -> tuple[int, int, list[str]]:
    """Score consistency and safe visibility rather than body shape or flexibility."""
    score = 40
    tags: list[str] = []

    if signal.visible:
        score += 20
    else:
        tags.append("step into frame")

    if signal.centered:
        score += 12
    else:
        tags.append("center your body")

    if signal.confidence >= 0.65:
        score += 12
    elif signal.confidence < 0.35:
        tags.append("improve lighting")

    if signal.steady:
        score += 10
    else:
        tags.append("hold steady")

    score += min(6, int(max(0.0, signal.hold_seconds) // 5))
    score = max(0, min(100, score))

    stars = 3 if score >= 85 else 2 if score >= 65 else 1 if score >= 40 else 0
    return score, stars, tags


def xp_from_session(total_score: int, completed_segments: int, completed: bool) -> int:
    base = completed_segments * 20
    score_bonus = max(0, min(80, total_score // max(1, completed_segments * 2)))
    completion_bonus = 50 if completed else 0
    return base + score_bonus + completion_bonus
