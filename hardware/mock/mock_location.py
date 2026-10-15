"""Mock location provider for macOS simulation without active network requests."""

from typing import Optional

from core.logger import setup_logger
from core.models import GeoLocation
from hardware.base import BaseLocationProvider


class MockLocationProvider(BaseLocationProvider):
    """Simulates geolocation lookup without external HTTP network calls.

    Defaults to the coordinates documented in the Black Book test results
    (Mumbai, Maharashtra, India).
    """

    def __init__(
        self,
        default_location: Optional[GeoLocation] = None,
        logger_name: str = "viss.mock_location",
    ):
        self._logger = setup_logger(logger_name)
        if default_location is not None:
            self._location = default_location
        else:
            # Coordinates from Black Book Poster (Mumbai / Navi Mumbai area)
            self._location = GeoLocation(
                latitude=19.074800,
                longitude=72.885600,
                city="Mumbai",
                region="Maharashtra",
                country="India",
                source="MOCK",
            )
        self._is_available: bool = True

    def set_location(self, location: Optional[GeoLocation]) -> None:
        """Sets a custom location."""
        self._location = location

    def set_available(self, available: bool) -> None:
        """Toggles network availability simulation (offline mode)."""
        self._is_available = available

    def get_location(self) -> Optional[GeoLocation]:
        """Resolves location or returns None if offline."""
        if not self._is_available:
            self._logger.debug("MockLocationProvider: Location unavailable (offline simulation).")
            return None
        return self._location
