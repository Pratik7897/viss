"""Milestone 3 camera capture test for VISS.

Verifies CSI camera initialization via Picamera2 on Raspberry Pi,
captures a single RGB video frame, checks shape/dimensions, and writes
an image preview to disk.

Usage:
  python3 scripts/test_camera.py [--output frame.jpg]
"""

import argparse
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.logger import setup_logger
from hardware.camera.picam2_camera import PiCamera2Driver


def parse_args():
    parser = argparse.ArgumentParser(description="Test CSI camera capture via Picamera2")
    parser.add_argument("--output", type=str, default="test_capture.jpg", help="Output file path to save test frame")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = setup_logger("viss.test_camera")
    print("=" * 65)
    print("VISS CSI Camera (Picamera2) Hardware Verification")
    print("=" * 65)

    cam = PiCamera2Driver(width=640, height=480)
    try:
        print("Starting PiCamera2Driver (resolution: 640x480 RGB888)...")
        cam.start()
    except RuntimeError as e:
        print(f"[FAIL] Could not start CSI camera: {e}")
        print("\nTroubleshooting Checklist:")
        print("1. Ensure ribbon cable is seated firmly with metal contacts facing the HDMI ports.")
        print("2. Ensure camera interface is enabled in /boot/firmware/config.txt (camera_auto_detect=1).")
        print("3. Verify with 'rpicam-hello --list-cameras'.")
        return 1

    try:
        print("Capturing single video frame...")
        frame = cam.capture_frame()
        if frame is None:
            print("[FAIL] Frame capture returned None.")
            return 1

        print(f"[PASS] Successfully captured frame!")
        print(f"  Shape: {frame.shape}")
        print(f"  Type:  {frame.dtype}")
        print(f"  Size:  {frame.size} bytes")

        # Optionally save using PIL or cv2 if installed
        saved = False
        try:
            import cv2
            # BaseCamera returns RGB; cv2 expects BGR for imwrite
            bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            cv2.imwrite(args.output, bgr)
            print(f"  Saved test image preview to '{args.output}' via OpenCV.")
            saved = True
        except ImportError:
            pass

        if not saved:
            try:
                from PIL import Image
                img = Image.fromarray(frame)
                img.save(args.output)
                print(f"  Saved test image preview to '{args.output}' via PIL.")
                saved = True
            except ImportError:
                print(f"  (Note: Install python3-opencv or PIL to save '{args.output}' preview to disk)")

        return 0
    finally:
        print("Stopping camera...")
        cam.stop()
        print("Camera hardware closed cleanly.")


if __name__ == "__main__":
    sys.exit(main())
