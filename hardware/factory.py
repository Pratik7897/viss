"""Hardware driver factory for selecting mock or production Raspberry Pi drivers."""

from dataclasses import dataclass
from typing import Optional

from config.settings import AppConfig, get_config
from core.logger import setup_logger
from hardware.alert.gpio_buzzer import GPIOBuzzer
from hardware.base import (
    BaseButton,
    BaseBuzzer,
    BaseCamera,
    BaseDistanceSensor,
    BaseGSM,
    BaseLocationProvider,
)
from hardware.button.gpio_button import GPIOButton
from hardware.camera.picam2_camera import PiCamera2Driver
from hardware.distance.gpio_distance import GPIODistanceSensor
from hardware.gsm.serial_gsm import SerialGSM
from hardware.mock.mock_button import MockButton
from hardware.mock.mock_buzzer import MockBuzzer
from hardware.mock.mock_camera import MockCamera
from hardware.mock.mock_distance import MockDistanceSensor
from hardware.mock.mock_gsm import MockGSM
from hardware.mock.mock_location import MockLocationProvider


@dataclass
class HardwareBundle:
    """Encapsulates all physical or simulated hardware drivers."""

    distance_sensor: BaseDistanceSensor
    camera: BaseCamera
    buzzer: BaseBuzzer
    button: BaseButton
    gsm: BaseGSM
    location_provider: BaseLocationProvider

    def close_all(self) -> None:
        """Safely closes all initialized drivers."""
        for dev in (self.buzzer, self.button, self.gsm):
            try:
                dev.close()
            except Exception:
                pass
        for active_dev in (self.distance_sensor, self.camera):
            try:
                active_dev.stop()
            except Exception:
                pass


def create_mock_hardware(config: Optional[AppConfig] = None) -> HardwareBundle:
    """Instantiates a complete bundle of mock drivers for simulation on macOS."""
    cfg = config or get_config()
    return HardwareBundle(
        distance_sensor=MockDistanceSensor(),
        camera=MockCamera(
            width=cfg.vision.frame_width,
            height=cfg.vision.frame_height,
        ),
        buzzer=MockBuzzer(),
        button=MockButton(),
        gsm=MockGSM(),
        location_provider=MockLocationProvider(),
    )


def create_production_hardware(config: Optional[AppConfig] = None) -> HardwareBundle:
    """Instantiates production Raspberry Pi drivers using configured pins and buses.

    Raises RuntimeError with clear diagnostics if required system libraries or hardware
    interfaces are missing. Does NOT fall back silently to mock mode.
    """
    cfg = config or get_config()
    logger = setup_logger("viss.hardware_factory")
    created_devices = []

    try:
        # 1. Ultrasonic distance sensor (gpiozero)
        dist_sensor = GPIODistanceSensor(
            trig_pin=cfg.pins.hcsr04_trig,
            echo_pin=cfg.pins.hcsr04_echo,
            max_distance_m=cfg.thresholds.max_distance_m,
            min_distance_m=cfg.thresholds.min_distance_m,
        )
        created_devices.append(dist_sensor)

        # 2. CSI Camera (Picamera2)
        cam = PiCamera2Driver(
            width=cfg.vision.frame_width,
            height=cfg.vision.frame_height,
        )
        created_devices.append(cam)

        # 3. Acoustic buzzer (gpiozero)
        buzzer = GPIOBuzzer(
            pin=cfg.pins.buzzer,
            fast_beep_on_s=cfg.thresholds.fast_beep_on_s,
            fast_beep_off_s=cfg.thresholds.fast_beep_off_s,
            slow_beep_on_s=cfg.thresholds.slow_beep_on_s,
            slow_beep_off_s=cfg.thresholds.slow_beep_off_s,
        )
        created_devices.append(buzzer)

        # 4. Emergency tactile push button (gpiozero)
        button = GPIOButton(
            pin=cfg.pins.emergency_button,
            pull_up=True,
            bounce_time_s=0.05,
        )
        created_devices.append(button)

        # 5. Cellular GSM modem (pyserial)
        gsm = SerialGSM(
            port=cfg.emergency.uart_port,
            baudrate=cfg.emergency.uart_baud,
            timeout_s=cfg.emergency.uart_timeout_s,
        )
        created_devices.append(gsm)

        # 6. Geolocation provider (mock IP lookup until physical GPS module is added)
        loc = MockLocationProvider()

        logger.info("Production hardware bundle created successfully.")
        return HardwareBundle(
            distance_sensor=dist_sensor,
            camera=cam,
            buzzer=buzzer,
            button=button,
            gsm=gsm,
            location_provider=loc,
        )

    except Exception as e:
        logger.error("Failed to construct production hardware drivers: %s. Cleaning up...", e)
        # Clean up any partially constructed devices
        for dev in created_devices:
            if hasattr(dev, "close"):
                try:
                    dev.close()
                except Exception:
                    pass
            elif hasattr(dev, "stop"):
                try:
                    dev.stop()
                except Exception:
                    pass
        raise RuntimeError(f"Production hardware initialization failed: {e}") from e


def create_hardware_bundle(config: Optional[AppConfig] = None) -> HardwareBundle:
    """Selects mock or production hardware based on config.is_mock_mode."""
    cfg = config or get_config()
    if cfg.is_mock_mode:
        return create_mock_hardware(cfg)
    return create_production_hardware(cfg)
