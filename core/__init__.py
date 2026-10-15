"""Core domain logic, models, decision engine, emergency coordination, and application controller."""
from .models import (
    BuzzerPattern,
    SystemStatus,
    ReadingQuality,
    DistanceReading,
    BoundingBox,
    Detection,
    FrameDetections,
    GeoLocation,
    EmergencyEvent,
)
from .logger import setup_logger
from .engine import DecisionEngine, InvalidReadingPolicy
from .sms_coordinator import SMSCoordinator, compose_emergency_message
from .sound_player import BaseSoundPlayer, MockSoundPlayer, SystemSoundPlayer
# ApplicationController is imported lazily via __getattr__ to avoid circular import
# with vision.detector when vision modules are imported before core.controller.

def __getattr__(name: str):
    if name == "ApplicationController":
        from .controller import ApplicationController
        return ApplicationController
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "BuzzerPattern",
    "SystemStatus",
    "ReadingQuality",
    "DistanceReading",
    "BoundingBox",
    "Detection",
    "FrameDetections",
    "GeoLocation",
    "EmergencyEvent",
    "setup_logger",
    "DecisionEngine",
    "InvalidReadingPolicy",
    "SMSCoordinator",
    "compose_emergency_message",
    "BaseSoundPlayer",
    "MockSoundPlayer",
    "SystemSoundPlayer",
    "ApplicationController",
]
