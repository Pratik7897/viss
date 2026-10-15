"""Core Decision Engine for the Visual Impairment Support System (VISS).

This module coordinates proximity risk evaluation by mapping ultrasonic distance
measurements to acoustic alert patterns (BuzzerPattern), managing vision-arming
gates, and preventing redundant hardware commands.

ORIGINAL BLACK BOOK vs. RECOMMENDED SAFETY MODES:
-------------------------------------------------
1. Distance Bands (from Black Book Ch 5.3.1 code):
   - dist < near_threshold_m (0.40m): CONTINUOUS tone.
   - near_threshold_m <= dist < mid_threshold_m (0.80m): FAST_BEEP.
   - mid_threshold_m <= dist < far_threshold_m (1.50m): SLOW_BEEP.
   - dist >= far_threshold_m (1.50m): OFF.

2. Invalid/Failed Sensor Reading Handling:
   - Original Black Book: If dist is None, the function returns None (buzzer turns OFF).
     This is dangerous in assistive robotics because a sensor dropout right in front
     of an obstacle would silence the warning and trick the user into stepping forward.
   - VISS Safe Handling: When a sensor reading is invalid or None, the engine does NOT
     treat it as confirmed clear space. Instead, it maintains the last active warning
     pattern during transient dropouts (up to a configurable timeout), or applies a
     configurable fallback policy.

3. Vision Arming Gate:
   - Original Black Book (Ch 5.3.1): armed = (now - last_seen_ts) <= ARM_WINDOW.
     The buzzer ONLY sounded if a vision target (person/dog/cat/car) was seen in the last 1.0s.
     Static hazards like blank walls and poles were ignored.
   - VISS Default: Distance-based proximity warnings trigger independently of camera
     detections, while preserving the Black Book arming gate as a configurable mode.
"""

from enum import Enum
import time
from typing import Optional

from config.settings import AppConfig, ThresholdConfig, VisionConfig, get_config
from core.logger import setup_logger
from core.models import BuzzerPattern, DistanceReading, ReadingQuality
from hardware.base import BaseBuzzer


class InvalidReadingPolicy(str, Enum):
    """Behavior policy when an ultrasonic distance reading fails or is invalid."""

    MAINTAIN_LAST = "MAINTAIN_LAST"  # Maintain last known pattern for grace period (Safe)
    SILENT = "SILENT"                # Immediately turn off buzzer (Black Book compatibility)
    CAUTION = "CAUTION"              # Transition to SLOW_BEEP caution warning


class DecisionEngine:
    """Evaluates sensor inputs and drives acoustic alert state transitions."""

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        invalid_reading_policy: InvalidReadingPolicy = InvalidReadingPolicy.MAINTAIN_LAST,
        invalid_reading_grace_s: float = 0.50,
        logger_name: str = "viss.engine",
    ):
        self._config = config or get_config()
        self._thresholds: ThresholdConfig = self._config.thresholds
        self._vision_config: VisionConfig = self._config.vision
        self._policy = invalid_reading_policy
        self._grace_s = invalid_reading_grace_s
        self._logger = setup_logger(logger_name)

        # State tracking
        self._current_pattern: BuzzerPattern = BuzzerPattern.OFF
        self._last_valid_pattern: BuzzerPattern = BuzzerPattern.OFF
        self._last_valid_reading_ts: float = 0.0
        self._hardware_command_count: int = 0
        self._consecutive_invalid_count: int = 0

    @property
    def current_pattern(self) -> BuzzerPattern:
        """Currently active acoustic alert pattern."""
        return self._current_pattern

    @property
    def hardware_command_count(self) -> int:
        """Number of actual hardware state change commands dispatched."""
        return self._hardware_command_count

    @property
    def is_sensor_healthy(self) -> bool:
        """Returns False if consecutive sensor readings have failed."""
        return self._consecutive_invalid_count == 0

    def pick_beep_pattern(self, dist_m: Optional[float]) -> BuzzerPattern:
        """Maps a distance in meters to a BuzzerPattern using configured thresholds.

        Boundary semantics (matching Black Book Ch 5.3.1):
        - dist_m < near (0.40): CONTINUOUS
        - dist_m < mid (0.80): FAST_BEEP (at 0.40m, result is FAST_BEEP)
        - dist_m < far (1.50): SLOW_BEEP (at 0.80m, result is SLOW_BEEP)
        - dist_m >= far (1.50): OFF (at 1.50m, result is OFF)

        Args:
            dist_m: Valid physical distance in meters, or None.

        Returns:
            BuzzerPattern corresponding to the distance band.
        """
        if dist_m is None:
            return BuzzerPattern.OFF

        if dist_m < self._thresholds.near_threshold_m:
            return BuzzerPattern.CONTINUOUS
        elif dist_m < self._thresholds.mid_threshold_m:
            return BuzzerPattern.FAST_BEEP
        elif dist_m < self._thresholds.far_threshold_m:
            return BuzzerPattern.SLOW_BEEP
        else:
            return BuzzerPattern.OFF

    def is_vision_armed(
        self,
        last_target_seen_ts: Optional[float],
        current_time: Optional[float] = None,
    ) -> bool:
        """Determines if the buzzer is allowed to sound based on camera detections.

        In Default Mode (require_vision_for_buzzer=False):
            Always returns True. Ultrasonic alerts function independently.
        In Black Book Compatibility Mode (require_vision_for_buzzer=True):
            Returns True only if a target entity was identified within arm_window_s.
        """
        if not self._vision_config.require_vision_for_buzzer:
            return True

        if last_target_seen_ts is None:
            return False

        now = current_time if current_time is not None else time.time()
        return (now - last_target_seen_ts) <= self._vision_config.arm_window_s

    def evaluate_reading(
        self,
        reading: Optional[DistanceReading],
        last_target_seen_ts: Optional[float] = None,
        current_time: Optional[float] = None,
    ) -> BuzzerPattern:
        """Calculates the desired buzzer pattern for the given sensor reading.

        Handles boundary conditions, vision arming, and invalid reading policies.
        """
        now = current_time if current_time is not None else time.time()

        # Step 1: Handle Invalid, None, or Error Readings
        if reading is None or not reading.is_valid:
            self._consecutive_invalid_count += 1
            self._logger.debug(
                "Invalid distance reading received (quality=%s). Applying policy %s.",
                reading.quality.value if reading else "NONE",
                self._policy.value,
            )

            if self._policy == InvalidReadingPolicy.SILENT:
                return BuzzerPattern.OFF
            elif self._policy == InvalidReadingPolicy.CAUTION:
                return BuzzerPattern.SLOW_BEEP
            elif self._policy == InvalidReadingPolicy.MAINTAIN_LAST:
                # If we were previously warning of an obstacle, maintain that warning
                # during a brief sensor dropout window to protect the user.
                if (
                    self._last_valid_pattern != BuzzerPattern.OFF
                    and (now - self._last_valid_reading_ts) <= self._grace_s
                ):
                    return self._last_valid_pattern
                return BuzzerPattern.OFF

        # Reading is valid
        self._consecutive_invalid_count = 0
        self._last_valid_reading_ts = now

        # Step 2: Check Vision-Arming Gate
        armed = self.is_vision_armed(last_target_seen_ts, current_time=now)
        if not armed:
            self._logger.debug("Buzzer disarmed by vision gate (no target in window).")
            return BuzzerPattern.OFF

        # Step 3: Map Valid Distance to Pattern
        pattern = self.pick_beep_pattern(reading.distance_m)
        self._last_valid_pattern = pattern
        return pattern

    def update_buzzer(
        self,
        desired_pattern: BuzzerPattern,
        buzzer: Optional[BaseBuzzer] = None,
    ) -> bool:
        """Applies desired pattern to the buzzer, suppressing redundant commands.

        Args:
            desired_pattern: Target BuzzerPattern.
            buzzer: Hardware or mock buzzer instance (optional).

        Returns:
            True if pattern changed and hardware was commanded; False if suppressed.
        """
        if desired_pattern == self._current_pattern:
            # Pattern unchanged: avoid redundant hardware commands
            return False

        self._logger.info(
            "Pattern transition: %s -> %s",
            self._current_pattern.value,
            desired_pattern.value,
        )
        self._current_pattern = desired_pattern

        if buzzer is not None:
            buzzer.set_pattern(desired_pattern)
            self._hardware_command_count += 1

        return True

    def process_cycle(
        self,
        reading: Optional[DistanceReading],
        buzzer: Optional[BaseBuzzer] = None,
        last_target_seen_ts: Optional[float] = None,
        current_time: Optional[float] = None,
    ) -> BuzzerPattern:
        """Executes a complete decision cycle: evaluate reading and update buzzer.

        Args:
            reading: Ultrasonic sensor reading.
            buzzer: Buzzer driver.
            last_target_seen_ts: Vision target detection timestamp.
            current_time: Optional mock timestamp for deterministic testing.

        Returns:
            Active BuzzerPattern after update.
        """
        desired = self.evaluate_reading(
            reading=reading,
            last_target_seen_ts=last_target_seen_ts,
            current_time=current_time,
        )
        self.update_buzzer(desired, buzzer=buzzer)
        return self._current_pattern
