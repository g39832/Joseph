"""
voice/wake_word.py
-------------------
Wake word detection for JOSEPH.

Listens continuously for the word "Joseph" using openWakeWord.
When detected, triggers the speech-to-text pipeline.

openWakeWord runs locally, uses very little CPU, and works
in the background without interrupting anything else.

Detection flow:
  Microphone → openWakeWord → "joseph" detected → callback()
  → AudioManager records speech → SpeechToText transcribes
  → Text sent to LLM → Response spoken by TTS
"""

import logging
import threading
import time
from typing import Callable, Optional

import numpy as np

from configs.settings import settings
from voice.audio_manager import AudioManager, CHUNK_SAMPLES, SAMPLE_RATE

logger = logging.getLogger(__name__)

# openWakeWord processes 80ms chunks at 16kHz
OWW_CHUNK_SIZE = 1280  # 80ms at 16kHz
DETECTION_THRESHOLD = 0.5  # Confidence threshold (0-1)
COOLDOWN_SECONDS = 2.0     # Minimum time between detections


class WakeWordDetector:
    """
    Continuously listens for the wake word "Joseph".

    When detected, calls the provided callback function.
    Runs on a background thread — never blocks the main thread.

    Usage:
        def on_wake():
            print("Wake word detected!")

        detector = WakeWordDetector(on_wake_callback=on_wake)
        detector.start()
        # ... runs in background ...
        detector.stop()
    """

    def __init__(
        self,
        audio_manager: AudioManager,
        on_wake_callback: Optional[Callable] = None,
        wake_word: Optional[str] = None,
    ):
        self.audio_manager = audio_manager
        self.on_wake_callback = on_wake_callback
        self.wake_word = (wake_word or settings.WAKE_WORD).lower()
        self._model = None
        self._available = False
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_detection = 0.0
        self._audio_buffer = np.array([], dtype=np.float32)
        self._fingerprint = None
        self._load_fingerprint()
        self._load_model()

    def _load_fingerprint(self) -> None:
        """Load voice fingerprint if available."""
        try:
            from voice.voice_fingerprint import load_fingerprint
            self._fingerprint = load_fingerprint()
            if self._fingerprint:
                logger.info(
                    f"Voice fingerprint loaded "
                    f"({self._fingerprint['n_samples']} samples, "
                    f"threshold={self._fingerprint['threshold']:.2f})"
                )
        except Exception as e:
            logger.debug(f"Fingerprint load error: {e}")

    def _load_model(self) -> None:
        """Load the openWakeWord model, downloading if needed."""
        try:
            # Ensure models are downloaded first
            from openwakeword.utils import download_models
            download_models()

            from openwakeword.model import Model

            # "hey_jarvis" is the closest built-in model to "joseph"
            # Responds to a similar 2-syllable wake phrase
            # Custom "joseph" model can be trained in a future phase
            self._model = Model(
                wakeword_models=["hey_jarvis"],
                inference_framework="onnx",
            )

            self._available = True
            logger.info(
                f"Wake word detector loaded "
                f"(listening for: '{self.wake_word}' via hey_jarvis model)"
            )

        except Exception as e:
            logger.warning(
                f"openWakeWord failed to load: {e}. "
                "Wake word detection disabled. "
                "You can still use push-to-talk (🎤 button)."
            )
            self._available = False

    def start(self) -> bool:
        """
        Start listening for the wake word in the background.

        Returns:
            True if started successfully.
        """
        if not self._available:
            logger.warning("Wake word detector not available")
            return False

        if self._running:
            return True

        if not self.audio_manager.is_streaming:
            if not self.audio_manager.start_stream():
                logger.error("Cannot start audio stream for wake word detection")
                return False

        self._running = True
        self._thread = threading.Thread(
            target=self._detection_loop,
            daemon=True,
            name="WakeWord-Detector",
        )
        self._thread.start()
        logger.info(f"Wake word detection started — say '{self.wake_word}'")
        return True

    def stop(self) -> None:
        """Stop the wake word detection loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("Wake word detection stopped")

    def _detection_loop(self) -> None:
        """
        Main detection loop — runs on background thread.
        Continuously reads audio and checks for wake word.
        """
        logger.debug("Wake word detection loop started")

        while self._running:
            try:
                chunk = self.audio_manager.read_chunk()
                if chunk is None:
                    time.sleep(0.01)
                    continue

                # Accumulate audio into the buffer
                self._audio_buffer = np.concatenate([self._audio_buffer, chunk])

                # Process when we have enough samples
                while len(self._audio_buffer) >= OWW_CHUNK_SIZE:
                    process_chunk = self._audio_buffer[:OWW_CHUNK_SIZE]
                    self._audio_buffer = self._audio_buffer[OWW_CHUNK_SIZE:]

                    # Run wake word detection
                    self._process_chunk(process_chunk)

            except Exception as e:
                logger.error(f"Wake word detection error: {e}")
                time.sleep(0.1)

    def _process_chunk(self, chunk: np.ndarray) -> None:
        """
        Process a single audio chunk through the wake word model.
        Uses voice fingerprint verification if available.
        """
        try:
            chunk_int16 = (chunk * 32767).astype(np.int16)
            prediction = self._model.predict(chunk_int16)

            for model_name, score in prediction.items():
                if score >= DETECTION_THRESHOLD:
                    now = time.time()
                    if now - self._last_detection >= COOLDOWN_SECONDS:
                        # Optional: verify with voice fingerprint
                        if self._fingerprint:
                            is_match, confidence = self._verify_fingerprint(chunk)
                            if not is_match:
                                logger.debug(
                                    f"Wake word rejected by fingerprint "
                                    f"(confidence={confidence:.2f})"
                                )
                                continue

                        self._last_detection = now
                        logger.info(
                            f"Wake word detected! "
                            f"(model={model_name}, score={score:.3f})"
                        )
                        self._on_detected()
                        break

        except Exception as e:
            logger.debug(f"Chunk processing error: {e}")

    def _verify_fingerprint(self, audio: np.ndarray) -> tuple[bool, float]:
        """Verify audio against stored voice fingerprint."""
        try:
            from voice.voice_fingerprint import match_audio
            return match_audio(audio, self._fingerprint)
        except Exception:
            return True, 1.0  # If verification fails, allow through

    def _on_detected(self) -> None:
        """Called when wake word is detected."""
        # Flush the audio buffer to avoid processing stale audio
        self.audio_manager.flush_buffer()
        self._audio_buffer = np.array([], dtype=np.float32)

        # Call the user's callback
        if self.on_wake_callback:
            try:
                self.on_wake_callback()
            except Exception as e:
                logger.error(f"Wake word callback error: {e}")

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def is_running(self) -> bool:
        return self._running

    def __repr__(self) -> str:
        return (
            f"WakeWordDetector(word='{self.wake_word}', "
            f"available={self._available}, "
            f"running={self._running})"
        )
