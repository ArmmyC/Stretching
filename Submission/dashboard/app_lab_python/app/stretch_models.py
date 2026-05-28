from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

EPSILON = 1e-8
MIN_VISIBILITY = 0.25


@dataclass(frozen=True)
class HamstringParams:
    knee_good_deg: float = 160.0
    knee_bad_deg: float = 125.0
    fold_good_deg: float = 65.0
    fold_bad_deg: float = 125.0
    reach_good_leg_lengths: float = 0.35
    reach_bad_leg_lengths: float = 0.95


@dataclass(frozen=True)
class SideBendParams:
    overhead_good_widths: float = 0.75
    overhead_bad_widths: float = 0.10
    tilt_good_deg: float = 15.0
    tilt_bad_deg: float = 3.0
    elbow_good_deg: float = 150.0
    elbow_bad_deg: float = 105.0
    side_reach_good_widths: float = 0.28
    side_reach_bad_widths: float = 0.02


def evaluate_stretch_model(
    model_key: str | None,
    pose_metrics: dict[str, Any] | None,
    nano_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    landmarks = (pose_metrics or {}).get("landmarks") or {}
    if not model_key:
        return {"available": False, "model": None, "reason": "no_model_for_stretch"}
    if not landmarks:
        return {"available": False, "model": model_key, "reason": "no_pose_landmarks"}

    if model_key == "hamstring_reach":
        return score_hamstring_reach(landmarks, nano_metrics)
    if model_key == "side_bend":
        return score_side_bend(landmarks, nano_metrics)
    return {"available": False, "model": model_key, "reason": "unknown_model"}


def score_hamstring_reach(landmarks: dict[str, dict[str, float]], nano_metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    params = HamstringParams()
    points = _required_points(
        landmarks,
        (
            "left_shoulder",
            "right_shoulder",
            "left_wrist",
            "right_wrist",
            "left_hip",
            "right_hip",
            "left_knee",
            "right_knee",
            "left_ankle",
            "right_ankle",
        ),
    )
    if points is None:
        return {"available": False, "model": "hamstring_reach", "reason": "missing_lower_body_landmarks"}

    left_score, left_metrics = _score_hamstring_side(points, "left", params)
    right_score, right_metrics = _score_hamstring_side(points, "right", params)
    if left_score >= right_score:
        pose_score = left_score
        metrics = left_metrics
        metrics["active_side"] = "left"
    else:
        pose_score = right_score
        metrics = right_metrics
        metrics["active_side"] = "right"

    nano_score = _nano_stability_score(nano_metrics)
    final_score = _blend_with_nano(pose_score, nano_score, pose_weight=0.9)
    return {
        "available": True,
        "model": "hamstring_reach",
        "label": "Standing hamstring reach",
        "score": round(final_score, 1),
        "pose_score": round(pose_score, 1),
        "nano_score": round(nano_score, 1) if nano_score is not None else None,
        "success": final_score >= 75.0,
        "feedback": _feedback_from_score(final_score, "Reach toward the front ankle", "Good hamstring reach"),
        "metrics": _round_metrics(metrics),
    }


def score_side_bend(landmarks: dict[str, dict[str, float]], nano_metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    params = SideBendParams()
    points = _required_points(landmarks, ("left_shoulder", "right_shoulder", "left_hip", "right_hip"))
    if points is None:
        return {"available": False, "model": "side_bend", "reason": "missing_torso_landmarks"}

    left_shoulder = points["left_shoulder"]
    right_shoulder = points["right_shoulder"]
    left_hip = points["left_hip"]
    right_hip = points["right_hip"]
    shoulder_width = float(np.linalg.norm(left_shoulder[:2] - right_shoulder[:2]))
    if shoulder_width < EPSILON:
        return {"available": False, "model": "side_bend", "reason": "shoulders_too_close"}

    shoulder_mid = (left_shoulder + right_shoulder) / 2.0
    hip_mid = (left_hip + right_hip) / 2.0
    spine = shoulder_mid - hip_mid
    lateral_tilt = math.degrees(math.atan2(abs(float(spine[0])), max(abs(float(spine[1])), EPSILON)))
    bend_side = "left" if float(spine[0]) < 0.0 else "right"

    wrist_points = [point for point in (_point(landmarks, "left_wrist"), _point(landmarks, "right_wrist")) if point is not None]
    if not wrist_points:
        return {"available": False, "model": "side_bend", "reason": "missing_wrist_landmarks"}
    wrist_mid = np.mean(np.vstack(wrist_points), axis=0)

    overhead = (float(shoulder_mid[1]) - float(wrist_mid[1])) / shoulder_width
    side_reach = abs(float(wrist_mid[0] - shoulder_mid[0])) / shoulder_width
    reach_same_side = (float(wrist_mid[0] - shoulder_mid[0]) < 0.0 and bend_side == "left") or (
        float(wrist_mid[0] - shoulder_mid[0]) > 0.0 and bend_side == "right"
    )
    if not reach_same_side:
        side_reach *= 0.55

    elbow_angles: list[float] = []
    left_elbow = _point(landmarks, "left_elbow")
    left_wrist = _point(landmarks, "left_wrist")
    right_elbow = _point(landmarks, "right_elbow")
    right_wrist = _point(landmarks, "right_wrist")
    if left_elbow is not None and left_wrist is not None:
        elbow_angles.append(_angle_degrees(left_shoulder, left_elbow, left_wrist))
    if right_elbow is not None and right_wrist is not None:
        elbow_angles.append(_angle_degrees(right_shoulder, right_elbow, right_wrist))
    elbow_extension = float(np.nanmean(elbow_angles)) if elbow_angles else float("nan")

    overhead_score = _normalize_score(overhead, params.overhead_good_widths, params.overhead_bad_widths)
    tilt_score = _normalize_score(lateral_tilt, params.tilt_good_deg, params.tilt_bad_deg)
    elbow_score = _normalize_score(elbow_extension, params.elbow_good_deg, params.elbow_bad_deg)
    side_reach_score = _normalize_score(side_reach, params.side_reach_good_widths, params.side_reach_bad_widths)
    pose_score = (
        0.35 * overhead_score
        + 0.35 * tilt_score
        + 0.20 * elbow_score
        + 0.10 * side_reach_score
    )

    nano_arm_score = _nano_arm_raise_score(nano_metrics)
    nano_stability = _nano_stability_score(nano_metrics)
    nano_score = None
    if nano_arm_score is not None or nano_stability is not None:
        nano_score = _mean([value for value in (nano_arm_score, nano_stability) if value is not None])
    final_score = _blend_with_nano(pose_score, nano_score, pose_weight=0.78)

    return {
        "available": True,
        "model": "side_bend",
        "label": "Standing side bend",
        "score": round(final_score, 1),
        "pose_score": round(pose_score, 1),
        "nano_score": round(nano_score, 1) if nano_score is not None else None,
        "success": final_score >= 75.0,
        "feedback": _feedback_from_score(final_score, "Raise arms overhead and bend sideways", "Good side bend hold"),
        "metrics": _round_metrics(
            {
                "bend_side": bend_side,
                "overhead": overhead,
                "lateral_tilt": lateral_tilt,
                "elbow_extension": elbow_extension,
                "side_reach": side_reach,
                "reach_same_side": reach_same_side,
                "overhead_score": overhead_score,
                "tilt_score": tilt_score,
                "elbow_score": elbow_score,
                "side_reach_score": side_reach_score,
                "nano_arm_score": nano_arm_score,
                "nano_stability_score": nano_stability,
            }
        ),
    }


def _score_hamstring_side(points: dict[str, np.ndarray], side: str, params: HamstringParams) -> tuple[float, dict[str, Any]]:
    left_hip = points["left_hip"]
    right_hip = points["right_hip"]
    left_knee = points["left_knee"]
    right_knee = points["right_knee"]
    left_ankle = points["left_ankle"]
    right_ankle = points["right_ankle"]
    shoulder_mid = (points["left_shoulder"] + points["right_shoulder"]) / 2.0
    hip_mid = (left_hip + right_hip) / 2.0
    wrist_mid = (points["left_wrist"] + points["right_wrist"]) / 2.0

    if side == "left":
        front_hip, front_knee, front_ankle = left_hip, left_knee, left_ankle
        rear_hip, rear_knee, rear_ankle = right_hip, right_knee, right_ankle
    else:
        front_hip, front_knee, front_ankle = right_hip, right_knee, right_ankle
        rear_hip, rear_knee, rear_ankle = left_hip, left_knee, left_ankle

    front_knee_angle = _angle_degrees(front_hip, front_knee, front_ankle)
    rear_knee_angle = _angle_degrees(rear_hip, rear_knee, rear_ankle)
    hip_fold_angle = _angle_degrees(shoulder_mid, hip_mid, front_knee)
    leg_length = _mean(
        [
            _distance(front_hip, front_knee) + _distance(front_knee, front_ankle),
            _distance(rear_hip, rear_knee) + _distance(rear_knee, rear_ankle),
        ]
    )
    reach_distance = _distance(wrist_mid, front_ankle) / max(leg_length, EPSILON)

    knee_score = _normalize_score(front_knee_angle, params.knee_good_deg, params.knee_bad_deg)
    fold_score = _normalize_score(hip_fold_angle, params.fold_good_deg, params.fold_bad_deg, higher_is_better=False)
    reach_score = _normalize_score(
        reach_distance,
        params.reach_good_leg_lengths,
        params.reach_bad_leg_lengths,
        higher_is_better=False,
    )
    total = 0.35 * knee_score + 0.35 * fold_score + 0.30 * reach_score
    return float(np.clip(total, 0.0, 100.0)), {
        "side": side,
        "front_knee_angle": front_knee_angle,
        "rear_knee_angle": rear_knee_angle,
        "hip_fold_angle": hip_fold_angle,
        "reach_distance": reach_distance,
        "knee_score": knee_score,
        "fold_score": fold_score,
        "reach_score": reach_score,
    }


def _required_points(landmarks: dict[str, dict[str, float]], names: tuple[str, ...]) -> dict[str, np.ndarray] | None:
    points: dict[str, np.ndarray] = {}
    for name in names:
        landmark = _point(landmarks, name)
        if landmark is None:
            return None
        points[name] = landmark
    return points


def _point(landmarks: dict[str, dict[str, float]], name: str) -> np.ndarray | None:
    landmark = landmarks.get(name)
    if not landmark:
        return None
    if float(landmark.get("visibility", 0.0)) < MIN_VISIBILITY:
        return None
    return np.asarray(
        [float(landmark.get("x", 0.0)), float(landmark.get("y", 0.0)), float(landmark.get("z", 0.0))],
        dtype=np.float32,
    )


def _angle_degrees(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    v1 = a - b
    v2 = c - b
    denom = float(np.linalg.norm(v1) * np.linalg.norm(v2))
    if denom < EPSILON:
        return float("nan")
    cos_theta = float(np.dot(v1, v2) / denom)
    return math.degrees(math.acos(float(np.clip(cos_theta, -1.0, 1.0))))


def _distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


def _normalize_score(value: float, good: float, bad: float, higher_is_better: bool = True) -> float:
    if not np.isfinite(value):
        return 0.0
    if higher_is_better:
        return 100.0 * _clamp01((value - bad) / max(good - bad, EPSILON))
    return 100.0 * _clamp01((bad - value) / max(bad - good, EPSILON))


def _nano_arm_raise_score(nano_metrics: dict[str, Any] | None) -> float | None:
    if not nano_metrics or not nano_metrics.get("fresh"):
        return None
    az = _safe_float(nano_metrics.get("az"))
    roll = _safe_float(nano_metrics.get("roll"))
    relative_pitch = _safe_float(nano_metrics.get("relative_pitch"))
    scores: list[float] = []
    if az is not None:
        scores.append(_normalize_score(-az, 0.55, 0.10))
    if roll is not None:
        scores.append(_normalize_score(abs(roll), 75.0, 25.0))
    if relative_pitch is not None:
        scores.append(_normalize_score(abs(relative_pitch), 55.0, 20.0))
    if nano_metrics.get("arm_raised") is True:
        scores.append(100.0)
    return _mean(scores) if scores else None


def _nano_stability_score(nano_metrics: dict[str, Any] | None) -> float | None:
    if not nano_metrics or not nano_metrics.get("fresh"):
        return None
    explicit = _safe_float(nano_metrics.get("stability_score"))
    if explicit is not None:
        return float(np.clip(explicit, 0.0, 100.0))
    gyro_mag = _safe_float(nano_metrics.get("gyro_mag"))
    if gyro_mag is not None:
        return 100.0 * _clamp01((35.0 - gyro_mag) / 35.0)
    if nano_metrics.get("stable") is True:
        return 100.0
    if nano_metrics.get("stable") is False:
        return 35.0
    return None


def _blend_with_nano(pose_score: float, nano_score: float | None, pose_weight: float) -> float:
    if nano_score is None:
        return float(np.clip(pose_score, 0.0, 100.0))
    return float(np.clip(pose_weight * pose_score + (1.0 - pose_weight) * nano_score, 0.0, 100.0))


def _feedback_from_score(score: float, low_text: str, high_text: str) -> str:
    if score >= 75.0:
        return high_text
    if score >= 55.0:
        return "Keep steady"
    return low_text


def _round_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    rounded: dict[str, Any] = {}
    for key, value in metrics.items():
        if isinstance(value, (float, np.floating)):
            rounded[key] = None if not np.isfinite(value) else round(float(value), 3)
        else:
            rounded[key] = value
    return rounded


def _safe_float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _clamp01(value: float) -> float:
    return float(np.clip(value, 0.0, 1.0))


def _mean(values: list[float]) -> float:
    finite = [float(value) for value in values if np.isfinite(value)]
    return float(np.mean(finite)) if finite else 0.0
