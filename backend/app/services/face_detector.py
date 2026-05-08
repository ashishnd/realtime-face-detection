from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass(frozen=True)
class FaceBox:
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    confidence: float


class FaceDetector:
    """Face detection without OpenCV. Uses MediaPipe when available."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._mp_fd: Any = None
        self._enabled = True

    def _ensure(self) -> None:
        if self._mp_fd is not None or not self._enabled:
            return
        try:
            import mediapipe as mp  # type: ignore
        except Exception:
            self._enabled = False
            return

        self._mp_fd = mp.solutions.face_detection.FaceDetection(
            model_selection=0,
            min_detection_confidence=0.5,
        )

    def detect(self, rgb: Any) -> FaceBox | None:
        """rgb: HxWx3 uint8 RGB-like object. Returns first detected face or None."""
        try:
            import numpy as np  # type: ignore
        except Exception:
            return None

        arr = rgb if isinstance(rgb, np.ndarray) else np.asarray(rgb, dtype=np.uint8)
        if arr.ndim != 3 or arr.shape[2] != 3:
            return None
        h, w = arr.shape[0], arr.shape[1]
        if h == 0 or w == 0:
            return None

        with self._lock:
            self._ensure()
            if not self._enabled or self._mp_fd is None:
                return None

            res = self._mp_fd.process(arr)  # type: ignore[union-attr]
            if not res.detections:
                return None

            det = res.detections[0]
            rel = det.location_data.relative_bounding_box
            x_min = max(0.0, rel.xmin * w)
            y_min = max(0.0, rel.ymin * h)
            x_max = min(float(w), (rel.xmin + rel.width) * w)
            y_max = min(float(h), (rel.ymin + rel.height) * h)
            conf = float(det.score[0]) if det.score else 0.0
            return FaceBox(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max, confidence=conf)

    def close(self) -> None:
        with self._lock:
            if self._mp_fd is not None:
                self._mp_fd.close()
                self._mp_fd = None
