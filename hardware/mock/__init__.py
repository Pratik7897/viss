"""Mock hardware driver implementations for macOS and automated testing."""
from .mock_distance import MockDistanceSensor
from .mock_camera import MockCamera
from .mock_buzzer import MockBuzzer
from .mock_gsm import MockGSM
from .mock_location import MockLocationProvider
from .mock_button import MockButton

__all__ = [
    "MockDistanceSensor",
    "MockCamera",
    "MockBuzzer",
    "MockGSM",
    "MockLocationProvider",
    "MockButton",
]
