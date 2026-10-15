"""Vision capture and detection pipeline connecting cameras with object detectors."""

from typing import Optional

from core.logger import setup_logger
from core.models import FrameDetections
from hardware.base import BaseCamera
from vision.detector import ObjectDetector


class VisionPipeline:
    """Connects a camera capture device with an object detector.

    Keeps image acquisition decoupled from neural network inference.
    """

    def __init__(
        self,
        camera: BaseCamera,
        detector: ObjectDetector,
        logger_name: str = "viss.vision_pipeline",
    ):
        self._camera = camera
        self._detector = detector
        self._logger = setup_logger(logger_name)

    @property
    def camera(self) -> BaseCamera:
        return self._camera

    @property
    def detector(self) -> ObjectDetector:
        return self._detector

    def start(self) -> None:
        """Starts camera streaming."""
        if not self._camera.is_active:
            self._camera.start()
            self._logger.info("Vision pipeline camera started.")

    def stop(self) -> None:
        """Stops camera streaming."""
        if self._camera.is_active:
            self._camera.stop()
            self._logger.info("Vision pipeline camera stopped.")

    def capture_and_detect(self) -> Optional[FrameDetections]:
        """Captures the next frame from the camera and runs object detection.

        Returns:
            FrameDetections if a frame was captured; None if camera failed or is stopped.
        """
        frame = self._camera.capture_frame()
        if frame is None:
            self._logger.debug("No frame captured from camera.")
            return None

        return self._detector.detect(frame)
