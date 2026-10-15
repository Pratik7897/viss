"""Milestone 7 & 8 live camera inference and spoken alert test for VISS.

Integrates:
1. PiCamera2 CSI camera capture
2. MobileNet-SSD neural network inference via OpenCV DNN
3. Real-time spoken announcements through earphones via VoiceAlertPlayer

Usage:
  python3 scripts/test_live_inference.py [--duration 20] [--confidence 0.50]
"""

import argparse
import os
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import VisionConfig, get_config
from core.logger import setup_logger
from core.voice_alert import VoiceAlertPlayer
from hardware.camera.picam2_camera import PiCamera2Driver
from vision.detector import ObjectDetector, OpenCVInferenceEngine
from vision.pipeline import VisionPipeline


def parse_args():
    parser = argparse.ArgumentParser(description="Test live camera object detection and spoken alerts")
    parser.add_argument("--duration", type=float, default=20.0, help="Test run duration in seconds")
    parser.add_argument("--confidence", type=float, default=0.50, help="Confidence threshold (0.0 to 1.0)")
    parser.add_argument("--prototxt", type=str, default="vision/weights/MobileNetSSD_deploy.prototxt")
    parser.add_argument("--weights", type=str, default="vision/weights/MobileNetSSD_deploy.caffemodel")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = setup_logger("viss.test_live_inference")
    print("=" * 70)
    print("VISS Milestone 7 & 8: Live Camera Inference & Spoken Announcements")
    print("=" * 70)

    # 1. Verify model weights
    if not os.path.isfile(args.prototxt) or not os.path.isfile(args.weights):
        print(f"[FAIL] MobileNet-SSD model files missing!")
        print(f"  Prototxt: {args.prototxt} ({'Found' if os.path.isfile(args.prototxt) else 'MISSING'})")
        print(f"  Weights:  {args.weights} ({'Found' if os.path.isfile(args.weights) else 'MISSING'})")
        print("\nDownload them first:")
        print("  curl -L -o vision/weights/MobileNetSSD_deploy.prototxt \\")
        print("    https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/voc/MobileNetSSD_deploy.prototxt")
        print("  curl -L -o vision/weights/MobileNetSSD_deploy.caffemodel \\")
        print("    https://github.com/chuanqi305/MobileNet-SSD/raw/master/MobileNetSSD_deploy.caffemodel")
        return 1

    # 2. Initialize OpenCV Inference Engine
    try:
        print("Loading MobileNet-SSD Caffe model into OpenCV DNN...")
        engine = OpenCVInferenceEngine(
            prototxt_path=args.prototxt,
            weights_path=args.weights,
            swap_rb=True,
        )
        print("[PASS] OpenCVInferenceEngine ready.")
    except Exception as e:
        print(f"[FAIL] Could not load OpenCV inference engine: {e}")
        return 1

    # 3. Initialize Camera
    cam = PiCamera2Driver(width=640, height=480)
    try:
        print("Starting PiCamera2 CSI camera...")
        cam.start()
        print("[PASS] Camera active.")
    except Exception as e:
        print(f"[FAIL] Could not start CSI camera: {e}")
        return 1

    # 4. Initialize Voice Player
    voice = VoiceAlertPlayer(
        enabled=True,
        cooldown_s=3.0,
        announcement_format="{label} detected",
    )
    print(f"Voice Alert Engine: {'[ACTIVE]' if voice.is_available else '[DISABLED / UNAVAILABLE]'}")

    # 5. Assemble Detector and Pipeline
    vision_cfg = VisionConfig(
        confidence_threshold=args.confidence,
        target_classes=("person", "dog", "cat", "car"),
        filter_to_targets=True,
    )
    detector = ObjectDetector(config=vision_cfg, engine=engine)
    pipeline = VisionPipeline(camera=cam, detector=detector)

    print("\nRunning live inference pipeline for %.1f seconds..." % args.duration)
    print("Point the camera at a person, car, or pet to trigger spoken voice alerts.")
    print("Press Ctrl+C to abort early.\n")

    start_time = time.time()
    frames_processed = 0

    try:
        while time.time() - start_time < args.duration:
            loop_start = time.time()
            frame_detections = pipeline.capture_and_detect()
            frames_processed += 1

            if frame_detections and frame_detections.detections:
                targets = [d.label for d in frame_detections.detections]
                print(f"[{time.strftime('%H:%M:%S')}] Detected targets: {', '.join(targets)}")
                for d in frame_detections.detections:
                    print(f"   -> {d.label.upper()} (confidence: {d.confidence:.2f}, bbox: {d.box.to_tuple()})")
                    voice.announce(d.label)
            else:
                if frames_processed % 15 == 0:
                    print(f"[{time.strftime('%H:%M:%S')}] Scanning... (no target objects in frame)")

            elapsed = time.time() - loop_start
            sleep_time = max(0.0, 0.05 - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        pipeline.stop()
        voice.close()
        total_time = time.time() - start_time
        fps = frames_processed / max(0.1, total_time)
        print("\n" + "=" * 70)
        print(f"Session Summary:")
        print(f"  Processed {frames_processed} frames in {total_time:.1f}s ({fps:.1f} FPS)")
        print(f"  Announcements made: {voice.announcements_made}")
        print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
