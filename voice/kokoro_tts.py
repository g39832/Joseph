"""
voice/kokoro_tts.py
--------------------
Neural TTS using Kokoro-ONNX — Phase 9.

Kokoro is a high-quality, fast, local neural TTS engine.
Sounds dramatically better than Windows SAPI voices.
Runs completely offline, no API keys needed.

Voice options (American English):
  af_heart   — warm female voice (recommended)
  af_bella   — clear female voice
  am_adam    — natural male voice
  am_michael — deeper male voice

Model downloads automatically on first use (~80MB).
"""

import logging
import queue
import threading
import time
from typing import Optional

import numpy as np

from configs.settings import settings

logger = logging.getLogger(__name__)

# Default voice — change to preference
DEFAULT_VOICE = "am_adam"   # Natural male voice for Joseph
SAMPLE_RATE = 24000          # Kokoro outputs at 24kHz


class KokoroTTS:
    """
    Neural text-to-speech using Kokoro-ONNX.

    Dramatically better quality than Windows SAPI.
    Runs locally, no internet needed after first model download.

    Usage:
        tts = KokoroTTS()
        tts.speak("Hello, I am Joseph.")
    """

    def __init__(self, voice: str = DEFAULT_VOICE):
        self.voice = voice
        self._kokoro = None
        self._available = False
        self._speak_queue: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()
        self._is_speaking = False
        self._thread: Optional[threading.Thread] = None
        self._initialize()

    def _initialize(self) -> None:
        """Initialize Kokoro model."""
        try:
            from kokoro_onnx import Kokoro

            logger.info("Loading Kokoro TTS model (first run downloads ~80MB)...")
            start = time.time()
            self._kokoro = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
            elapsed = time.time() - start
            self._available = True
            logger.info(f"Kokoro TTS ready in {elapsed:.1f}s — voice: {self.voice}")

            # Start background speaking thread
            self._thread = threading.Thread(
                target=self._speak_worker,
                daemon=True,
                name="KokoroTTS-Worker",
            )
            self._thread.start()

        except Exception as e:
            logger.warning(f"Kokoro TTS failed: {e}. Falling back to pyttsx3.")
            self._available = False

    def _speak_worker(self) -> None:
        """Background thread that processes the speak queue."""
        while not self._stop_event.is_set():
            try:
                text = self._speak_queue.get(timeout=0.5)
                if text is None:
                    break

                self._is_speaking = True
                self._synthesize_and_play(text)
                self._is_speaking = False
                self._speak_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Kokoro speak error: {e}")
                self._is_speaking = False

    def _synthesize_and_play(self, text: str) -> None:
        """Synthesize text and play audio."""
        try:
            import sounddevice as sd

            # Generate audio
            samples, sample_rate = self._kokoro.create(
                text,
                voice=self.voice,
                speed=1.0,
                lang="en-us",
            )

            # Play audio
            sd.play(samples, sample_rate)
            sd.wait()

        except Exception as e:
            logger.error(f"Kokoro synthesis error: {e}")

    def speak(self, text: str, interrupt: bool = False) -> None:
        """Queue text for speaking."""
        if not self._available:
            return

        clean = self._clean_text(text)
        if not clean:
            return

        if interrupt:
            self.stop_speaking()

        self._speak_queue.put(clean)

    def speak_sync(self, text: str) -> None:
        """Speak and wait until done."""
        if not self._available:
            return
        clean = self._clean_text(text)
        if not clean:
            return
        self._speak_queue.put(clean)
        self._speak_queue.join()

    def stop_speaking(self) -> None:
        """Stop current speech and clear queue."""
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass

        while not self._speak_queue.empty():
            try:
                self._speak_queue.get_nowait()
                self._speak_queue.task_done()
            except queue.Empty:
                break

        self._is_speaking = False

    def set_voice(self, voice: str) -> None:
        """Change the voice."""
        self.voice = voice
        logger.info(f"Kokoro voice changed to: {voice}")

    def list_voices(self) -> list[str]:
        """Return available voice names."""
        return [
            "af_heart",    # Warm female
            "af_bella",    # Clear female
            "af_nicole",   # Soft female
            "af_sarah",    # Bright female
            "am_adam",     # Natural male
            "am_michael",  # Deep male
            "bf_emma",     # British female
            "bm_george",   # British male
        ]

    def _clean_text(self, text: str) -> str:
        """Clean text for TTS."""
        import re
        text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)
        text = re.sub(r'`{1,3}.*?`{1,3}', '', text, flags=re.DOTALL)
        text = re.sub(r'https?://\S+', 'a link', text)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'[^\x00-\x7F]+', '', text)
        text = re.sub(r'\n+', '. ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def stop(self) -> None:
        """Shut down TTS engine."""
        self._stop_event.set()
        self._speak_queue.put(None)
        if self._thread:
            self._thread.join(timeout=2)

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    def __repr__(self) -> str:
        return f"KokoroTTS(voice={self.voice}, available={self._available})"
