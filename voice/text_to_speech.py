"""
voice/text_to_speech.py
------------------------
Text-to-speech engine for JOSEPH.

Phase 2 uses pyttsx3 — Windows built-in voices, zero latency,
works completely offline with no model downloads.

Architecture is designed so swapping to Coqui TTS later
only requires changing the engine class, not any calling code.

The TTS engine runs on a dedicated background thread because
pyttsx3 blocks while speaking. This keeps the UI responsive.
"""

import logging
import queue
import re
import threading
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)


class TextToSpeech:
    """
    Text-to-speech using pyttsx3 (Windows SAPI voices).

    Runs on a background thread so speaking never blocks
    the main thread or UI.

    Usage:
        tts = TextToSpeech()
        tts.speak("Hello, I'm Joseph.")
        tts.speak("Opening YouTube now.")
    """

    def __init__(self):
        self._engine = None
        self._available = False
        self._speak_queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._is_speaking = False
        self._initialize()

    def _initialize(self) -> None:
        """Initialize pyttsx3 engine on a dedicated thread."""
        try:
            import pyttsx3

            # pyttsx3 must be initialized on the thread that uses it
            self._engine = pyttsx3.init()

            # Configure voice properties
            self._engine.setProperty("rate", 175)    # Words per minute (175 = natural)
            self._engine.setProperty("volume", 0.95) # 0.0 to 1.0

            # Try to find a good Windows voice
            self._set_best_voice()

            self._available = True
            logger.info("TextToSpeech initialized (pyttsx3)")

            # Start the background speaking thread
            self._thread = threading.Thread(
                target=self._speak_worker,
                daemon=True,
                name="TTS-Worker",
            )
            self._thread.start()

        except Exception as e:
            logger.warning(f"TTS initialization failed: {e}. Voice output disabled.")
            self._available = False

    def _set_best_voice(self) -> None:
        """
        Select the best available Windows voice.
        Prefers David (male) or Zira (female) — the clearest built-in voices.
        """
        try:
            voices = self._engine.getProperty("voices")
            if not voices:
                return

            # Log available voices
            for v in voices:
                logger.debug(f"Available voice: {v.name} ({v.id})")

            # Preference order
            preferred = ["david", "mark", "zira", "hazel"]
            for pref in preferred:
                for voice in voices:
                    if pref in voice.name.lower():
                        self._engine.setProperty("voice", voice.id)
                        logger.info(f"TTS voice selected: {voice.name}")
                        return

            # Fall back to first available voice
            self._engine.setProperty("voice", voices[0].id)
            logger.info(f"TTS voice (fallback): {voices[0].name}")

        except Exception as e:
            logger.warning(f"Voice selection failed: {e}")

    def _speak_worker(self) -> None:
        """
        Background thread that processes the speak queue.
        Runs continuously until stop() is called.
        """
        while not self._stop_event.is_set():
            try:
                text = self._speak_queue.get(timeout=0.5)
                if text is None:  # Poison pill — stop signal
                    break

                self._is_speaking = True
                logger.debug(f"TTS speaking: {text[:60]}...")

                try:
                    self._engine.say(text)
                    self._engine.runAndWait()
                except Exception as e:
                    logger.error(f"TTS speak error: {e}")
                finally:
                    self._is_speaking = False
                    self._speak_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"TTS worker error: {e}")

    def speak(self, text: str, interrupt: bool = False) -> None:
        """
        Queue text to be spoken aloud.

        Args:
            text: The text to speak.
            interrupt: If True, clear the queue before adding this text.
                       Use for urgent responses that should cut off current speech.
        """
        if not self._available:
            logger.debug(f"TTS unavailable, skipping: {text[:40]}")
            return

        # Clean the text before speaking
        clean = self._clean_for_speech(text)
        if not clean:
            return

        if interrupt:
            self.stop_speaking()

        self._speak_queue.put(clean)
        logger.debug(f"TTS queued: {clean[:60]}")

    def speak_sync(self, text: str) -> None:
        """
        Speak text and WAIT until finished.
        Use for short confirmations where you need to wait.
        """
        if not self._available:
            return

        clean = self._clean_for_speech(text)
        if not clean:
            return

        self._speak_queue.put(clean)
        self._speak_queue.join()  # Wait for queue to empty

    def stop_speaking(self) -> None:
        """Stop current speech and clear the queue."""
        if not self._available:
            return

        # Clear the queue
        while not self._speak_queue.empty():
            try:
                self._speak_queue.get_nowait()
                self._speak_queue.task_done()
            except queue.Empty:
                break

        # Stop current speech
        try:
            self._engine.stop()
        except Exception:
            pass

        self._is_speaking = False

    def set_rate(self, rate: int) -> None:
        """
        Set speaking rate.
        Args:
            rate: Words per minute. 150=slow, 175=normal, 200=fast
        """
        if self._engine:
            self._engine.setProperty("rate", rate)

    def set_volume(self, volume: float) -> None:
        """
        Set volume.
        Args:
            volume: 0.0 to 1.0
        """
        if self._engine:
            self._engine.setProperty("volume", max(0.0, min(1.0, volume)))

    def _clean_for_speech(self, text: str) -> str:
        """
        Clean text so it sounds natural when spoken.

        Removes:
        - Markdown formatting (*bold*, _italic_, `code`)
        - URLs
        - Excessive punctuation
        - Emoji
        - Special characters that sound weird spoken aloud
        """
        if not text:
            return ""

        # Remove markdown bold/italic
        text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)
        text = re.sub(r'_{1,3}(.*?)_{1,3}', r'\1', text)

        # Remove inline code
        text = re.sub(r'`{1,3}.*?`{1,3}', '', text, flags=re.DOTALL)

        # Remove URLs
        text = re.sub(r'https?://\S+', 'a link', text)

        # Remove markdown headers
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

        # Remove bullet points (replace with pause)
        text = re.sub(r'^\s*[-*•]\s+', '', text, flags=re.MULTILINE)

        # Remove emoji (basic range)
        text = re.sub(r'[^\x00-\x7F]+', '', text)

        # Remove multiple spaces/newlines
        text = re.sub(r'\n+', '. ', text)
        text = re.sub(r'\s+', ' ', text)

        # Remove special chars that sound bad
        text = re.sub(r'[#@$%^&*\[\]{}|\\<>]', '', text)

        return text.strip()

    @property
    def is_speaking(self) -> bool:
        """True if currently speaking."""
        return self._is_speaking

    @property
    def is_available(self) -> bool:
        """True if TTS is ready to use."""
        return self._available

    def stop(self) -> None:
        """Shut down the TTS engine cleanly."""
        self._stop_event.set()
        self._speak_queue.put(None)  # Poison pill
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("TTS engine stopped")

    def __repr__(self) -> str:
        return f"TextToSpeech(available={self._available}, speaking={self._is_speaking})"


# Module-level singleton
tts = TextToSpeech()
