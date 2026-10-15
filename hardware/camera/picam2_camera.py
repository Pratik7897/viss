"""Raspberry Pi Camera Module V2 driver using Picamera2.

Conforms to BaseCamera interface and outputs canonical RGB frames for downstream
inference matching Black Book Ch 5.3.1.
"""

from typing import Any, Optional, Tuple

from core.logger import setup_logger
from hardware.base import BaseCamera


class PiCamera2Driver(BaseCamera):
    """Production CSI camera driver for Raspberry Pi using Picamera2.

    Deferred initialization: does not import picamera2 at module level.
    """

    def __init__(
        self,
        width: int = 640,
        height: int = 480,
        logger_name: str = "viss.picam2_camera",
    ):
        self._width = width
        self._height = height
        self._logger = setup_logger(logger_name)

        self._picam2: Optional[Any] = None
        self._is_active: bool = False

    @property
    def is_active(self) -> bool:
        return self._is_active

    def get_resolution(self) -> Tuple[int, int]:
        return (self._width, self._height)

    def start(self) -> None:
        """Configures and starts Picamera2 video streaming in RGB format."""
        if self._is_active:
            self._logger.debug("PiCamera2Driver is already active.")
            return

        try:
            from picamera2 import Picamera2
        except ImportError as e:
            raise RuntimeError(
                "picamera2 is not installed. Install python3-picamera2 on Raspberry Pi OS Bookworm "
                "to capture from the physical CSI camera."
            ) from e

        try:
            self._picam2 = Picamera2()
            video_config = self._picam2.create_video_configuration(
                main={"size": (self._width, self._height), "format": "RGB888"}
            )
            self._picam2.configure(video_config)
            self._picam2.start()
            self._is_active = True
            self._logger.info("PiCamera2Driver started at resolution %dx%d (RGB888).", self._width, self._height)
        except Exception as e:
            self._picam2 = None
            self._is_active = False
            self._logger.error("Failed to start Picamera2: %s", e)
            raise RuntimeError(f"Could not initialize Pi Camera via Picamera2 ({e})") from e

    def capture_frame(self) -> Optional[Any]:
        """Captures next RGB video frame as a numpy array.

        Returns None if frame capture fails or camera is inactive.
        """
        if not self._is_active or self._picam2 is None:
            return None

        try:
            frame = self._picam2.capture_array()
            if frame is None or getattr(frame, "size", 0) == 0:
                self._logger.warning("Picamera2 returned an empty frame.")
                return None

            # Ensure 3-channel RGB
            if hasattr(frame, "ndim") and frame.ndim == 3 and frame.shape[2] >= 3:
                return frame[:, :, :3]

            return frame
        except Exception as e:
            self._logger.error("Picamera2 frame capture exception: %s", e)
            return None

    def stop(self) -> None:
        """Stops video stream and closes camera hardware."""
        if self._picam2 is not None:
            try:
                self._picam2.stop()
                self._picam2.close()
            except Exception as e:
                self._logger.debug("Error stopping/closing Picamera2: %s", e)
            self._picam2 = None

        self._is_active = False
        self._logger.info("PiCamera2Driver stopped.")
