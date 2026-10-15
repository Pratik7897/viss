"""Hardware abstraction interfaces (Abstract Base Classes) for VISS.

These interfaces define the contract that both real Raspberry Pi drivers
and mock/simulation drivers must adhere to. This guarantees that application
logic never relies directly on physical pins, hardware buses, or OS-specific drivers.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, Tuple

from core.models import BuzzerPattern, DistanceReading, GeoLocation


class BaseDistanceSensor(ABC):
    """Abstract interface for ultrasonic distance measurement devices."""

    @abstractmethod
    def start(self) -> None:
        """Initializes the sensor and begins measurement polling."""
        pass

    @abstractmethod
    def read_distance(self) -> DistanceReading:
        """Returns the most recent distance measurement in meters."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Halts sensor operation and releases resources."""
        pass

    @property
    @abstractmethod
    def is_active(self) -> bool:
        """Returns True if the sensor is currently running."""
        pass


class BaseCamera(ABC):
    """Abstract interface for video capture devices."""

    @abstractmethod
    def start(self) -> None:
        """Starts video streaming and readies frame capture."""
        pass

    @abstractmethod
    def capture_frame(self) -> Optional[Any]:
        """Captures and returns the next video frame (e.g., numpy RGB array).

        Returns None if frame capture fails or camera is stopped.
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stops video streaming and releases camera hardware."""
        pass

    @property
    @abstractmethod
    def is_active(self) -> bool:
        """Returns True if camera stream is active."""
        pass

    @abstractmethod
    def get_resolution(self) -> Tuple[int, int]:
        """Returns (width, height) in pixels."""
        pass


class BaseBuzzer(ABC):
    """Abstract interface for audio proximity alert devices (buzzer)."""

    @abstractmethod
    def set_pattern(self, pattern: BuzzerPattern) -> None:
        """Updates the acoustic alert pattern (OFF, CONTINUOUS, FAST_BEEP, SLOW_BEEP)."""
        pass

    @abstractmethod
    def turn_off(self) -> None:
        """Immediately silences the buzzer."""
        pass

    @property
    @abstractmethod
    def current_pattern(self) -> BuzzerPattern:
        """Returns the currently active acoustic alert pattern."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Releases buzzer GPIO / hardware resources."""
        pass


class BaseGSM(ABC):
    """Abstract interface for cellular GSM modem modules (SIM800L)."""

    @abstractmethod
    def send_sms(self, phone_number: str, message: str) -> Tuple[bool, str]:
        """Sends an SMS message to the specified phone number.

        Args:
            phone_number: Recipient telephone number in international format.
            message: Text payload of the SMS.

        Returns:
            Tuple of (success: bool, status_message: str).
        """
        pass

    @property
    @abstractmethod
    def is_ready(self) -> bool:
        """Returns True if the modem is powered and registered on cellular network."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Closes serial connection to modem."""
        pass


class BaseLocationProvider(ABC):
    """Abstract interface for geolocation resolvers."""

    @abstractmethod
    def get_location(self) -> Optional[GeoLocation]:
        """Resolves and returns the current coordinates and locality.

        Returns None if resolution times out or is offline.
        """
        pass


class BaseButton(ABC):
    """Abstract interface for tactile input devices (Emergency button)."""

    @abstractmethod
    def is_pressed(self) -> bool:
        """Returns True if the button is currently depressed."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Releases button GPIO resources."""
        pass
