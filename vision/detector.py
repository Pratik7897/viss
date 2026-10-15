"""MobileNet-SSD object detection module for the Visual Impairment Support System (VISS).

This module implements the computer vision pipeline using OpenCV DNN and MobileNet-SSD
with Caffe pre-trained weights, matching the implementation in Black Book Chapter 5.3.1.

IMPORTANT NOTES ON MODEL FILES & DEPENDENCIES:
----------------------------------------------
1. Model Architecture: MobileNet-SSD trained on the 20-class Pascal VOC dataset.
2. Expected Model Files:
   - Prototxt: MobileNetSSD_deploy.prototxt
   - Weights:  MobileNetSSD_deploy.caffemodel
3. Offline / Mock Execution:
   - To enable development and automated testing on macOS without downloading large
     binary weights (~23 MB) or requiring OpenCV to be installed in every environment,
     an extensible BaseInferenceEngine interface and StubInferenceEngine are provided.
   - When OpenCV and weights are available, OpenCVInferenceEngine performs real inference.
"""

from abc import ABC, abstractmethod
import math
import os
import time
from typing import Any, List, Optional, Sequence, Tuple, Union

from config.settings import VisionConfig, get_config
from core.logger import setup_logger
from core.models import BoundingBox, Detection, FrameDetections

# Pascal VOC 20-class taxonomy (including background class 0)
PASCAL_VOC_CLASSES: Tuple[str, ...] = (
    "background",
    "aeroplane",
    "bicycle",
    "bird",
    "boat",
    "bottle",
    "bus",
    "car",
    "cat",
    "chair",
    "cow",
    "diningtable",
    "dog",
    "horse",
    "motorbike",
    "person",
    "pottedplant",
    "sheep",
    "sofa",
    "train",
    "tvmonitor",
)

# Canonical target entities from Black Book Ch 5.3.1
DEFAULT_TARGET_CLASSES: Tuple[str, ...] = ("person", "dog", "cat", "car")


class BaseInferenceEngine(ABC):
    """Abstract interface for neural network inference engines."""

    @abstractmethod
    def forward(self, frame: Any) -> Any:
        """Executes forward inference pass on the given input frame.

        Returns raw detections matrix or list of candidate detections.
        """
        pass

    @property
    @abstractmethod
    def is_ready(self) -> bool:
        """Returns True if the engine is initialized with valid weights."""
        pass


class StubInferenceEngine(BaseInferenceEngine):
    """In-memory stub inference engine for testing without weights or OpenCV."""

    def __init__(self, logger_name: str = "viss.stub_engine"):
        self._logger = setup_logger(logger_name)
        self._custom_detections: Optional[Any] = None
        self._simulate_error: bool = False
        self._is_ready: bool = True

    @property
    def is_ready(self) -> bool:
        return self._is_ready

    def set_ready(self, ready: bool) -> None:
        self._is_ready = ready

    def set_simulate_error(self, should_error: bool) -> None:
        self._simulate_error = should_error

    def set_raw_detections(self, raw_output: Optional[Any]) -> None:
        """Sets custom raw detection output to return on forward()."""
        self._custom_detections = raw_output

    def forward(self, frame: Any) -> Any:
        """Returns preset test detections or raises simulated error."""
        if self._simulate_error:
            raise RuntimeError("Simulated inference engine error")

        if not self._is_ready:
            raise RuntimeError("Inference engine is not ready (missing weights)")

        if self._custom_detections is not None:
            return self._custom_detections

        # Default: empty detections array of shape (1, 1, 0, 7)
        return []


class OpenCVInferenceEngine(BaseInferenceEngine):
    """Real OpenCV DNN Caffe inference engine.

    Requires opencv-python and valid MobileNetSSD model files.
    """

    def __init__(
        self,
        prototxt_path: str,
        weights_path: str,
        swap_rb: bool = True,
        logger_name: str = "viss.opencv_engine",
    ):
        self._logger = setup_logger(logger_name)
        self._prototxt_path = prototxt_path
        self._weights_path = weights_path
        self._swap_rb = swap_rb
        self._net: Optional[Any] = None

        self._validate_and_load()

    @property
    def swap_rb(self) -> bool:
        """Returns True if RGB channels are swapped to BGR during blob creation."""
        return self._swap_rb

    def _validate_and_load(self) -> None:
        """Validates file paths and initializes OpenCV Caffe DNN."""
        try:
            import cv2
        except ImportError as e:
            raise RuntimeError(
                "OpenCV (cv2) is not installed. Please install opencv-python "
                "to use OpenCVInferenceEngine."
            ) from e

        if not os.path.isfile(self._prototxt_path):
            raise FileNotFoundError(
                f"MobileNet-SSD prototxt file not found: '{self._prototxt_path}'. "
                "Please download 'MobileNetSSD_deploy.prototxt' from the OpenCV "
                "repository or specify a valid path."
            )

        if not os.path.isfile(self._weights_path):
            raise FileNotFoundError(
                f"MobileNet-SSD caffemodel weights file not found: '{self._weights_path}'. "
                "Please download 'MobileNetSSD_deploy.caffemodel' (~23 MB) from the "
                "official Caffe MobileNetSSD repository and place it in the weights directory."
            )

        self._logger.info("Loading Caffe network from '%s'...", self._weights_path)
        self._net = cv2.dnn.readNetFromCaffe(self._prototxt_path, self._weights_path)
        self._net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self._net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        cv2.setUseOptimized(True)
        self._logger.info("OpenCV Caffe DNN successfully initialized.")

    @property
    def is_ready(self) -> bool:
        return self._net is not None

    def forward(self, frame: Any) -> Any:
        """Preprocesses frame and performs forward pass through Caffe DNN.

        Expects an RGB frame adhering to the BaseCamera interface contract.
        By default (swap_rb=True), blobFromImage converts RGB to BGR in-place,
        matching the channel order expected by the Caffe MobileNet-SSD weights.
        """
        if not self.is_ready:
            raise RuntimeError("OpenCV DNN is not ready.")

        import cv2

        # Preprocessing matching Black Book Ch 5.3.1:
        # Resize to (320, 240) -> blobFromImage at (300, 300) with scale 0.007843
        inf_w, inf_h = 320, 240
        small = cv2.resize(frame, (inf_w, inf_h), interpolation=cv2.INTER_LINEAR)
        blob = cv2.dnn.blobFromImage(
            small,
            scalefactor=0.007843,
            size=(300, 300),
            mean=(127.5, 127.5, 127.5),
            swapRB=self._swap_rb,
            crop=False,
        )
        self._net.setInput(blob)
        return self._net.forward()


class ObjectDetector:
    """Parses video frames into structured Detection and FrameDetections models."""

    def __init__(
        self,
        config: Optional[VisionConfig] = None,
        engine: Optional[BaseInferenceEngine] = None,
        target_classes: Optional[Sequence[str]] = None,
        confidence_threshold: Optional[float] = None,
        filter_to_targets: Optional[bool] = None,
        logger_name: str = "viss.detector",
    ):
        self._config = config or get_config().vision
        self._engine = engine or StubInferenceEngine()
        self._logger = setup_logger(logger_name)

        self._target_classes = tuple(
            target_classes if target_classes is not None else self._config.target_classes
        )
        self._confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else self._config.confidence_threshold
        )
        self._filter_to_targets = (
            filter_to_targets
            if filter_to_targets is not None
            else self._config.filter_to_targets
        )

    @property
    def target_classes(self) -> Tuple[str, ...]:
        return self._target_classes

    @property
    def confidence_threshold(self) -> float:
        return self._confidence_threshold

    @property
    def filter_to_targets(self) -> bool:
        return self._filter_to_targets

    def _extract_frame_dimensions(self, frame: Any) -> Tuple[int, int]:
        """Safely extracts (width, height) from various frame representations."""
        # NumPy array: shape is (height, width, channels)
        if hasattr(frame, "shape") and len(frame.shape) >= 2:
            return int(frame.shape[1]), int(frame.shape[0])

        # Dictionary representation (e.g. from MockCamera without numpy)
        if isinstance(frame, dict):
            w = int(frame.get("width", self._config.frame_width))
            h = int(frame.get("height", self._config.frame_height))
            return max(1, w), max(1, h)

        # Fallback to configured defaults
        return self._config.frame_width, self._config.frame_height

    def _is_frame_valid(self, frame: Any) -> bool:
        """Validates that frame is non-empty and accessible."""
        if frame is None:
            return False

        if hasattr(frame, "size"):
            # Check empty numpy array
            if frame.size == 0:
                return False

        return True

    def detect(self, frame: Any) -> FrameDetections:
        """Processes a single video frame and returns all identified detections.

        Args:
            frame: Video frame (numpy array or frame dict).

        Returns:
            FrameDetections containing filtered Detection objects.
        """
        now = time.time()

        if not self._is_frame_valid(frame):
            self._logger.debug("Empty or None frame received; returning empty detections.")
            return FrameDetections(detections=(), timestamp=now)

        width, height = self._extract_frame_dimensions(frame)

        # Execute forward pass through inference engine
        try:
            raw_detections = self._engine.forward(frame)
        except Exception as e:
            self._logger.error("Inference failed: %s", e)
            return FrameDetections(
                detections=(),
                frame_width=width,
                frame_height=height,
                timestamp=now,
            )

        parsed_detections: List[Detection] = []

        # Iterate over raw detections
        # Support both NumPy 4D tensor (1, 1, N, 7) and Python sequences
        rows = self._normalize_detection_rows(raw_detections)

        for row in rows:
            detection = self._parse_single_detection(row, width, height, now)
            if detection is not None:
                parsed_detections.append(detection)

        return FrameDetections(
            detections=tuple(parsed_detections),
            frame_width=width,
            frame_height=height,
            timestamp=now,
        )

    def _normalize_detection_rows(self, raw_output: Any) -> List[Any]:
        """Normalizes Caffe 4D tensor or list of rows into an iterable list."""
        if raw_output is None:
            return []

        # If NumPy array of shape (1, 1, N, 7)
        if hasattr(raw_output, "shape"):
            shape = raw_output.shape
            if len(shape) == 4 and shape[0] == 1 and shape[1] == 1 and shape[3] == 7:
                # Shape is (1, 1, N, 7) -> return list of rows
                return [raw_output[0, 0, i] for i in range(shape[2])]
            elif len(shape) == 2 and shape[1] == 7:
                return [raw_output[i] for i in range(shape[0])]

        # If standard Python sequence
        if isinstance(raw_output, (list, tuple)):
            if len(raw_output) == 0:
                return []
            first = raw_output[0]
            # Check if nested (1, 1, N, 7) list structure
            if isinstance(first, (list, tuple)) and len(raw_output) == 1 and len(first) == 1:
                return list(first[0])
            return list(raw_output)

        return []

    def _parse_single_detection(
        self,
        row: Any,
        width: int,
        height: int,
        timestamp: float,
    ) -> Optional[Detection]:
        """Parses a single 7-element detection row: [0, class_id, conf, x1, y1, x2, y2]."""
        try:
            if len(row) < 7:
                return None

            class_id_val = row[1]
            conf_val = row[2]
            x1_norm = row[3]
            y1_norm = row[4]
            x2_norm = row[5]
            y2_norm = row[6]

            # Validate numeric confidence
            conf = float(conf_val)
            if math.isnan(conf) or math.isinf(conf):
                return None

            # Enforce confidence threshold strictly
            if conf < self._confidence_threshold:
                return None

            # Clamp confidence to [0.0, 1.0] for Detection model validation
            conf = max(0.0, min(1.0, conf))

            # Validate class ID
            class_id = int(class_id_val)
            if not (0 <= class_id < len(PASCAL_VOC_CLASSES)):
                return None

            label = PASCAL_VOC_CLASSES[class_id]

            # Target class filtering
            if self._filter_to_targets and (label not in self._target_classes):
                return None

            # Bounding box conversion and clamping
            x1 = int(round(float(x1_norm) * width))
            y1 = int(round(float(y1_norm) * height))
            x2 = int(round(float(x2_norm) * width))
            y2 = int(round(float(y2_norm) * height))

            x1_clamped = max(0, min(x1, width - 1))
            y1_clamped = max(0, min(y1, height - 1))
            x2_clamped = max(0, min(x2, width - 1))
            y2_clamped = max(0, min(y2, height - 1))

            # Ensure valid box dimensions
            box_x1 = min(x1_clamped, x2_clamped)
            box_x2 = max(x1_clamped, x2_clamped)
            box_y1 = min(y1_clamped, y2_clamped)
            box_y2 = max(y1_clamped, y2_clamped)

            box = BoundingBox(x1=box_x1, y1=box_y1, x2=box_x2, y2=box_y2)

            return Detection(
                label=label,
                confidence=conf,
                box=box,
                timestamp=timestamp,
            )

        except (ValueError, TypeError, IndexError) as e:
            self._logger.debug("Skipping malformed detection row: %s (error: %s)", row, e)
            return None
