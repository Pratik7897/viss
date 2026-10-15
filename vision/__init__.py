"""Vision module providing MobileNet-SSD detection and pipeline orchestration."""
from .detector import (
    PASCAL_VOC_CLASSES,
    DEFAULT_TARGET_CLASSES,
    BaseInferenceEngine,
    StubInferenceEngine,
    OpenCVInferenceEngine,
    ObjectDetector,
)
from .pipeline import VisionPipeline

__all__ = [
    "PASCAL_VOC_CLASSES",
    "DEFAULT_TARGET_CLASSES",
    "BaseInferenceEngine",
    "StubInferenceEngine",
    "OpenCVInferenceEngine",
    "ObjectDetector",
    "VisionPipeline",
]
