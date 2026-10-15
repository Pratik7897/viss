"""Mock cellular GSM modem for macOS testing without physical SIM800L or UART."""

import time
from typing import Any, Dict, List, Tuple

from core.logger import setup_logger
from hardware.base import BaseGSM


class MockGSM(BaseGSM):
    """Simulates a SIM800L GSM modem.

    Records outgoing SMS messages in memory and allows injecting simulated
    cellular connection errors or timeouts.
    """

    def __init__(self, logger_name: str = "viss.mock_gsm"):
        self._logger = setup_logger(logger_name)
        self._is_ready: bool = True
        self._simulate_failure: bool = False
        self._sent_messages: List[Dict[str, Any]] = []
        self._is_closed: bool = False

    def send_sms(self, phone_number: str, message: str) -> Tuple[bool, str]:
        """Simulates sending an SMS without cellular hardware."""
        if self._is_closed:
            return False, "Modem is closed"

        if not self._is_ready:
            self._logger.warning("SMS failed: SIM800L modem not registered on network.")
            return False, "Network not registered (NO CARRIER)"

        if self._simulate_failure:
            self._logger.warning("SMS failed: Simulated transmission error.")
            return False, "Simulated AT command error / Timeout"

        if not phone_number or len(phone_number.strip()) < 5:
            self._logger.error("SMS failed: Invalid phone number '%s'.", phone_number)
            return False, "Invalid phone number format"

        record = {
            "phone_number": phone_number,
            "message": message,
            "timestamp": time.time(),
        }
        self._sent_messages.append(record)
        self._logger.info("SMS successfully simulated to %s (%d chars)", phone_number, len(message))
        self._logger.debug("SMS payload: %s", message.replace("\n", " | "))
        return True, "SMS sent successfully (Mock)"

    @property
    def is_ready(self) -> bool:
        return self._is_ready and not self._is_closed

    def set_network_ready(self, ready: bool) -> None:
        """Toggles network registration state."""
        self._is_ready = ready

    def set_simulate_failure(self, simulate_fail: bool) -> None:
        """Injects simulated transmission failures."""
        self._simulate_failure = simulate_fail

    @property
    def sent_messages(self) -> List[Dict[str, Any]]:
        """Returns all messages sent through this mock instance."""
        return list(self._sent_messages)

    def clear_messages(self) -> None:
        """Clears the sent message log."""
        self._sent_messages.clear()

    def close(self) -> None:
        """Shuts down mock modem."""
        self._is_closed = True
        self._logger.debug("MockGSM closed.")
