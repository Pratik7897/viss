"""Mock push button for emergency trigger simulation on macOS."""

from core.logger import setup_logger
from hardware.base import BaseButton


class MockButton(BaseButton):
    """Simulates an emergency tactile push button without physical GPIO."""

    def __init__(self, logger_name: str = "viss.mock_button"):
        self._logger = setup_logger(logger_name)
        self._is_pressed: bool = False
        self._is_closed: bool = False

    def press(self) -> None:
        """Simulates pressing the button."""
        if self._is_closed:
            raise RuntimeError("Cannot press a closed MockButton.")
        self._is_pressed = True
        self._logger.info("Emergency button PRESSED.")

    def release(self) -> None:
        """Simulates releasing the button."""
        self._is_pressed = False
        self._logger.debug("Emergency button RELEASED.")

    def is_pressed(self) -> bool:
        return self._is_pressed and not self._is_closed

    def close(self) -> None:
        self._is_pressed = False
        self._is_closed = True
        self._logger.debug("MockButton closed.")
