"""Platform-aware audio player abstraction for the Visual Impairment Support System (VISS).

The original Black Book (Ch 5.3.1) played static WAV files using the Linux 'aplay' command:
- 'a.wav' for animal detections ('dog', 'cat')
- 'h.wav' for human/vehicle detections ('person', 'car')

On macOS, 'afplay' is the native command-line audio player.
This module provides a platform-aware abstraction with graceful fallbacks for missing
sound files or missing playback binaries, plus a MockSoundPlayer for automated testing.
"""

from abc import ABC, abstractmethod
import os
import platform
import shutil
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional

from core.logger import setup_logger


class BaseSoundPlayer(ABC):
    """Abstract interface for audio alert playback."""

    @abstractmethod
    def play_category(self, category: str) -> bool:
        """Plays sound associated with an alert category (e.g. 'animal', 'human').

        Args:
            category: 'animal' or 'human'.

        Returns:
            True if playback was initiated, False otherwise.
        """
        pass

    @abstractmethod
    def play_file(self, file_path: str) -> bool:
        """Plays the specified audio file.

        Args:
            file_path: Path to sound file on disk.

        Returns:
            True if playback was initiated, False otherwise.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Releases audio player resources."""
        pass


class MockSoundPlayer(BaseSoundPlayer):
    """In-memory mock sound player for unit testing without spawning audio processes."""

    def __init__(self, logger_name: str = "viss.mock_sound_player"):
        self._logger = setup_logger(logger_name)
        self._played_sounds: List[Dict[str, Any]] = []
        self._is_closed: bool = False
        self._simulate_failure: bool = False

    @property
    def played_sounds(self) -> List[Dict[str, Any]]:
        return list(self._played_sounds)

    def set_simulate_failure(self, failure: bool) -> None:
        self._simulate_failure = failure

    def clear(self) -> None:
        self._played_sounds.clear()

    def play_category(self, category: str) -> bool:
        if self._is_closed or self._simulate_failure:
            return False
        record = {"category": category, "timestamp": time.time()}
        self._played_sounds.append(record)
        self._logger.debug("MockSoundPlayer: Category '%s' played.", category)
        return True

    def play_file(self, file_path: str) -> bool:
        if self._is_closed or self._simulate_failure:
            return False
        record = {"file_path": file_path, "timestamp": time.time()}
        self._played_sounds.append(record)
        self._logger.debug("MockSoundPlayer: File '%s' played.", file_path)
        return True

    def close(self) -> None:
        self._is_closed = True


class SystemSoundPlayer(BaseSoundPlayer):
    """Cross-platform sound player using afplay (macOS) or aplay (Linux/Raspberry Pi)."""

    def __init__(
        self,
        sound_dir: str = "",
        animal_sound_file: str = "a.wav",
        human_sound_file: str = "h.wav",
        enabled: bool = True,
        logger_name: str = "viss.sound_player",
    ):
        self._logger = setup_logger(logger_name)
        if not sound_dir:
            default_sounds_dir = os.path.join(os.getcwd(), "sounds")
            self._sound_dir = default_sounds_dir if os.path.isdir(default_sounds_dir) else os.getcwd()
        else:
            self._sound_dir = sound_dir
        self._animal_sound_file = animal_sound_file
        self._human_sound_file = human_sound_file
        self._enabled = enabled
        self._is_closed = False

        # Determine platform-specific player utility
        sys_platform = platform.system()
        if sys_platform == "Darwin":
            self._player_bin = shutil.which("afplay")
        elif sys_platform == "Linux":
            self._player_bin = shutil.which("aplay")
        else:
            self._player_bin = None

        if self._enabled and not self._player_bin:
            self._logger.warning(
                "Audio playback binary ('afplay'/'aplay') not found on %s. Audio alerts disabled.",
                sys_platform,
            )

    @property
    def is_available(self) -> bool:
        return self._enabled and self._player_bin is not None and not self._is_closed

    def play_category(self, category: str) -> bool:
        if category == "animal":
            filename = self._animal_sound_file
        elif category == "human":
            filename = self._human_sound_file
        else:
            self._logger.warning("Unknown audio alert category: %s", category)
            return False

        full_path = os.path.join(self._sound_dir, filename)
        return self.play_file(full_path)

    def play_file(self, file_path: str) -> bool:
        if not self.is_available:
            self._logger.debug("Audio playback skipped: player unavailable or disabled.")
            return False

        if not os.path.isfile(file_path):
            self._logger.warning("Audio file not found: %s", file_path)
            return False

        # Non-blocking playback in a daemon thread matching Black Book Ch 5.3.1
        def _worker():
            try:
                subprocess.run(
                    [self._player_bin, file_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5.0,
                )
            except Exception as e:
                self._logger.error("Error playing audio '%s': %s", file_path, e)

        t = threading.Thread(target=_worker, daemon=True, name="viss-audio-worker")
        t.start()
        return True

    def close(self) -> None:
        self._is_closed = True
