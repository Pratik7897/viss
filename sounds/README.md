# VISS Alert Sounds

This directory contains lightweight, deterministic PCM audio tones used for auditory proximity and category alerts:

| File | Alert Category | Target Classes | Tone Specification |
| :--- | :--- | :--- | :--- |
| `a.wav` | `animal` | `dog`, `cat` | 880 Hz (A5), 0.25 s, 16 kHz 16-bit Mono PCM |
| `h.wav` | `human` | `person`, `car` | 440 Hz (A4), 0.25 s, 16 kHz 16-bit Mono PCM |

## Generation & Licensing
These tones are synthetically generated via Python standard library (`wave`, `struct`, `math`) without external assets or dependencies:
```bash
python3 scripts/generate_alert_tones.py
```

## Runtime Safety
- Sound alerts are completely **opt-in** (`--sound` CLI flag or `VISS_ENABLE_SOUND=true`).
- Playback occurs in background worker threads with a 5-second process timeout, ensuring audio never blocks proximity distance ranging.
- If sound files are absent or unreadable, `SystemSoundPlayer` logs a warning and returns `False` safely without crashing.
