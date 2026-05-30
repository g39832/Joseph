"""
voice/voice_controller.py
--------------------------
Master voice controller for JOSEPH.

Coordinates the full voice pipeline:
  1. WakeWordDetector listens continuously
  2. "Joseph" detected → TTS says "Yes?"
  3. AudioManager records user speech
  4. SpeechToText transcribes it
  5. Text sent to LLM (via callback)
  6. LLM response spoken by TTS

Also supports push-to-talk mode (no wake word needed).

This is the ONLY voice module the rest of the app imports.
"""

import logging
import threading
import time
from enum import Enum
from typing import Callable, Optional

from configs.settings import settings
from voice.audio_manager import AudioManager
from voice.text_to_speech import TextToSpeech
from voice.speech_to_text import SpeechToText
from voice.wake_word import WakeWordDetector

logger = logging.getLogger(__name__)


class VoiceState(Enum):
    """Current state of the voice system."""
    IDLE = "idle"               # Waiting for wake word
    WAKE_DETECTED = "wake"      # Wake word just detected
    LISTENING = "listening"     # Recording user speech
    PROCESSING = "processing"   # Transcribing / sending to LLM
    SPEAKING = "speaking"       # Joseph is speaking
    DISABLED = "disabled"       # Voice system off


class VoiceController:
    """
    Orchestrates the complete voice interaction pipeline.

    Usage:
        def handle_text(text: str) -> str:
            # Send to LLM, return response
            return llm.chat(text)

        voice = VoiceController(on_text_callback=handle_text)
        voice.start()
        # Now say "Joseph" and start talking
    """

    def __init__(
        self,
        on_text_callback: Optional[Callable[[str], str]] = None,
        on_state_change: Optional[Callable[[VoiceState], None]] = None,
    ):
        """
        Args:
            on_text_callback: Called with transcribed text.
                              Should return Joseph's response string.
            on_state_change: Called whenever voice state changes.
                             Useful for updating UI indicators.
        """
        self.on_text_callback = on_text_callback
        self.on_state_change = on_state_change

        self._state = VoiceState.DISABLED
        self._lock = threading.Lock()

        # Initialize components
        self.audio = AudioManager()
        self.tts = TextToSpeech()
        from voice.speech_to_text import stt as _stt_singleton
        self.stt = _stt_singleton
        self.wake_detector = WakeWordDetector(
            audio_manager=self.audio,
            on_wake_callback=self._on_wake_word,
        )

        logger.info(
            f"VoiceController initialized\n"
            f"  TTS: {self.tts.is_available}\n"
            f"  STT: {self.stt.is_available}\n"
            f"  Wake word: {self.wake_detector.is_available}\n"
            f"  Microphone: {self.audio.is_available}"
        )

    def start(self, push_to_talk: bool = False) -> bool:
        """
        Start the voice system.

        Args:
            push_to_talk: If True, skip wake word and use manual trigger.
                          If False, listen continuously for "Joseph".

        Returns:
            True if started successfully.
        """
        if not self.audio.is_available:
            logger.error("No microphone available — voice system cannot start")
            return False

        if not self.audio.start_stream():
            logger.error("Failed to start audio stream")
            return False

        if push_to_talk:
            self._set_state(VoiceState.IDLE)
            logger.info("Voice system started in push-to-talk mode")
        else:
            if self.wake_detector.is_available:
                self.wake_detector.start()
                self._set_state(VoiceState.IDLE)
                logger.info(
                    f"Voice system started — say '{settings.WAKE_WORD}' to activate"
                )
            else:
                # Wake word unavailable — fall back to push-to-talk
                logger.warning(
                    "Wake word unavailable, falling back to push-to-talk"
                )
                self._set_state(VoiceState.IDLE)

        return True

    def stop(self) -> None:
        """Stop all voice components cleanly."""
        self.wake_detector.stop()
        self.audio.stop_stream()
        self.tts.stop()
        self._set_state(VoiceState.DISABLED)
        logger.info("Voice system stopped")

    def push_to_talk(self) -> None:
        """
        Manually trigger listening (push-to-talk mode).
        Call this when the user presses a button or hotkey.
        """
        if self._state not in (VoiceState.IDLE, VoiceState.DISABLED):
            logger.debug(f"Push-to-talk ignored — state is {self._state}")
            return

        logger.info("Push-to-talk triggered")
        self._start_listening()

    def speak(self, text: str, interrupt: bool = False) -> None:
        """
        Speak text aloud.

        Args:
            text: Text to speak.
            interrupt: Stop current speech first.
        """
        if not text:
            return

        self._set_state(VoiceState.SPEAKING)
        self.tts.speak(text, interrupt=interrupt)

        # Return to idle after speaking
        # (TTS is async, so we set a timer to reset state)
        words = len(text.split())
        estimated_duration = max(1.0, words / 2.5)  # ~150 wpm
        threading.Timer(estimated_duration, self._return_to_idle).start()

    def _on_wake_word(self) -> None:
        """Called by WakeWordDetector when wake word is detected."""
        if self._state != VoiceState.IDLE:
            logger.debug(f"Wake word ignored — state is {self._state}")
            return

        logger.info("Wake word detected — activating")
        self._set_state(VoiceState.WAKE_DETECTED)

        # Respond to wake word
        from brain.personality import PersonalityEngine
        pe = PersonalityEngine()
        wake_response = pe.get_wake_response()
        self.tts.speak(wake_response)

        # Brief pause then start listening
        time.sleep(0.6)
        self._start_listening()

    def _start_listening(self) -> None:
        """Start recording user speech."""
        self._set_state(VoiceState.LISTENING)
        # Flush stale audio, then wait briefly so user has time to start speaking
        self.audio.flush_buffer()
        time.sleep(0.4)  # 400ms grace period before recording starts

        thread = threading.Thread(
            target=self._record_and_process,
            daemon=True,
            name="Voice-Record",
        )
        thread.start()

    def _record_and_process(self) -> None:
        """
        Background thread: record speech, transcribe, get response.
        """
        try:
            logger.info("Recording user speech — speak now...")

            audio = self.audio.record_until_silence(
                max_seconds=15.0,
                silence_duration=1.8,
            )

            if audio is None:
                logger.info("No speech detected in recording")
                self._return_to_idle()
                return

            duration = len(audio) / 16000
            logger.info(f"Recorded {duration:.1f}s of audio — transcribing...")

            self._set_state(VoiceState.PROCESSING)
            text = self.stt.transcribe(audio)

            if not text:
                logger.info("Transcription returned empty — nothing understood")
                self._return_to_idle()
                return

            logger.info(f"Transcribed: '{text}'")

            # Check for interrupt commands FIRST
            if self._is_interrupt_command(text):
                logger.info("Interrupt command detected — stopping speech")
                self.tts.stop_speaking()
                self._return_to_idle()
                return

            # Send to callback (LLM)
            if self.on_text_callback:
                try:
                    response = self.on_text_callback(text)
                    if response:
                        self.speak(response)
                except Exception as e:
                    logger.error(f"Text callback error: {e}")
                    self.tts.speak("Sorry, something went wrong.")

            self._return_to_idle()

        except Exception as e:
            logger.error(f"Record and process error: {e}")
            self._return_to_idle()

    def _is_interrupt_command(self, text: str) -> bool:
        """Check if the transcribed text is an interrupt/stop command."""
        interrupt_phrases = {
            "stop", "stop it", "shut up", "quiet", "silence",
            "enough", "cancel", "nevermind", "never mind",
            "be quiet", "stop talking", "that's enough",
        }
        return text.lower().strip().rstrip(".,!") in interrupt_phrases

    def _return_to_idle(self) -> None:
        """Return to idle state (listening for wake word)."""
        if self._state != VoiceState.DISABLED:
            self._set_state(VoiceState.IDLE)

    def _set_state(self, new_state: VoiceState) -> None:
        """Update voice state and notify callback."""
        with self._lock:
            if self._state != new_state:
                logger.debug(f"Voice state: {self._state.value} → {new_state.value}")
                self._state = new_state
                if self.on_state_change:
                    try:
                        self.on_state_change(new_state)
                    except Exception as e:
                        logger.debug(f"State change callback error: {e}")

    @property
    def state(self) -> VoiceState:
        return self._state

    @property
    def is_ready(self) -> bool:
        """True if voice system is initialized and ready."""
        return (
            self.audio.is_available
            and self.tts.is_available
            and self.stt.is_available
        )

    def get_status(self) -> dict:
        """Return status of all voice components."""
        return {
            "state": self._state.value,
            "microphone": self.audio.is_available,
            "tts": self.tts.is_available,
            "stt": self.stt.is_available,
            "wake_word": self.wake_detector.is_available,
            "streaming": self.audio.is_streaming,
        }

    def __repr__(self) -> str:
        return (
            f"VoiceController(state={self._state.value}, "
            f"ready={self.is_ready})"
        )
