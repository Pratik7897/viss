"""Unit tests for domain models and dataclasses."""

import unittest

from core.models import (
    BoundingBox,
    BuzzerPattern,
    Detection,
    DistanceReading,
    EmergencyEvent,
    FrameDetections,
    GeoLocation,
    ReadingQuality,
    SystemStatus,
)


class TestModels(unittest.TestCase):
    """Verifies dataclass behavior, validations, and formatting."""

    def test_distance_reading_valid(self):
        reading = DistanceReading(distance_m=0.35)
        self.assertTrue(reading.is_valid)
        self.assertEqual(reading.formatted_text(), "0.35 m")

    def test_distance_reading_unknown(self):
        reading = DistanceReading(distance_m=None, quality=ReadingQuality.ERROR)
        self.assertFalse(reading.is_valid)
        self.assertEqual(reading.formatted_text(), "unknown")

    def test_bounding_box_dimensions(self):
        box = BoundingBox(x1=50, y1=100, x2=250, y2=400)
        self.assertEqual(box.width, 200)
        self.assertEqual(box.height, 300)

    def test_detection_valid(self):
        det = Detection(label="person", confidence=0.85)
        self.assertEqual(det.label, "person")
        self.assertAlmostEqual(det.confidence, 0.85)

    def test_detection_invalid_confidence_raises(self):
        with self.assertRaises(ValueError):
            Detection(label="person", confidence=1.2)

        with self.assertRaises(ValueError):
            Detection(label="person", confidence=-0.1)

    def test_frame_detections_helpers(self):
        d1 = Detection(label="person", confidence=0.92)
        d2 = Detection(label="bottle", confidence=0.65)
        d3 = Detection(label="car", confidence=0.78)

        frame = FrameDetections(detections=(d1, d2, d3))
        self.assertEqual(frame.labels, ["person", "bottle", "car"])

        targets = ("person", "dog", "cat", "car")
        self.assertTrue(frame.has_target(targets))
        self.assertFalse(frame.has_target(("airplane", "train")))

        best = frame.highest_confidence_target(targets)
        self.assertIsNotNone(best)
        self.assertEqual(best.label, "person")
        self.assertAlmostEqual(best.confidence, 0.92)

    def test_geo_location_formatting(self):
        geo = GeoLocation(
            latitude=19.074800,
            longitude=72.885600,
            city="Mumbai",
            region="Maharashtra",
            country="India",
        )
        self.assertEqual(
            geo.maps_url(), "https://maps.google.com/?q=19.074800,72.885600"
        )
        self.assertEqual(geo.location_summary(), "Mumbai, Maharashtra, India")

    def test_emergency_event_creation(self):
        geo = GeoLocation(
            latitude=19.074800,
            longitude=72.885600,
            city="Mumbai",
            region="Maharashtra",
            country="India",
        )
        event = EmergencyEvent(
            trigger="BUTTON_PRESS",
            detected_label="person",
            distance_text="0.65 m",
            location=geo,
            composed_message="[ALERT]\nDetected: person\nRange: 0.65 m",
        )
        self.assertEqual(event.trigger, "BUTTON_PRESS")
        self.assertEqual(event.detected_label, "person")
        self.assertEqual(event.distance_text, "0.65 m")
        self.assertIsNotNone(event.location)

    def test_enums(self):
        self.assertEqual(BuzzerPattern.OFF.value, "OFF")
        self.assertEqual(BuzzerPattern.CONTINUOUS.value, "CONTINUOUS")
        self.assertEqual(BuzzerPattern.FAST_BEEP.value, "FAST_BEEP")
        self.assertEqual(BuzzerPattern.SLOW_BEEP.value, "SLOW_BEEP")
        self.assertEqual(SystemStatus.RUNNING.value, "RUNNING")


if __name__ == "__main__":
    unittest.main()
