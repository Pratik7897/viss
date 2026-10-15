"""Milestone 11 SIM800L GSM modem serial UART communication test for VISS.

ELECTRICAL AND POWER WARNING:
  - SIM800L requires 3.7V - 4.4V (nominal 4.0V) and draws up to 2.0A peak current!
  - Do NOT power SIM800L from Raspberry Pi 3.3V or 5V rail directly!
  - Common ground: External supply GND must connect to Raspberry Pi GND.
  - UART: Pi TXD (Pin 8) -> SIM800L RXD; Pi RXD (Pin 10) <- SIM800L TXD.

Usage:
  python3 scripts/test_gsm_uart.py [--port /dev/ttyS0] [--baud 9600] [--test-sms +91XXXXXXXXXX]
"""

import argparse
import os
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.logger import setup_logger
from hardware.gsm.serial_gsm import SerialGSM


def parse_args():
    parser = argparse.ArgumentParser(description="Test SIM800L GSM serial UART communication")
    parser.add_argument("--port", type=str, default="/dev/ttyS0", help="UART port (default: /dev/ttyS0)")
    parser.add_argument("--baud", type=int, default=9600, help="UART baudrate (default: 9600)")
    parser.add_argument("--test-sms", type=str, default=None, help="Optional destination phone number to send test SMS")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = setup_logger("viss.test_gsm")
    print("=" * 65)
    print("VISS Milestone 11: SIM800L GSM Serial UART Test")
    print(f"Port: {args.port} @ {args.baud} baud")
    print("=" * 65)

    if not os.path.exists(args.port):
        print(f"[FAIL] Serial port '{args.port}' does not exist on this system.")
        print("  On Raspberry Pi: Ensure serial hardware is enabled in raspi-config.")
        print("  Check available serial ports: ls -l /dev/ttyS* /dev/ttyAMA* /dev/serial*")
        return 1

    gsm = SerialGSM(port=args.port, baudrate=args.baud, timeout_s=3.0)

    print(f"1. Checking AT synchronization on {args.port}...")
    ready = gsm.is_ready()
    if not ready:
        print(f"[FAIL] SIM800L did not respond to 'AT' command on {args.port}.")
        print("\nTroubleshooting Checklist:")
        print("1. Power supply: Is the SIM800L receiving 3.7V - 4.4V with >=2A capacity?")
        print("2. Common ground: Is the external power supply GND tied to Raspberry Pi GND?")
        print("3. TX/RX crossover: Pi TX (Pin 8) must go to SIM800L RX; Pi RX (Pin 10) to SIM800L TX.")
        print("4. Serial console: Is Linux login console disabled on this port in raspi-config?")
        print("5. Permissions: Is the user in the 'dialout' group? ('sudo usermod -aG dialout $USER')")
        return 1

    print("[PASS] SIM800L responded OK to AT synchronization!")

    # Check network registration if interactive
    try:
        import serial
        ser = serial.Serial(args.port, args.baud, timeout=2.0)
        ser.write(b"AT+CSQ\r")
        time.sleep(0.3)
        csq = ser.read(ser.in_waiting or 100).decode(errors="ignore")
        print(f"2. Signal Quality (AT+CSQ): {csq.strip()}")

        ser.write(b"AT+CREG?\r")
        time.sleep(0.3)
        creg = ser.read(ser.in_waiting or 100).decode(errors="ignore")
        print(f"3. Network Registration (AT+CREG?): {creg.strip()}")
        ser.close()
    except Exception as e:
        print(f"  Note: Could not run extended AT commands: {e}")

    # Optional SMS test
    if args.test_sms:
        print(f"\n4. Sending test SMS to '{args.test_sms}'...")
        success, msg = gsm.send_sms(args.test_sms, "VISS System Alert: Hardware Test Message from Raspberry Pi 4.")
        print(f"  Result: {'[PASS]' if success else '[FAIL]'} {msg}")
    else:
        print("\n(Skipping live SMS test. Pass '--test-sms +<number>' to test SMS dispatch).")

    gsm.close()
    print("\nSIM800L test completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
