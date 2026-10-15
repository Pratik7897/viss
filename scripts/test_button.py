"""Milestone 10 emergency tactile push button verification script for VISS.

WIRING:
  - One leg of the button -> BCM GPIO 17 (Physical Pin 11)
  - Other leg of the button -> Ground GND (Physical Pin 9 or 14)
  - Uses internal pull-up resistor. No external resistor required.

Usage:
  python3 scripts/test_button.py [--pin 17] [--duration 15]
"""

import argparse
import os
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.logger import setup_logger
from hardware.button.gpio_button import GPIOButton


def parse_args():
    parser = argparse.ArgumentParser(description="Test emergency tactile push button")
    parser.add_argument("--pin", type=int, default=17, help="BCM GPIO pin for button (default: 17)")
    parser.add_argument("--duration", type=float, default=15.0, help="Test duration in seconds")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = setup_logger("viss.test_button")
    print("=" * 65)
    print("VISS Milestone 10: Emergency Tactile Push Button Test")
    print(f"Pin: BCM GPIO {args.pin} (Physical Pin 11) with Internal Pull-Up")
    print("Wiring: GPIO 17 to Switch Terminal 1; GND to Switch Terminal 2")
    print("=" * 65)

    button = GPIOButton(pin=args.pin, pull_up=True, bounce_time_s=0.05)
    try:
        # Trigger initialization
        _ = button.is_pressed()
        print("[PASS] GPIOButton initialized successfully.")
    except Exception as e:
        print(f"[FAIL] Could not initialize GPIO button on pin {args.pin}: {e}")
        return 1

    print("\nListening for button presses... (Press and release the button)")
    print("Press Ctrl+C to stop.\n")

    start_time = time.time()
    last_state = False
    press_count = 0

    try:
        while time.time() - start_time < args.duration:
            pressed = button.is_pressed()
            if pressed and not last_state:
                press_count += 1
                print(f"[{time.strftime('%H:%M:%S')}] BUTTON PRESSED (Event #{press_count})")
            elif not pressed and last_state:
                print(f"[{time.strftime('%H:%M:%S')}] Button released.")

            last_state = pressed
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        button.close()
        print(f"\nButton closed. Recorded {press_count} press events.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
