"""Central configuration module for the Visual Impairment Support System (VISS).

This module defines all configurable parameters, GPIO assignments, distance
thresholds, vision parameters, communication settings, and runtime execution flags.

IMPORTANT ENGINEERING NOTE ON DISCREPANCIES (per PROJECT_REFERENCE_REVIEW.md):
-----------------------------------------------------------------------------
1. Ultrasonic Pin Assignment:
   - Report Table 5.1 & Schematic Fig 4.2: TRIG=GPIO24, ECHO=GPIO23.
   - Report Code (Ch 5.3.1): TRIG=GPIO23, ECHO=GPIO24 (inverted).
   We default to Table 5.1 (TRIG=24, ECHO=23), but allow full configuration.
2. Vision Arming Gate:
   - Original Black Book code required a vision target before the buzzer will sound
     (require_vision_for_buzzer=True).
   - In real-world navigation, physical obstacles like walls and poles are not recognized
     as target classes (person/dog/cat/car). Therefore, Phase 2 defaults to distance-based
     warnings independent of camera detections (require_vision_for_buzzer=False), while
     preserving the original Black Book logic as an optional compatibility mode.
3. Object Detection Architecture:
   - Report narrative and paper mention Haar Cascades, but executable code strictly uses
     MobileNet-SSD (Caffe DNN) on 20 Pascal VOC classes.
"""

from dataclasses import dataclass, field
import os
from typing import Tuple


@dataclass(frozen=True)
class PinConfig:
    """GPIO pin configuration for Raspberry Pi 4 (BCM numbering).

    Note: These pin numbers apply when running on the physical Raspberry Pi.
    On macOS, all hardware access is mocked and these values are ignored.
    """

    # Ultrasonic Sensor (HC-SR04)
    # Default matches Report Table 5.1 and Schematic Fig 4.2.
    # Set to trig=23, echo=24 if matching the original code line DistanceSensor(echo=24, trigger=23).
    hcsr04_trig: int = 24
    hcsr04_echo: int = 23

    # Buzzer
    buzzer: int = 18

    # Emergency Push Button
    emergency_button: int = 17

    # Vibration Motor (Proposed Improvement: unassigned in original BOM and code)
    vibration_motor: int | None = None

    # UART Pins for SIM800L (Informational; managed by Linux /dev/ttyS0 driver)
    uart_txd: int = 14  # Physical Pin 8 (Pi TXD -> SIM800L RXD)
    uart_rxd: int = 15  # Physical Pin 10 (Pi RXD -> SIM800L TXD)


@dataclass(frozen=True)
class ThresholdConfig:
    """Distance and timing thresholds for proximity alerts."""

    # Distance bands (in meters) from Black Book Ch 5.3.1 code
    near_threshold_m: float = 0.40  # < 0.40m: Continuous alert tone
    mid_threshold_m: float = 0.80   # 0.40m - 0.80m: Fast beeping
    far_threshold_m: float = 1.50   # 0.80m - 1.50m: Slow beeping
    max_distance_m: float = 4.00    # HC-SR04 maximum reliable range
    min_distance_m: float = 0.02    # HC-SR04 minimum detection limit (2 cm)

    # Beep timing cadences (seconds on, seconds off)
    fast_beep_on_s: float = 0.08
    fast_beep_off_s: float = 0.08

    slow_beep_on_s: float = 0.15
    slow_beep_off_s: float = 0.25

    # Polling frequency
    sensor_poll_interval_s: float = 0.012  # ~83 Hz loop timing


ALL_PASCAL_VOC_CLASSES: Tuple[str, ...] = (
    "aeroplane",
    "bicycle",
    "bird",
    "boat",
    "bottle",
    "bus",
    "car",
    "cat",
    "chair",
    "cow",
    "diningtable",
    "dog",
    "horse",
    "motorbike",
    "person",
    "pottedplant",
    "sheep",
    "sofa",
    "train",
    "tvmonitor",
)


@dataclass(frozen=True)
class VisionConfig:
    """Computer vision and object detection configuration."""

    # Arming window from Black Book code: duration in seconds after detecting
    # a target entity during which the buzzer is allowed to sound.
    arm_window_s: float = 1.0

    # Minimum detection confidence (0.0 to 1.0)
    confidence_threshold: float = 0.50

    # Target classes triggering auditory alert (Pascal VOC 20 taxonomy).
    # Defaults to all 20 classes so that people, animals, and common indoor/outdoor
    # obstacles (chair, bottle, table, sofa, screen, etc.) are detected and announced.
    target_classes: Tuple[str, ...] = ALL_PASCAL_VOC_CLASSES

    # Camera resolution
    frame_width: int = 640
    frame_height: int = 480

    # Model input inference dimensions
    inference_width: int = 320
    inference_height: int = 240

    # BEHAVIORAL TOGGLE:
    # False = Default safety mode (buzzer sounds on ANY physical obstacle, independent of camera).
    # True = Black Book compatibility mode (buzzer only sounds if vision detected a target class).
    require_vision_for_buzzer: bool = False

    # MobileNet-SSD Caffe model files
    prototxt_path: str = "vision/weights/MobileNetSSD_deploy.prototxt"
    weights_path: str = "vision/weights/MobileNetSSD_deploy.caffemodel"

    # Filter detections to target_classes only
    filter_to_targets: bool = True


@dataclass(frozen=True)
class EmergencyConfig:
    """Emergency distress alerting and cellular modem settings."""

    destination_phone: str = "+00CHANGEME"  # Override via VISS_PHONE_NUMBER env var
    uart_port: str = "/dev/ttyS0"             # Default: mini-UART (/dev/ttyS0).
                                               # Override with VISS_UART_PORT=/dev/ttyAMA0
                                               # when PL011 (full UART) is configured via
                                               # dtoverlay=disable-bt in /boot/firmware/config.txt.
    uart_baud: int = 9600
    uart_timeout_s: float = 2.0

    # Location resolution
    geo_url: str = "http://ip-api.com/json"
    geo_timeout_s: float = 2.5
    geo_cache_ttl_s: float = 120.0

    # Hardware debouncing for push button (seconds)
    button_bounce_time_s: float = 0.05

    # Accidental duplicate trigger cooldown (seconds)
    cooldown_s: float = 10.0


@dataclass(frozen=True)
class RuntimeConfig:
    """Runtime execution settings for ApplicationController."""

    enable_gui: bool = False
    enable_sound: bool = False
    sound_dir: str = ""
    animal_sound_file: str = "a.wav"
    human_sound_file: str = "h.wav"
    animal_classes: Tuple[str, ...] = ("dog", "cat", "bird", "horse", "sheep", "cow")
    human_classes: Tuple[str, ...] = ("person", "car", "bus", "motorbike", "bicycle", "train")
    obstacle_classes: Tuple[str, ...] = (
        "chair",
        "sofa",
        "diningtable",
        "bottle",
        "tvmonitor",
        "pottedplant",
    )
    camera_poll_interval_s: float = 0.033
    button_poll_interval_s: float = 0.05

    # Voice announcement settings
    enable_voice_alerts: bool = True
    voice_cooldown_s: float = 3.0       # Minimum seconds between same-label announcements
    voice_queue_max: int = 5            # Maximum queued announcements before dropping
    voice_rate: int = 160               # Speech rate (words per minute) for pyttsx3
    voice_volume: float = 1.0           # Volume (0.0 to 1.0)
    voice_announcement_format: str = "{label} detected"  # Template; {label} replaced by class name


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration aggregating all subsystems."""

    is_mock_mode: bool = True
    log_level: str = "INFO"

    pins: PinConfig = field(default_factory=PinConfig)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)
    emergency: EmergencyConfig = field(default_factory=EmergencyConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)


def get_config() -> AppConfig:
    """Factory function loading application configuration with environment overrides.

    Supported Environment Variables:
    - VISS_MOCK_MODE: "true" / "1" (default) or "false" / "0"
    - VISS_LOG_LEVEL: "DEBUG", "INFO", "WARNING", "ERROR"
    - VISS_REQUIRE_VISION_FOR_BUZZER: "true" (compatibility mode) or "false" (default safety mode)
    - VISS_TARGET_CLASSES: "all" (default) or comma-separated list like "person,dog,chair,bottle"
    - VISS_PHONE_NUMBER: Custom guardian phone number string
    - VISS_UART_PORT: Serial port for SIM800L modem UART communication.
                      Default: "/dev/ttyS0" (Raspberry Pi mini-UART, GPIO14/15).
                      Set to "/dev/ttyAMA0" after configuring dtoverlay=disable-bt
                      in /boot/firmware/config.txt to use the more stable PL011 UART.
                      Unused in mock mode.
    - VISS_TRIG_PIN: Custom HC-SR04 TRIG GPIO pin number
    - VISS_ECHO_PIN: Custom HC-SR04 ECHO GPIO pin number
    - VISS_EMERGENCY_COOLDOWN_S: Minimum seconds between consecutive emergency SMS sends
    - VISS_CONFIDENCE_THRESHOLD: Detection confidence threshold float (e.g. "0.60")
    - VISS_PROTOTXT_PATH: Custom path to MobileNet-SSD prototxt
    - VISS_WEIGHTS_PATH: Custom path to MobileNet-SSD caffemodel
    - VISS_ENABLE_GUI: "true" to display cv2.imshow window (default "false")
    - VISS_ENABLE_SOUND: "true" to play audio alerts via afplay/aplay (default "false")
    - VISS_SOUND_DIR: Directory containing audio files
    """
    mock_mode_env = os.getenv("VISS_MOCK_MODE", "true").lower() in ("true", "1", "yes")
    log_level = os.getenv("VISS_LOG_LEVEL", "INFO").upper()

    # Default to False (independent distance warnings). If explicitly set to "true", use Black Book mode.
    req_vision_env = os.getenv("VISS_REQUIRE_VISION_FOR_BUZZER")
    require_vision = (
        req_vision_env.lower() in ("true", "1", "yes")
        if req_vision_env is not None
        else False
    )

    # Pin overrides
    trig_pin = int(os.getenv("VISS_TRIG_PIN", "24"))
    echo_pin = int(os.getenv("VISS_ECHO_PIN", "23"))

    phone_number = os.getenv("VISS_PHONE_NUMBER", "+00CHANGEME")
    uart_port = os.getenv("VISS_UART_PORT", "/dev/ttyS0")
    cooldown_s = float(os.getenv("VISS_EMERGENCY_COOLDOWN_S", "10.0"))

    # Vision overrides
    conf_thresh = float(os.getenv("VISS_CONFIDENCE_THRESHOLD", "0.50"))
    prototxt_path = os.getenv("VISS_PROTOTXT_PATH", "vision/weights/MobileNetSSD_deploy.prototxt")
    weights_path = os.getenv("VISS_WEIGHTS_PATH", "vision/weights/MobileNetSSD_deploy.caffemodel")

    target_classes_env = os.getenv("VISS_TARGET_CLASSES")
    if target_classes_env:
        if target_classes_env.strip().lower() == "all":
            target_classes = ALL_PASCAL_VOC_CLASSES
        else:
            target_classes = tuple(c.strip().lower() for c in target_classes_env.split(",") if c.strip())
    else:
        target_classes = ALL_PASCAL_VOC_CLASSES

    # Runtime overrides
    enable_gui = os.getenv("VISS_ENABLE_GUI", "false").lower() in ("true", "1", "yes")
    enable_sound = os.getenv("VISS_ENABLE_SOUND", "false").lower() in ("true", "1", "yes")
    sound_dir = os.getenv("VISS_SOUND_DIR", "")

    # Voice announcement overrides
    enable_voice = os.getenv("VISS_ENABLE_VOICE", "true").lower() in ("true", "1", "yes")
    voice_cooldown = float(os.getenv("VISS_VOICE_COOLDOWN_S", "3.0"))
    voice_queue_max = int(os.getenv("VISS_VOICE_QUEUE_MAX", "5"))
    voice_rate = int(os.getenv("VISS_VOICE_RATE", "160"))
    voice_format = os.getenv("VISS_VOICE_FORMAT", "{label} detected")

    return AppConfig(
        is_mock_mode=mock_mode_env,
        log_level=log_level,
        pins=PinConfig(hcsr04_trig=trig_pin, hcsr04_echo=echo_pin),
        thresholds=ThresholdConfig(),
        vision=VisionConfig(
            require_vision_for_buzzer=require_vision,
            confidence_threshold=conf_thresh,
            prototxt_path=prototxt_path,
            weights_path=weights_path,
            target_classes=target_classes,
        ),
        emergency=EmergencyConfig(
            destination_phone=phone_number,
            uart_port=uart_port,
            cooldown_s=cooldown_s,
        ),
        runtime=RuntimeConfig(
            enable_gui=enable_gui,
            enable_sound=enable_sound,
            sound_dir=sound_dir,
            enable_voice_alerts=enable_voice,
            voice_cooldown_s=voice_cooldown,
            voice_queue_max=voice_queue_max,
            voice_rate=voice_rate,
            voice_announcement_format=voice_format,
        ),
    )
