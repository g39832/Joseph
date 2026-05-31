"""
voice/continuous_listener.py
-----------------------------
Continuous listening mode for JOSEPH.

After wake word detection, this module runs a background thread that
continuously monitors the microphone. Uses VAD (Voice Activity Detection)
to automatically detect when the user starts and stops speaking.

Flow:
  1. Wake word detected → start listening
  2. VAD detects speech → accumulate audio
  3. VAD detects silence → stop accumulation
  4. Transcribe accumulated audio → send to callback
  5. Return to listening for next utterance
  6. Stop listening after idle timeout

Falls back to push-to-talk style (single recording) if VAD is unavailable.
"""

import logging
import threading
import time
from typing import Callable, Optional

import numpy as np

from configs.settings import settings
from voice.audio_manager import AudioManager, CHUNK_DURATION
from voice.vad import VAD
from voice.streaming_stt import StreamingSTT

logger = logging.getLogger(__name__)

# Listening parameters
MAX_LISTEN_SECONDS = 30.0          # Maximum continuous listen time
SPEECH_TIMEOUT_SECONDS = 3.0       # Silence this long = end of utterance
PRE_SPEECH_PAD_SECONDS = 0.5       # Audio before speech detection to keep
MIN_UTTERANCE_SAMPLES = int(16000 * 0.3)  # Minimum utterance length
IDLE_TIMEOUT_SECONDS = 10.0        # No speech detected = stop listening


class ContinuousListener:
    """
    Continuously listens for user speech and auto-transcribes.

    After activation, runs a background thread that monitors the
    microphone with VAD. When speech starts, it accumulates audio
    until silence is detected, then transcribes and calls the callback.

    Usage:
        def on_transcribed(text: str):
            print(f"User said: {text}")

        listener = ContinuousListener(
            audio_manager=audio,
            on_transcribed=on_transcribed,
        )
        listener.start()
        # ... user speaks naturally ...
        listener.stop()
    """

    def __init__(
        self,
        audio_manager: AudioManager,
        on_transcribed: Optional[Callable[[str], None]] = None,
        on_listening_change: Optional[Callable[[bool], None]] = None,
        vad: Optional[VAD] = None,
        streaming_stt: Optional[StreamingSTT] = None,
    ):
        """
        Args:
            audio_manager: AudioManager instance for microphone access.
            on_transcribed: Called with transcribed text when user finishes speaking.
            on_listening_change: Called with True when listening starts,
                                False when it stops.
            vad: VAD instance. Created with defaults if not provided.
            streaming_stt: StreamingSTT for partial results. Not used if None.
        """
        self.audio_manager = audio_manager
        self.on_transcribed = on_transcribed
        self.on_listening_change = on_listening_change
        self._vad = vad or VAD()
        self._streaming_stt = streaming_stt
        self._running = False
        self._listening = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._audio_buffer: list[np.ndarray] = []
        self._speech_buffer: list[np.ndarray] = []

    def start(self) -> bool:
        """
        Start the continuous listener background thread.

        Returns:
            True if started successfully.
        """
        if self._running:
            return True

        if not self.audio_manager.is_streaming:
            if not self.audio_manager.start_stream():
                logger.error("Cannot start audio stream for continuous listening")
                return False

        self._running = True
        self._listening = False
        self._audio_buffer = []
        self._speech_buffer = []

        self._thread = threading.Thread(
            target=self._listener_loop,
            daemon=True,
            name="Continuous-Listener",
        )
        self._thread.start()
        logger.info("Continuous listener started")
        return True

    def stop(self) -> None:
        """Stop the continuous listener."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        self._set_listening(False)
        logger.info("Continuous listener stopped")

    def _listener_loop(self) -> None:
        """
        Main background thread: monitor microphone for speech.
        """
        logger.debug("Continuous listener loop started")
        speech_active = False
        silence_start = 0.0
        speech_start_time = 0.0
        last_activity_time = time.time()

        while self._running:
            try:
                chunk = self.audio_manager.read_chunk()
                if chunk is None:
                    time.sleep(0.01)
                    continue

                # Always keep a rolling buffer for pre-speech padding
                self._audio_buffer.append(chunk)
                max_pad_chunks = int(PRE_SPEECH_PAD_SECONDS / CHUNK_DURATION)
                while len(self._audio_buffer) > max_pad_chunks:
                    self._audio_buffer.pop(0)

                # Check for speech
                is_speech = self._vad.is_speech(chunk)

                if is_speech and not speech_active:
                    # Speech just started
                    speech_active = True
                    speech_start_time = time.time()
                    self._set_listening(True)

                    # Include pre-speech padding
                    self._speech_buffer = list(self._audio_buffer)
                    self._speech_buffer.append(chunk)

                    # Start streaming STT if available
                    if self._streaming_stt and self._streaming_stt.is_available:
                        self._streaming_stt.start()
                        for buffered_chunk in self._speech_buffer:
                            self._streaming_stt.feed_audio(buffered_chunk)

                    logger.debug("Speech started")

                elif is_speech and speech_active:
                    # Continuing speech
                    self._speech_buffer.append(chunk)
                    if self._streaming_stt and self._streaming_stt.is_streaming:
                        self._streaming_stt.feed_audio(chunk)

                elif not is_speech and speech_active:
                    # Potential silence — check if speech has ended
                    self._speech_buffer.append(chunk)
                    if self._streaming_stt and self._streaming_stt.is_streaming:
                        self._streaming_stt.feed_audio(chunk)

                    if silence_start == 0.0:
                        silence_start = time.time()
                    elif time.time() - silence_start >= SPEECH_TIMEOUT_SECONDS:
                        # Speech has ended — transcribe and process
                        self._process_utterance()
                        speech_active = False
                        silence_start = 0.0
                        self._speech_buffer = []
                        self._set_listening(False)

                elif not is_speech and not speech_active:
                    # Silence — check idle timeout
                    silence_start = 0.0
                    if self._listening:
                        now = time.time()
                        if now - last_activity_time >= IDLE_TIMEOUT_SECONDS:
                            logger.debug("Idle timeout — stopping listen")
                            self._set_listening(False)
                        last_activity_time = now

            except Exception as e:
                logger.error(f"Listener loop error: {e}")
                time.sleep(0.1)

    def _process_utterance(self) -> None:
        """
        Transcribe the accumulated speech buffer and call the callback.
        """
        if not self._speech_buffer:
            return

        # Concatenate all speech chunks
        audio = np.concatenate(self._speech_buffer)

        if len(audio) < MIN_UTTERANCE_SAMPLES:
            logger.debug("Utterance too short — discarding")
            return

        # Try streaming STT final result first
        text = None
        if self._streaming_stt and self._streaming_stt.is_streaming:
            text = self._streaming_stt.stop()

        # Fall back to direct transcription
        if not text:
            text = self._transcribe_audio(audio)

        if text and self.on_transcribed:
            try:
                self.on_transcribed(text)
            except Exception as e:
                logger.error(f"Transcribed callback error: {e}")

    def _transcribe_audio(self, audio: np.ndarray) -> Optional[str]:
        """
        Transcribe audio using the speech-to-text module.

        Uses the SpeechToText singleton for consistency.
        """
        try:
            from voice.speech_to_text import stt

            if not stt.is_available:
                logger.warning("STT not available for transcription")
                return None

            return stt.transcribe(audio)

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None

    def _set_listening(self, active: bool) -> None:
        """Update listening state and notify callback."""
        with self._lock:
            if self._listening != active:
                self._listening = active
                if self.on_listening_change:
                    try:
                        self.on_listening_change(active)
                    except Exception as e:
                        logger.debug(f"Listening change callback error: {e}")

    @property
    def is_listening(self) -> bool:
        return self._listening

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def vad(self) -> VAD:
        return self._vad

    def __repr__(self) -> str:
        return (
            f"ContinuousListener(running={self._running}, "
            f"listening={self._listening})"
        )
