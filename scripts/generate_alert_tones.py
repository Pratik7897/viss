"""Generates deterministic, synthetic WAV alert tones using Python standard library only.

No external packages or audio libraries required. Produces:
- 'sounds/a.wav': High alert tone (880 Hz, 0.25s) for animal entity warnings ('dog', 'cat')
- 'sounds/h.wav': Mid alert tone (440 Hz, 0.25s) for human/obstacle warnings ('person', 'car')
"""

import math
import os
import struct
import wave


def generate_sine_wave(
    filepath: str,
    frequency_hz: float = 440.0,
    duration_s: float = 0.25,
    sample_rate: int = 16000,
    volume: float = 0.5,
) -> str:
    """Generates a clean PCM WAV audio tone with a smooth windowed envelope.

    Args:
        filepath: Target output file path.
        frequency_hz: Tone frequency in Hertz.
        duration_s: Tone duration in seconds.
        sample_rate: Samples per second (default 16 kHz).
        volume: Peak amplitude factor (0.0 to 1.0).

    Returns:
        Absolute path to the created WAV file.
    """
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    num_samples = int(sample_rate * duration_s)

    with wave.open(filepath, "w") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit signed PCM
        wav_file.setframerate(sample_rate)

        frames = bytearray()
        for i in range(num_samples):
            # Half-sine envelope smoothly tapers volume at onset and cutoff
            envelope = math.sin(math.pi * i / num_samples)
            t = i / sample_rate
            sample_val = int(32767.0 * volume * envelope * math.sin(2.0 * math.pi * frequency_hz * t))
            # Clamp to 16-bit signed range
            sample_val = max(-32768, min(32767, sample_val))
            frames.extend(struct.pack("<h", sample_val))

        wav_file.writeframes(frames)

    return filepath


def create_default_alert_sounds(target_dir: str = "sounds") -> None:
    """Generates the standard alert sound files (a.wav and h.wav)."""
    os.makedirs(target_dir, exist_ok=True)

    # 1. Animal warning: 880 Hz (A5) - higher alert pitch
    animal_path = os.path.join(target_dir, "a.wav")
    generate_sine_wave(animal_path, frequency_hz=880.0, duration_s=0.25, volume=0.4)

    # 2. Human / vehicle warning: 440 Hz (A4) - mid alert pitch
    human_path = os.path.join(target_dir, "h.wav")
    generate_sine_wave(human_path, frequency_hz=440.0, duration_s=0.25, volume=0.4)


if __name__ == "__main__":
    sounds_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sounds")
    create_default_alert_sounds(sounds_dir)
    print(f"Alert sounds generated in {sounds_dir}: a.wav, h.wav")
