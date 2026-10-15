"""Raspberry Pi GPIO tactile push button driver using gpiozero."""

from typing import Any, Optional

from core.logger import setup_logger
from hardware.base import BaseButton


class GPIOButton(BaseButton):
    """Production tactile push button driver for Raspberry Pi using gpiozero.Button.

    Supports internal pull-up and hardware debouncing.
    Deferred initialization: does not access GPIO at module import time.
    """

    def __init__(
        self,
        pin: int = 17,
        pull_up: bool = True,
        bounce_time_s: float = 0.05,
        logger_name: str = "viss.gpio_button",
    ):
        self._pin = pin
        self._pull_up = pull_up
        self._bounce_time_s = bounce_time_s
        self._logger = setup_logger(logger_name)

        self._button: Optional[Any] = None
        self._is_closed: bool = False

    @property
    def pin(self) -> int:
        return self._pin

    @property
    def is_closed(self) -> bool:
        return self._is_closed

    def _ensure_initialized(self) -> None:
        """Lazily instantiates gpiozero.Button on first access."""
        if self._button is not None:
            return

        try:
            from gpiozero import Button
        except ImportError as e:
            raise RuntimeError(
                "gpiozero is not installed. Install python3-gpiozero on Raspberry Pi OS "
                "to read the physical emergency push button."
            ) from e

        try:
            self._button = Button(
                pin=self._pin,
                pull_up=self._pull_up,
                bounce_time=self._bounce_time_s,
            )
            self._logger.info(
                "GPIOButton initialized on BCM GPIO%d (pull_up=%s, bounce=%.2fs).",
                self._pin,
                self._pull_up,
                self._bounce_time_s,
            )
        except Exception as e:
            self._button = None
            self._logger.error("Failed to initialize gpiozero Button on GPIO%d: %s", self._pin, e)
            raise RuntimeError(f"Could not initialize push button on GPIO{self._pin} ({e})") from e

    def is_pressed(self) -> bool:
        """Returns True if the button is currently held down, False otherwise."""
        if self._is_closed:
            return False

        try:
            self._ensure_initialized()
            return bool(self._button.is_pressed)
        except Exception as e:
            self._logger.warning("Error reading button state on GPIO%d: %s", self._pin, e)
            return False

    def close(self) -> None:
        """Releases GPIO pin resources."""
        if self._is_closed:
            return

        if self._button is not None:
            try:
                self._button.close()
            except Exception as e:
                self._logger.debug("Error closing gpiozero Button: %s", e)
            self._button = None

        self._is_closed = True
        self._logger.info("GPIOButton closed on GPIO%d.", self._pin)
