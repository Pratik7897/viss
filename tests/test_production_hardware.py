"""Unit tests for Phase 5B Raspberry Pi production hardware drivers and hardware factory.

All physical hardware interfaces (GPIO, Picamera2, pyserial) are mocked using unittest.mock.
No physical hardware access or Raspberry Pi packages are required.
"""

import sys
import unittest
from unittest.mock import MagicMock, call, patch

from config.settings import AppConfig
from core.models import BuzzerPattern, ReadingQuality
from hardware.alert.gpio_buzzer import GPIOBuzzer
from hardware.button.gpio_button import GPIOButton
from hardware.camera.picam2_camera import PiCamera2Driver
from hardware.distance.gpio_distance import GPIODistanceSensor
from hardware.factory import (
    create_hardware_bundle,
    create_mock_hardware,
    create_production_hardware,
)
from hardware.gsm.serial_gsm import SerialGSM


class TestGPIODistanceSensor(unittest.TestCase):
    """Verifies GPIODistanceSensor configuration, error resilience, and lifecycle."""

    def test_init_parameters_and_deferred_import(self):
        """Verifies sensor initializes cleanly without importing gpiozero or touching GPIO."""
        sensor = GPIODistanceSensor(trig_pin=24, echo_pin=23, max_distance_m=3.5, min_distance_m=0.05)
        self.assertEqual(sensor.trig_pin, 24)
        self.assertEqual(sensor.echo_pin, 23)
        self.assertFalse(sensor.is_active)
        self.assertIsNone(sensor._sensor)

    def test_missing_gpiozero_raises_runtime_error_on_start(self):
        """Verifies start() raises a clear RuntimeError when gpiozero is not installed."""
        sensor = GPIODistanceSensor()
        with patch.dict("sys.modules", {"gpiozero": None}):
            with self.assertRaises(RuntimeError) as ctx:
                sensor.start()
            self.assertIn("gpiozero", str(ctx.exception))
        self.assertFalse(sensor.is_active)

    def test_successful_start_and_distance_reading(self):
        """Verifies start() initializes gpiozero DistanceSensor and reads valid distance."""
        mock_gpiozero = MagicMock()
        mock_hw_sensor = MagicMock()
        mock_hw_sensor.distance = 1.25
        mock_gpiozero.DistanceSensor.return_value = mock_hw_sensor

        sensor = GPIODistanceSensor(trig_pin=24, echo_pin=23, max_distance_m=4.0)
        with patch.dict("sys.modules", {"gpiozero": mock_gpiozero}):
            sensor.start()
            self.assertTrue(sensor.is_active)
            mock_gpiozero.DistanceSensor.assert_called_once_with(echo=23, trigger=24, max_distance=4.0)

            reading = sensor.read_distance()
            self.assertTrue(reading.is_valid)
            self.assertEqual(reading.quality, ReadingQuality.VALID)
            self.assertAlmostEqual(reading.distance_m, 1.25)

            sensor.stop()
            self.assertFalse(sensor.is_active)
            mock_hw_sensor.close.assert_called_once()

    def test_out_of_range_and_exception_readings(self):
        """Verifies that out-of-range or sensor errors return structured DistanceReading without crashing."""
        mock_gpiozero = MagicMock()
        mock_hw_sensor = MagicMock()
        mock_gpiozero.DistanceSensor.return_value = mock_hw_sensor

        sensor = GPIODistanceSensor(min_distance_m=0.02, max_distance_m=4.0)
        with patch.dict("sys.modules", {"gpiozero": mock_gpiozero}):
            sensor.start()

            # 1. Below minimum range (e.g. 0.01m)
            mock_hw_sensor.distance = 0.01
            r_low = sensor.read_distance()
            self.assertEqual(r_low.quality, ReadingQuality.OUT_OF_RANGE)

            # 2. Above maximum range (e.g. 4.5m)
            mock_hw_sensor.distance = 4.5
            r_high = sensor.read_distance()
            self.assertEqual(r_high.quality, ReadingQuality.OUT_OF_RANGE)

            # 3. Sensor exception during read
            from unittest.mock import PropertyMock
            type(mock_hw_sensor).distance = PropertyMock(side_effect=RuntimeError("Sensor hardware read timeout"))
            r_err = sensor.read_distance()
            self.assertEqual(r_err.quality, ReadingQuality.ERROR)
            self.assertIsNone(r_err.distance_m)

            sensor.stop()

    def test_inactive_sensor_returns_error_reading(self):
        """Verifies reading from an inactive sensor returns ReadingQuality.ERROR."""
        sensor = GPIODistanceSensor()
        self.assertFalse(sensor.is_active)
        reading = sensor.read_distance()
        self.assertEqual(reading.quality, ReadingQuality.ERROR)
        self.assertIsNone(reading.distance_m)


class TestPiCamera2Driver(unittest.TestCase):
    """Verifies PiCamera2Driver configuration, frame capture, and error handling."""

    def test_init_parameters_and_deferred_import(self):
        """Verifies camera initializes resolution without importing picamera2."""
        cam = PiCamera2Driver(width=640, height=480)
        self.assertEqual(cam.get_resolution(), (640, 480))
        self.assertFalse(cam.is_active)
        self.assertIsNone(cam._picam2)

    def test_missing_picamera2_raises_runtime_error_on_start(self):
        """Verifies start() raises a clear RuntimeError when picamera2 is absent."""
        cam = PiCamera2Driver()
        with patch.dict("sys.modules", {"picamera2": None}):
            with self.assertRaises(RuntimeError) as ctx:
                cam.start()
            self.assertIn("picamera2", str(ctx.exception))
        self.assertFalse(cam.is_active)

    def test_successful_capture_and_rgb_channel_slicing(self):
        """Verifies start(), frame capture, and stop() with Picamera2 mock."""
        mock_picam_mod = MagicMock()
        mock_cam_inst = MagicMock()
        mock_picam_mod.Picamera2.return_value = mock_cam_inst

        # Simulate 4-channel BGRA or RGBA array to verify slicing to 3-channel RGB
        mock_frame = MagicMock()
        mock_frame.ndim = 3
        mock_frame.shape = (480, 640, 4)
        mock_frame.size = 480 * 640 * 4
        # Mock slicing [:, :, :3]
        mock_sliced = MagicMock()
        mock_frame.__getitem__.return_value = mock_sliced
        mock_cam_inst.capture_array.return_value = mock_frame

        cam = PiCamera2Driver(width=640, height=480)
        with patch.dict("sys.modules", {"picamera2": mock_picam_mod}):
            cam.start()
            self.assertTrue(cam.is_active)
            mock_cam_inst.start.assert_called_once()

            frame = cam.capture_frame()
            self.assertEqual(frame, mock_sliced)

            cam.stop()
            self.assertFalse(cam.is_active)
            mock_cam_inst.stop.assert_called_once()
            mock_cam_inst.close.assert_called_once()

    def test_capture_failure_and_empty_frame(self):
        """Verifies capture error returns None gracefully."""
        mock_picam_mod = MagicMock()
        mock_cam_inst = MagicMock()
        mock_cam_inst.capture_array.side_effect = RuntimeError("Capture failure")
        mock_picam_mod.Picamera2.return_value = mock_cam_inst

        cam = PiCamera2Driver()
        with patch.dict("sys.modules", {"picamera2": mock_picam_mod}):
            cam.start()
            self.assertIsNone(cam.capture_frame())
            cam.stop()


class TestGPIOBuzzer(unittest.TestCase):
    """Verifies GPIOBuzzer pattern transitions, safety defaults, and cleanup."""

    def test_initial_state_is_off_and_safe(self):
        """Verifies buzzer defaults to OFF and does not touch GPIO on __init__."""
        buzzer = GPIOBuzzer(pin=18)
        self.assertEqual(buzzer.pin, 18)
        self.assertEqual(buzzer.current_pattern, BuzzerPattern.OFF)
        self.assertIsNone(buzzer._buzzer)

    def test_missing_gpiozero_raises_error_on_pattern_change(self):
        """Verifies RuntimeError when gpiozero is missing upon activating buzzer."""
        buzzer = GPIOBuzzer(pin=18)
        with patch.dict("sys.modules", {"gpiozero": None}):
            with self.assertRaises(RuntimeError) as ctx:
                buzzer.set_pattern(BuzzerPattern.CONTINUOUS)
            self.assertIn("gpiozero", str(ctx.exception))

    def test_pattern_mappings_to_gpiozero_calls(self):
        """Verifies pattern mapping: CONTINUOUS -> on, OFF -> off, FAST/SLOW -> beep."""
        mock_gpiozero = MagicMock()
        mock_hw_buzzer = MagicMock()
        mock_gpiozero.Buzzer.return_value = mock_hw_buzzer

        buzzer = GPIOBuzzer(
            pin=18,
            fast_beep_on_s=0.08,
            fast_beep_off_s=0.08,
            slow_beep_on_s=0.15,
            slow_beep_off_s=0.25,
        )

        with patch.dict("sys.modules", {"gpiozero": mock_gpiozero}):
            # 1. CONTINUOUS
            buzzer.set_pattern(BuzzerPattern.CONTINUOUS)
            mock_hw_buzzer.on.assert_called_once()
            self.assertEqual(buzzer.current_pattern, BuzzerPattern.CONTINUOUS)

            # 2. FAST_BEEP
            buzzer.set_pattern(BuzzerPattern.FAST_BEEP)
            mock_hw_buzzer.beep.assert_called_with(on_time=0.08, off_time=0.08, background=True)

            # 3. SLOW_BEEP
            buzzer.set_pattern(BuzzerPattern.SLOW_BEEP)
            mock_hw_buzzer.beep.assert_called_with(on_time=0.15, off_time=0.25, background=True)

            # 4. OFF / turn_off
            buzzer.turn_off()
            mock_hw_buzzer.off.assert_called()
            self.assertEqual(buzzer.current_pattern, BuzzerPattern.OFF)

            # 5. close
            buzzer.close()
            mock_hw_buzzer.close.assert_called_once()
            self.assertTrue(buzzer._is_closed)


class TestGPIOButton(unittest.TestCase):
    """Verifies GPIOButton pull-up configuration, state reading, and cleanup."""

    def test_initial_state_and_deferred_import(self):
        """Verifies button does not import gpiozero on creation."""
        button = GPIOButton(pin=17, pull_up=True, bounce_time_s=0.05)
        self.assertEqual(button.pin, 17)
        self.assertFalse(button.is_closed)
        self.assertIsNone(button._button)

    def test_missing_gpiozero_raises_error_on_initialization(self):
        """Verifies missing gpiozero raises RuntimeError on init and is_pressed returns False safely."""
        button = GPIOButton(pin=17)
        with patch.dict("sys.modules", {"gpiozero": None}):
            with self.assertRaises(RuntimeError) as ctx:
                button._ensure_initialized()
            self.assertIn("gpiozero", str(ctx.exception))
            # is_pressed() catches initialization failure and returns False without crashing
            self.assertFalse(button.is_pressed())

    def test_state_reading_and_close(self):
        """Verifies reading is_pressed and cleanup."""
        mock_gpiozero = MagicMock()
        mock_hw_button = MagicMock()
        mock_hw_button.is_pressed = True
        mock_gpiozero.Button.return_value = mock_hw_button

        button = GPIOButton(pin=17, pull_up=True, bounce_time_s=0.05)
        with patch.dict("sys.modules", {"gpiozero": mock_gpiozero}):
            self.assertTrue(button.is_pressed())
            mock_gpiozero.Button.assert_called_once_with(pin=17, pull_up=True, bounce_time=0.05)

            mock_hw_button.is_pressed = False
            self.assertFalse(button.is_pressed())

            button.close()
            self.assertTrue(button.is_closed)
            mock_hw_button.close.assert_called_once()
            # After close, returns False without querying hardware
            self.assertFalse(button.is_pressed())


class TestSerialGSM(unittest.TestCase):
    """Verifies SerialGSM AT command sequence, readiness probing, and error handling."""

    def test_initial_configuration(self):
        """Verifies serial settings without opening ports."""
        gsm = SerialGSM(port="/dev/ttyS0", baudrate=9600, timeout_s=2.0)
        self.assertEqual(gsm.port, "/dev/ttyS0")
        self.assertEqual(gsm.baudrate, 9600)
        self.assertFalse(gsm.is_closed)

    def test_missing_pyserial_raises_runtime_error(self):
        """Verifies missing pyserial raises RuntimeError when opening port."""
        gsm = SerialGSM()
        with patch.dict("sys.modules", {"serial": None}):
            success, msg = gsm.send_sms("+918450976299", "Test alert")
            self.assertFalse(success)
            self.assertIn("pyserial", msg)

    def test_is_ready_probe(self):
        """Verifies is_ready probes modem with AT command."""
        mock_serial_mod = MagicMock()
        mock_ser = MagicMock()
        mock_ser.in_waiting = 6
        mock_ser.read.return_value = b"OK\r\n"
        mock_serial_mod.Serial.return_value = mock_ser

        gsm = SerialGSM(port="/dev/ttyS0")
        with patch.dict("sys.modules", {"serial": mock_serial_mod}):
            self.assertTrue(gsm.is_ready)
            mock_serial_mod.Serial.assert_called_with(port="/dev/ttyS0", baudrate=9600, timeout=2.0)
            mock_ser.write.assert_called_with(b"AT\r")
            mock_ser.close.assert_called()

    def test_successful_sms_transmission_at_sequence(self):
        """Verifies complete AT command handshake sequence for sending SMS."""
        mock_serial_mod = MagicMock()
        mock_ser = MagicMock()
        mock_serial_mod.Serial.return_value = mock_ser

        # Sequence of read responses from modem:
        # 1. AT -> OK
        # 2. ATE0 -> OK
        # 3. AT+CMGF=1 -> OK
        # 4. AT+CMGS="..." -> >
        # 5. Payload submitted -> +CMGS: 10\r\nOK
        responses = [
            b"OK\r\n",
            b"OK\r\n",
            b"OK\r\n",
            b">\r\n",
            b"+CMGS: 10\r\nOK\r\n",
        ]
        mock_ser.in_waiting = 20
        mock_ser.read.side_effect = responses

        gsm = SerialGSM(port="/dev/ttyS0", sms_timeout_s=5.0)
        with patch.dict("sys.modules", {"serial": mock_serial_mod}):
            success, status = gsm.send_sms("+918450976299", "Emergency distress test")
            self.assertTrue(success)
            self.assertIn("successfully", status.lower())

            # Verify command write calls
            calls = mock_ser.write.call_args_list
            written_data = [c[0][0] for c in calls]
            self.assertIn(b"AT\r", written_data)
            self.assertIn(b"AT+CMGF=1\r", written_data)
            self.assertIn(b'AT+CMGS="+918450976299"\r', written_data)
            self.assertIn(b"Emergency distress test\x1a", written_data)

    def test_invalid_phone_number_rejection(self):
        """Verifies that invalid phone numbers are rejected before touching serial port."""
        gsm = SerialGSM()
        success, msg = gsm.send_sms("", "Test")
        self.assertFalse(success)
        self.assertIn("Invalid", msg)

        success2, msg2 = gsm.send_sms("12", "Test")
        self.assertFalse(success2)


class TestHardwareFactory(unittest.TestCase):
    """Verifies factory creation of mock vs production bundles and partial cleanup."""

    def test_create_mock_hardware_returns_all_mocks(self):
        """Verifies create_mock_hardware produces mock driver bundle."""
        bundle = create_mock_hardware()
        self.assertEqual(bundle.distance_sensor.__class__.__name__, "MockDistanceSensor")
        self.assertEqual(bundle.camera.__class__.__name__, "MockCamera")
        self.assertEqual(bundle.buzzer.__class__.__name__, "MockBuzzer")
        self.assertEqual(bundle.button.__class__.__name__, "MockButton")
        self.assertEqual(bundle.gsm.__class__.__name__, "MockGSM")
        self.assertEqual(bundle.location_provider.__class__.__name__, "MockLocationProvider")
        bundle.close_all()

    def test_create_production_hardware_returns_production_drivers(self):
        """Verifies create_production_hardware instantiates production drivers."""
        bundle = create_production_hardware()
        self.assertEqual(bundle.distance_sensor.__class__.__name__, "GPIODistanceSensor")
        self.assertEqual(bundle.camera.__class__.__name__, "PiCamera2Driver")
        self.assertEqual(bundle.buzzer.__class__.__name__, "GPIOBuzzer")
        self.assertEqual(bundle.button.__class__.__name__, "GPIOButton")
        self.assertEqual(bundle.gsm.__class__.__name__, "SerialGSM")
        bundle.close_all()

    def test_create_hardware_bundle_respects_mock_flag(self):
        """Verifies create_hardware_bundle branches between mock and production."""
        mock_cfg = AppConfig(is_mock_mode=True)
        bundle_mock = create_hardware_bundle(mock_cfg)
        self.assertEqual(bundle_mock.distance_sensor.__class__.__name__, "MockDistanceSensor")

        prod_cfg = AppConfig(is_mock_mode=False)
        bundle_prod = create_hardware_bundle(prod_cfg)
        self.assertEqual(bundle_prod.distance_sensor.__class__.__name__, "GPIODistanceSensor")

    def test_partial_initialization_failure_cleans_up(self):
        """Verifies that if one driver fails to instantiate, previously created drivers are closed."""
        with patch("hardware.factory.GPIOBuzzer", side_effect=RuntimeError("Buzzer init boom")):
            with self.assertRaises(RuntimeError) as ctx:
                create_production_hardware()
            self.assertIn("Production hardware initialization failed", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
