#!/bin/sh
set -eu

APP_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$APP_DIR"

if [ ! -f ".venv-mediapipe/bin/activate" ]; then
  echo "Missing .venv-mediapipe. Create it before running MediaPipe." >&2
  exit 1
fi

. .venv-mediapipe/bin/activate

fuser -k 8000/tcp 2>/dev/null || true

export PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-http://100.85.1.123:8000}"
export POSE_BACKEND="${POSE_BACKEND:-mediapipe}"
export POSE_FALLBACK_BACKEND="${POSE_FALLBACK_BACKEND:-none}"
export POSE_DELEGATE="${POSE_DELEGATE:-cpu}"
export POSE_ASYNC_ENABLED="${POSE_ASYNC_ENABLED:-true}"
export POSE_MAX_ASYNC_FPS="${POSE_MAX_ASYNC_FPS:-4}"
export POSE_INFERENCE_WIDTH="${POSE_INFERENCE_WIDTH:-192}"
export POSE_FRAME_STRIDE="${POSE_FRAME_STRIDE:-1}"

python main.py
