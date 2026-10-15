"""Unit tests for SystemSoundPlayer and MockSoundPlayer audio alert subsystems."""

import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

from core.sound_player import MockSoundPlayer, SystemSoundPlayer


class TestSoundPlayer(unittest.TestCase):
    """Verifies audio player behavior, fallback paths, and mock audio execution."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.sound_dir = self.temp_dir.name
        # Create a real temporary test WAV file in the temporary directory
        self.valid_sound_path = os.path.join(self.sound_dir, "test_audio.wav")
        with open(self.valid_sound_path, "wb") as f:
            f.write(b"RIFF dummy wav data")

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("subprocess.run")
    def test_disabled_player_refuses_playback(self, mock_subprocess):
        """Verifies that SystemSoundPlayer(enabled=False) refuses playback without invoking subprocess."""
        player = SystemSoundPlayer(
            sound_dir=self.sound_dir,
            enabled=False,
        )
        self.assertFalse(player.is_available)

        # Attempt to play existing file directly
        result_file = player.play_file(self.valid_sound_path)
        self.assertFalse(result_file)

        # Attempt to play category
        result_category = player.play_category("animal")
        self.assertFalse(result_category)

        # Subprocess must never be called
        mock_subprocess.assert_not_called()

    @patch("subprocess.run")
    def test_nonexistent_audio_file_returns_failure_cleanly(self, mock_subprocess):
        """Verifies that nonexistent audio file returns failure without invoking subprocess."""
        player = SystemSoundPlayer(
            sound_dir=self.sound_dir,
            enabled=True,
        )
        # Ensure player has a binary configured for testing even if run on platform without afplay/aplay
        player._player_bin = "/usr/bin/afplay"

        nonexistent_path = os.path.join(self.sound_dir, "nonexistent.wav")
        result = player.play_file(nonexistent_path)

        self.assertFalse(result)
        mock_subprocess.assert_not_called()

    @patch("subprocess.run")
    def test_missing_sound_directory_handled_safely(self, mock_subprocess):
        """Verifies that a missing sound directory fails safely without crashing or spawning subprocess."""
        missing_dir = os.path.join(self.sound_dir, "missing_subdir")
        player = SystemSoundPlayer(
            sound_dir=missing_dir,
            animal_sound_file="a.wav",
            human_sound_file="h.wav",
            enabled=True,
        )
        player._player_bin = "/usr/bin/afplay"

        self.assertFalse(player.play_category("animal"))
        self.assertFalse(player.play_category("human"))
        mock_subprocess.assert_not_called()

    @patch("subprocess.run")
    def test_closing_player_prevents_subsequent_playback(self, mock_subprocess):
        """Verifies that closing the player sets is_available to False and blocks future playback."""
        player = SystemSoundPlayer(
            sound_dir=self.sound_dir,
            animal_sound_file=os.path.basename(self.valid_sound_path),
            enabled=True,
        )
        player._player_bin = "/usr/bin/afplay"
        self.assertTrue(player.is_available)

        player.close()
        self.assertFalse(player.is_available)

        # Subsequent playback must fail
        self.assertFalse(player.play_file(self.valid_sound_path))
        self.assertFalse(player.play_category("animal"))
        mock_subprocess.assert_not_called()

    @patch("subprocess.run")
    def test_unknown_category_refuses_playback(self, mock_subprocess):
        """Verifies that unknown sound categories are rejected cleanly."""
        player = SystemSoundPlayer(sound_dir=self.sound_dir, enabled=True)
        player._player_bin = "/usr/bin/afplay"

        result = player.play_category("unknown_category")
        self.assertFalse(result)
        mock_subprocess.assert_not_called()

    @patch("shutil.which", return_value=None)
    @patch("subprocess.run")
    def test_missing_system_binary_disables_player(self, mock_subprocess, mock_which):
        """Verifies that absence of afplay/aplay binary disables playback gracefully."""
        player = SystemSoundPlayer(sound_dir=self.sound_dir, enabled=True)
        self.assertFalse(player.is_available)
        self.assertIsNone(player._player_bin)

        self.assertFalse(player.play_file(self.valid_sound_path))
        mock_subprocess.assert_not_called()

    @patch("subprocess.run")
    def test_successful_playback_invokes_subprocess(self, mock_subprocess):
        """Verifies that valid file with available player executes subprocess asynchronously."""
        called_event = threading.Event()

        def fake_run(*args, **kwargs):
            called_event.set()
            return MagicMock(returncode=0)

        mock_subprocess.side_effect = fake_run

        player = SystemSoundPlayer(
            sound_dir=self.sound_dir,
            animal_sound_file=os.path.basename(self.valid_sound_path),
            enabled=True,
        )
        player._player_bin = "/mock/bin/afplay"

        result = player.play_category("animal")
        self.assertTrue(result)

        # Wait for daemon thread to execute subprocess.run
        signaled = called_event.wait(timeout=2.0)
        self.assertTrue(signaled, "Worker thread did not invoke subprocess within timeout")

        mock_subprocess.assert_called_once_with(
            ["/mock/bin/afplay", self.valid_sound_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5.0,
        )

    @patch("subprocess.run")
    def test_subprocess_execution_exception_handled_cleanly(self, mock_subprocess):
        """Verifies that subprocess errors inside worker thread do not propagate unhandled."""
        error_event = threading.Event()

        def failing_run(*args, **kwargs):
            error_event.set()
            raise subprocess.SubprocessError("Simulated playback process error")

        mock_subprocess.side_effect = failing_run

        player = SystemSoundPlayer(
            sound_dir=self.sound_dir,
            enabled=True,
        )
        player._player_bin = "/mock/bin/afplay"

        result = player.play_file(self.valid_sound_path)
        self.assertTrue(result)

        signaled = error_event.wait(timeout=2.0)
        self.assertTrue(signaled, "Worker thread did not encounter error event within timeout")

    def test_mock_sound_player_lifecycle_and_recording(self):
        """Verifies that MockSoundPlayer accurately records played categories and files."""
        mock_player = MockSoundPlayer()

        self.assertEqual(len(mock_player.played_sounds), 0)
        self.assertTrue(mock_player.play_category("animal"))
        self.assertTrue(mock_player.play_file("/path/to/h.wav"))

        self.assertEqual(len(mock_player.played_sounds), 2)
        self.assertEqual(mock_player.played_sounds[0]["category"], "animal")
        self.assertEqual(mock_player.played_sounds[1]["file_path"], "/path/to/h.wav")

        # Test clear
        mock_player.clear()
        self.assertEqual(len(mock_player.played_sounds), 0)

        # Test simulated failure
        mock_player.set_simulate_failure(True)
        self.assertFalse(mock_player.play_category("animal"))
        self.assertFalse(mock_player.play_file("/path/to/h.wav"))
        self.assertEqual(len(mock_player.played_sounds), 0)

        mock_player.set_simulate_failure(False)
        self.assertTrue(mock_player.play_category("human"))

        # Test close
        mock_player.close()
        self.assertFalse(mock_player.play_category("human"))
        self.assertFalse(mock_player.play_file("/path/to/h.wav"))

    def test_default_sounds_directory_and_wav_files(self):
        """Verifies that generated alert sound assets (a.wav, h.wav) exist and conform to WAV specifications."""
        import wave

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sounds_dir = os.path.join(base_dir, "sounds")

        for sound_name in ("a.wav", "h.wav"):
            wav_path = os.path.join(sounds_dir, sound_name)
            self.assertTrue(os.path.isfile(wav_path), f"Expected alert sound {wav_path} to exist.")

            with wave.open(wav_path, "r") as wf:
                self.assertEqual(wf.getnchannels(), 1, f"{sound_name} should be mono.")
                self.assertEqual(wf.getsampwidth(), 2, f"{sound_name} should be 16-bit PCM.")
                self.assertEqual(wf.getframerate(), 16000, f"{sound_name} should have 16 kHz sample rate.")
                self.assertGreater(wf.getnframes(), 0, f"{sound_name} should contain audio frames.")

    def test_system_sound_player_auto_discovery_of_sounds_dir(self):
        """Verifies that SystemSoundPlayer defaults to 'sounds' directory if present when sound_dir is empty."""
        player = SystemSoundPlayer(sound_dir="", enabled=False)
        self.assertTrue(
            player._sound_dir.endswith("sounds"),
            f"Expected player sound_dir to resolve to 'sounds', got '{player._sound_dir}'",
        )


if __name__ == "__main__":
    unittest.main()
