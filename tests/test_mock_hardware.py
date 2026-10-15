"""Unit tests for mock hardware driver implementations."""

import unittest

from core.models import BuzzerPattern, ReadingQuality
from hardware.mock import (
    MockButton,
    MockBuzzer,
    MockCamera,
    MockDistanceSensor,
    MockGSM,
    MockLocationProvider,
)


class TestMockHardware(unittest.TestCase):
    """Verifies that all mock drivers adhere to their contracts and simulate expected behavior."""

    def test_mock_distance_sensor_lifecycle_and_reading(self):
        sensor = MockDistanceSensor(initial_distance_m=1.2)
        # Reading before start should indicate inactive/error
        self.assertFalse(sensor.is_active)
        r = sensor.read_distance()
        self.assertEqual(r.quality, ReadingQuality.ERROR)

        sensor.start()
        self.assertTrue(sensor.is_active)
        r = sensor.read_distance()
        self.assertEqual(r.quality, ReadingQuality.VALID)
        self.assertAlmostEqual(r.distance_m, 1.2)

        # Set fixed distance
        sensor.set_distance(0.35)
        r = sensor.read_distance()
        self.assertAlmostEqual(r.distance_m, 0.35)

        # Sequence testing
        sensor.set_sequence([0.5, 0.2, 1.5])
        self.assertAlmostEqual(sensor.read_distance().distance_m, 0.5)
        self.assertAlmostEqual(sensor.read_distance().distance_m, 0.2)
        self.assertAlmostEqual(sensor.read_distance().distance_m, 1.5)
        # Should cycle back
        self.assertAlmostEqual(sensor.read_distance().distance_m, 0.5)

        # Error simulation
        sensor.set_simulate_error(True)
        r = sensor.read_distance()
        self.assertEqual(r.quality, ReadingQuality.ERROR)
        self.assertIsNone(r.distance_m)

        sensor.stop()
        self.assertFalse(sensor.is_active)

    def test_mock_distance_sensor_out_of_bounds(self):
        sensor = MockDistanceSensor()
        sensor.start()

        # Less than HC-SR04 minimum (2 cm)
        sensor.set_distance(0.01)
        r = sensor.read_distance()
        self.assertEqual(r.quality, ReadingQuality.OUT_OF_RANGE)

        # Greater than HC-SR04 maximum (4.0 m)
        sensor.set_distance(5.5)
        r = sensor.read_distance()
        self.assertEqual(r.quality, ReadingQuality.OUT_OF_RANGE)

        sensor.stop()

    def test_mock_camera(self):
        camera = MockCamera(width=640, height=480)
        self.assertFalse(camera.is_active)
        self.assertIsNone(camera.capture_frame())

        camera.start()
        self.assertTrue(camera.is_active)
        self.assertEqual(camera.get_resolution(), (640, 480))

        frame = camera.capture_frame()
        self.assertIsNotNone(frame)

        # Test custom frame injection
        camera.set_custom_frame({"custom": "test_frame"})
        self.assertEqual(camera.capture_frame(), {"custom": "test_frame"})

        camera.stop()
        self.assertFalse(camera.is_active)
        self.assertIsNone(camera.capture_frame())

    def test_mock_buzzer(self):
        buzzer = MockBuzzer()
        self.assertEqual(buzzer.current_pattern, BuzzerPattern.OFF)
        self.assertEqual(buzzer.pattern_history, [BuzzerPattern.OFF])

        buzzer.set_pattern(BuzzerPattern.FAST_BEEP)
        self.assertEqual(buzzer.current_pattern, BuzzerPattern.FAST_BEEP)

        buzzer.set_pattern(BuzzerPattern.CONTINUOUS)
        self.assertEqual(buzzer.current_pattern, BuzzerPattern.CONTINUOUS)

        buzzer.turn_off()
        self.assertEqual(buzzer.current_pattern, BuzzerPattern.OFF)

        self.assertEqual(
            buzzer.pattern_history,
            [
                BuzzerPattern.OFF,
                BuzzerPattern.FAST_BEEP,
                BuzzerPattern.CONTINUOUS,
                BuzzerPattern.OFF,
            ],
        )

        buzzer.close()
        with self.assertRaises(RuntimeError):
            buzzer.set_pattern(BuzzerPattern.SLOW_BEEP)

    def test_mock_gsm_sms(self):
        gsm = MockGSM()
        self.assertTrue(gsm.is_ready)

        success, msg = gsm.send_sms("+918450976299", "Test Emergency Message")
        self.assertTrue(success)
        self.assertEqual(len(gsm.sent_messages), 1)
        self.assertEqual(gsm.sent_messages[0]["phone_number"], "+918450976299")
        self.assertEqual(gsm.sent_messages[0]["message"], "Test Emergency Message")

        # Invalid phone number
        success, msg = gsm.send_sms("12", "Test")
        self.assertFalse(success)

        # Network not ready simulation
        gsm.set_network_ready(False)
        success, msg = gsm.send_sms("+918450976299", "Another message")
        self.assertFalse(success)
        self.assertIn("NO CARRIER", msg)

        # Error simulation
        gsm.set_network_ready(True)
        gsm.set_simulate_failure(True)
        success, msg = gsm.send_sms("+918450976299", "Should fail")
        self.assertFalse(success)

        gsm.close()
        self.assertFalse(gsm.is_ready)

    def test_mock_location_provider(self):
        loc_provider = MockLocationProvider()
        loc = loc_provider.get_location()
        self.assertIsNotNone(loc)
        self.assertEqual(loc.city, "Mumbai")
        self.assertEqual(loc.country, "India")

        # Offline toggle
        loc_provider.set_available(False)
        self.assertIsNone(loc_provider.get_location())

    def test_mock_button(self):
        btn = MockButton()
        self.assertFalse(btn.is_pressed())

        btn.press()
        self.assertTrue(btn.is_pressed())

        btn.release()
        self.assertFalse(btn.is_pressed())

        btn.close()
        with self.assertRaises(RuntimeError):
            btn.press()


if __name__ == "__main__":
    unittest.main()
