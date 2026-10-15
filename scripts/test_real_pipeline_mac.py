"""Test F: Integrated Real-Camera -> Inference -> Spoken-Alert pipeline on macOS.

Streams live frames from your Mac webcam, runs MobileNet-SSD neural network
inference, decodes bounding boxes, and speaks detected target objects in real time.

Usage:
  python3 scripts/test_real_pipeline_mac.py [--duration 15] [--confidence 0.45] [--camera-index 0]
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
from hardware.camera.opencv_camera import OpenCVCamera
from vision.detector import ObjectDetector, OpenCVInferenceEngine
from vision.pipeline import VisionPipeline


def parse_args():
    parser = argparse.ArgumentParser(description="Test live Mac webcam object detection and spoken alerts")
    parser.add_argument("--duration", type=float, default=15.0, help="Test duration in seconds (0 for indefinite until Ctrl+C)")
    parser.add_argument("--confidence", type=float, default=0.45, help="Confidence threshold (0.0 to 1.0)")
    parser.add_argument("--camera-index", type=int, default=0, help="Webcam device index (default: 0)")
    parser.add_argument("--prototxt", type=str, default="vision/weights/MobileNetSSD_deploy.prototxt")
    parser.add_argument("--weights", type=str, default="vision/weights/MobileNetSSD_deploy.caffemodel")
    parser.add_argument(
        "--target-classes",
        type=str,
        default="all",
        help="Comma-separated target classes or 'all' to detect all 20 classes (default: 'all')",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = setup_logger("viss.test_real_pipeline_mac")
    print("=" * 70)
    print("Test F: Real Mac Webcam -> Neural Network -> Spoken Alerts Pipeline")
    print("=" * 70)

    # 1. Verify weights
    if not os.path.isfile(args.prototxt) or not os.path.isfile(args.weights):
        print(f"[FAIL] Missing model weights!")
        print(f"  Prototxt: {args.prototxt} ({'Found' if os.path.isfile(args.prototxt) else 'MISSING'})")
        print(f"  Weights:  {args.weights} ({'Found' if os.path.isfile(args.weights) else 'MISSING'})")
        return 1

    # 2. Initialize Inference Engine
    try:
        print("Loading MobileNet-SSD Caffe model into OpenCV DNN...")
        engine = OpenCVInferenceEngine(
            prototxt_path=args.prototxt,
            weights_path=args.weights,
            swap_rb=True,
        )
        print("[PASS] OpenCVInferenceEngine initialized.")
    except Exception as e:
        print(f"[FAIL] Inference engine error: {e}")
        return 1

    # 3. Initialize Mac Webcam
    camera = OpenCVCamera(device_index=args.camera_index, width=640, height=480)
    try:
        print(f"Opening Mac camera device #{args.camera_index}...")
        camera.start()
        print("[PASS] Camera connected and active.")
    except Exception as e:
        print(f"[FAIL] Could not access camera: {e}\n")
        print("Permissions Reminder:")
        print("Grant Camera permission in: Apple Menu -> System Settings -> Privacy & Security -> Camera")
        return 1

    # 4. Initialize Voice Alert Player (using native macOS say)
    voice = VoiceAlertPlayer(
        enabled=True,
        cooldown_s=3.0,
        announcement_format="{label} detected",
    )
    print(f"Voice Synthesizer: {'[READY: ' + (voice.backend_name or 'offline') + ']' if voice.is_available else '[UNAVAILABLE]'}")

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
    pipeline = VisionPipeline(camera=camera, detector=detector)

    duration_str = f"for {args.duration:.1f}s" if args.duration > 0 else "indefinitely"
    print(f"\nRunning live pipeline {duration_str}...")
    print("Step in front of the camera to trigger real-time spoken alerts.")
    print("Press Ctrl+C to terminate cleanly.\n")

    start_time = time.time()
    frames_processed = 0

    try:
        while True:
            if args.duration > 0 and (time.time() - start_time) >= args.duration:
                break

            loop_start = time.time()
            frame_detections = pipeline.capture_and_detect()
            frames_processed += 1

            if frame_detections and frame_detections.detections:
                labels = [d.label.upper() for d in frame_detections.detections]
                print(f"[{time.strftime('%H:%M:%S')}] TARGET DETECTED: {', '.join(labels)}")
                for d in frame_detections.detections:
                    box_str = f"[{d.box.x1}, {d.box.y1}, {d.box.x2}, {d.box.y2}]"
                    print(f"   -> {d.label.capitalize()} (confidence: {d.confidence:.2f}, bbox: {box_str})")
                    voice.announce(d.label)
            else:
                if frames_processed % 15 == 0:
                    print(f"[{time.strftime('%H:%M:%S')}] Monitoring... (no target in frame)")

            elapsed = time.time() - loop_start
            sleep_time = max(0.0, 0.05 - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\nPipeline interrupted by user.")
    finally:
        pipeline.stop()
        voice.close()
        total_time = time.time() - start_time
        fps = frames_processed / max(0.1, total_time)
        print("\n" + "=" * 70)
        print(f"Session Summary:")
        print(f"  Processed {frames_processed} frames in {total_time:.1f}s ({fps:.1f} FPS)")
        print(f"  Announcements made: {voice.announcements_made}")
        print(f"  Announcements deduplicated: {voice.announcements_deduplicated}")
        print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
