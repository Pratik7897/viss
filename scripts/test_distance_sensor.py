"""Milestone 9 HC-SR04 ultrasonic distance sensor verification script for VISS.

ELECTRICAL WARNING:
  Do NOT connect HC-SR04 ECHO directly to GPIO 23 without a voltage divider!
  HC-SR04 ECHO is 5.0V. Raspberry Pi GPIO is 3.3V maximum.
  Ensure a 1k:2k voltage divider or level shifter is installed before running this test.

Usage:
  python3 scripts/test_distance_sensor.py [--trig 24] [--echo 23] [--duration 15]
"""

import argparse
import os
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.logger import setup_logger
from core.models import ReadingQuality
from hardware.distance.gpio_distance import GPIODistanceSensor


def parse_args():
    parser = argparse.ArgumentParser(description="Test HC-SR04 ultrasonic distance sensor")
    parser.add_argument("--trig", type=int, default=24, help="BCM GPIO pin for TRIG (default: 24)")
    parser.add_argument("--echo", type=int, default=23, help="BCM GPIO pin for ECHO (default: 23)")
    parser.add_argument("--duration", type=float, default=15.0, help="Test duration in seconds")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = setup_logger("viss.test_distance")
    print("=" * 65)
    print("VISS Milestone 9: HC-SR04 Ultrasonic Distance Sensor Test")
    print(f"TRIG: BCM GPIO {args.trig} (Pin 18)")
    print(f"ECHO: BCM GPIO {args.echo} (Pin 16) [PROTECTED BY VOLTAGE DIVIDER]")
    print("=" * 65)

    sensor = GPIODistanceSensor(trig_pin=args.trig, echo_pin=args.echo)
    try:
        sensor.start()
        print("[PASS] GPIODistanceSensor initialized successfully.")
    except Exception as e:
        print(f"[FAIL] Could not initialize sensor: {e}")
        return 1

    print("\nReading distance values (hold an obstacle 10 cm - 150 cm in front):")
    print("Press Ctrl+C to stop.\n")

    start_time = time.time()
    valid_count = 0
    total_count = 0

    try:
        while time.time() - start_time < args.duration:
            reading = sensor.read_distance()
            total_count += 1
            if reading.quality == ReadingQuality.VALID:
                valid_count += 1
                dist_cm = reading.distance_m * 100.0
                bar = "#" * int(min(50, dist_cm / 3))
                print(f"[{reading.quality.value:5s}] {dist_cm:6.1f} cm | {bar}")
            else:
                print(f"[{reading.quality.value:5s}] reading: {reading.distance_m}")

            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        sensor.stop()
        print("\nSensor stopped.")
        print(f"Summary: {valid_count}/{total_count} valid readings received.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
