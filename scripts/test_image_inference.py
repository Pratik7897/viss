"""Test C: Real image inference against a supplied test image for VISS.

Executes MobileNet-SSD detection on a static image, decodes bounding boxes,
measures execution latency, and optionally announces detected objects.

Usage:
  python3 scripts/test_image_inference.py [--image path/to/image.jpg] [--confidence 0.40] [--speak]
"""

import argparse
import os
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import VisionConfig
from core.logger import setup_logger
from core.voice_alert import VoiceAlertPlayer
from vision.detector import ObjectDetector, OpenCVInferenceEngine


def parse_args():
    parser = argparse.ArgumentParser(description="Test MobileNet-SSD inference on a static image")
    parser.add_argument(
        "--image",
        type=str,
        default="vision/test_assets/sample_cat.jpg",
        help="Path to input image file (JPEG or PNG)",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.40,
        help="Detection confidence threshold between 0.0 and 1.0 (default: 0.40)",
    )
    parser.add_argument(
        "--speak",
        action="store_true",
        help="Speak detected object names through system audio (TTS)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional path to save output image annotated with bounding boxes",
    )
    parser.add_argument(
        "--target-classes",
        type=str,
        default="all",
        help="Comma-separated target classes or 'all' to detect all 20 classes (default: 'all')",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = setup_logger("viss.test_image_inference")
    print("=" * 70)
    print("Test C: Still Image Inference with MobileNet-SSD")
    print("=" * 70)

    if not os.path.isfile(args.image):
        print(f"[FAIL] Input image not found: '{args.image}'")
        return 1

    try:
        import cv2
    except ImportError:
        print("[FAIL] OpenCV (cv2) is required. Install with: pip install 'opencv-python<5.0'")
        return 1

    # 1. Read input image
    bgr = cv2.imread(args.image)
    if bgr is None:
        print(f"[FAIL] OpenCV could not decode image: '{args.image}'")
        return 1

    h, w = bgr.shape[:2]
    print(f"Loaded image: '{args.image}' (Resolution: {w}x{h}, Channels: {bgr.shape[2]})")

    # BaseCamera / ObjectDetector contract expects canonical RGB frames
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    # 2. Load model
    prototxt = "vision/weights/MobileNetSSD_deploy.prototxt"
    weights = "vision/weights/MobileNetSSD_deploy.caffemodel"
    try:
        engine = OpenCVInferenceEngine(
            prototxt_path=prototxt,
            weights_path=weights,
            swap_rb=True,
        )
    except Exception as e:
        print(f"[FAIL] Could not load model: {e}")
        return 1

    from config.settings import ALL_PASCAL_VOC_CLASSES
    if args.target_classes.strip().lower() == "all":
        targets = ALL_PASCAL_VOC_CLASSES
        filter_targets = False
    else:
        targets = tuple(c.strip().lower() for c in args.target_classes.split(",") if c.strip())
        filter_targets = True

    vision_cfg = VisionConfig(
        confidence_threshold=args.confidence,
        target_classes=targets,
        filter_to_targets=filter_targets,
    )
    detector = ObjectDetector(config=vision_cfg, engine=engine)

    # 3. Perform inference & benchmark latency
    print(f"Running detection (confidence threshold: {args.confidence:.2f})...")
    t0 = time.time()
    detections = detector.detect(rgb)
    latency_ms = (time.time() - t0) * 1000

    print(f"[PASS] Inference completed in {latency_ms:.2f} ms ({1000.0/max(1.0, latency_ms):.1f} FPS equivalent).")
    print("-" * 70)
    print(f"Detected {len(detections.detections)} target objects:")

    for idx, d in enumerate(detections.detections, 1):
        box_coords = f"[{d.box.x1}, {d.box.y1}, {d.box.x2}, {d.box.y2}]"
        print(f"  #{idx}: {d.label.upper():8s} | Confidence: {d.confidence:.2f} ({d.confidence*100:.1f}%) | BBox: {box_coords}")

        if args.output:
            # Draw bounding box on BGR image
            cv2.rectangle(bgr, (d.box.x1, d.box.y1), (d.box.x2, d.box.y2), (0, 255, 0), 2)
            cv2.putText(
                bgr,
                f"{d.label} {d.confidence:.2f}",
                (d.box.x1, max(15, d.box.y1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2,
            )

    if args.output:
        cv2.imwrite(args.output, bgr)
        print(f"\nSaved annotated image to: {args.output}")

    # 4. Optional spoken alert announcement
    if args.speak and len(detections.detections) > 0:
        print("\nAnnouncing detected objects via voice alert player...")
        voice = VoiceAlertPlayer(enabled=True, cooldown_s=0.5)
        for d in detections.detections:
            voice.announce(d.label)
            time.sleep(1.8)
        voice.close()

    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
