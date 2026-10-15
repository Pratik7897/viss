"""Central application controller orchestrating all VISS subsystems.

Coordinates:
- Distance monitoring & ultrasonic proximity alerting (dedicated worker thread)
- Computer vision capture & neural network inference (dedicated worker thread)
- Spoken voice announcements through earphones (VoiceAlertPlayer worker)
- Audio notification playback (platform-aware sound player)
- Emergency push-button monitoring & distress SMS dispatch (event worker)
"""

from dataclasses import dataclass
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from config.settings import AppConfig, get_config
from core.engine import DecisionEngine
from core.logger import setup_logger
from core.models import (
    BuzzerPattern,
    DistanceReading,
    FrameDetections,
    ReadingQuality,
    SystemStatus,
)
from core.sms_coordinator import SMSCoordinator
from core.sound_player import BaseSoundPlayer, MockSoundPlayer, SystemSoundPlayer
from core.voice_alert import VoiceAlertPlayer, MockVoiceAlertPlayer
from hardware.base import (
    BaseButton,
    BaseBuzzer,
    BaseCamera,
    BaseDistanceSensor,
    BaseGSM,
    BaseLocationProvider,
)
from hardware.mock import (
    MockButton,
    MockBuzzer,
    MockCamera,
    MockDistanceSensor,
    MockGSM,
    MockLocationProvider,
)
from vision.detector import ObjectDetector, StubInferenceEngine
from vision.pipeline import VisionPipeline


class ApplicationController:
    """Manages the full lifecycle and thread synchronization for VISS."""

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        distance_sensor: Optional[BaseDistanceSensor] = None,
        camera: Optional[BaseCamera] = None,
        buzzer: Optional[BaseBuzzer] = None,
        button: Optional[BaseButton] = None,
        gsm: Optional[BaseGSM] = None,
        location_provider: Optional[BaseLocationProvider] = None,
        detector: Optional[ObjectDetector] = None,
        decision_engine: Optional[DecisionEngine] = None,
        sms_coordinator: Optional[SMSCoordinator] = None,
        sound_player: Optional[BaseSoundPlayer] = None,
        voice_player: Optional[Any] = None,
        logger_name: str = "viss.controller",
    ):
        self._config = config or get_config()
        self._logger = setup_logger(logger_name)

        # Injected hardware and drivers
        self._distance_sensor = distance_sensor or MockDistanceSensor()
        self._camera = camera or MockCamera(
            width=self._config.vision.frame_width,
            height=self._config.vision.frame_height,
        )
        self._buzzer = buzzer or MockBuzzer()
        self._button = button or MockButton()
        self._gsm = gsm or MockGSM()
        self._location_provider = location_provider or MockLocationProvider()

        # Injected vision detector & pipeline
        self._detector = detector or ObjectDetector(
            config=self._config.vision,
            engine=StubInferenceEngine(),
        )
        self._vision_pipeline = VisionPipeline(
            camera=self._camera,
            detector=self._detector,
        )

        # Injected decision engine & SMS coordinator
        self._decision_engine = decision_engine or DecisionEngine(
            config=self._config,
        )
        self._sms_coordinator = sms_coordinator or SMSCoordinator(
            gsm=self._gsm,
            location_provider=self._location_provider,
            config=self._config.emergency,
        )

        # Audio alert player (WAV beeps)
        if sound_player is not None:
            self._sound_player = sound_player
        elif self._config.runtime.enable_sound and not self._config.is_mock_mode:
            self._sound_player = SystemSoundPlayer(
                sound_dir=self._config.runtime.sound_dir,
                animal_sound_file=self._config.runtime.animal_sound_file,
                human_sound_file=self._config.runtime.human_sound_file,
                enabled=True,
            )
        else:
            self._sound_player = MockSoundPlayer()

        # Voice announcement player (spoken TTS alerts)
        if voice_player is not None:
            self._voice_player = voice_player
        elif self._config.runtime.enable_voice_alerts and not self._config.is_mock_mode:
            self._voice_player = VoiceAlertPlayer(
                enabled=True,
                cooldown_s=self._config.runtime.voice_cooldown_s,
                max_queue_size=self._config.runtime.voice_queue_max,
                speech_rate=self._config.runtime.voice_rate,
                volume=self._config.runtime.voice_volume,
                announcement_format=self._config.runtime.voice_announcement_format,
            )
        else:
            self._voice_player = MockVoiceAlertPlayer()

        # Lifecycle synchronization
        self._status: SystemStatus = SystemStatus.STOPPED
        self._state_lock = threading.Lock()
        self._stop_event = threading.Event()

        # Worker threads
        self._distance_thread: Optional[threading.Thread] = None
        self._vision_thread: Optional[threading.Thread] = None
        self._button_thread: Optional[threading.Thread] = None

        # Cross-thread state variables
        self._latest_distance_m: Optional[float] = None
        self._last_target_seen_ts: Optional[float] = None
        self._last_detected_label: Optional[str] = None
        self._last_button_state: bool = False

        # Diagnostic counters
        self._distance_loop_count: int = 0
        self._vision_loop_count: int = 0
        self._button_loop_count: int = 0

    @classmethod
    def create_mock(cls, config: Optional[AppConfig] = None) -> "ApplicationController":
        """Factory creating a fully mock-backed controller for simulation and testing."""
        cfg = config or get_config()
        return cls(
            config=cfg,
            distance_sensor=MockDistanceSensor(),
            camera=MockCamera(),
            buzzer=MockBuzzer(),
            button=MockButton(),
            gsm=MockGSM(),
            location_provider=MockLocationProvider(),
            detector=ObjectDetector(config=cfg.vision, engine=StubInferenceEngine()),
            decision_engine=DecisionEngine(config=cfg),
            sound_player=MockSoundPlayer(),
            voice_player=MockVoiceAlertPlayer(),
        )

    @classmethod
    def create_hardware(cls, config: Optional[AppConfig] = None) -> "ApplicationController":
        """Factory creating a production hardware-backed controller for Raspberry Pi.

        Uses the real OpenCVInferenceEngine with configured model paths.
        Raises RuntimeError if production hardware dependencies fail.
        """
        from hardware.factory import create_production_hardware
        from vision.detector import OpenCVInferenceEngine

        cfg = config or get_config()
        logger = setup_logger("viss.controller_factory")

        # Initialize physical hardware
        bundle = create_production_hardware(cfg)

        # Initialize the real inference engine with configured model paths
        try:
            engine = OpenCVInferenceEngine(
                prototxt_path=cfg.vision.prototxt_path,
                weights_path=cfg.vision.weights_path,
            )
            logger.info("Production OpenCVInferenceEngine loaded successfully.")
        except (FileNotFoundError, RuntimeError) as e:
            bundle.close_all()
            raise RuntimeError(
                f"Cannot start production mode: {e}. "
                f"Ensure model files exist at:\n"
                f"  Prototxt: {cfg.vision.prototxt_path}\n"
                f"  Weights:  {cfg.vision.weights_path}\n"
                f"See vision/weights/README.md for download instructions."
            ) from e

        detector = ObjectDetector(config=cfg.vision, engine=engine)

        return cls(
            config=cfg,
            distance_sensor=bundle.distance_sensor,
            camera=bundle.camera,
            buzzer=bundle.buzzer,
            button=bundle.button,
            gsm=bundle.gsm,
            location_provider=bundle.location_provider,
            detector=detector,
        )

    @classmethod
    def create_mac_real(
        cls,
        config: Optional[AppConfig] = None,
        camera_device: int = 0,
    ) -> "ApplicationController":
        """Factory creating a real vision & speech controller for testing on macOS.

        Uses the real Mac webcam (OpenCVCamera), real MobileNet-SSD Caffe model
        (OpenCVInferenceEngine), and real offline voice alerts (VoiceAlertPlayer via macOS say),
        paired with mock GPIO sensors so that no physical Raspberry Pi pins are required.
        """
        from hardware.camera.opencv_camera import OpenCVCamera
        from vision.detector import OpenCVInferenceEngine

        cfg = config or get_config()
        logger = setup_logger("viss.controller_factory")

        # 1. Initialize real OpenCV camera (Mac webcam)
        camera = OpenCVCamera(
            device_index=camera_device,
            width=cfg.vision.frame_width,
            height=cfg.vision.frame_height,
        )

        # 2. Initialize real OpenCV inference engine with model files
        try:
            engine = OpenCVInferenceEngine(
                prototxt_path=cfg.vision.prototxt_path,
                weights_path=cfg.vision.weights_path,
                swap_rb=True,
            )
            logger.info("macOS OpenCVInferenceEngine loaded successfully.")
        except (FileNotFoundError, RuntimeError) as e:
            raise RuntimeError(
                f"Cannot start macOS real mode: {e}. "
                f"Ensure model files exist at:\n"
                f"  Prototxt: {cfg.vision.prototxt_path}\n"
                f"  Weights:  {cfg.vision.weights_path}\n"
                f"See MODEL_SELECTION.md for download instructions."
            ) from e

        detector = ObjectDetector(config=cfg.vision, engine=engine)

        # 3. Real voice alert player
        voice_player = VoiceAlertPlayer(
            enabled=cfg.runtime.enable_voice_alerts,
            cooldown_s=cfg.runtime.voice_cooldown_s,
            max_queue_size=cfg.runtime.voice_queue_max,
            speech_rate=cfg.runtime.voice_rate,
            announcement_format=cfg.runtime.voice_announcement_format,
        )

        logger.info("ApplicationController initialized for real macOS testing.")
        return cls(
            config=cfg,
            camera=camera,
            detector=detector,
            voice_player=voice_player,
            distance_sensor=MockDistanceSensor(),
            buzzer=MockBuzzer(),
            button=MockButton(),
            gsm=MockGSM(),
            location_provider=MockLocationProvider(),
        )

    @classmethod
    def create(cls, config: Optional[AppConfig] = None) -> "ApplicationController":
        """Selects mock or hardware controller based on config.is_mock_mode."""
        cfg = config or get_config()
        if cfg.is_mock_mode:
            return cls.create_mock(cfg)
        return cls.create_hardware(cfg)

    # ----------------- Property Accessors -----------------

    @property
    def status(self) -> SystemStatus:
        with self._state_lock:
            return self._status

    @property
    def is_running(self) -> bool:
        with self._state_lock:
            return self._status == SystemStatus.RUNNING

    @property
    def latest_distance_m(self) -> Optional[float]:
        with self._state_lock:
            return self._latest_distance_m

    @property
    def last_target_seen_ts(self) -> Optional[float]:
        with self._state_lock:
            return self._last_target_seen_ts

    @property
    def last_detected_label(self) -> Optional[str]:
        with self._state_lock:
            return self._last_detected_label

    @property
    def current_buzzer_pattern(self) -> BuzzerPattern:
        return self._decision_engine.current_pattern

    @property
    def decision_engine(self) -> DecisionEngine:
        return self._decision_engine

    @property
    def sms_coordinator(self) -> SMSCoordinator:
        return self._sms_coordinator

    @property
    def sound_player(self) -> BaseSoundPlayer:
        return self._sound_player

    @property
    def voice_player(self) -> Any:
        return self._voice_player

    @property
    def distance_sensor(self) -> BaseDistanceSensor:
        return self._distance_sensor

    @property
    def buzzer(self) -> BaseBuzzer:
        return self._buzzer

    @property
    def button(self) -> BaseButton:
        return self._button

    @property
    def camera(self) -> BaseCamera:
        return self._camera

    # ----------------- Lifecycle Controls -----------------

    def start(self) -> None:
        """Starts all subsystems and spawns concurrent worker threads.

        Safe to call repeatedly (subsequent calls when running are ignored).
        """
        with self._state_lock:
            if self._status == SystemStatus.RUNNING:
                self._logger.warning("ApplicationController is already running; start() ignored.")
                return

            self._logger.info("Starting ApplicationController subsystems...")
            self._status = SystemStatus.INITIALIZING
            self._stop_event.clear()

            # Start hardware drivers
            try:
                self._distance_sensor.start()
                self._vision_pipeline.start()
            except Exception as e:
                self._status = SystemStatus.ERROR
                self._logger.error("Failed to start hardware drivers: %s", e)
                raise

            # Spawn decoupled worker threads
            self._distance_thread = threading.Thread(
                target=self._distance_worker,
                name="viss-distance-worker",
                daemon=True,
            )
            self._vision_thread = threading.Thread(
                target=self._vision_worker,
                name="viss-vision-worker",
                daemon=True,
            )
            self._button_thread = threading.Thread(
                target=self._button_worker,
                name="viss-button-worker",
                daemon=True,
            )

            self._distance_thread.start()
            self._vision_thread.start()
            self._button_thread.start()

            self._status = SystemStatus.RUNNING
            self._logger.info("ApplicationController successfully running.")

    def stop(self, timeout_s: float = 2.0) -> None:
        """Signals stop event, joins worker threads, and releases resources.

        Safe to call repeatedly (subsequent calls when stopped are ignored).
        """
        with self._state_lock:
            if self._status == SystemStatus.STOPPED:
                return
            self._logger.info("Stopping ApplicationController...")
            self._status = SystemStatus.STOPPED
            self._stop_event.set()

        # Join worker threads
        for t in (self._distance_thread, self._vision_thread, self._button_thread):
            if t is not None and t.is_alive():
                t.join(timeout=timeout_s)

        # Release resources and silence alerts
        try:
            self._buzzer.turn_off()
        except Exception as e:
            self._logger.debug("Error silencing buzzer on shutdown: %s", e)

        try:
            self._distance_sensor.stop()
        except Exception as e:
            self._logger.debug("Error stopping distance sensor: %s", e)

        try:
            self._vision_pipeline.stop()
        except Exception as e:
            self._logger.debug("Error stopping vision pipeline: %s", e)

        try:
            self._sound_player.close()
        except Exception as e:
            self._logger.debug("Error closing sound player: %s", e)

        try:
            self._voice_player.close()
        except Exception as e:
            self._logger.debug("Error closing voice player: %s", e)

        self._logger.info("ApplicationController shutdown complete.")

    # ----------------- Worker Loops -----------------

    def _distance_worker(self) -> None:
        """Dedicated thread for continuous ultrasonic distance polling and buzzer updates."""
        poll_interval = self._config.thresholds.sensor_poll_interval_s

        while not self._stop_event.is_set():
            self._distance_loop_count += 1
            reading: Optional[DistanceReading] = None

            try:
                reading = self._distance_sensor.read_distance()
            except Exception as e:
                self._logger.error("Distance sensor read exception: %s", e)
                reading = DistanceReading(
                    distance_m=None,
                    timestamp=time.time(),
                    quality=ReadingQuality.ERROR,
                )

            # Update shared state
            with self._state_lock:
                if reading is not None and reading.is_valid:
                    self._latest_distance_m = reading.distance_m
                target_seen_ts = self._last_target_seen_ts

            # Evaluate distance against proximity bands and drive buzzer
            try:
                self._decision_engine.process_cycle(
                    reading=reading,
                    buzzer=self._buzzer,
                    last_target_seen_ts=target_seen_ts,
                )
            except Exception as e:
                self._logger.error("Decision engine evaluation exception: %s", e)

            # Avoid busy-waiting
            self._stop_event.wait(timeout=poll_interval)

    def _vision_worker(self) -> None:
        """Dedicated thread for camera capture, neural network inference, and voice/sound triggers."""
        poll_interval = self._config.runtime.camera_poll_interval_s
        target_classes = set(self._config.vision.target_classes)
        animal_classes = set(self._config.runtime.animal_classes)
        human_classes = set(self._config.runtime.human_classes)

        while not self._stop_event.is_set():
            self._vision_loop_count += 1
            frame_detections: Optional[FrameDetections] = None

            try:
                frame_detections = self._vision_pipeline.capture_and_detect()
            except Exception as e:
                self._logger.error("Vision pipeline inference exception: %s", e)
                frame_detections = None

            if frame_detections is not None and len(frame_detections.detections) > 0:
                now = time.time()
                detected_labels = frame_detections.labels

                # Check if any target entity was detected
                seen_targets = [lbl for lbl in detected_labels if lbl in target_classes]
                if seen_targets:
                    with self._state_lock:
                        self._last_target_seen_ts = now
                        self._last_detected_label = seen_targets[0]

                    # Voice announcements for each unique detected target.
                    # VoiceAlertPlayer handles per-label cooldown internally
                    # so the same continuously visible object is NOT re-announced.
                    announced_labels = set()
                    for lbl in seen_targets:
                        if lbl not in announced_labels:
                            self._voice_player.announce(lbl)
                            announced_labels.add(lbl)

                    # WAV beep alerts matching Black Book Ch 5.3.1
                    if any(lbl in animal_classes for lbl in detected_labels):
                        self._sound_player.play_category("animal")
                    elif any(lbl in human_classes for lbl in detected_labels):
                        self._sound_player.play_category("human")

            # Avoid busy-waiting
            self._stop_event.wait(timeout=poll_interval)

    def _button_worker(self) -> None:
        """Dedicated thread monitoring tactile push button for emergency SOS triggers."""
        poll_interval = self._config.runtime.button_poll_interval_s

        while not self._stop_event.is_set():
            self._button_loop_count += 1
            is_pressed = False

            try:
                is_pressed = self._button.is_pressed()
            except Exception as e:
                self._logger.error("Button polling exception: %s", e)

            # Detect rising edge (transition from unpressed to pressed)
            if is_pressed and not self._last_button_state:
                self._logger.info("Emergency button press detected. Triggering distress alert...")

                with self._state_lock:
                    label = self._last_detected_label
                    distance_m = self._latest_distance_m

                # Trigger emergency in a background thread so button loop is never blocked
                threading.Thread(
                    target=self._handle_emergency_press,
                    args=(label, distance_m),
                    name="viss-emergency-dispatch",
                    daemon=True,
                ).start()

            self._last_button_state = is_pressed
            self._stop_event.wait(timeout=poll_interval)

    def _handle_emergency_press(
        self,
        label: Optional[str],
        distance_m: Optional[float],
    ) -> None:
        """Executes emergency message dispatch through SMS coordinator."""
        try:
            success, status, body = self._sms_coordinator.trigger_emergency(
                label=label,
                distance_m=distance_m,
            )
            if success:
                self._logger.info("Distress alert successfully dispatched: %s", status)
            elif status == "COOLDOWN_ACTIVE":
                self._logger.debug("Duplicate distress trigger suppressed by cooldown.")
            else:
                self._logger.warning("Distress alert dispatch failed: %s", status)
        except Exception as e:
            self._logger.error("Unexpected error in emergency dispatch handler: %s", e)
