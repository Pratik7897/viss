"""Mock ultrasonic distance sensor for simulation and testing on macOS."""

import time
from typing import Iterator, List, Optional, Union

from core.logger import setup_logger
from core.models import DistanceReading, ReadingQuality
from hardware.base import BaseDistanceSensor


class MockDistanceSensor(BaseDistanceSensor):
    """Simulates an ultrasonic distance sensor without physical GPIO.

    Allows providing:
    - A fixed distance value.
    - A predefined sequence of distance measurements (cycling or one-pass).
    - An optional error generator (e.g. simulating disconnected sensor).
    """

    def __init__(
        self,
        initial_distance_m: Optional[float] = 1.0,
        distance_sequence: Optional[List[Optional[float]]] = None,
        simulate_error: bool = False,
        logger_name: str = "viss.mock_distance",
    ):
        self._logger = setup_logger(logger_name)
        self._is_active: bool = False
        self._fixed_distance: Optional[float] = initial_distance_m
        self._sequence: Optional[List[Optional[float]]] = distance_sequence
        self._seq_index: int = 0
        self._simulate_error: bool = simulate_error

    def start(self) -> None:
        """Starts mock sensor polling."""
        self._is_active = True
        self._logger.debug("MockDistanceSensor started.")

    def stop(self) -> None:
        """Stops mock sensor polling."""
        self._is_active = False
        self._logger.debug("MockDistanceSensor stopped.")

    @property
    def is_active(self) -> bool:
        return self._is_active

    def set_distance(self, distance_m: Optional[float]) -> None:
        """Sets a new fixed distance value."""
        self._fixed_distance = distance_m
        self._sequence = None
        self._logger.debug("Mock distance set to: %s m", distance_m)

    def set_sequence(self, sequence: List[Optional[float]]) -> None:
        """Configures a repeating list of distance measurements."""
        self._sequence = sequence
        self._seq_index = 0
        self._logger.debug("Mock distance sequence configured with %d steps", len(sequence))

    def set_simulate_error(self, should_error: bool) -> None:
        """Simulates sensor hardware faults."""
        self._simulate_error = should_error

    def read_distance(self) -> DistanceReading:
        """Returns the next mock distance measurement."""
        if not self._is_active:
            return DistanceReading(
                distance_m=None,
                timestamp=time.time(),
                quality=ReadingQuality.ERROR,
            )

        if self._simulate_error:
            return DistanceReading(
                distance_m=None,
                timestamp=time.time(),
                quality=ReadingQuality.ERROR,
            )

        # Sequence-based reading
        if self._sequence is not None and len(self._sequence) > 0:
            dist = self._sequence[self._seq_index]
            self._seq_index = (self._seq_index + 1) % len(self._sequence)
        else:
            dist = self._fixed_distance

        # Determine quality based on HC-SR04 physical limits (2cm to 4m)
        if dist is None or dist < 0.02 or dist > 4.0:
            quality = ReadingQuality.OUT_OF_RANGE if dist is not None else ReadingQuality.ERROR
        else:
            quality = ReadingQuality.VALID

        return DistanceReading(
            distance_m=dist,
            timestamp=time.time(),
            quality=quality,
        )
