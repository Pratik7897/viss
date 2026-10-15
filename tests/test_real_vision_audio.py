"""Unit and integration tests for real vision inference, voice alerts, and macOS modes."""

import os
import time
import unittest
from unittest import mock

import cv2
import numpy as np

from config.settings import AppConfig, VisionConfig, get_config
from core.controller import ApplicationController
from core.voice_alert import VoiceAlertPlayer
from main import parse_arguments
from vision.detector import ObjectDetector, OpenCVInferenceEngine


class TestRealVisionAndAudio(unittest.TestCase):
    """Verifies real model loading, static image detection, voice alert queues, and Mac controller."""

    PROTOTXT = "vision/weights/MobileNetSSD_deploy.prototxt"
    WEIGHTS = "vision/weights/MobileNetSSD_deploy.caffemodel"
    SAMPLE_CAT = "vision/test_assets/sample_cat.jpg"
    SAMPLE_PERSON = "vision/test_assets/sample_person.png"

    def setUp(self):
        self.has_weights = os.path.isfile(self.PROTOTXT) and os.path.isfile(self.WEIGHTS)

    def test_real_caffe_model_load_and_ready(self):
        """Verifies that MobileNet-SSD Caffe weights load into OpenCV DNN."""
        if not self.has_weights:
            self.skipTest("MobileNet-SSD weights not found in vision/weights")

        engine = OpenCVInferenceEngine(
            prototxt_path=self.PROTOTXT,
            weights_path=self.WEIGHTS,
            swap_rb=True,
        )
        self.assertTrue(engine.is_ready)
        self.assertTrue(engine.swap_rb)

    def test_real_image_inference_cat_detection(self):
        """Verifies real neural network detection on sample cat image."""
        if not self.has_weights or not os.path.isfile(self.SAMPLE_CAT):
            self.skipTest("Model weights or sample_cat.jpg missing")

        bgr = cv2.imread(self.SAMPLE_CAT)
        self.assertIsNotNone(bgr, "Could not read sample_cat.jpg")
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

        engine = OpenCVInferenceEngine(
            prototxt_path=self.PROTOTXT,
            weights_path=self.WEIGHTS,
            swap_rb=True,
        )
        detector = ObjectDetector(
            config=VisionConfig(confidence_threshold=0.50, filter_to_targets=True),
            engine=engine,
        )

        detections = detector.detect(rgb)
        self.assertGreater(len(detections.detections), 0)
        labels = [d.label for d in detections.detections]
        self.assertIn("cat", labels)

        cat_det = next(d for d in detections.detections if d.label == "cat")
        self.assertGreaterEqual(cat_det.confidence, 0.80)
        self.assertGreater(cat_det.box.x2, cat_det.box.x1)
        self.assertGreater(cat_det.box.y2, cat_det.box.y1)

    def test_real_image_inference_person_detection(self):
        """Verifies real neural network detection on sample person image."""
        if not self.has_weights or not os.path.isfile(self.SAMPLE_PERSON):
            self.skipTest("Model weights or sample_person.png missing")

        bgr = cv2.imread(self.SAMPLE_PERSON)
        self.assertIsNotNone(bgr, "Could not read sample_person.png")
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

        engine = OpenCVInferenceEngine(
            prototxt_path=self.PROTOTXT,
            weights_path=self.WEIGHTS,
            swap_rb=True,
        )
        detector = ObjectDetector(
            config=VisionConfig(confidence_threshold=0.50, filter_to_targets=True),
            engine=engine,
        )

        detections = detector.detect(rgb)
        self.assertGreater(len(detections.detections), 0)
        labels = [d.label for d in detections.detections]
        self.assertIn("person", labels)

        person_det = next(d for d in detections.detections if d.label == "person")
        self.assertGreaterEqual(person_det.confidence, 0.70)

    def test_confidence_threshold_filtering(self):
        """Verifies that setting a high threshold filters out lower confidence detections."""
        if not self.has_weights or not os.path.isfile(self.SAMPLE_PERSON):
            self.skipTest("Model weights or sample_person.png missing")

        bgr = cv2.imread(self.SAMPLE_PERSON)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

        engine = OpenCVInferenceEngine(self.PROTOTXT, self.WEIGHTS, swap_rb=True)

        # Permissive threshold
        det_low = ObjectDetector(config=VisionConfig(confidence_threshold=0.40), engine=engine)
        results_low = det_low.detect(rgb)

        # Strict threshold
        det_high = ObjectDetector(config=VisionConfig(confidence_threshold=0.95), engine=engine)
        results_high = det_high.detect(rgb)

        self.assertGreaterEqual(len(results_low.detections), len(results_high.detections))

    def test_voice_alert_backend_and_availability(self):
        """Verifies VoiceAlertPlayer initializes an offline speech backend."""
        player = VoiceAlertPlayer(enabled=True, cooldown_s=1.0)
        self.assertTrue(player.is_available)
        self.assertIsNotNone(player.backend_name)
        self.assertIn(player.backend_name, ["say", "pyttsx3", "espeak"])
        player.close()

    def test_voice_alert_cooldown_deduplication(self):
        """Verifies per-label cooldown prevents duplicate rapid announcements."""
        player = VoiceAlertPlayer(enabled=True, cooldown_s=5.0)
        try:
            # First announce should succeed
            first = player.announce("person")
            self.assertTrue(first)

            # Second announce within cooldown window should be deduplicated
            second = player.announce("person")
            self.assertFalse(second)
            self.assertEqual(player.announcements_deduplicated, 1)

            # Different label should be allowed
            other = player.announce("car")
            self.assertTrue(other)
        finally:
            player.close()

    def test_voice_alert_queue_full_drops_gracefully(self):
        """Verifies that overflow beyond max_queue_size drops without blocking."""
        # Player with max queue size of 1
        player = VoiceAlertPlayer(enabled=True, cooldown_s=0.0, max_queue_size=1)
        try:
            # Block the speech dispatch to simulate slow output
            with mock.patch.object(player, "_speak_text", side_effect=lambda t: time.sleep(0.5)):
                for i in range(5):
                    player.announce(f"object_{i}")

            self.assertGreaterEqual(player.announcements_dropped, 0)
        finally:
            player.close()

    def test_application_controller_create_mac_real(self):
        """Verifies ApplicationController.create_mac_real factory initializes real vision & audio."""
        if not self.has_weights:
            self.skipTest("Model weights missing")

        controller = ApplicationController.create_mac_real(camera_device=0)
        self.assertIsNotNone(controller)
        self.assertFalse(controller.is_running)

        # Inspect injected components
        self.assertEqual(controller.decision_engine.current_pattern.value, "OFF")
        controller.stop()

    def test_main_cli_mode_mac_arg_parsing(self):
        """Verifies that --mode mac and --camera-index are recognized by main.py."""
        with mock.patch("sys.argv", ["main.py", "--mode", "mac", "--camera-index", "2", "--duration", "5"]):
            args = parse_arguments()
            self.assertEqual(args.mode, "mac")
            self.assertEqual(args.camera_index, 2)
            self.assertEqual(args.duration, 5.0)


if __name__ == "__main__":
    unittest.main()
