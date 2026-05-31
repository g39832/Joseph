"""
voice/streaming_stt.py
-----------------------
Streaming speech-to-text for JOSEPH.

Provides partial (interim) transcriptions while the user is still
speaking, then delivers a final transcription when speech ends.

Uses faster-whisper under the hood — runs periodic transcriptions on
accumulating audio buffers to produce interim results. Falls back to
the regular SpeechToSTT singleton if streaming is unavailable.

Usage:
    stt = StreamingSTT()
    stt.on_partial(lambda text: print(f"Partial: {text}"))
    stt.on_final(lambda text: print(f"Final: {text}"))
    stt.start(audio_generator)
    # ... feed audio chunks ...
    stt.stop()
"""

import logging
import threading
import time
from queue import Queue, Empty
from typing import Callable, Optional

import numpy as np

from configs.settings import settings

logger = logging.getLogger(__name__)

# Streaming parameters
INTERIM_INTERVAL = 0.6          # Seconds between partial transcription updates
MIN_INTERIM_SAMPLES = int(16000 * 1.0)  # At least 1s of audio before partial
MIN_FINAL_SAMPLES = int(16000 * 0.5)    # At least 0.5s for final transcription


class StreamingSTT:
    """
    Streaming speech-to-text with interim results.

    Listens to an audio generator (queue or iterable of numpy arrays),
    periodically transcribes the accumulated audio to produce partial
    results, then delivers a final transcription when stopped.

    The transcription interval is configurable — shorter intervals give
    more responsive partial results but use more CPU.

    Falls back to the regular SpeechToText singleton if the streaming
    model can't be loaded.
    """

    def __init__(self, model_size: Optional[str] = None):
        self.model_size = model_size or settings.WHISPER_MODEL
        self._model = None
        self._available = False
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._audio_queue: Queue = Queue()
        self._accumulated = np.array([], dtype=np.float32)
        self._last_interim_time = 0.0
        self._partial_callbacks: list[Callable[[str], None]] = []
        self._final_callbacks: list[Callable[[str], None]] = []
        self._load_model()

    def _load_model(self) -> None:
        """Load the Whisper model for streaming (same as SpeechToText)."""
        try:
            from faster_whisper import WhisperModel

            logger.info(f"Loading streaming Whisper model '{self.model_size}'...")
            start = time.time()

            self._model = WhisperModel(
                self.model_size,
                device="cuda",
                compute_type="float16",
                num_workers=2,
            )

            elapsed = time.time() - start
            self._available = True
            logger.info(f"Streaming Whisper model loaded in {elapsed:.1f}s")

        except Exception as e:
            logger.warning(
                f"Streaming Whisper model failed to load: {e}. "
                "Falling back to regular STT."
            )
            self._available = False

    def on_partial(self, callback: Callable[[str], None]) -> None:
        """
        Register a callback for partial (interim) transcriptions.

        Args:
            callback: Called with partial text string as user speaks.
        """
        if callback not in self._partial_callbacks:
            self._partial_callbacks.append(callback)

    def on_final(self, callback: Callable[[str], None]) -> None:
        """
        Register a callback for the final transcription.

        Args:
            callback: Called with final text when user stops speaking.
        """
        if callback not in self._final_callbacks:
            self._final_callbacks.append(callback)

    def remove_partial(self, callback: Callable[[str], None]) -> None:
        """Remove a previously registered partial callback."""
        if callback in self._partial_callbacks:
            self._partial_callbacks.remove(callback)

    def remove_final(self, callback: Callable[[str], None]) -> None:
        """Remove a previously registered final callback."""
        if callback in self._final_callbacks:
            self._final_callbacks.remove(callback)

    def start(self) -> bool:
        """
        Start the streaming transcription thread.

        Returns:
            True if started successfully.
        """
        if self._running:
            return True

        if not self._available or self._model is None:
            logger.warning("Streaming STT not available")
            return False

        self._running = True
        self._accumulated = np.array([], dtype=np.float32)
        self._last_interim_time = 0.0

        # Clear any stale audio
        while True:
            try:
                self._audio_queue.get_nowait()
            except Empty:
                break

        self._thread = threading.Thread(
            target=self._streaming_loop,
            daemon=True,
            name="Streaming-STT",
        )
        self._thread.start()
        logger.info("Streaming transcription started")
        return True

    def stop(self) -> Optional[str]:
        """
        Stop streaming and return the final transcription.

        Returns:
            Final transcribed text, or None if no speech detected.
        """
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

        final_text = None
        if len(self._accumulated) >= MIN_FINAL_SAMPLES:
            final_text = self._transcribe_final(self._accumulated)

        self._accumulated = np.array([], dtype=np.float32)
        logger.info("Streaming transcription stopped")
        return final_text

    def feed_audio(self, chunk: np.ndarray) -> None:
        """
        Feed an audio chunk into the streaming pipeline.

        Args:
            chunk: Numpy float32 array at 16kHz.
        """
        if chunk is not None and len(chunk) > 0:
            self._audio_queue.put(chunk)

    def _streaming_loop(self) -> None:
        """
        Background thread: collect audio, emit partial transcriptions.
        """
        logger.debug("Streaming transcription loop started")

        while self._running:
            try:
                chunk = self._audio_queue.get(timeout=0.1)
                self._accumulated = np.concatenate([self._accumulated, chunk])

                # Emit partial results at regular intervals
                now = time.time()
                if (now - self._last_interim_time >= INTERIM_INTERVAL
                        and len(self._accumulated) >= MIN_INTERIM_SAMPLES):
                    self._last_interim_time = now
                    self._emit_partial()

            except Empty:
                # Check if we have accumulated audio to emit
                if (len(self._accumulated) >= MIN_INTERIM_SAMPLES
                        and time.time() - self._last_interim_time >= INTERIM_INTERVAL):
                    self._last_interim_time = time.time()
                    self._emit_partial()
                continue

            except Exception as e:
                logger.error(f"Streaming loop error: {e}")
                time.sleep(0.1)

    def _emit_partial(self) -> None:
        """Transcribe accumulated audio and notify partial callbacks."""
        if not self._partial_callbacks:
            return

        text = self._transcribe(self._accumulated)
        if text:
            for cb in self._partial_callbacks:
                try:
                    cb(text)
                except Exception as e:
                    logger.debug(f"Partial callback error: {e}")

    def _transcribe(self, audio: np.ndarray) -> Optional[str]:
        """
        Transcribe audio — returns transcribed text or None.

        This is a lightweight transcription for interim results
        (no hallucination filtering, minimal post-processing).
        """
        if self._model is None:
            return None

        try:
            # Normalize audio
            max_val = np.max(np.abs(audio))
            if max_val > 0:
                audio_norm = audio / max_val
            else:
                audio_norm = audio

            segments, _ = self._model.transcribe(
                audio_norm,
                language="en",
                beam_size=3,  # Smaller beam = faster, less accurate
                vad_filter=False,  # No VAD — we want raw partial results
                condition_on_previous_text=False,
            )

            text_parts = [segment.text.strip() for segment in segments]
            if not text_parts:
                return None

            return " ".join(text_parts).strip()

        except Exception as e:
            logger.debug(f"Streaming transcription error: {e}")
            return None

    def _transcribe_final(self, audio: np.ndarray) -> Optional[str]:
        """
        Transcribe the full audio for the final result.

        Uses the same parameters as SpeechToText.transcribe for
        consistent quality (larger beam, VAD filtering, hallucination
        filtering).
        """
        if self._model is None:
            return None

        if len(audio) < MIN_FINAL_SAMPLES:
            return None

        try:
            # Normalize
            max_val = np.max(np.abs(audio))
            if max_val > 0:
                audio = audio / max_val

            segments, info = self._model.transcribe(
                audio,
                language="en",
                beam_size=5,
                vad_filter=True,
                vad_parameters={
                    "min_silence_duration_ms": 800,
                    "speech_pad_ms": 400,
                    "threshold": 0.3,
                },
                condition_on_previous_text=False,
            )

            text_parts = []
            total_confidence = 0.0
            segment_count = 0

            for segment in segments:
                text_parts.append(segment.text.strip())
                total_confidence += segment.avg_logprob
                segment_count += 1

            if not text_parts:
                return None

            if segment_count > 0:
                avg_confidence = total_confidence / segment_count
                if avg_confidence < -2.0:
                    logger.debug(
                        f"Low confidence final transcription ({avg_confidence:.2f})"
                    )
                    return None

            full_text = " ".join(text_parts).strip()

            # Filter hallucinations
            hallucinations = {
                "thank you", "thanks for watching", "you", ".",
                "", "bye", "bye bye", "thank you for watching", "thanks",
            }
            if full_text.lower().strip(".").strip() in hallucinations:
                logger.debug(f"Filtered final hallucination: '{full_text}'")
                return None

            logger.info(
                f"Streaming final: '{full_text}' "
                f"(lang={info.language}, prob={info.language_probability:.2f})"
            )
            return full_text

        except Exception as e:
            logger.error(f"Final transcription error: {e}")
            return None

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def is_streaming(self) -> bool:
        return self._running

    def __repr__(self) -> str:
        return (
            f"StreamingSTT(model={self.model_size}, "
            f"available={self._available}, "
            f"streaming={self._running})"
        )
