"""Unit tests for configuration management and environment overrides."""

import os
import unittest
from unittest import mock

from config.settings import AppConfig, PinConfig, ThresholdConfig, VisionConfig, EmergencyConfig, get_config


class TestConfig(unittest.TestCase):
    """Verifies default settings and environment overrides."""

    def test_default_config_values(self):
        """Verifies default configuration matches specifications with safety defaults."""
        config = get_config()

        # By default on development machine, mock mode should be True
        self.assertTrue(config.is_mock_mode)
        self.assertEqual(config.log_level, "INFO")

        # Pin assignments default to Table 5.1 / Schematic Fig 4.2
        self.assertEqual(config.pins.hcsr04_trig, 24)
        self.assertEqual(config.pins.hcsr04_echo, 23)
        self.assertEqual(config.pins.buzzer, 18)
        self.assertEqual(config.pins.emergency_button, 17)
        self.assertIsNone(config.pins.vibration_motor)

        # Distance thresholds (meters)
        self.assertAlmostEqual(config.thresholds.near_threshold_m, 0.40)
        self.assertAlmostEqual(config.thresholds.mid_threshold_m, 0.80)
        self.assertAlmostEqual(config.thresholds.far_threshold_m, 1.50)
        self.assertAlmostEqual(config.thresholds.max_distance_m, 4.00)
        self.assertAlmostEqual(config.thresholds.min_distance_m, 0.02)

        # Vision configuration
        self.assertEqual(config.vision.arm_window_s, 1.0)
        self.assertEqual(config.vision.confidence_threshold, 0.50)
        self.assertIn("person", config.vision.target_classes)
        self.assertIn("car", config.vision.target_classes)
        self.assertIn("dog", config.vision.target_classes)
        self.assertIn("cat", config.vision.target_classes)

        # Default is independent distance warnings (require_vision_for_buzzer=False)
        self.assertFalse(config.vision.require_vision_for_buzzer)

        # Emergency communication
        self.assertEqual(config.emergency.destination_phone, "+00CHANGEME")
        self.assertEqual(config.emergency.uart_port, "/dev/ttyS0")
        self.assertEqual(config.emergency.uart_baud, 9600)
        self.assertAlmostEqual(config.emergency.cooldown_s, 10.0)

    def test_threshold_ordering(self):
        """Verifies mathematical ordering of distance zones."""
        t = ThresholdConfig()
        self.assertLess(t.min_distance_m, t.near_threshold_m)
        self.assertLess(t.near_threshold_m, t.mid_threshold_m)
        self.assertLess(t.mid_threshold_m, t.far_threshold_m)
        self.assertLess(t.far_threshold_m, t.max_distance_m)

    def test_environment_overrides(self):
        """Verifies that environment variables correctly override defaults."""
        custom_env = {
            "VISS_MOCK_MODE": "false",
            "VISS_LOG_LEVEL": "DEBUG",
            "VISS_REQUIRE_VISION_FOR_BUZZER": "true",  # Compatibility mode
            "VISS_PHONE_NUMBER": "+919999988888",
            "VISS_TRIG_PIN": "23",                     # Inverted code pin test
            "VISS_ECHO_PIN": "24",
            "VISS_EMERGENCY_COOLDOWN_S": "15.0",
        }

        with mock.patch.dict(os.environ, custom_env, clear=False):
            cfg = get_config()
            self.assertFalse(cfg.is_mock_mode)
            self.assertEqual(cfg.log_level, "DEBUG")
            self.assertTrue(cfg.vision.require_vision_for_buzzer)
            self.assertEqual(cfg.emergency.destination_phone, "+919999988888")
            self.assertEqual(cfg.pins.hcsr04_trig, 23)
            self.assertEqual(cfg.pins.hcsr04_echo, 24)
            self.assertAlmostEqual(cfg.emergency.cooldown_s, 15.0)

    def test_uart_port_default(self):
        """Verifies UART port defaults to /dev/ttyS0 (mini-UART) when VISS_UART_PORT is unset."""
        # Remove any stray env var so the default is exercised cleanly.
        env_without_uart = {k: v for k, v in os.environ.items() if k != "VISS_UART_PORT"}
        with mock.patch.dict(os.environ, env_without_uart, clear=True):
            cfg = get_config()
            self.assertEqual(cfg.emergency.uart_port, "/dev/ttyS0")

    def test_uart_port_env_override(self):
        """Verifies VISS_UART_PORT overrides the default serial port in EmergencyConfig."""
        with mock.patch.dict(os.environ, {"VISS_UART_PORT": "/dev/ttyAMA0"}, clear=False):
            cfg = get_config()
            self.assertEqual(cfg.emergency.uart_port, "/dev/ttyAMA0")

    def test_uart_port_custom_device(self):
        """Verifies VISS_UART_PORT accepts arbitrary device paths (e.g. USB-to-serial adapters)."""
        with mock.patch.dict(os.environ, {"VISS_UART_PORT": "/dev/ttyUSB0"}, clear=False):
            cfg = get_config()
            self.assertEqual(cfg.emergency.uart_port, "/dev/ttyUSB0")


class TestSerialGSMPortPropagation(unittest.TestCase):
    """Verifies that the hardware factory propagates the configured UART port to SerialGSM.

    No serial port is opened; all hardware access is mocked.
    """

    def test_factory_passes_default_port_to_serial_gsm(self):
        """Verifies create_production_hardware passes cfg.emergency.uart_port to SerialGSM."""
        from config.settings import AppConfig, EmergencyConfig
        from hardware.factory import create_production_hardware

        cfg = AppConfig(is_mock_mode=False, emergency=EmergencyConfig(uart_port="/dev/ttyS0"))
        bundle = create_production_hardware(cfg)
        self.assertEqual(bundle.gsm.port, "/dev/ttyS0")
        bundle.close_all()

    def test_factory_passes_overridden_port_to_serial_gsm(self):
        """Verifies the factory honours a non-default UART port (/dev/ttyAMA0)."""
        from config.settings import AppConfig, EmergencyConfig
        from hardware.factory import create_production_hardware

        cfg = AppConfig(is_mock_mode=False, emergency=EmergencyConfig(uart_port="/dev/ttyAMA0"))
        bundle = create_production_hardware(cfg)
        self.assertEqual(bundle.gsm.port, "/dev/ttyAMA0")
        bundle.close_all()

    def test_env_var_uart_port_reaches_serial_gsm_via_get_config(self):
        """End-to-end: VISS_UART_PORT env var flows through get_config() into SerialGSM.port."""
        from config.settings import get_config
        from hardware.factory import create_production_hardware

        with mock.patch.dict(os.environ, {"VISS_UART_PORT": "/dev/ttyAMA0"}, clear=False):
            cfg = get_config()
            bundle = create_production_hardware(cfg)
            self.assertEqual(bundle.gsm.port, "/dev/ttyAMA0")
            bundle.close_all()


if __name__ == "__main__":
    unittest.main()
