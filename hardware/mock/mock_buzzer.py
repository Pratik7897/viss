"""Mock buzzer for proximity alert simulation on macOS."""

from typing import List

from core.logger import setup_logger
from core.models import BuzzerPattern
from hardware.base import BaseBuzzer


class MockBuzzer(BaseBuzzer):
    """Simulates a buzzer without Raspberry Pi GPIO.

    Records pattern transitions and state history for verification in unit tests.
    """

    def __init__(self, logger_name: str = "viss.mock_buzzer"):
        self._logger = setup_logger(logger_name)
        self._current_pattern: BuzzerPattern = BuzzerPattern.OFF
        self._pattern_history: List[BuzzerPattern] = [BuzzerPattern.OFF]
        self._is_closed: bool = False

    def set_pattern(self, pattern: BuzzerPattern) -> None:
        """Updates acoustic alert pattern."""
        if self._is_closed:
            raise RuntimeError("Cannot operate on a closed MockBuzzer.")

        if pattern != self._current_pattern:
            self._logger.info("Buzzer pattern changed: %s -> %s", self._current_pattern.value, pattern.value)
            self._current_pattern = pattern
            self._pattern_history.append(pattern)

    def turn_off(self) -> None:
        """Silences the buzzer."""
        self.set_pattern(BuzzerPattern.OFF)

    @property
    def current_pattern(self) -> BuzzerPattern:
        return self._current_pattern

    @property
    def pattern_history(self) -> List[BuzzerPattern]:
        """Full log of pattern changes since initialization."""
        return list(self._pattern_history)

    def clear_history(self) -> None:
        """Resets the pattern history log."""
        self._pattern_history = [self._current_pattern]

    def close(self) -> None:
        """Shuts down mock buzzer."""
        self.turn_off()
        self._is_closed = True
        self._logger.debug("MockBuzzer closed.")
