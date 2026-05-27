from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np


class CameraSource(ABC):
    """Common contract for every camera source feeding the processing pipeline."""

    source_type: str

    @abstractmethod
    def start(self) -> bool:
        """Start the source. Returns True when the source is usable."""

    @abstractmethod
    def read(self) -> np.ndarray | None:
        """Return the latest BGR frame, or None when no frame is available."""

    @abstractmethod
    def stop(self) -> None:
        """Release source resources."""

    @abstractmethod
    def is_active(self) -> bool:
        """Return True when the source should still be considered active."""

    @abstractmethod
    def get_info(self) -> dict[str, Any]:
        """Return dashboard-safe status and diagnostics for this source."""
