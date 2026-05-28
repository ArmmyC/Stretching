from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_NCNN_MODEL_DIR = "models/yolov8n-pose_ncnn_model"
DEFAULT_NCNN_INPUT_SIZE = 320
DEFAULT_NCNN_CONFIDENCE = 0.25
DEFAULT_NCNN_IOU = 0.45
DEFAULT_NCNN_GPU_INDEX = 0

COCO_TO_STRETCHSENSE = {
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
    source_width: int
    source_height: int


class NcnnYoloPose:
    """YOLO pose inference through NCNN/Vulkan.

    This backend targets Ultralytics YOLO pose NCNN exports that produce rows
    shaped like [x, y, w, h, confidence, 17 * (x, y, confidence)].
    """

    def __init__(
        self,
        model_dir: str | Path,
        input_size: int = DEFAULT_NCNN_INPUT_SIZE,
        use_vulkan: bool = True,
        gpu_index: int = DEFAULT_NCNN_GPU_INDEX,
        confidence_threshold: float = DEFAULT_NCNN_CONFIDENCE,
        iou_threshold: float = DEFAULT_NCNN_IOU,
    ):
        self.model_dir = Path(model_dir).expanduser()
        self.param_path = self.model_dir / "model.ncnn.param"
        self.bin_path = self.model_dir / "model.ncnn.bin"
        preferred_param_path = self.param_path
        preferred_bin_path = self.bin_path
        if not self.param_path.exists():
            self.param_path = self.model_dir / "model.param"
        if not self.bin_path.exists():
            self.bin_path = self.model_dir / "model.bin"
        self.expected_paths = (
            preferred_param_path,
            preferred_bin_path,
            self.model_dir / "model.param",
            self.model_dir / "model.bin",
        )

        self.input_size = int(input_size)
        self.use_vulkan = bool(use_vulkan)
        self.gpu_index = int(gpu_index)
        self.confidence_threshold = float(confidence_threshold)
        self.iou_threshold = float(iou_threshold)
        self.input_name = "in0"
        self.output_names: list[str] = []
        self.active_device = "none"
        self.last_output_shapes: dict[str, tuple[int, ...]] = {}

        self._ncnn: Any = None
        self._net: Any = None

    def load(self) -> None:
        if not self.param_path.exists() or not self.bin_path.exists():
            raise FileNotFoundError(
                "NCNN model files missing. Expected either "
                f"{self.expected_paths[0]} + {self.expected_paths[1]} or "
                f"{self.expected_paths[2]} + {self.expected_paths[3]}."
            )

        import ncnn

        self._ncnn = ncnn
        self.input_name, self.output_names = _parse_ncnn_param_io(self.param_path)
        if not self.output_names:
            self.output_names = ["out0", "output0", "output"]

        net = ncnn.Net()
        net.opt.use_vulkan_compute = self.use_vulkan
        net.opt.num_threads = max(1, int(os.getenv("NCNN_NUM_THREADS", "2")))
        if self.use_vulkan and hasattr(net, "set_vulkan_device"):
            net.set_vulkan_device(self.gpu_index)

        ret_param = net.load_param(str(self.param_path))
        ret_model = net.load_model(str(self.bin_path))
        if ret_param != 0 or ret_model != 0:
            raise RuntimeError(f"NCNN model load failed param={ret_param} bin={ret_model}")

        self._net = net
        self.active_device = f"vulkan:{self.gpu_index}" if self.use_vulkan else "cpu"
        logger.info(
            "NCNN pose model loaded. param=%s bin=%s input=%s outputs=%s device=%s",
            self.param_path,
            self.bin_path,
            self.input_name,
            self.output_names,
            self.active_device,
        )

    def detect(self, frame_bgr: np.ndarray) -> tuple[dict[str, dict[str, float]], float]:
        if self._net is None or self._ncnn is None:
            raise RuntimeError("NCNN pose model is not loaded.")

        input_image, letterbox = _letterbox(frame_bgr, self.input_size)
        mat = self._to_ncnn_mat(input_image)

        extractor = self._net.create_extractor()
        extractor.input(self.input_name, mat)

        outputs: dict[str, np.ndarray] = {}
        for name in self.output_names:
            try:
                ret, out = extractor.extract(name)
            except Exception:
                continue
            if ret == 0:
                outputs[name] = np.array(out)

        self.last_output_shapes = {name: tuple(value.shape) for name, value in outputs.items()}
        predictions = _find_pose_predictions(outputs)
        if predictions is None:
            logger.warning("Unsupported NCNN pose output shapes: %s", self.last_output_shapes)
            return {}, 0.0

        detection = _select_detection(predictions, self.confidence_threshold, self.iou_threshold)
        if detection is None:
            return {}, 0.0

        landmarks = _detection_to_landmarks(detection, letterbox, self.input_size)
        confidence = float(detection[4]) if detection.shape[0] > 4 else 0.0
        return landmarks, confidence

    def _to_ncnn_mat(self, image_bgr: np.ndarray) -> Any:
        ncnn = self._ncnn
        pixel_type = _pixel_type(ncnn, "PIXEL_BGR2RGB")
        h, w = image_bgr.shape[:2]

        if hasattr(ncnn.Mat, "from_pixels"):
            mat = ncnn.Mat.from_pixels(image_bgr, pixel_type, w, h)
        else:
            rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            chw = np.ascontiguousarray(rgb.transpose(2, 0, 1), dtype=np.float32)
            mat = ncnn.Mat(chw).clone()

        mat.substract_mean_normalize([], [1.0 / 255.0, 1.0 / 255.0, 1.0 / 255.0])
        return mat


def _letterbox(frame_bgr: np.ndarray, target_size: int) -> tuple[np.ndarray, LetterboxInfo]:
    h, w = frame_bgr.shape[:2]
    scale = min(target_size / float(w), target_size / float(h))
    resized_w = max(1, int(round(w * scale)))
    resized_h = max(1, int(round(h * scale)))
    resized = cv2.resize(frame_bgr, (resized_w, resized_h), interpolation=cv2.INTER_AREA)

    canvas = np.full((target_size, target_size, 3), 114, dtype=np.uint8)
    pad_x = (target_size - resized_w) // 2
    pad_y = (target_size - resized_h) // 2
    canvas[pad_y : pad_y + resized_h, pad_x : pad_x + resized_w] = resized
    return canvas, LetterboxInfo(scale=scale, pad_x=pad_x, pad_y=pad_y, source_width=w, source_height=h)


def _find_pose_predictions(outputs: dict[str, np.ndarray]) -> np.ndarray | None:
    for output in outputs.values():
        candidates = _normalise_output(output)
        for candidate in candidates:
            if candidate.ndim == 2 and candidate.shape[1] >= 56:
                return candidate
    return None


def _normalise_output(output: np.ndarray) -> list[np.ndarray]:
    arr = np.asarray(output, dtype=np.float32)
    arr = np.squeeze(arr)
    candidates: list[np.ndarray] = []
    if arr.ndim == 1 and arr.size >= 56:
        candidates.append(arr.reshape(1, -1))
    elif arr.ndim == 2:
        candidates.append(arr)
        candidates.append(arr.T)
    elif arr.ndim == 3:
        for index in range(arr.shape[0]):
            candidates.extend(_normalise_output(arr[index]))

    cleaned: list[np.ndarray] = []
    for candidate in candidates:
        if candidate.ndim != 2:
            continue
        if candidate.shape[0] == 0 or candidate.shape[1] == 0:
            continue
        if candidate.shape[1] < candidate.shape[0] and candidate.shape[0] <= 128:
            candidate = candidate.T
        cleaned.append(np.ascontiguousarray(candidate, dtype=np.float32))
    return cleaned


def _select_detection(predictions: np.ndarray, confidence_threshold: float, iou_threshold: float) -> np.ndarray | None:
    if predictions.shape[1] < 56:
        return None
    scores = predictions[:, 4]
    keep = np.where(scores >= confidence_threshold)[0]
    if keep.size == 0:
        return None

    boxes_xyxy = np.array([_xywh_to_xyxy(predictions[index, :4]) for index in keep], dtype=np.float32)
    order = scores[keep].argsort()[::-1]
    keep_ordered = keep[order]
    boxes_ordered = boxes_xyxy[order]

    selected: list[int] = []
    while keep_ordered.size:
        current = keep_ordered[0]
        selected.append(int(current))
        if keep_ordered.size == 1:
            break
        ious = np.array([_iou(boxes_ordered[0], box) for box in boxes_ordered[1:]], dtype=np.float32)
        keep_mask = ious <= iou_threshold
        keep_ordered = keep_ordered[1:][keep_mask]
        boxes_ordered = boxes_ordered[1:][keep_mask]

    if not selected:
        return None
    best_index = max(selected, key=lambda idx: float(scores[idx]))
    return predictions[best_index]


def _detection_to_landmarks(
    detection: np.ndarray,
    letterbox: LetterboxInfo,
    input_size: int,
) -> dict[str, dict[str, float]]:
    keypoints = detection[5:]
    if keypoints.size < 17 * 3:
        return {}
    keypoints = keypoints[: 17 * 3].reshape(17, 3)
    if np.nanmax(np.abs(keypoints[:, :2])) <= 2.0:
        keypoints[:, :2] *= float(input_size)

    landmarks: dict[str, dict[str, float]] = {}
    for coco_index, name in COCO_TO_STRETCHSENSE.items():
        x_model, y_model, confidence = keypoints[coco_index]
        x_source = (float(x_model) - letterbox.pad_x) / max(letterbox.scale, 1e-6)
        y_source = (float(y_model) - letterbox.pad_y) / max(letterbox.scale, 1e-6)
        landmarks[name] = {
            "x": float(np.clip(x_source / max(letterbox.source_width, 1), 0.0, 1.0)),
            "y": float(np.clip(y_source / max(letterbox.source_height, 1), 0.0, 1.0)),
            "z": 0.0,
            "visibility": float(np.clip(confidence, 0.0, 1.0)),
        }
    return landmarks


def _xywh_to_xyxy(box: np.ndarray) -> np.ndarray:
    x, y, w, h = [float(v) for v in box]
    return np.array([x - w / 2.0, y - h / 2.0, x + w / 2.0, y + h / 2.0], dtype=np.float32)


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    x1 = max(float(a[0]), float(b[0]))
    y1 = max(float(a[1]), float(b[1]))
    x2 = min(float(a[2]), float(b[2]))
    y2 = min(float(a[3]), float(b[3]))
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, float(a[2] - a[0])) * max(0.0, float(a[3] - a[1]))
    area_b = max(0.0, float(b[2] - b[0])) * max(0.0, float(b[3] - b[1]))
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _pixel_type(ncnn: Any, name: str) -> Any:
    container = getattr(ncnn.Mat, "PixelType", None)
    if container and hasattr(container, name):
        return getattr(container, name)
    if hasattr(ncnn.Mat, name):
        return getattr(ncnn.Mat, name)
    return 3


def _parse_ncnn_param_io(param_path: Path) -> tuple[str, list[str]]:
    input_name = "in0"
    used_blobs: set[str] = set()
    produced_blobs: list[str] = []

    try:
        lines = param_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return input_name, []

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("7767517"):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        layer_type = parts[0]
        try:
            input_count = int(parts[2])
            output_count = int(parts[3])
        except ValueError:
            continue
        names = parts[4 : 4 + input_count + output_count]
        input_blobs = names[:input_count]
        output_blobs = names[input_count : input_count + output_count]
        used_blobs.update(input_blobs)
        produced_blobs.extend(output_blobs)
        if layer_type == "Input" and output_blobs:
            input_name = output_blobs[0]

    output_names = [name for name in produced_blobs if name not in used_blobs]
    return input_name, output_names
