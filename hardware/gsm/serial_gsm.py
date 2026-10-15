"""Serial UART driver for SIM800L cellular GSM modem using pyserial.

ELECTRICAL AND POWER WARNING:
  1. The SIM800L module requires 3.7V - 4.4V (nominal 4.0V) and draws up to 2.0A
     burst transmit current during cellular uplink bursts.
  2. The SIM800L CANNOT be powered from the Raspberry Pi 5V rail (destroys module)
     or the 3.3V rail (causes continuous brownouts and bootloops).
  3. A dedicated 3.7V Li-ion battery (18650 cell with protection board) or a
     regulated 4.0V DC-DC converter is required, sharing a common ground with the Pi.
  4. Raspberry Pi UART TXD (3.3V) connects to SIM800L RXD; SIM800L TXD connects to Pi RXD.
"""

import time
from typing import Any, Optional, Tuple

from core.logger import setup_logger
from hardware.base import BaseGSM


class SerialGSM(BaseGSM):
    """Production SIM800L cellular modem driver communicating over serial UART.

    Implements AT-command sequence matching Black Book Ch 5.3.1.
    Deferred initialization: does not access serial ports at module import time.
    """

    def __init__(
        self,
        port: str = "/dev/ttyS0",
        baudrate: int = 9600,
        timeout_s: float = 2.0,
        sms_timeout_s: float = 20.0,
        logger_name: str = "viss.serial_gsm",
    ):
        self._port = port
        self._baudrate = baudrate
        self._timeout_s = timeout_s
        self._sms_timeout_s = sms_timeout_s
        self._logger = setup_logger(logger_name)

        self._serial: Optional[Any] = None
        self._is_closed: bool = False

    @property
    def port(self) -> str:
        return self._port

    @property
    def baudrate(self) -> int:
        return self._baudrate

    @property
    def is_closed(self) -> bool:
        return self._is_closed

    def _open_serial(self) -> Any:
        """Opens serial UART device using pyserial."""
        try:
            import serial
        except ImportError as e:
            raise RuntimeError(
                "pyserial is not installed. Install pyserial (or python3-serial on Raspberry Pi OS) "
                "to communicate with the SIM800L modem."
            ) from e

        try:
            ser = serial.Serial(
                port=self._port,
                baudrate=self._baudrate,
                timeout=self._timeout_s,
            )
            return ser
        except Exception as e:
            self._logger.error("Failed to open serial port '%s': %s", self._port, e)
            raise RuntimeError(f"UART port '{self._port}' could not be opened: {e}") from e

    def _send_cmd(
        self,
        ser: Any,
        cmd: str,
        expect: str = "OK",
        delay_s: float = 0.2,
        tries: int = 2,
    ) -> Tuple[bool, str]:
        """Sends an AT command and checks for expected response string."""
        last_resp = ""
        for attempt in range(tries):
            try:
                ser.write((cmd + "\r").encode())
                time.sleep(delay_s)
                bytes_to_read = getattr(ser, "in_waiting", 0) or 200
                raw = ser.read(bytes_to_read)
                last_resp = raw.decode(errors="ignore") if isinstance(raw, bytes) else str(raw)
                if expect in last_resp:
                    return True, last_resp
            except Exception as e:
                self._logger.debug("AT command attempt %d failed: %s", attempt + 1, e)
        return False, last_resp

    @property
    def is_ready(self) -> bool:
        """Checks if modem responds to AT synchronization."""
        if self._is_closed:
            return False

        ser = None
        try:
            ser = self._open_serial()
            ok, _ = self._send_cmd(ser, "AT", expect="OK", tries=2)
            return ok
        except Exception as e:
            self._logger.debug("Modem readiness check failed: %s", e)
            return False
        finally:
            if ser is not None:
                try:
                    ser.close()
                except Exception:
                    pass

    def send_sms(self, phone_number: str, message: str) -> Tuple[bool, str]:
        """Dispatches an SMS message using SIM800L AT command sequence.

        AT sequence:
          1. AT -> Check attention / link
          2. ATE0 -> Disable local echo
          3. AT+CMGF=1 -> Set SMS text format
          4. AT+CMGS="<number>" -> Request prompt (expect '>')
          5. <text> + \x1A (Ctrl+Z) -> Submit message payload
          6. Wait for +CMGS: and OK response
        """
        if self._is_closed:
            return False, "SIM800L driver is closed"

        if not phone_number or len(phone_number.strip()) < 5:
            return False, f"Invalid phone number '{phone_number}'"

        ser = None
        try:
            ser = self._open_serial()

            # 1. Attention sync
            ok, resp = self._send_cmd(ser, "AT", expect="OK", tries=2)
            if not ok:
                return False, f"No modem response to AT: {resp.strip()}"

            # 2. Disable command echo
            self._send_cmd(ser, "ATE0", expect="OK", tries=1)

            # 3. Set SMS text mode
            ok, resp = self._send_cmd(ser, "AT+CMGF=1", expect="OK", tries=2)
            if not ok:
                return False, f"Failed to set text mode (AT+CMGF=1): {resp.strip()}"

            # 4. Initiate SMS message
            cmgs_cmd = f'AT+CMGS="{phone_number}"'
            ok, resp = self._send_cmd(ser, cmgs_cmd, expect=">", delay_s=0.3, tries=2)
            if not ok:
                return False, f"Failed to obtain CMGS prompt (>): {resp.strip()}"

            # 5. Send message payload terminated by Ctrl+Z (\x1A)
            payload = (message + "\x1A").encode()
            ser.write(payload)

            # 6. Wait for confirmation (+CMGS: ... OK)
            deadline = time.time() + self._sms_timeout_s
            buf = ""
            while time.time() < deadline:
                bytes_avail = getattr(ser, "in_waiting", 0) or 1
                chunk = ser.read(bytes_avail)
                if chunk:
                    chunk_str = chunk.decode(errors="ignore") if isinstance(chunk, bytes) else str(chunk)
                    buf += chunk_str
                    if "+CMGS:" in buf and "OK" in buf:
                        self._logger.info("SMS successfully dispatched to %s.", phone_number)
                        return True, "SMS sent successfully (SIM800L)"
                time.sleep(0.1)

            self._logger.warning("SMS submission timed out after %.1fs. Buffer: %s", self._sms_timeout_s, buf)
            return False, f"SMS delivery timeout: {buf.strip()}"

        except Exception as e:
            self._logger.error("Exception during SMS transmission: %s", e)
            return False, f"UART communication failure: {e}"
        finally:
            if ser is not None:
                try:
                    ser.close()
                except Exception as e:
                    self._logger.debug("Error closing serial port: %s", e)

    def close(self) -> None:
        """Closes modem driver."""
        self._is_closed = True
        self._logger.info("SerialGSM driver closed on %s.", self._port)
