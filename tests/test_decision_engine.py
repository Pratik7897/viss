"""Unit tests for the DecisionEngine, boundary conditions, arming modes, and error policies."""

import unittest

from config.settings import AppConfig, ThresholdConfig, VisionConfig
from core.engine import DecisionEngine, InvalidReadingPolicy
from core.models import BuzzerPattern, DistanceReading, ReadingQuality
from hardware.mock.mock_buzzer import MockBuzzer


class TestDecisionEngine(unittest.TestCase):
    """Verifies proximity band mapping, boundary semantics, vision arming, and hardware deduplication."""

    def setUp(self):
        # Default engine uses standard thresholds and independent distance warnings
        self.engine = DecisionEngine()

    def test_exact_boundary_conditions(self):
        """Verifies exact distance boundary thresholds matching Black Book code:

        - dist < 0.40m: CONTINUOUS
        - 0.40m <= dist < 0.80m: FAST_BEEP (at 0.40m exact, result is FAST_BEEP)
        - 0.80m <= dist < 1.50m: SLOW_BEEP (at 0.80m exact, result is SLOW_BEEP)
        - dist >= 1.50m: OFF (at 1.50m exact, result is OFF)
        """
        # Critical Zone (< 0.40m)
        self.assertEqual(self.engine.pick_beep_pattern(0.02), BuzzerPattern.CONTINUOUS)
        self.assertEqual(self.engine.pick_beep_pattern(0.20), BuzzerPattern.CONTINUOUS)
        self.assertEqual(self.engine.pick_beep_pattern(0.399), BuzzerPattern.CONTINUOUS)

        # Exact boundary at near_threshold (0.40m) falls into mid band
        self.assertEqual(self.engine.pick_beep_pattern(0.40), BuzzerPattern.FAST_BEEP)

        # Warning Zone (0.40m to < 0.80m)
        self.assertEqual(self.engine.pick_beep_pattern(0.50), BuzzerPattern.FAST_BEEP)
        self.assertEqual(self.engine.pick_beep_pattern(0.799), BuzzerPattern.FAST_BEEP)

        # Exact boundary at mid_threshold (0.80m) falls into far band
        self.assertEqual(self.engine.pick_beep_pattern(0.80), BuzzerPattern.SLOW_BEEP)

        # Caution Zone (0.80m to < 1.50m)
        self.assertEqual(self.engine.pick_beep_pattern(1.00), BuzzerPattern.SLOW_BEEP)
        self.assertEqual(self.engine.pick_beep_pattern(1.499), BuzzerPattern.SLOW_BEEP)

        # Exact boundary at far_threshold (1.50m) falls into safe zone (OFF)
        self.assertEqual(self.engine.pick_beep_pattern(1.50), BuzzerPattern.OFF)

        # Safe Zone (> 1.50m)
        self.assertEqual(self.engine.pick_beep_pattern(2.00), BuzzerPattern.OFF)
        self.assertEqual(self.engine.pick_beep_pattern(4.00), BuzzerPattern.OFF)
        self.assertEqual(self.engine.pick_beep_pattern(5.00), BuzzerPattern.OFF)

    def test_custom_injected_configuration(self):
        """Verifies that the engine respects thresholds from config rather than hardcoding."""
        custom_thresholds = ThresholdConfig(
            near_threshold_m=0.30,
            mid_threshold_m=0.60,
            far_threshold_m=1.00,
        )
        custom_config = AppConfig(thresholds=custom_thresholds)
        custom_engine = DecisionEngine(config=custom_config)

        # Under custom thresholds:
        # < 0.30 is CONTINUOUS; 0.35 is FAST_BEEP (between 0.30 and 0.60)
        self.assertEqual(custom_engine.pick_beep_pattern(0.25), BuzzerPattern.CONTINUOUS)
        self.assertEqual(custom_engine.pick_beep_pattern(0.35), BuzzerPattern.FAST_BEEP)
        self.assertEqual(custom_engine.pick_beep_pattern(0.70), BuzzerPattern.SLOW_BEEP)
        self.assertEqual(custom_engine.pick_beep_pattern(1.00), BuzzerPattern.OFF)

    def test_invalid_reading_handling_maintain_last_policy(self):
        """Verifies safe handling of invalid sensor readings under MAINTAIN_LAST policy."""
        engine = DecisionEngine(
            invalid_reading_policy=InvalidReadingPolicy.MAINTAIN_LAST,
            invalid_reading_grace_s=1.0,
        )

        t0 = 1000.0
        # Valid reading puts engine in CONTINUOUS alert
        valid_reading = DistanceReading(distance_m=0.25, timestamp=t0)
        self.assertEqual(
            engine.evaluate_reading(valid_reading, current_time=t0),
            BuzzerPattern.CONTINUOUS,
        )
        self.assertTrue(engine.is_sensor_healthy)

        # Momentary sensor dropout at t0 + 0.3s (within 1.0s grace period)
        error_reading = DistanceReading(
            distance_m=None,
            timestamp=t0 + 0.3,
            quality=ReadingQuality.ERROR,
        )
        # MUST NOT treat as confirmed safe distance! Maintains CONTINUOUS warning
        self.assertEqual(
            engine.evaluate_reading(error_reading, current_time=t0 + 0.3),
            BuzzerPattern.CONTINUOUS,
        )
        self.assertFalse(engine.is_sensor_healthy)

        # None reading (sensor timeout)
        self.assertEqual(
            engine.evaluate_reading(None, current_time=t0 + 0.6),
            BuzzerPattern.CONTINUOUS,
        )

        # Extended dropout beyond grace period (t0 + 1.5s)
        self.assertEqual(
            engine.evaluate_reading(error_reading, current_time=t0 + 1.5),
            BuzzerPattern.OFF,
        )

    def test_invalid_reading_handling_silent_policy(self):
        """Verifies Black Book compatibility mode for invalid readings (SILENT policy)."""
        engine = DecisionEngine(
            invalid_reading_policy=InvalidReadingPolicy.SILENT,
        )
        t0 = 1000.0
        valid_reading = DistanceReading(distance_m=0.25, timestamp=t0)
        self.assertEqual(
            engine.evaluate_reading(valid_reading, current_time=t0),
            BuzzerPattern.CONTINUOUS,
        )

        # Dropout immediately silences the buzzer in compatibility mode
        error_reading = DistanceReading(distance_m=None, quality=ReadingQuality.ERROR)
        self.assertEqual(
            engine.evaluate_reading(error_reading, current_time=t0 + 0.1),
            BuzzerPattern.OFF,
        )

    def test_invalid_reading_handling_caution_policy(self):
        """Verifies CAUTION policy escalates to SLOW_BEEP on sensor failure."""
        engine = DecisionEngine(
            invalid_reading_policy=InvalidReadingPolicy.CAUTION,
        )
        error_reading = DistanceReading(distance_m=None, quality=ReadingQuality.ERROR)
        self.assertEqual(
            engine.evaluate_reading(error_reading),
            BuzzerPattern.SLOW_BEEP,
        )

    def test_hardware_command_deduplication(self):
        """Verifies that redundant buzzer commands are suppressed when pattern does not change."""
        buzzer = MockBuzzer()
        engine = DecisionEngine()

        # Step 1: First reading in Critical zone (0.30m) -> CONTINUOUS
        pattern = engine.process_cycle(DistanceReading(distance_m=0.30), buzzer=buzzer)
        self.assertEqual(pattern, BuzzerPattern.CONTINUOUS)
        self.assertEqual(engine.hardware_command_count, 1)
        self.assertEqual(buzzer.current_pattern, BuzzerPattern.CONTINUOUS)

        # Step 2: Next 5 readings in the same zone -> no new hardware commands!
        for d in [0.32, 0.28, 0.35, 0.20, 0.38]:
            p = engine.process_cycle(DistanceReading(distance_m=d), buzzer=buzzer)
            self.assertEqual(p, BuzzerPattern.CONTINUOUS)
            self.assertEqual(engine.hardware_command_count, 1)

        # Step 3: Transition to Warning zone (0.60m) -> FAST_BEEP (dispatches command 2)
        p = engine.process_cycle(DistanceReading(distance_m=0.60), buzzer=buzzer)
        self.assertEqual(p, BuzzerPattern.FAST_BEEP)
        self.assertEqual(engine.hardware_command_count, 2)
        self.assertEqual(buzzer.current_pattern, BuzzerPattern.FAST_BEEP)

        # Step 4: Transition to Safe zone (2.00m) -> OFF (dispatches command 3)
        p = engine.process_cycle(DistanceReading(distance_m=2.00), buzzer=buzzer)
        self.assertEqual(p, BuzzerPattern.OFF)
        self.assertEqual(engine.hardware_command_count, 3)
        self.assertEqual(buzzer.current_pattern, BuzzerPattern.OFF)

        # Step 5: Remaining in Safe zone -> no new command
        p = engine.process_cycle(DistanceReading(distance_m=2.50), buzzer=buzzer)
        self.assertEqual(engine.hardware_command_count, 3)

    def test_camera_arming_default_independent_mode(self):
        """In default safety mode, distance alerts trigger even without camera target detections."""
        cfg = AppConfig(vision=VisionConfig(require_vision_for_buzzer=False))
        engine = DecisionEngine(config=cfg)

        t0 = 100.0
        reading = DistanceReading(distance_m=0.30, timestamp=t0)

        # No camera target has ever been detected (last_target_seen_ts=None)
        # Should still alert because an obstacle is 30 cm away!
        pattern = engine.evaluate_reading(reading, last_target_seen_ts=None, current_time=t0)
        self.assertEqual(pattern, BuzzerPattern.CONTINUOUS)

        # Target detected in distant past (expired window)
        pattern = engine.evaluate_reading(reading, last_target_seen_ts=t0 - 100.0, current_time=t0)
        self.assertEqual(pattern, BuzzerPattern.CONTINUOUS)

    def test_camera_arming_black_book_compatibility_mode(self):
        """In Black Book mode, the buzzer is silenced unless a vision target was recently seen."""
        cfg = AppConfig(
            vision=VisionConfig(
                require_vision_for_buzzer=True,
                arm_window_s=1.0,
            )
        )
        engine = DecisionEngine(config=cfg)

        t0 = 100.0
        reading = DistanceReading(distance_m=0.30, timestamp=t0)

        # Case 1: No vision target seen -> Disarmed -> Pattern OFF
        pattern = engine.evaluate_reading(reading, last_target_seen_ts=None, current_time=t0)
        self.assertEqual(pattern, BuzzerPattern.OFF)

        # Case 2: Vision target seen 0.5s ago (within 1.0s window) -> Armed -> Pattern CONTINUOUS
        pattern = engine.evaluate_reading(reading, last_target_seen_ts=t0 - 0.5, current_time=t0)
        self.assertEqual(pattern, BuzzerPattern.CONTINUOUS)

        # Case 3: Vision target seen 1.5s ago (outside 1.0s window) -> Disarmed -> Pattern OFF
        pattern = engine.evaluate_reading(reading, last_target_seen_ts=t0 - 1.5, current_time=t0)
        self.assertEqual(pattern, BuzzerPattern.OFF)


if __name__ == "__main__":
    unittest.main()
