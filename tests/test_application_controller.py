"""Integration tests for ApplicationController, lifecycle orchestration, and thread synchronization."""

import time
import unittest

from config.settings import AppConfig, ThresholdConfig, VisionConfig
from core.controller import ApplicationController
from core.models import BuzzerPattern, SystemStatus
from core.sound_player import MockSoundPlayer
from hardware.mock import (
    MockButton,
    MockBuzzer,
    MockCamera,
    MockDistanceSensor,
    MockGSM,
    MockLocationProvider,
)
from vision.detector import ObjectDetector, StubInferenceEngine


class TestApplicationController(unittest.TestCase):
    """Verifies end-to-end integration across all hardware mocks, threads, and decision layers."""

    def setUp(self):
        self.mock_sensor = MockDistanceSensor(initial_distance_m=2.0)
        self.mock_camera = MockCamera()
        self.mock_buzzer = MockBuzzer()
        self.mock_button = MockButton()
        self.mock_gsm = MockGSM()
        self.mock_loc = MockLocationProvider()
        self.mock_sound = MockSoundPlayer()

        self.stub_engine = StubInferenceEngine()
        self.config = AppConfig(
            is_mock_mode=True,
            thresholds=ThresholdConfig(sensor_poll_interval_s=0.01),
            vision=VisionConfig(require_vision_for_buzzer=False),
        )
        self.detector = ObjectDetector(
            config=self.config.vision,
            engine=self.stub_engine,
        )

        self.controller = ApplicationController(
            config=self.config,
            distance_sensor=self.mock_sensor,
            camera=self.mock_camera,
            buzzer=self.mock_buzzer,
            button=self.mock_button,
            gsm=self.mock_gsm,
            location_provider=self.mock_loc,
            detector=self.detector,
            sound_player=self.mock_sound,
        )

    def tearDown(self):
        if self.controller.is_running:
            self.controller.stop(timeout_s=1.0)

    def test_startup_and_shutdown_lifecycle(self):
        """Verifies clean transition from STOPPED -> RUNNING -> STOPPED."""
        self.assertFalse(self.controller.is_running)
        self.assertEqual(self.controller.status, SystemStatus.STOPPED)

        self.controller.start()
        self.assertTrue(self.controller.is_running)
        self.assertEqual(self.controller.status, SystemStatus.RUNNING)

        self.controller.stop(timeout_s=1.0)
        self.assertFalse(self.controller.is_running)
        self.assertEqual(self.controller.status, SystemStatus.STOPPED)

    def test_repeated_start_and_stop_is_idempotent(self):
        """Verifies that calling start() and stop() repeatedly is safe."""
        self.controller.start()
        self.assertTrue(self.controller.is_running)

        # Second start call when already running should be a no-op
        self.controller.start()
        self.assertTrue(self.controller.is_running)

        self.controller.stop(timeout_s=1.0)
        self.assertFalse(self.controller.is_running)

        # Second stop call when already stopped should be a no-op
        self.controller.stop(timeout_s=1.0)
        self.assertFalse(self.controller.is_running)

    def test_distance_warnings_continue_when_vision_inference_fails(self):
        """Verifies that distance polling and buzzer alerts are decoupled from vision failures."""
        # 1. Set ultrasonic distance to 0.35m (Critical zone -> CONTINUOUS)
        self.mock_sensor.set_distance(0.35)

        # 2. Simulate vision inference crash
        self.stub_engine.set_simulate_error(True)

        self.controller.start()

        # Allow distance worker to process cycles
        deadline = time.time() + 1.0
        while time.time() < deadline:
            if self.controller.current_buzzer_pattern == BuzzerPattern.CONTINUOUS:
                break
            time.sleep(0.02)

        # Proximity warning MUST still trigger despite vision engine crashing!
        self.assertEqual(self.controller.current_buzzer_pattern, BuzzerPattern.CONTINUOUS)
        self.assertEqual(self.mock_buzzer.current_pattern, BuzzerPattern.CONTINUOUS)
        self.assertAlmostEqual(self.controller.latest_distance_m, 0.35)

    def test_emergency_button_event_dispatch_and_duplicate_suppression(self):
        """Verifies tactile button triggers distress SMS and cooldown suppresses duplicates."""
        self.mock_sensor.set_distance(0.60)
        self.stub_engine.set_raw_detections([
            [0, 15, 0.92, 0.1, 0.1, 0.5, 0.5],  # class 15 = person
        ])

        self.controller.start()

        # Allow vision and distance workers to register state
        deadline = time.time() + 1.0
        while time.time() < deadline:
            if self.controller.last_detected_label == "person":
                break
            time.sleep(0.02)

        # Step 1: First button press
        self.mock_button.press()

        # Wait for background dispatch thread to complete
        deadline = time.time() + 1.5
        while time.time() < deadline:
            if len(self.mock_gsm.sent_messages) == 1:
                break
            time.sleep(0.02)

        self.assertEqual(len(self.mock_gsm.sent_messages), 1)
        msg = self.mock_gsm.sent_messages[0]["message"]
        self.assertIn("Detected: person", msg)
        self.assertIn("Loc: Mumbai, Maharashtra, India", msg)

        # Step 2: Release and immediately press again (rapid panic press)
        self.mock_button.release()
        self.mock_button.press()
        time.sleep(0.1)

        # Duplicate MUST be suppressed by cooldown; message count remains 1
        self.assertEqual(len(self.mock_gsm.sent_messages), 1)

    def test_sound_playback_on_category_detection(self):
        """Verifies that animal and human detections trigger the sound player."""
        # Detect person (class 15) -> should trigger 'human' sound category
        self.stub_engine.set_raw_detections([
            [0, 15, 0.88, 0.1, 0.1, 0.5, 0.5],
        ])

        self.controller.start()

        deadline = time.time() + 1.0
        while time.time() < deadline:
            if any(s.get("category") == "human" for s in self.mock_sound.played_sounds):
                break
            time.sleep(0.02)

        categories = [s.get("category") for s in self.mock_sound.played_sounds]
        self.assertIn("human", categories)

        # Switch to cat (class 8) -> should trigger 'animal' sound category
        self.stub_engine.set_raw_detections([
            [0, 8, 0.85, 0.1, 0.1, 0.5, 0.5],
        ])

        deadline = time.time() + 1.0
        while time.time() < deadline:
            if any(s.get("category") == "animal" for s in self.mock_sound.played_sounds):
                break
            time.sleep(0.02)

        categories = [s.get("category") for s in self.mock_sound.played_sounds]
        self.assertIn("animal", categories)

    def test_camera_failure_resilience(self):
        """Verifies controller remains healthy and operable if camera capture fails."""
        # Stop camera immediately to simulate hardware capture failure
        self.mock_camera.stop()

        self.controller.start()
        self.assertTrue(self.controller.is_running)

        # Change distance and verify distance monitoring operates normally
        self.mock_sensor.set_distance(0.70)

        deadline = time.time() + 1.0
        while time.time() < deadline:
            if self.controller.current_buzzer_pattern == BuzzerPattern.FAST_BEEP:
                break
            time.sleep(0.02)

        self.assertEqual(self.controller.current_buzzer_pattern, BuzzerPattern.FAST_BEEP)

    def test_distance_sensor_failure_resilience(self):
        """Verifies controller survives distance sensor hardware exceptions."""
        self.mock_sensor.set_simulate_error(True)

        self.controller.start()
        self.assertTrue(self.controller.is_running)

        # Give distance worker time to process error reading
        time.sleep(0.1)
        self.assertTrue(self.controller.is_running)

    def test_create_mock_factory(self):
        """Verifies that create_mock factory generates a fully functioning controller."""
        ctrl = ApplicationController.create_mock()
        self.assertFalse(ctrl.is_running)
        ctrl.start()
        self.assertTrue(ctrl.is_running)
        ctrl.stop(timeout_s=1.0)
        self.assertFalse(ctrl.is_running)


if __name__ == "__main__":
    unittest.main()
