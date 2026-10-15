"""OpenCV webcam capture device for macOS local testing."""

from typing import Any, Optional, Tuple

from core.logger import setup_logger
from hardware.base import BaseCamera


class OpenCVCamera(BaseCamera):
    """Captures live frames from a local USB/FaceTime webcam using OpenCV.

    Optional driver for macOS development. Fails gracefully if OpenCV is not installed
    or if camera hardware cannot be accessed.
    """

    def __init__(
        self,
        device_index: int = 0,
        width: int = 640,
        height: int = 480,
        logger_name: str = "viss.opencv_camera",
    ):
        self._device_index = device_index
        self._width = width
        self._height = height
        self._logger = setup_logger(logger_name)

        self._cap: Optional[Any] = None
        self._is_active: bool = False

    def start(self) -> None:
        """Opens video capture device."""
        try:
            import cv2
        except ImportError as e:
            raise RuntimeError(
                "OpenCV (cv2) is not installed. Install opencv-python "
                "to capture from a physical webcam on macOS."
            ) from e

        self._cap = cv2.VideoCapture(self._device_index)
        if not self._cap.isOpened():
            self._cap = None
            raise RuntimeError(
                f"Could not open webcam at device index {self._device_index}. "
                "Ensure a camera is connected and terminal permissions are granted."
            )

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        self._is_active = True
        self._logger.info("OpenCVCamera started on device index %d.", self._device_index)

    def capture_frame(self) -> Optional[Any]:
        """Reads the next frame, converts native webcam BGR to RGB, and returns it.

        Conforms strictly to the BaseCamera contract which specifies standard RGB frames.
        """
        if not self._is_active or self._cap is None:
            return None

        import cv2

        ret, frame = self._cap.read()
        if not ret or frame is None:
            self._logger.warning("Failed to read frame from webcam.")
            return None

        # OpenCV VideoCapture returns BGR by default; convert to canonical RGB
        # so that downstream pipelines and models receive consistent RGB input.
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    def stop(self) -> None:
        """Releases the camera device."""
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception as e:
                self._logger.debug("Error releasing camera: %s", e)
            self._cap = None

        self._is_active = False
        self._logger.info("OpenCVCamera stopped.")

    @property
    def is_active(self) -> bool:
        return self._is_active

    def get_resolution(self) -> Tuple[int, int]:
        return (self._width, self._height)
