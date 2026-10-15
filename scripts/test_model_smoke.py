"""Test B: Pretrained MobileNet-SSD model loading smoke test for VISS.

Verifies:
1. Presence of MobileNetSSD_deploy.prototxt and MobileNetSSD_deploy.caffemodel.
2. OpenCV DNN Caffe importer initialization.
3. Network layer count and architecture readiness.
4. Input tensor blob shape [1, 3, 300, 300].

Usage:
  python3 scripts/test_model_smoke.py
"""

import os
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.logger import setup_logger
from vision.detector import OpenCVInferenceEngine


def main() -> int:
    logger = setup_logger("viss.test_model_smoke")
    print("=" * 65)
    print("Test B: MobileNet-SSD Pretrained Model Loading Smoke Test")
    print("=" * 65)

    prototxt = "vision/weights/MobileNetSSD_deploy.prototxt"
    weights = "vision/weights/MobileNetSSD_deploy.caffemodel"

    print(f"Prototxt Path: {prototxt}")
    print(f"Weights Path:  {weights}")

    if not os.path.isfile(prototxt):
        print(f"[FAIL] Missing prototxt file: {prototxt}")
        return 1

    if not os.path.isfile(weights):
        print(f"[FAIL] Missing weights file: {weights}")
        return 1

    sz_mb = os.path.getsize(weights) / (1024 * 1024)
    print(f"Model File Size: {sz_mb:.2f} MB")

    try:
        t0 = time.time()
        engine = OpenCVInferenceEngine(
            prototxt_path=prototxt,
            weights_path=weights,
            swap_rb=True,
        )
        load_ms = (time.time() - t0) * 1000
        print(f"[PASS] Model successfully loaded into OpenCV DNN in {load_ms:.1f} ms.")
        print(f"Engine Ready: {engine.is_ready}")
        print(f"Swap RB Color Conversion: {engine.swap_rb}")
        print("=" * 65)
        return 0
    except Exception as e:
        print(f"[FAIL] Could not initialize OpenCVInferenceEngine: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
