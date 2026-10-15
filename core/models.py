"""Core data models and domain entities for the Visual Impairment Support System (VISS).

These models are decoupled from any specific hardware platform or sensor driver,
allowing testing and simulation on macOS without physical GPIO or camera hardware.
"""

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import List, Optional, Tuple


class BuzzerPattern(str, Enum):
    """Buzzer acoustic alert patterns."""

    OFF = "OFF"
    CONTINUOUS = "CONTINUOUS"
    FAST_BEEP = "FAST_BEEP"
    SLOW_BEEP = "SLOW_BEEP"


class SystemStatus(str, Enum):
    """Overall operational state of the VISS device."""

    INITIALIZING = "INITIALIZING"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class ReadingQuality(str, Enum):
    """Data quality status of a distance sensor measurement."""

    VALID = "VALID"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"


@dataclass(frozen=True)
class DistanceReading:
    """Represents a single distance measurement from an ultrasonic sensor.

    Attributes:
        distance_m: Distance in meters, or None if reading failed/out-of-range.
        timestamp: Unix timestamp (time.time()) when the reading was taken.
        quality: Reading quality descriptor (VALID, OUT_OF_RANGE, ERROR).
    """

    distance_m: Optional[float]
    timestamp: float = field(default_factory=time.time)
    quality: ReadingQuality = ReadingQuality.VALID

    @property
    def is_valid(self) -> bool:
        """Returns True if the measurement is within physical sensor bounds."""
        return self.quality == ReadingQuality.VALID and self.distance_m is not None

    def formatted_text(self) -> str:
        """User-friendly text representation matching the Black Book SMS format."""
        if self.distance_m is not None:
            return f"{self.distance_m:.2f} m"
        return "unknown"


@dataclass(frozen=True)
class BoundingBox:
    """Bounding box coordinates normalized or pixel-scaled."""

    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return max(0, self.x2 - self.x1)

    @property
    def height(self) -> int:
        return max(0, self.y2 - self.y1)


@dataclass(frozen=True)
class Detection:
    """A single object detected by the computer vision model.

    Attributes:
        label: Class name (e.g. 'person', 'dog', 'car').
        confidence: Prediction confidence score between 0.0 and 1.0.
        box: Coordinates of the bounding box on the camera frame.
        timestamp: Unix timestamp when detection occurred.
    """

    label: str
    confidence: float
    box: Optional[BoundingBox] = None
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self):
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"Confidence score must be between 0.0 and 1.0, got {self.confidence}"
            )


@dataclass(frozen=True)
class FrameDetections:
    """Collection of all objects detected in a single video frame."""

    detections: Tuple[Detection, ...] = field(default_factory=tuple)
    frame_width: int = 640
    frame_height: int = 480
    timestamp: float = field(default_factory=time.time)

    @property
    def labels(self) -> List[str]:
        """List of all detected class labels in this frame."""
        return [d.label for d in self.detections]

    def has_target(self, target_classes: Tuple[str, ...]) -> bool:
        """Returns True if any detected object matches the target classes."""
        return any(d.label in target_classes for d in self.detections)

    def highest_confidence_target(
        self, target_classes: Tuple[str, ...]
    ) -> Optional[Detection]:
        """Returns the highest confidence detection matching target_classes."""
        targets = [d for d in self.detections if d.label in target_classes]
        if not targets:
            return None
        return max(targets, key=lambda d: d.confidence)


@dataclass(frozen=True)
class GeoLocation:
    """Geographical location information for emergency alerts.

    Attributes:
        latitude: Geographic latitude in decimal degrees.
        longitude: Geographic longitude in decimal degrees.
        city: City name, if resolved.
        region: Administrative region or state.
        country: Country name.
        source: Resolution source ('IP', 'GSM_CELL', 'GPS', or 'MOCK').
        timestamp: Timestamp of location acquisition.
    """

    latitude: float
    longitude: float
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    source: str = "IP"
    timestamp: float = field(default_factory=time.time)

    def maps_url(self) -> str:
        """Generates Google Maps link matching the format in the Black Book code."""
        return f"https://maps.google.com/?q={self.latitude:.6f},{self.longitude:.6f}"

    def location_summary(self) -> str:
        """Formats city, region, country line."""
        parts = [p for p in (self.city, self.region, self.country) if p]
        return ", ".join(parts) if parts else "Unknown Location"


@dataclass(frozen=True)
class EmergencyEvent:
    """Represents an emergency distress event triggered by the push button.

    Attributes:
        trigger: Reason for alert (e.g. 'BUTTON_PRESS').
        timestamp: Event creation timestamp.
        detected_label: Most recently observed hazard entity label.
        distance_text: Formatted distance string (e.g. '0.45 m' or 'unknown').
        location: Resolved geolocation or None if unavailable.
        composed_message: The exact SMS payload body to be sent via GSM.
    """

    trigger: str
    timestamp: float = field(default_factory=time.time)
    detected_label: str = "N/A"
    distance_text: str = "unknown"
    location: Optional[GeoLocation] = None
    composed_message: str = ""
