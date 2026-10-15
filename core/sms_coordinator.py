"""Emergency SMS Coordinator for the Visual Impairment Support System (VISS).

This module coordinates emergency distress alert composition, location resolution,
cellular SMS dispatch, and accidental duplicate suppression (cooldown).

DOCUMENTED SMS FORMAT & VARIATIONS IN REFERENCE DOCUMENTS:
---------------------------------------------------------
1. Executable Code Listing (Black Book Ch 5.3.1, Pages 41-42) [Primary Specification]:
   When location is available:
       [ALERT]
       Detected: {label}
       Range: {distance_text}
       Loc: {city}, {region}, {country}
       https://maps.google.com/?q={latitude:.6f},{longitude:.6f}
   When location is unavailable:
       [ALERT]
       Detected: {label}
       Range: {distance_text}
       Loc: unavailable

2. Avishkar Poster Figure A.1:
   Matches the Code listing format above. For example:
       [ALERT]
       Detected: N/A
       Range: 11.31 m
       Loc: Mumbai, Maharashtra, India
       https://maps.google.com/?q=19.074800,72.885600

3. Narrative Inconsistencies:
   - Section 3.2.4 text states: "Emergency! Please help. Location: [IP based location]"
   - Section 4.3 text states: "Emergency, please help"
   Because the Code listing and poster represent the functional implementation,
   we implement the structured [ALERT] format while documenting the narrative variation.
"""

import time
from typing import List, Optional, Tuple

from config.settings import EmergencyConfig, get_config
from core.logger import setup_logger
from core.models import EmergencyEvent, GeoLocation
from hardware.base import BaseGSM, BaseLocationProvider


def compose_emergency_message(
    label: Optional[str] = None,
    distance_m: Optional[float] = None,
    location: Optional[GeoLocation] = None,
) -> str:
    """Formats the emergency SMS message according to Black Book Chapter 5.3.1.

    Args:
        label: Most recently detected object label (e.g. 'person', 'car', or None).
        distance_m: Current measured distance in meters, or None.
        location: Resolved GeoLocation instance, or None.

    Returns:
        Structured text message payload for SMS transmission.
    """
    detected_label = label if label else "N/A"
    distance_text = f"{distance_m:.2f} m" if distance_m is not None else "unknown"

    if location is not None:
        loc_summary = location.location_summary()
        maps_link = location.maps_url()
        return (
            f"[ALERT]\n"
            f"Detected: {detected_label}\n"
            f"Range: {distance_text}\n"
            f"Loc: {loc_summary}\n"
            f"{maps_link}"
        )
    else:
        return (
            f"[ALERT]\n"
            f"Detected: {detected_label}\n"
            f"Range: {distance_text}\n"
            f"Loc: unavailable"
        )


class SMSCoordinator:
    """Coordinates emergency triggers, location fetching, SMS dispatch, and deduplication."""

    def __init__(
        self,
        gsm: BaseGSM,
        location_provider: Optional[BaseLocationProvider] = None,
        config: Optional[EmergencyConfig] = None,
        logger_name: str = "viss.sms_coordinator",
    ):
        self._gsm = gsm
        self._location_provider = location_provider
        self._config = config or get_config().emergency
        self._logger = setup_logger(logger_name)

        # State tracking
        self._last_sent_ts: float = 0.0
        self._history: List[EmergencyEvent] = []

    @property
    def destination_phone(self) -> str:
        return self._config.destination_phone

    @property
    def cooldown_s(self) -> float:
        return self._config.cooldown_s

    @property
    def last_sent_ts(self) -> float:
        return self._last_sent_ts

    @property
    def history(self) -> List[EmergencyEvent]:
        """Audit log of triggered emergency events."""
        return list(self._history)

    def is_in_cooldown(self, current_time: Optional[float] = None) -> bool:
        """Returns True if the cooldown period is currently active."""
        now = current_time if current_time is not None else time.time()
        return (now - self._last_sent_ts) < self._config.cooldown_s

    def cooldown_remaining_s(self, current_time: Optional[float] = None) -> float:
        """Returns remaining seconds before another SMS can be sent, or 0.0."""
        now = current_time if current_time is not None else time.time()
        remaining = self._config.cooldown_s - (now - self._last_sent_ts)
        return max(0.0, remaining)

    def trigger_emergency(
        self,
        label: Optional[str] = None,
        distance_m: Optional[float] = None,
        current_time: Optional[float] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """Handles an emergency push button press.

        Resolves location, checks deduplication cooldown, formats SMS, and sends via GSM.

        Args:
            label: Detected hazard label (optional).
            distance_m: Current distance in meters (optional).
            current_time: Mock timestamp for deterministic testing (optional).

        Returns:
            Tuple of:
            - success: bool (True if SMS was successfully transmitted)
            - status_code: str ('SENT', 'COOLDOWN_ACTIVE', 'GSM_UNAVAILABLE', 'GSM_SEND_FAILED')
            - message_body: Optional[str] (the formatted message payload, or None if in cooldown)
        """
        now = current_time if current_time is not None else time.time()

        # Step 1: Prevent duplicate sends during active cooldown
        if self.is_in_cooldown(current_time=now):
            remaining = self.cooldown_remaining_s(current_time=now)
            self._logger.warning(
                "Emergency trigger suppressed: cooldown active (%.1fs remaining).",
                remaining,
            )
            return False, "COOLDOWN_ACTIVE", None

        # Step 2: Check Modem Readiness
        if not self._gsm.is_ready:
            self._logger.error("Emergency trigger failed: GSM modem is not ready or registered.")
            # Still compose the message for logging / event record
            loc = self._location_provider.get_location() if self._location_provider else None
            msg = compose_emergency_message(label=label, distance_m=distance_m, location=loc)
            return False, "GSM_UNAVAILABLE", msg

        # Step 3: Resolve Location
        location = None
        if self._location_provider is not None:
            try:
                location = self._location_provider.get_location()
            except Exception as e:
                self._logger.error("Location resolution error: %s", e)
                location = None

        # Step 4: Compose Message
        message = compose_emergency_message(
            label=label,
            distance_m=distance_m,
            location=location,
        )

        # Step 5: Dispatch via GSM Modem
        phone = self._config.destination_phone
        self._logger.info("Dispatching emergency SMS to %s...", phone)
        success, info = self._gsm.send_sms(phone_number=phone, message=message)

        if success:
            self._last_sent_ts = now
            event = EmergencyEvent(
                trigger="BUTTON_PRESS",
                timestamp=now,
                detected_label=label or "N/A",
                distance_text=f"{distance_m:.2f} m" if distance_m is not None else "unknown",
                location=location,
                composed_message=message,
            )
            self._history.append(event)
            self._logger.info("Emergency SMS successfully transmitted. Status: %s", info)
            return True, "SENT", message
        else:
            self._logger.error("Failed to transmit emergency SMS: %s", info)
            return False, f"GSM_SEND_FAILED: {info}", message
