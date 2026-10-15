"""Unit tests for emergency SMS composition, location fallback, and cooldown deduplication."""

import unittest

from config.settings import EmergencyConfig
from core.models import GeoLocation
from core.sms_coordinator import SMSCoordinator, compose_emergency_message
from hardware.mock.mock_gsm import MockGSM
from hardware.mock.mock_location import MockLocationProvider


class TestEmergencyCoordinator(unittest.TestCase):
    """Verifies Black Book message format, location resolution, modem errors, and duplicate suppression."""

    def setUp(self):
        self.mock_gsm = MockGSM()
        self.mock_loc = MockLocationProvider()
        self.config = EmergencyConfig(
            destination_phone="+918450976299",
            cooldown_s=10.0,
        )
        self.coordinator = SMSCoordinator(
            gsm=self.mock_gsm,
            location_provider=self.mock_loc,
            config=self.config,
        )

    def test_message_formatting_with_full_location(self):
        """Matches Black Book Ch 5.3.1 code format when location is available."""
        loc = GeoLocation(
            latitude=19.074800,
            longitude=72.885600,
            city="Mumbai",
            region="Maharashtra",
            country="India",
        )
        msg = compose_emergency_message(
            label="person",
            distance_m=0.65,
            location=loc,
        )

        expected = (
            "[ALERT]\n"
            "Detected: person\n"
            "Range: 0.65 m\n"
            "Loc: Mumbai, Maharashtra, India\n"
            "https://maps.google.com/?q=19.074800,72.885600"
        )
        self.assertEqual(msg, expected)

    def test_message_formatting_with_unavailable_location(self):
        """Matches Black Book fallback format when location lookup fails or is offline."""
        msg = compose_emergency_message(
            label="car",
            distance_m=1.20,
            location=None,
        )

        expected = (
            "[ALERT]\n"
            "Detected: car\n"
            "Range: 1.20 m\n"
            "Loc: unavailable"
        )
        self.assertEqual(msg, expected)

    def test_message_formatting_with_missing_inputs(self):
        """Verifies default values when label or distance are unknown."""
        msg = compose_emergency_message(label=None, distance_m=None, location=None)
        expected = (
            "[ALERT]\n"
            "Detected: N/A\n"
            "Range: unknown\n"
            "Loc: unavailable"
        )
        self.assertEqual(msg, expected)

    def test_successful_emergency_trigger_and_dispatch(self):
        """Verifies end-to-end trigger flow through mock GSM modem."""
        t0 = 500.0
        success, status, body = self.coordinator.trigger_emergency(
            label="dog",
            distance_m=0.45,
            current_time=t0,
        )

        self.assertTrue(success)
        self.assertEqual(status, "SENT")
        self.assertIsNotNone(body)
        self.assertIn("Detected: dog", body)
        self.assertIn("Range: 0.45 m", body)
        self.assertIn("Loc: Mumbai, Maharashtra, India", body)

        # Verify MockGSM record
        self.assertEqual(len(self.mock_gsm.sent_messages), 1)
        sent = self.mock_gsm.sent_messages[0]
        self.assertEqual(sent["phone_number"], "+918450976299")
        self.assertEqual(sent["message"], body)

        # Verify history log
        self.assertEqual(len(self.coordinator.history), 1)
        event = self.coordinator.history[0]
        self.assertEqual(event.detected_label, "dog")
        self.assertEqual(event.distance_text, "0.45 m")
        self.assertEqual(event.trigger, "BUTTON_PRESS")

    def test_cooldown_deduplication_suppresses_rapid_presses(self):
        """Prevents accidental spam / multiple SMS dispatches when button is repeatedly pressed."""
        t0 = 1000.0

        # Press 1 at t=1000s -> Succeeds
        success1, status1, _ = self.coordinator.trigger_emergency(
            label="person", distance_m=0.50, current_time=t0
        )
        self.assertTrue(success1)
        self.assertEqual(status1, "SENT")
        self.assertEqual(len(self.mock_gsm.sent_messages), 1)

        # Press 2 at t=1001s (1s later, cooldown is 10s) -> Suppressed
        self.assertTrue(self.coordinator.is_in_cooldown(current_time=t0 + 1.0))
        self.assertAlmostEqual(self.coordinator.cooldown_remaining_s(current_time=t0 + 1.0), 9.0)

        success2, status2, body2 = self.coordinator.trigger_emergency(
            label="person", distance_m=0.48, current_time=t0 + 1.0
        )
        self.assertFalse(success2)
        self.assertEqual(status2, "COOLDOWN_ACTIVE")
        self.assertIsNone(body2)
        # SMS count must remain 1
        self.assertEqual(len(self.mock_gsm.sent_messages), 1)

        # Press 3 at t=1008s (8s later) -> Still Suppressed
        success3, status3, _ = self.coordinator.trigger_emergency(
            label="person", distance_m=0.45, current_time=t0 + 8.0
        )
        self.assertFalse(success3)
        self.assertEqual(status3, "COOLDOWN_ACTIVE")
        self.assertEqual(len(self.mock_gsm.sent_messages), 1)

        # Press 4 at t=1010.1s (after 10s cooldown expires) -> Succeeds
        self.assertFalse(self.coordinator.is_in_cooldown(current_time=t0 + 10.1))
        success4, status4, _ = self.coordinator.trigger_emergency(
            label="car", distance_m=0.30, current_time=t0 + 10.1
        )
        self.assertTrue(success4)
        self.assertEqual(status4, "SENT")
        # Second SMS successfully dispatched
        self.assertEqual(len(self.mock_gsm.sent_messages), 2)

    def test_modem_not_ready_error_handling(self):
        """Verifies clean error return when GSM modem has no cellular network connection."""
        self.mock_gsm.set_network_ready(False)

        success, status, body = self.coordinator.trigger_emergency(label="person", distance_m=0.4)
        self.assertFalse(success)
        self.assertEqual(status, "GSM_UNAVAILABLE")
        self.assertIsNotNone(body)
        # No SMS should have been transmitted
        self.assertEqual(len(self.mock_gsm.sent_messages), 0)

    def test_modem_send_failure_error_handling(self):
        """Verifies clean error return when GSM AT command transmission fails."""
        self.mock_gsm.set_simulate_failure(True)

        success, status, body = self.coordinator.trigger_emergency(label="person", distance_m=0.4)
        self.assertFalse(success)
        self.assertIn("GSM_SEND_FAILED", status)
        self.assertIsNotNone(body)
        self.assertEqual(len(self.mock_gsm.sent_messages), 0)

    def test_location_provider_exception_handled_gracefully(self):
        """Verifies that an exception in location lookup does not crash the emergency pipeline."""
        class BrokenLocationProvider(MockLocationProvider):
            def get_location(self):
                raise ConnectionError("DNS lookup failed")

        broken_coord = SMSCoordinator(
            gsm=self.mock_gsm,
            location_provider=BrokenLocationProvider(),
            config=self.config,
        )

        success, status, body = broken_coord.trigger_emergency(label="person", distance_m=0.5)
        self.assertTrue(success)
        self.assertEqual(status, "SENT")
        self.assertIn("Loc: unavailable", body)


if __name__ == "__main__":
    unittest.main()
