from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_MOVENET_MODEL_PATH = "models/movenet_lightning.tflite"
DEFAULT_MOVENET_INPUT_SIZE = 192
DEFAULT_MOVENET_NUM_THREADS = 2

COCO_TO_YUEDMAI = {
    5: "left_shoulder",
    6: "right_shoulder",
    7: "left_elbow",
    8: "right_elbow",
    9: "left_wrist",
    10: "right_wrist",
    11: "left_hip",
    12: "right_hip",
    13: "left_knee",
    14: "right_knee",
    15: "left_ankle",
    16: "right_ankle",
}


@dataclass
class LetterboxInfo:
    scale: float
    pad_x: int
    pad_y: int
    target_size: int
    source_width: int
    source_height: int


class MoveNetPose:
    """MoveNet SinglePose through a TensorFlow Lite/LiteRT interpreter."""

    def __init__(
        self,
        model_path: str | Path,
        input_size: int | None = None,
        num_threads: int = DEFAULT_MOVENET_NUM_THREADS,
    ):
        self.model_path = Path(model_path).expanduser()
        self.input_size_override = int(input_size or 0)
        self.num_threads = int(num_threads)
        self.runtime_name = "none"
        self.input_size = int(input_size or DEFAULT_MOVENET_INPUT_SIZE)
        self.input_details: list[dict[str, Any]] = []
        self.output_details: list[dict[str, Any]] = []
        self.output_shapes: dict[str, tuple[int, ...]] = {}
        self._interpreter: Any = None

    def load(self) -> None:
        if not self.model_path.exists():
            raise FileNotFoundError(f"MoveNet model missing: {self.model_path}")

        interpreter_class, runtime_name = _load_interpreter_class()
        try:
            interpreter = interpreter_class(model_path=str(self.model_path), num_threads=self.num_threads)
        except TypeError:
            interpreter = interpreter_class(model_path=str(self.model_path))

        interpreter.allocate_tensors()
        self._interpreter = interpreter
        self.runtime_name = runtime_name
        self.input_details = interpreter.get_input_details()
        self.output_details = interpreter.get_output_details()
        self.input_size = self._resolve_input_size()
        logger.info(
            "MoveNet model loaded. path=%s runtime=%s input_size=%s num_threads=%s",
            self.model_path,
            self.runtime_name,
            self.input_size,
            self.num_threads,
        )

    def detect(self, frame_bgr: np.ndarray) -> tuple[dict[str, dict[str, float]], float]:
        if self._interpreter is None:
            raise RuntimeError("MoveNet model is not loaded.")

        input_image, letterbox = _letterbox(frame_bgr, self.input_size)
        input_tensor = self._prepare_input(input_image)
        input_index = self.input_details[0]["index"]
        self._interpreter.set_tensor(input_index, input_tensor)
        self._interpreter.invoke()

        outputs = []
        for output_detail in self.output_details:
            output = self._interpreter.get_tensor(output_detail["index"])
            output = _dequantize_output(output, output_detail)
            outputs.append(output)
            self.output_shapes[output_detail.get("name", f"out{len(outputs)-1}")] = tuple(output.shape)

        keypoints = _find_keypoints(outputs)
        if keypoints is None:
            logger.warning("Unsupported MoveNet output shapes: %s", self.output_shapes)
            return {}, 0.0

        landmarks = _keypoints_to_landmarks(keypoints, letterbox)
        confidence = float(np.mean(keypoints[:, 2])) if keypoints.size else 0.0
        return landmarks, confidence

    def _resolve_input_size(self) -> int:
        if self.input_size_override > 0:
            return self.input_size_override
        if not self.input_details:
            return DEFAULT_MOVENET_INPUT_SIZE
        shape = self.input_details[0].get("shape")
        if shape is None or len(shape) < 3:
            return DEFAULT_MOVENET_INPUT_SIZE
        height = int(shape[1])
        width = int(shape[2])
        if height > 0 and width > 0 and height == width:
            return height
        return DEFAULT_MOVENET_INPUT_SIZE

    def _prepare_input(self, image_bgr: np.ndarray) -> np.ndarray:
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        input_detail = self.input_details[0]
        dtype = input_detail.get("dtype", np.float32)
        tensor = np.expand_dims(rgb, axis=0)

        if dtype == np.float32:
            return tensor.astype(np.float32) / 255.0
        if dtype == np.int32:
            return tensor.astype(np.int32)
        if dtype == np.uint8:
            return tensor.astype(np.uint8)
        if dtype == np.int8:
            scale, zero_point = input_detail.get("quantization", (0.0, 0))
            scale = scale or 1.0
            quantized = np.round(tensor.astype(np.float32) / scale + zero_point)
            return np.clip(quantized, -128, 127).astype(np.int8)
        return tensor.astype(dtype)


def _letterbox(frame_bgr: np.ndarray, target_size: int) -> tuple[np.ndarray, LetterboxInfo]:
    h, w = frame_bgr.shape[:2]
    scale = min(target_size / float(w), target_size / float(h))
    resized_w = max(1, int(round(w * scale)))
    resized_h = max(1, int(round(h * scale)))
    resized = cv2.resize(frame_bgr, (resized_w, resized_h), interpolation=cv2.INTER_AREA)

    canvas = np.zeros((target_size, target_size, 3), dtype=np.uint8)
    pad_x = (target_size - resized_w) // 2
    pad_y = (target_size - resized_h) // 2
    canvas[pad_y : pad_y + resized_h, pad_x : pad_x + resized_w] = resized
    return canvas, LetterboxInfo(
        scale=scale,
        pad_x=pad_x,
        pad_y=pad_y,
        target_size=target_size,
        source_width=w,
        source_height=h,
    )


def _find_keypoints(outputs: list[np.ndarray]) -> np.ndarray | None:
    for output in outputs:
        arr = np.asarray(output, dtype=np.float32)
        arr = np.squeeze(arr)
        if arr.shape == (17, 3):
            return arr
        if arr.size >= 51:
            candidate = arr.reshape(-1, 17, 3)[0]
            return candidate.astype(np.float32)
    return None


def _keypoints_to_landmarks(
    keypoints: np.ndarray,
    letterbox: LetterboxInfo,
) -> dict[str, dict[str, float]]:
    landmarks: dict[str, dict[str, float]] = {}
    for coco_index, name in COCO_TO_YUEDMAI.items():
        y_model, x_model, score = keypoints[coco_index]
        x_letterboxed = float(x_model) * letterbox.target_size
        y_letterboxed = float(y_model) * letterbox.target_size
        x_source = (x_letterboxed - letterbox.pad_x) / max(letterbox.scale, 1e-6)
        y_source = (y_letterboxed - letterbox.pad_y) / max(letterbox.scale, 1e-6)
        landmarks[name] = {
            "x": float(np.clip(x_source / max(letterbox.source_width, 1), 0.0, 1.0)),
            "y": float(np.clip(y_source / max(letterbox.source_height, 1), 0.0, 1.0)),
            "z": 0.0,
            "visibility": float(np.clip(score, 0.0, 1.0)),
        }
    return landmarks


def _dequantize_output(output: np.ndarray, output_detail: dict[str, Any]) -> np.ndarray:
    dtype = output_detail.get("dtype")
    if dtype in (np.float32, np.float64):
        return output
    scale, zero_point = output_detail.get("quantization", (0.0, 0))
    if not scale:
        return output
    return (output.astype(np.float32) - zero_point) * scale


def _load_interpreter_class() -> tuple[Any, str]:
    try:
        from ai_edge_litert.interpreter import Interpreter

        return Interpreter, "ai_edge_litert"
    except Exception as exc:
        litert_error = exc

    try:
        from tflite_runtime.interpreter import Interpreter

        return Interpreter, "tflite_runtime"
    except Exception as exc:
        tflite_error = exc

    try:
        import tensorflow as tf

        return tf.lite.Interpreter, "tensorflow"
    except Exception as exc:
        raise ImportError(
            "No TensorFlow Lite interpreter found. Install ai-edge-litert, tflite-runtime, or tensorflow."
        ) from exc
