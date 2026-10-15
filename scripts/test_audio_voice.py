"""Milestone 4 audio output and spoken voice alert test for VISS.

Tests both the earphone audio output path (via aplay on Linux or afplay on macOS)
and the offline text-to-speech engine (pyttsx3 with espeak-ng backend on Linux).

Usage:
  python3 scripts/test_audio_voice.py
"""

import os
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.logger import setup_logger
from core.sound_player import SystemSoundPlayer, MockSoundPlayer
from core.voice_alert import VoiceAlertPlayer


def main() -> int:
    logger = setup_logger("viss.test_audio_voice")
    print("=" * 65)
    print("VISS Earphone Audio & Spoken TTS Verification")
    print("=" * 65)
    print("Ensure your wired 3.5mm earphones or Bluetooth headset are connected.")
    print("Press Enter to begin audio tests...")
    # non-blocking wait if piped
    if sys.stdin.isatty():
        input()

    # Step 1: WAV tone playback test
    print("\n[Step 1/2] Testing WAV tone playback (Human Alert)...")
    player = SystemSoundPlayer(sound_dir="sounds", enabled=True)
    if player.is_available:
        success = player.play_category("human")
        print(f"  Playback request result: {'Dispatched successfully' if success else 'Failed'}")
        time.sleep(1.0)
    else:
        print("  SystemSoundPlayer is not available. Check that 'sounds/h.wav' exists and aplay/afplay is installed.")

    # Step 2: Spoken voice alert test
    print("\n[Step 2/2] Testing spoken voice announcement...")
    voice = VoiceAlertPlayer(
        enabled=True,
        cooldown_s=1.0,
        speech_rate=160,
        announcement_format="{label} detected",
    )

    if not voice.is_available:
        print("  [WARN] Offline TTS engine is not available.")
        print("  On macOS ensure /usr/bin/say exists; on Raspberry Pi install: sudo apt install espeak-ng && pip install pyttsx3")
        voice.close()
        return 1

    print(f"  Active TTS Backend: [{voice.backend_name}]")

    test_labels = ["person", "car"]
    for lbl in test_labels:
        print(f"  Speaking announcement: '{lbl} detected'...")
        voice.announce(lbl)
        time.sleep(2.5)

    voice.close()
    print("\nAudio verification completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
