"""Test D: Mac webcam initialization and frame capture test for VISS.

Tests local camera capture via OpenCVCamera on macOS, verifies RGB frame output,
and diagnoses camera permissions.

Usage:
  python3 scripts/test_mac_webcam.py [--device-index 0] [--output webcam_test.jpg]
"""

import argparse
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.logger import setup_logger
from hardware.camera.opencv_camera import OpenCVCamera


def parse_args():
    parser = argparse.ArgumentParser(description="Test Mac webcam capture via OpenCVCamera")
    parser.add_argument("--device-index", type=int, default=0, help="Webcam device index (default: 0)")
    parser.add_argument("--output", type=str, default="webcam_test.jpg", help="File to save captured preview")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = setup_logger("viss.test_mac_webcam")
    print("=" * 65)
    print(f"Test D: Mac Webcam (OpenCVCamera) Verification [Device #{args.device_index}]")
    print("=" * 65)

    cam = OpenCVCamera(device_index=args.device_index, width=640, height=480)

    try:
        print(f"Attempting to open camera device index {args.device_index}...")
        cam.start()
        print("[PASS] Camera opened successfully.")
    except Exception as e:
        print(f"[FAIL] Could not access webcam at index {args.device_index}: {e}\n")
        print("Troubleshooting & Permissions Checklist:")
        print("1. If using macOS, ensure your Terminal / IDE has Camera permission:")
        print("   Apple Menu -> System Settings -> Privacy & Security -> Camera -> Enable your terminal.")
        print("2. If another application (FaceTime, Zoom, Photo Booth) is using the camera, close it.")
        print("3. Try external USB camera by passing '--device-index 1'.")
        return 1

    try:
        print("Capturing single RGB video frame...")
        frame = cam.capture_frame()
        if frame is None:
            print("[FAIL] Captured frame is None.")
            return 1

        print(f"[PASS] Successfully captured frame!")
        print(f"  Shape: {frame.shape} (Height x Width x RGB Channels)")
        print(f"  Data Type: {frame.dtype}")
        print(f"  Memory Size: {frame.size} bytes")

        try:
            import cv2
            # BaseCamera returns RGB; cv2.imwrite expects BGR
            bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            cv2.imwrite(args.output, bgr)
            print(f"  Saved preview image to: '{args.output}'")
        except Exception as e:
            print(f"  Note: Could not save preview image to disk: {e}")

        return 0
    finally:
        print("Releasing camera hardware...")
        cam.stop()
        print("Camera closed cleanly.")


if __name__ == "__main__":
    sys.exit(main())
