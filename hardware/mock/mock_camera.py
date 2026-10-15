"""Mock camera simulator for macOS testing without Raspberry Pi CSI camera or Picamera2."""

import time
from typing import Any, Optional, Tuple

from core.logger import setup_logger
from hardware.base import BaseCamera

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


class MockCamera(BaseCamera):
    """Simulates a camera feed without hardware.

    Returns synthetic test frames (either dummy numpy RGB arrays or byte grids).
    """

    def __init__(
        self,
        width: int = 640,
        height: int = 480,
        logger_name: str = "viss.mock_camera",
    ):
        self._logger = setup_logger(logger_name)
        self._width = width
        self._height = height
        self._is_active: bool = False
        self._frame_count: int = 0
        self._custom_frame: Optional[Any] = None

    def start(self) -> None:
        """Starts mock camera."""
        self._is_active = True
        self._frame_count = 0
        self._logger.debug("MockCamera started at resolution %dx%d.", self._width, self._height)

    def stop(self) -> None:
        """Stops mock camera."""
        self._is_active = False
        self._logger.debug("MockCamera stopped. Total frames delivered: %d", self._frame_count)

    @property
    def is_active(self) -> bool:
        return self._is_active

    def get_resolution(self) -> Tuple[int, int]:
        return (self._width, self._height)

    def set_custom_frame(self, frame: Optional[Any]) -> None:
        """Injects a specific frame (e.g. from an image file or test fixture)."""
        self._custom_frame = frame

    def capture_frame(self) -> Optional[Any]:
        """Returns the next synthetic video frame."""
        if not self._is_active:
            return None

        self._frame_count += 1

        if self._custom_frame is not None:
            return self._custom_frame

        if HAS_NUMPY:
            # Generate a lightweight blank RGB frame (height, width, 3)
            return np.zeros((self._height, self._width, 3), dtype=np.uint8)
        else:
            # Fallback when numpy is not yet installed in virtualenv
            return {
                "width": self._width,
                "height": self._height,
                "channels": 3,
                "frame_id": self._frame_count,
                "timestamp": time.time(),
            }
