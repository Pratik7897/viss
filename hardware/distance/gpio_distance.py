"""Raspberry Pi GPIO ultrasonic distance sensor driver using gpiozero.

ELECTRICAL SAFETY WARNING:
  Standard HC-SR04 ultrasonic sensors output a 5.0V signal on the ECHO pin.
  Raspberry Pi GPIO pins are rated for a MAXIMUM of 3.3V.
  Connecting HC-SR04 ECHO directly to a Raspberry Pi GPIO pin without voltage
  protection will permanently damage the GPIO bank or SoC.
  A voltage divider (e.g., 1 kOhm in series, 2 kOhm to GND) or a 3.3V logic level
  shifter is REQUIRED between the ECHO pin and the configured GPIO pin.
"""

import time
from typing import Any, Optional

from core.logger import setup_logger
from core.models import DistanceReading, ReadingQuality
from hardware.base import BaseDistanceSensor


class GPIODistanceSensor(BaseDistanceSensor):
    """Production HC-SR04 ultrasonic sensor driver for Raspberry Pi using gpiozero.

    Deferred initialization: does not access GPIO or require gpiozero at module import time.
    """

    def __init__(
        self,
        trig_pin: int = 24,
        echo_pin: int = 23,
        max_distance_m: float = 4.0,
        min_distance_m: float = 0.02,
        logger_name: str = "viss.gpio_distance",
    ):
        self._trig_pin = trig_pin
        self._echo_pin = echo_pin
        self._max_distance_m = max_distance_m
        self._min_distance_m = min_distance_m
        self._logger = setup_logger(logger_name)

        self._sensor: Optional[Any] = None
        self._is_active: bool = False

    @property
    def trig_pin(self) -> int:
        return self._trig_pin

    @property
    def echo_pin(self) -> int:
        return self._echo_pin

    @property
    def is_active(self) -> bool:
        return self._is_active

    def start(self) -> None:
        """Initializes gpiozero DistanceSensor on configured BCM pins."""
        if self._is_active:
            self._logger.debug("GPIODistanceSensor is already active.")
            return

        try:
            from gpiozero import DistanceSensor
        except ImportError as e:
            raise RuntimeError(
                "gpiozero is not installed. Install python3-gpiozero on Raspberry Pi OS "
                "to use the physical GPIO distance sensor."
            ) from e

        try:
            self._sensor = DistanceSensor(
                echo=self._echo_pin,
                trigger=self._trig_pin,
                max_distance=self._max_distance_m,
            )
            self._is_active = True
            self._logger.info(
                "GPIODistanceSensor started on TRIG=GPIO%d, ECHO=GPIO%d (max=%.1fm).",
                self._trig_pin,
                self._echo_pin,
                self._max_distance_m,
            )
        except Exception as e:
            self._sensor = None
            self._is_active = False
            self._logger.error("Failed to initialize gpiozero DistanceSensor: %s", e)
            raise RuntimeError(f"Could not initialize HC-SR04 on GPIO pins ({e})") from e

    def read_distance(self) -> DistanceReading:
        """Reads distance from HC-SR04 sensor in meters.

        Returns DistanceReading with ReadingQuality.VALID, OUT_OF_RANGE, or ERROR.
        Does not raise unhandled exceptions.
        """
        now = time.time()
        if not self._is_active or self._sensor is None:
            return DistanceReading(
                distance_m=None,
                timestamp=now,
                quality=ReadingQuality.ERROR,
            )

        try:
            dist = float(self._sensor.distance)

            if dist < self._min_distance_m or dist > self._max_distance_m:
                return DistanceReading(
                    distance_m=dist,
                    timestamp=now,
                    quality=ReadingQuality.OUT_OF_RANGE,
                )

            return DistanceReading(
                distance_m=dist,
                timestamp=now,
                quality=ReadingQuality.VALID,
            )
        except Exception as e:
            self._logger.warning("HC-SR04 distance read error: %s", e)
            return DistanceReading(
                distance_m=None,
                timestamp=now,
                quality=ReadingQuality.ERROR,
            )

    def stop(self) -> None:
        """Releases GPIO pins and sensor resources."""
        if self._sensor is not None:
            try:
                self._sensor.close()
            except Exception as e:
                self._logger.debug("Error closing gpiozero DistanceSensor: %s", e)
            self._sensor = None

        self._is_active = False
        self._logger.info("GPIODistanceSensor stopped.")
