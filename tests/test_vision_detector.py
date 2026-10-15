"""Unit tests for MobileNet-SSD ObjectDetector, vision pipeline, and camera integration."""

import os
import unittest

from config.settings import VisionConfig
from core.models import BoundingBox, Detection, FrameDetections
from hardware.camera.opencv_camera import OpenCVCamera
from hardware.mock.mock_camera import MockCamera
from vision.detector import (
    DEFAULT_TARGET_CLASSES,
    PASCAL_VOC_CLASSES,
    ObjectDetector,
    OpenCVInferenceEngine,
    StubInferenceEngine,
)
from vision.pipeline import VisionPipeline


class TestVisionDetector(unittest.TestCase):
    """Verifies MobileNet-SSD detection parsing, boundary values, error resilience, and pipeline integration."""

    def setUp(self):
        self.stub_engine = StubInferenceEngine()
        self.config = VisionConfig(
            confidence_threshold=0.50,
            target_classes=("person", "dog", "cat", "car"),
            filter_to_targets=True,
            frame_width=640,
            frame_height=480,
        )
        self.detector = ObjectDetector(
            config=self.config,
            engine=self.stub_engine,
        )
        self.dummy_frame = {"width": 640, "height": 480}

    def test_target_class_filtering(self):
        """Verifies that non-target Pascal VOC classes are filtered out when filter_to_targets=True."""
        # Pascal VOC Class IDs:
        # 15 = person (target)
        # 7  = car (target)
        # 5  = bottle (non-target)
        # 9  = chair (non-target)
        raw_candidates = [
            [0, 15, 0.90, 0.1, 0.1, 0.5, 0.5],  # person (target)
            [0, 7, 0.85, 0.2, 0.2, 0.6, 0.6],   # car (target)
            [0, 5, 0.95, 0.3, 0.3, 0.7, 0.7],   # bottle (non-target)
            [0, 9, 0.75, 0.4, 0.4, 0.8, 0.8],   # chair (non-target)
        ]
        self.stub_engine.set_raw_detections(raw_candidates)

        # 1. With default filter_to_targets=True
        result = self.detector.detect(self.dummy_frame)
        self.assertEqual(len(result.detections), 2)
        self.assertEqual(result.labels, ["person", "car"])

        # 2. With filter_to_targets=False (detect all VOC entities)
        detector_all = ObjectDetector(
            config=self.config,
            engine=self.stub_engine,
            filter_to_targets=False,
        )
        result_all = detector_all.detect(self.dummy_frame)
        self.assertEqual(len(result_all.detections), 4)
        self.assertEqual(result_all.labels, ["person", "car", "bottle", "chair"])

    def test_confidence_threshold_boundaries(self):
        """Verifies exact confidence threshold boundary filtering (0.50)."""
        raw_candidates = [
            [0, 15, 0.499, 0.1, 0.1, 0.5, 0.5],  # Just below 0.50 -> Ignored
            [0, 15, 0.500, 0.1, 0.1, 0.5, 0.5],  # Exactly 0.50 -> Included
            [0, 15, 0.501, 0.1, 0.1, 0.5, 0.5],  # Just above 0.50 -> Included
        ]
        self.stub_engine.set_raw_detections(raw_candidates)

        result = self.detector.detect(self.dummy_frame)
        self.assertEqual(len(result.detections), 2)
        for d in result.detections:
            self.assertGreaterEqual(d.confidence, 0.50)

    def test_custom_confidence_threshold(self):
        """Verifies custom confidence threshold override."""
        raw_candidates = [
            [0, 15, 0.65, 0.1, 0.1, 0.5, 0.5],
            [0, 15, 0.75, 0.1, 0.1, 0.5, 0.5],
        ]
        self.stub_engine.set_raw_detections(raw_candidates)

        detector_high = ObjectDetector(
            config=self.config,
            engine=self.stub_engine,
            confidence_threshold=0.70,
        )
        result = detector_high.detect(self.dummy_frame)
        self.assertEqual(len(result.detections), 1)
        self.assertEqual(result.detections[0].confidence, 0.75)

    def test_bounding_box_coordinate_scaling_and_validity(self):
        """Verifies normalized coordinate conversion to pixel coordinates with clamping."""
        # Normalized coords: (x1=0.1, y1=0.2, x2=0.6, y2=0.8) on 640x480 frame
        # Expected: x1=64, y1=96, x2=384, y2=384
        raw_candidates = [
            [0, 15, 0.88, 0.1, 0.2, 0.6, 0.8],
        ]
        self.stub_engine.set_raw_detections(raw_candidates)

        result = self.detector.detect(self.dummy_frame)
        self.assertEqual(len(result.detections), 1)
        det = result.detections[0]
        self.assertIsNotNone(det.box)
        box = det.box
        self.assertEqual(box.x1, 64)
        self.assertEqual(box.y1, 96)
        self.assertEqual(box.x2, 384)
        self.assertEqual(box.y2, 384)
        self.assertEqual(box.width, 320)
        self.assertEqual(box.height, 288)

    def test_bounding_box_clamping_on_out_of_bounds_values(self):
        """Verifies that normalized coordinates outside [0.0, 1.0] are safely clamped."""
        # Normalized coords: (-0.5, -0.2, 1.5, 2.0)
        raw_candidates = [
            [0, 15, 0.90, -0.5, -0.2, 1.5, 2.0],
        ]
        self.stub_engine.set_raw_detections(raw_candidates)

        result = self.detector.detect(self.dummy_frame)
        self.assertEqual(len(result.detections), 1)
        box = result.detections[0].box
        self.assertEqual(box.x1, 0)
        self.assertEqual(box.y1, 0)
        self.assertEqual(box.x2, 639)
        self.assertEqual(box.y2, 479)

    def test_inverted_bounding_box_normalization(self):
        """Verifies that inverted bounding boxes (x1 > x2) are corrected."""
        # Inverted coords: x1=0.8, x2=0.2
        raw_candidates = [
            [0, 15, 0.90, 0.8, 0.7, 0.2, 0.1],
        ]
        self.stub_engine.set_raw_detections(raw_candidates)

        result = self.detector.detect(self.dummy_frame)
        self.assertEqual(len(result.detections), 1)
        box = result.detections[0].box
        self.assertLessEqual(box.x1, box.x2)
        self.assertLessEqual(box.y1, box.y2)

    def test_empty_and_none_frames(self):
        """Verifies clean handling when frame is None, empty, or wrong type."""
        # None frame
        r1 = self.detector.detect(None)
        self.assertEqual(len(r1.detections), 0)

        # Empty dict
        r2 = self.detector.detect({})
        self.assertEqual(len(r2.detections), 0)

        # Non-frame object (e.g. integer)
        r3 = self.detector.detect(12345)
        self.assertEqual(len(r3.detections), 0)

    def test_malformed_model_outputs_handled_gracefully(self):
        """Verifies that malformed, non-numeric, or incomplete output rows do not crash."""
        raw_candidates = [
            # Incomplete row (< 7 elements)
            [0, 15, 0.9],
            # Non-numeric class ID
            [0, "invalid_id", 0.9, 0.1, 0.1, 0.5, 0.5],
            # Non-numeric confidence
            [0, 15, "invalid_conf", 0.1, 0.1, 0.5, 0.5],
            # NaN confidence
            [0, 15, float("nan"), 0.1, 0.1, 0.5, 0.5],
            # Infinity confidence
            [0, 15, float("inf"), 0.1, 0.1, 0.5, 0.5],
            # Out of bounds class ID (> 20)
            [0, 999, 0.9, 0.1, 0.1, 0.5, 0.5],
            # Negative class ID
            [0, -1, 0.9, 0.1, 0.1, 0.5, 0.5],
            # One valid row among bad rows
            [0, 15, 0.92, 0.1, 0.1, 0.5, 0.5],
        ]
        self.stub_engine.set_raw_detections(raw_candidates)

        result = self.detector.detect(self.dummy_frame)
        self.assertEqual(len(result.detections), 1)
        self.assertEqual(result.detections[0].label, "person")

    def test_inference_exception_handled_gracefully(self):
        """Verifies that an unhandled exception in inference engine does not crash detect()."""
        self.stub_engine.set_simulate_error(True)
        result = self.detector.detect(self.dummy_frame)
        self.assertEqual(len(result.detections), 0)

    def test_no_false_detections_when_empty_output(self):
        """Verifies zero false detections when model returns empty array."""
        self.stub_engine.set_raw_detections([])
        result = self.detector.detect(self.dummy_frame)
        self.assertEqual(len(result.detections), 0)

    def test_missing_model_files_validation(self):
        """Verifies that OpenCVInferenceEngine raises FileNotFoundError with helpful message when files are absent."""
        fake_prototxt = "/nonexistent/path/MobileNetSSD_deploy.prototxt"
        fake_weights = "/nonexistent/path/MobileNetSSD_deploy.caffemodel"

        # If OpenCV is installed in the test environment, verify FileNotFoundError
        # If OpenCV is not installed, verify RuntimeError
        try:
            import cv2
            with self.assertRaises(FileNotFoundError) as ctx:
                OpenCVInferenceEngine(fake_prototxt, fake_weights)
            self.assertIn("prototxt", str(ctx.exception))
        except ImportError:
            with self.assertRaises(RuntimeError) as ctx:
                OpenCVInferenceEngine(fake_prototxt, fake_weights)
            self.assertIn("OpenCV", str(ctx.exception))

    def test_vision_pipeline_integration_with_mock_camera(self):
        """Verifies end-to-end integration of MockCamera, VisionPipeline, and ObjectDetector."""
        camera = MockCamera(width=640, height=480)
        pipeline = VisionPipeline(camera=camera, detector=self.detector)

        # Before camera start -> capture_and_detect returns None
        self.assertFalse(camera.is_active)
        self.assertIsNone(pipeline.capture_and_detect())

        # Start pipeline
        pipeline.start()
        self.assertTrue(camera.is_active)

        # Inject fake detection into stub engine
        self.stub_engine.set_raw_detections([
            [0, 8, 0.82, 0.2, 0.3, 0.7, 0.8],  # class_id 8 = cat
        ])

        result = pipeline.capture_and_detect()
        self.assertIsNotNone(result)
        self.assertEqual(result.frame_width, 640)
        self.assertEqual(result.frame_height, 480)
        self.assertEqual(len(result.detections), 1)
        self.assertEqual(result.detections[0].label, "cat")
        self.assertAlmostEqual(result.detections[0].confidence, 0.82)

        # Stop pipeline
        pipeline.stop()
        self.assertFalse(camera.is_active)
        self.assertIsNone(pipeline.capture_and_detect())

    def test_opencv_camera_error_on_uninstalled_or_missing_device(self):
        """Verifies that OpenCVCamera raises clear RuntimeError when unavailable."""
        cam = OpenCVCamera(device_index=999)
        with self.assertRaises(RuntimeError) as ctx:
            cam.start()
        # Message should mention either OpenCV installation or device opening failure
        msg = str(ctx.exception).lower()
        self.assertTrue("opencv" in msg or "device" in msg or "webcam" in msg)

    def test_opencv_inference_engine_swap_rb_configuration(self):
        """Verifies that OpenCVInferenceEngine defaults to swap_rb=True and supports override."""
        import tempfile
        from unittest.mock import MagicMock, patch

        with tempfile.NamedTemporaryFile() as f_proto, tempfile.NamedTemporaryFile() as f_weights:
            mock_cv2 = MagicMock()
            mock_net = MagicMock()
            mock_cv2.dnn.readNetFromCaffe.return_value = mock_net

            with patch.dict("sys.modules", {"cv2": mock_cv2}):
                # 1. Default should be swap_rb=True (converting RGB camera frame to Caffe BGR)
                engine_default = OpenCVInferenceEngine(
                    prototxt_path=f_proto.name,
                    weights_path=f_weights.name,
                )
                self.assertTrue(engine_default.swap_rb)

                # 2. Explicit swap_rb=False override
                engine_bgr = OpenCVInferenceEngine(
                    prototxt_path=f_proto.name,
                    weights_path=f_weights.name,
                    swap_rb=False,
                )
                self.assertFalse(engine_bgr.swap_rb)

    def test_opencv_inference_engine_forward_preprocessing_blob_call(self):
        """Verifies that forward pass invokes cv2.dnn.blobFromImage with expected swapRB parameter."""
        import tempfile
        from unittest.mock import MagicMock, patch

        with tempfile.NamedTemporaryFile() as f_proto, tempfile.NamedTemporaryFile() as f_weights:
            mock_cv2 = MagicMock()
            mock_net = MagicMock()
            mock_cv2.dnn.readNetFromCaffe.return_value = mock_net
            mock_resized = MagicMock()
            mock_cv2.resize.return_value = mock_resized
            mock_blob = MagicMock()
            mock_cv2.dnn.blobFromImage.return_value = mock_blob

            with patch.dict("sys.modules", {"cv2": mock_cv2}):
                engine = OpenCVInferenceEngine(
                    prototxt_path=f_proto.name,
                    weights_path=f_weights.name,
                    swap_rb=True,
                )
                dummy_rgb_frame = MagicMock()
                engine.forward(dummy_rgb_frame)

                # Verify resize called with (320, 240)
                mock_cv2.resize.assert_called_once_with(
                    dummy_rgb_frame, (320, 240), interpolation=mock_cv2.INTER_LINEAR
                )

                # Verify blobFromImage called with swapRB=True
                mock_cv2.dnn.blobFromImage.assert_called_once_with(
                    mock_resized,
                    scalefactor=0.007843,
                    size=(300, 300),
                    mean=(127.5, 127.5, 127.5),
                    swapRB=True,
                    crop=False,
                )
                mock_net.setInput.assert_called_once_with(mock_blob)
                mock_net.forward.assert_called_once()

    def test_opencv_camera_converts_bgr_to_rgb(self):
        """Verifies OpenCVCamera converts native webcam BGR to canonical RGB conforming to BaseCamera."""
        from unittest.mock import MagicMock, patch

        mock_cv2 = MagicMock()
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_bgr_frame = MagicMock()
        mock_cap.read.return_value = (True, mock_bgr_frame)
        mock_cv2.VideoCapture.return_value = mock_cap
        mock_rgb_frame = MagicMock()
        mock_cv2.cvtColor.return_value = mock_rgb_frame
        mock_cv2.COLOR_BGR2RGB = 4

        with patch.dict("sys.modules", {"cv2": mock_cv2}):
            cam = OpenCVCamera(device_index=0)
            cam.start()
            self.assertTrue(cam.is_active)

            frame = cam.capture_frame()
            self.assertEqual(frame, mock_rgb_frame)
            mock_cv2.cvtColor.assert_called_once_with(mock_bgr_frame, mock_cv2.COLOR_BGR2RGB)
            cam.stop()


if __name__ == "__main__":
    unittest.main()
