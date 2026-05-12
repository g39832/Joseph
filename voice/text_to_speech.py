"""
voice/text_to_speech.py
------------------------
Text-to-speech engine for JOSEPH.

Priority order:
1. Kokoro TTS (neural, high quality) — if available
2. pyttsx3 (Windows SAPI) — fallback

Kokoro sounds dramatically better. Downloads ~80MB model
on first use, runs completely offline after that.
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
    Unified TTS — uses Kokoro (neural) or pyttsx3 (fallback).

    Usage:
        tts = TextToSpeech()
        tts.speak("Hello, I am Joseph.")
    """

    def __init__(self):
        self._engine = None
        self._available = False
        self._backend = "none"
        self._speak_queue: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()
        self._is_speaking = False
        self._thread: Optional[threading.Thread] = None
        self._initialize()

    def _initialize(self) -> None:
        """Try Kokoro first, fall back to pyttsx3."""
        if self._try_kokoro():
            return
        self._try_pyttsx3()

    def _try_kokoro(self) -> bool:
        """Attempt to initialize Kokoro neural TTS."""
        try:
            from voice.kokoro_tts import KokoroTTS
            kokoro = KokoroTTS()
            if kokoro.is_available:
                self._engine = kokoro
                self._available = True
                self._backend = "kokoro"
                logger.info("TTS: Using Kokoro neural voice")
                return True
        except Exception as e:
            logger.debug(f"Kokoro TTS unavailable: {e}")
        return False

    def _try_pyttsx3(self) -> None:
        """Initialize pyttsx3 as fallback."""
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 175)
            engine.setProperty("volume", 0.95)
            self._set_best_pyttsx3_voice(engine)
            self._pyttsx3_engine = engine

            self._thread = threading.Thread(
                target=self._pyttsx3_worker,
                daemon=True,
                name="pyttsx3-Worker",
            )
            self._thread.start()

            self._available = True
            self._backend = "pyttsx3"
            logger.info("TTS: Using pyttsx3 (Windows SAPI)")

        except Exception as e:
            logger.warning(f"pyttsx3 TTS failed: {e}. Voice output disabled.")

    def _set_best_pyttsx3_voice(self, engine) -> None:
        """Select the best available Windows voice."""
        try:
            voices = engine.getProperty("voices")
            if not voices:
                return
            preferred = ["david", "mark", "zira", "hazel"]
            for pref in preferred:
                for voice in voices:
                    if pref in voice.name.lower():
                        engine.setProperty("voice", voice.id)
                        logger.info(f"TTS voice selected: {voice.name}")
                        return
            engine.setProperty("voice", voices[0].id)
            logger.info(f"TTS voice (fallback): {voices[0].name}")
        except Exception as e:
            logger.warning(f"Voice selection failed: {e}")

    def _pyttsx3_worker(self) -> None:
        """Background thread for pyttsx3 speech."""
        while not self._stop_event.is_set():
            try:
                text = self._speak_queue.get(timeout=0.5)
                if text is None:
                    break
                self._is_speaking = True
                try:
                    self._pyttsx3_engine.say(text)
                    self._pyttsx3_engine.runAndWait()
                except Exception as e:
                    logger.error(f"pyttsx3 speak error: {e}")
                finally:
                    self._is_speaking = False
                    self._speak_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"TTS worker error: {e}")

    def speak(self, text: str, interrupt: bool = False) -> None:
        """Queue text to be spoken aloud."""
        if not self._available:
            return
        clean = self._clean_for_speech(text)
        if not clean:
            return
        if self._backend == "kokoro":
            self._engine.speak(clean, interrupt=interrupt)
        else:
            if interrupt:
                self.stop_speaking()
            self._speak_queue.put(clean)

    def speak_sync(self, text: str) -> None:
        """Speak and wait until finished."""
        if not self._available:
            return
        clean = self._clean_for_speech(text)
        if not clean:
            return
        if self._backend == "kokoro":
            self._engine.speak_sync(clean)
        else:
            self._speak_queue.put(clean)
            self._speak_queue.join()

    def stop_speaking(self) -> None:
        """Stop current speech and clear queue."""
        if not self._available:
            return
        if self._backend == "kokoro":
            self._engine.stop_speaking()
        else:
            while not self._speak_queue.empty():
                try:
                    self._speak_queue.get_nowait()
                    self._speak_queue.task_done()
                except queue.Empty:
                    break
            try:
                self._pyttsx3_engine.stop()
            except Exception:
                pass
        self._is_speaking = False

    def set_rate(self, rate: int) -> None:
        """Set speaking rate (words per minute)."""
        if self._backend == "pyttsx3" and hasattr(self, "_pyttsx3_engine"):
            self._pyttsx3_engine.setProperty("rate", rate)

    def set_volume(self, volume: float) -> None:
        """Set volume (0.0 to 1.0)."""
        if self._backend == "pyttsx3" and hasattr(self, "_pyttsx3_engine"):
            self._pyttsx3_engine.setProperty("volume", max(0.0, min(1.0, volume)))

    def _clean_for_speech(self, text: str) -> str:
        """Clean text for natural speech."""
        if not text:
            return ""
        text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)
        text = re.sub(r'_{1,3}(.*?)_{1,3}', r'\1', text)
        text = re.sub(r'`{1,3}.*?`{1,3}', '', text, flags=re.DOTALL)
        text = re.sub(r'https?://\S+', 'a link', text)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*[-*•]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'[^\x00-\x7F]+', '', text)
        text = re.sub(r'\n+', '. ', text)
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[#@$%^&*\[\]{}|\\<>]', '', text)
        return text.strip()

    @property
    def is_speaking(self) -> bool:
        if self._backend == "kokoro" and self._engine:
            return self._engine.is_speaking
        return self._is_speaking

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def backend(self) -> str:
        return self._backend

    def stop(self) -> None:
        """Shut down TTS engine cleanly."""
        if self._backend == "kokoro" and self._engine:
            self._engine.stop()
        else:
            self._stop_event.set()
            self._speak_queue.put(None)
            if self._thread:
                self._thread.join(timeout=2)
        logger.info("TTS engine stopped")

    def __repr__(self) -> str:
        return f"TextToSpeech(backend={self._backend}, available={self._available})"


# Module-level singleton
tts = TextToSpeech()
