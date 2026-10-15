"""Voice announcement player for the Visual Impairment Support System (VISS).

Converts detected object labels into spoken announcements played through the
configured audio output (wired or Bluetooth earphones, or built-in speakers).

Architecture:
- A background worker thread reads from a bounded queue and dispatches to the TTS engine.
- Per-label cooldowns prevent repeated announcements of the same continuously visible object.
- Offline TTS implementations:
    * macOS: Uses built-in `/usr/bin/say` (native, zero-dependency, non-blocking via worker queue).
      Falls back to pyttsx3 if preferred.
    * Linux / Raspberry Pi OS: Uses pyttsx3 (delegates to espeak-ng) or direct `espeak-ng`.
- Audio playback does NOT block the camera/inference loop.
"""

import os
import platform
import queue
import shutil
import subprocess
import threading
import time
from typing import Dict, List, Optional

from core.logger import setup_logger

# Natural spoken translations for technical or concatenated taxonomy labels
FRIENDLY_SPEECH_LABELS: Dict[str, str] = {
    "diningtable": "table",
    "tvmonitor": "screen or monitor",
    "pottedplant": "potted plant",
    "sofa": "couch",
    "motorbike": "motorcycle",
    "aeroplane": "airplane",
    "cell phone": "mobile phone",
}


class VoiceAlertPlayer:
    """Announces detected objects as spoken text through earphones.

    Thread-safe: announce() can be called from any thread (e.g. the vision worker).
    """

    def __init__(
        self,
        enabled: bool = True,
        cooldown_s: float = 3.0,
        max_queue_size: int = 5,
        speech_rate: int = 160,
        volume: float = 1.0,
        announcement_format: str = "{label} detected",
        logger_name: str = "viss.voice_alert",
    ):
        self._enabled = enabled
        self._cooldown_s = cooldown_s
        self._announcement_format = announcement_format
        self._speech_rate = speech_rate
        self._volume = max(0.0, min(1.0, volume))
        self._logger = setup_logger(logger_name)

        # Per-label cooldown tracking: label -> last_announced_timestamp
        self._last_announced: Dict[str, float] = {}
        self._cooldown_lock = threading.Lock()

        # Bounded announcement queue
        self._queue: queue.Queue = queue.Queue(maxsize=max(1, max_queue_size))

        # TTS availability & backend ("say", "pyttsx3", "espeak", or None)
        self._tts_backend: Optional[str] = None
        self._tts_available: bool = False
        self._tts_engine = None  # Used if backend == "pyttsx3"
        self._ready_event = threading.Event()

        # Worker thread
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._is_closed: bool = False

        # Diagnostic counters
        self._announcements_made: int = 0
        self._announcements_dropped: int = 0
        self._announcements_deduplicated: int = 0

        if self._enabled:
            self._start_worker()
        else:
            self._ready_event.set()
            self._logger.info("VoiceAlertPlayer is disabled.")

    @property
    def is_available(self) -> bool:
        """True if TTS engine is available and player is active."""
        if not self._enabled or self._is_closed:
            return False
        # Wait briefly for worker initialization to finish
        self._ready_event.wait(timeout=1.5)
        return self._tts_available and not self._is_closed

    @property
    def backend_name(self) -> Optional[str]:
        """Returns the active speech synthesis backend name."""
        return self._tts_backend

    @property
    def announcements_made(self) -> int:
        return self._announcements_made

    @property
    def announcements_dropped(self) -> int:
        return self._announcements_dropped

    @property
    def announcements_deduplicated(self) -> int:
        return self._announcements_deduplicated

    def _start_worker(self) -> None:
        """Spawns the background TTS worker thread."""
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="viss-voice-worker",
            daemon=True,
        )
        self._worker_thread.start()

    def _init_tts(self) -> bool:
        """Initializes the TTS backend (must be called from the worker thread)."""
        system = platform.system()

        # 1. On macOS (Darwin), built-in /usr/bin/say is the most robust, non-blocking offline solution
        if system == "Darwin" and (os.path.exists("/usr/bin/say") or shutil.which("say")):
            self._tts_backend = "say"
            self._tts_available = True
            self._logger.info("Voice alert backend initialized using macOS native '/usr/bin/say' (rate=%d wpm).", self._speech_rate)
            return True

        # 2. Try pyttsx3 (standard across Linux / RPi OS)
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", self._speech_rate)
            engine.setProperty("volume", self._volume)
            self._tts_engine = engine
            self._tts_backend = "pyttsx3"
            self._tts_available = True
            self._logger.info("Voice alert backend initialized using pyttsx3 (rate=%d, volume=%.1f).", self._speech_rate, self._volume)
            return True
        except Exception as e:
            self._logger.debug("pyttsx3 initialization failed (%s); trying fallback CLI...", e)

        # 3. Direct espeak-ng fallback on Linux
        if shutil.which("espeak-ng") or shutil.which("espeak"):
            self._tts_backend = "espeak"
            self._tts_available = True
            self._logger.info("Voice alert backend initialized using system 'espeak-ng'.")
            return True

        # No backend found
        self._tts_backend = None
        self._tts_available = False
        self._logger.warning(
            "No offline TTS synthesizer found. On macOS ensure /usr/bin/say is present; "
            "on Raspberry Pi OS install: sudo apt install espeak-ng && pip install pyttsx3"
        )
        return False

    def _worker_loop(self) -> None:
        """Background thread: dequeues announcements and speaks them via TTS."""
        try:
            self._init_tts()
        finally:
            self._ready_event.set()

        if not self._tts_available:
            # Drain queue silently if TTS is unavailable
            while not self._stop_event.is_set():
                try:
                    self._queue.get(timeout=0.5)
                    self._queue.task_done()
                except queue.Empty:
                    continue
            return

        while not self._stop_event.is_set():
            try:
                text = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if text is None:
                # Sentinel value signals shutdown
                self._queue.task_done()
                break

            try:
                self._speak_text(text)
                self._announcements_made += 1
                self._logger.debug("Voice announced: '%s'", text)
            except Exception as e:
                self._logger.error("TTS playback error for '%s': %s", text, e)
            finally:
                self._queue.task_done()

        # Cleanup TTS engine
        try:
            if self._tts_engine is not None:
                self._tts_engine.stop()
        except Exception:
            pass

    def _speak_text(self, text: str) -> None:
        """Dispatches text to the active offline speech synthesizer."""
        if self._tts_backend == "say":
            # macOS native say command with speech rate flag (-r <words_per_minute>)
            subprocess.run(
                ["/usr/bin/say", "-r", str(self._speech_rate), text],
                check=False,
                capture_output=True,
            )
        elif self._tts_backend == "pyttsx3" and self._tts_engine is not None:
            self._tts_engine.say(text)
            self._tts_engine.runAndWait()
        elif self._tts_backend == "espeak":
            cmd = "espeak-ng" if shutil.which("espeak-ng") else "espeak"
            subprocess.run(
                [cmd, "-s", str(self._speech_rate), text],
                check=False,
                capture_output=True,
            )

    def announce(self, label: str) -> bool:
        """Queues a spoken announcement for the given detection label.

        Applies per-label cooldown deduplication and drops if queue is full.

        Args:
            label: The detected object label (e.g. 'person', 'car').

        Returns:
            True if the announcement was queued; False if deduplicated,
            dropped, or player is unavailable.
        """
        if self._is_closed or not self._enabled:
            return False

        if not label or not label.strip():
            return False

        # Per-label cooldown check
        now = time.time()
        with self._cooldown_lock:
            last_ts = self._last_announced.get(label, 0.0)
            if (now - last_ts) < self._cooldown_s:
                self._announcements_deduplicated += 1
                return False
            self._last_announced[label] = now

        # Format announcement text with friendly spoken translations
        spoken_label = FRIENDLY_SPEECH_LABELS.get(label.lower(), label)
        text = self._announcement_format.format(label=spoken_label.capitalize())

        # Non-blocking queue put
        try:
            self._queue.put_nowait(text)
            self._logger.debug("Queued voice announcement: '%s'", text)
            return True
        except queue.Full:
            self._announcements_dropped += 1
            self._logger.warning(
                "Voice queue full (%d items); dropped announcement: '%s'",
                self._queue.maxsize,
                text,
            )
            return False

    def close(self) -> None:
        """Stops the worker thread and releases TTS resources."""
        if self._is_closed:
            return

        self._is_closed = True
        self._stop_event.set()

        # Send sentinel to unblock worker
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass

        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=3.0)

        self._logger.info(
            "VoiceAlertPlayer closed. Announcements: %d made, %d deduplicated, %d dropped.",
            self._announcements_made,
            self._announcements_deduplicated,
            self._announcements_dropped,
        )


class MockVoiceAlertPlayer:
    """In-memory mock for unit testing without real TTS engine."""

    def __init__(self, logger_name: str = "viss.mock_voice"):
        self._logger = setup_logger(logger_name)
        self._announced: List[Dict] = []
        self._is_closed: bool = False
        self._simulate_failure: bool = False

    @property
    def is_available(self) -> bool:
        return not self._is_closed and not self._simulate_failure

    @property
    def backend_name(self) -> Optional[str]:
        return "mock"

    @property
    def announced(self) -> List[Dict]:
        return list(self._announced)

    @property
    def announcements_made(self) -> int:
        return len(self._announced)

    @property
    def announcements_dropped(self) -> int:
        return 0

    @property
    def announcements_deduplicated(self) -> int:
        return 0

    def set_simulate_failure(self, fail: bool) -> None:
        self._simulate_failure = fail

    def announce(self, label: str) -> bool:
        if self._is_closed or self._simulate_failure:
            return False
        record = {"label": label, "text": f"{label.capitalize()} detected", "timestamp": time.time()}
        self._announced.append(record)
        self._logger.debug("MockVoiceAlertPlayer: announced '%s'", label)
        return True

    def clear(self) -> None:
        self._announced.clear()

    def close(self) -> None:
        self._is_closed = True
