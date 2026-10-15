"""Application entry point for Visual Impairment Support System (VISS).

Usage:
  python3 main.py                  # Runs in simulation/mock mode on macOS
  python3 main.py --mode hardware  # Runs on Raspberry Pi with real hardware
  python3 main.py --duration 10    # Runs simulation for 10 seconds and exits
  python3 main.py --help           # Shows available command-line flags
"""

import argparse
import os
import signal
import sys
import time

from config.settings import AppConfig, get_config
from core.controller import ApplicationController
from core.logger import setup_logger


def parse_arguments() -> argparse.Namespace:
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Visual Impairment Support System (VISS) - Assistive Navigation Aid",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Run for specified seconds then exit cleanly (useful for testing/simulation).",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity level.",
    )
    parser.add_argument(
        "--sound",
        action="store_true",
        help="Enable WAV audio alert playback via system afplay/aplay.",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="mock",
        choices=["mock", "hardware", "mac"],
        help="Target execution mode: 'mock' (macOS simulation), 'mac' (real Mac webcam + real model + real speech), or 'hardware' (Raspberry Pi physical devices).",
    )
    parser.add_argument(
        "--camera-index",
        type=int,
        default=0,
        help="Device index of the camera (0 for built-in Mac FaceTime webcam, 1 for external USB webcam).",
    )
    parser.add_argument(
        "--no-voice",
        action="store_true",
        help="Disable spoken voice announcements (TTS).",
    )
    parser.add_argument(
        "--target-classes",
        type=str,
        default="all",
        help="Target classes to detect ('all' for all 20 VOC classes, or comma-separated list like 'person,dog,chair,bottle').",
    )
    return parser.parse_args()


def main() -> int:
    """Bootstraps and runs the VISS controller."""
    args = parse_arguments()
    logger = setup_logger("viss.main", level=args.log_level)

    mode_descriptions = {
        "hardware": "Production Hardware (Raspberry Pi 4/5)",
        "mac": "macOS Real Mode (Real Webcam + Real MobileNet-SSD + Offline Speech)",
        "mock": "Mock Simulation (macOS - No physical hardware needed)",
    }

    logger.info("=" * 65)
    logger.info("Visual Impairment Support System (VISS) - Starting...")
    logger.info("Mode: %s", mode_descriptions.get(args.mode, args.mode))
    logger.info("=" * 65)

    # Propagate CLI flags into environment BEFORE calling get_config()
    # so that the config factory picks them up consistently.
    if args.mode == "hardware":
        os.environ["VISS_MOCK_MODE"] = "false"
    else:
        os.environ["VISS_MOCK_MODE"] = "true"

    if args.sound:
        os.environ["VISS_ENABLE_SOUND"] = "true"

    if args.no_voice:
        os.environ["VISS_ENABLE_VOICE"] = "false"

    if args.target_classes:
        os.environ["VISS_TARGET_CLASSES"] = args.target_classes

    config = get_config()

    try:
        if args.mode == "hardware":
            controller = ApplicationController.create_hardware(config=config)
        elif args.mode == "mac":
            controller = ApplicationController.create_mac_real(
                config=config,
                camera_device=args.camera_index,
            )
        else:
            controller = ApplicationController.create_mock(config=config)
    except RuntimeError as e:
        logger.error("Initialization failure: %s", e)
        if args.mode == "mac" and "webcam" in str(e).lower():
            logger.error(
                "macOS Camera Permission Tip: Grant camera permission to your terminal in:\n"
                "  System Settings -> Privacy & Security -> Camera"
            )
        return 1

    # Register graceful shutdown signals
    def handle_signal(sig, frame):
        logger.info("Shutdown signal received (%d). Cleaning up...", sig)
        controller.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        controller.start()
        logger.info("VISS is running. Press Ctrl+C to terminate.")

        if args.duration is not None:
            logger.info("Running for %.1f seconds...", args.duration)
            time.sleep(args.duration)
        else:
            # Keep main thread alive
            while controller.is_running:
                time.sleep(0.5)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received.")
    except RuntimeError as e:
        logger.error("Application execution halted due to hardware error: %s", e)
        return 1
    finally:
        controller.stop()
        logger.info("VISS stopped cleanly.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
