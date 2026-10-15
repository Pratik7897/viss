"""Raspberry Pi GPIO acoustic buzzer driver using gpiozero.

ELECTRICAL SPECIFICATIONS & ASSUMPTIONS:
  1. The Black Book specifies an ACTIVE piezo buzzer controlled via high/low logic.
     Active buzzers include an internal oscillating circuit and emit sound upon
     receiving DC voltage. (Passive buzzers requiring PWM frequency modulation
     are not supported by this direct on/off driver).
  2. Raspberry Pi GPIO pins supply up to ~16 mA at 3.3V. While micro-piezo buzzers
     may trigger directly, driving a standard 5V buzzer directly from a GPIO pin can
     overdraw current. An NPN transistor (e.g., 2N2222 or BC547) or MOSFET driver
     circuit with a flyback protection diode should be used between GPIO 18 and
     the buzzer anode.
"""

from typing import Any, Optional

from core.logger import setup_logger
from core.models import BuzzerPattern
from hardware.base import BaseBuzzer


class GPIOBuzzer(BaseBuzzer):
    """Production proximity alert buzzer for Raspberry Pi using gpiozero.Buzzer.

    Supports continuous, fast beep, slow beep, and off patterns.
    Deferred initialization: does not access GPIO at module import time.
    """

    def __init__(
        self,
        pin: int = 18,
        active_high: bool = True,
        fast_beep_on_s: float = 0.08,
        fast_beep_off_s: float = 0.08,
        slow_beep_on_s: float = 0.15,
        slow_beep_off_s: float = 0.25,
        logger_name: str = "viss.gpio_buzzer",
    ):
        self._pin = pin
        self._active_high = active_high
        self._fast_on = fast_beep_on_s
        self._fast_off = fast_beep_off_s
        self._slow_on = slow_beep_on_s
        self._slow_off = slow_beep_off_s
        self._logger = setup_logger(logger_name)

        self._buzzer: Optional[Any] = None
        self._current_pattern: BuzzerPattern = BuzzerPattern.OFF
        self._is_closed: bool = False

    @property
    def pin(self) -> int:
        return self._pin

    @property
    def current_pattern(self) -> BuzzerPattern:
        return self._current_pattern

    def _ensure_initialized(self) -> None:
        """Lazily instantiates gpiozero.Buzzer on first access."""
        if self._buzzer is not None:
            return

        try:
            from gpiozero import Buzzer
        except ImportError as e:
            raise RuntimeError(
                "gpiozero is not installed. Install python3-gpiozero on Raspberry Pi OS "
                "to control the physical GPIO buzzer."
            ) from e

        try:
            self._buzzer = Buzzer(
                pin=self._pin,
                active_high=self._active_high,
                initial_value=False,
            )
            self._logger.info("GPIOBuzzer initialized on BCM GPIO%d.", self._pin)
        except Exception as e:
            self._buzzer = None
            self._logger.error("Failed to initialize gpiozero Buzzer on GPIO%d: %s", self._pin, e)
            raise RuntimeError(f"Could not initialize buzzer on GPIO{self._pin} ({e})") from e

    def set_pattern(self, pattern: BuzzerPattern) -> None:
        """Updates the acoustic alert pattern."""
        if self._is_closed:
            raise RuntimeError("Cannot operate on a closed GPIOBuzzer.")

        if pattern == self._current_pattern:
            return

        self._ensure_initialized()
        self._logger.info("Buzzer pattern transition: %s -> %s", self._current_pattern.value, pattern.value)
        self._current_pattern = pattern

        try:
            if pattern == BuzzerPattern.OFF:
                self._buzzer.off()
            elif pattern == BuzzerPattern.CONTINUOUS:
                self._buzzer.on()
            elif pattern == BuzzerPattern.FAST_BEEP:
                self._buzzer.beep(on_time=self._fast_on, off_time=self._fast_off, background=True)
            elif pattern == BuzzerPattern.SLOW_BEEP:
                self._buzzer.beep(on_time=self._slow_on, off_time=self._slow_off, background=True)
        except Exception as e:
            self._logger.error("Error setting buzzer pattern %s: %s", pattern.value, e)

    def turn_off(self) -> None:
        """Immediately silences the buzzer."""
        self.set_pattern(BuzzerPattern.OFF)

    def close(self) -> None:
        """Silences buzzer and releases GPIO pin."""
        if self._is_closed:
            return

        if self._buzzer is not None:
            try:
                self._buzzer.off()
                self._buzzer.close()
            except Exception as e:
                self._logger.debug("Error closing gpiozero Buzzer: %s", e)
            self._buzzer = None

        self._current_pattern = BuzzerPattern.OFF
        self._is_closed = True
        self._logger.info("GPIOBuzzer closed on GPIO%d.", self._pin)
