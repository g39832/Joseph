"""
voice/speech_to_text.py
------------------------
Speech-to-text using faster-whisper.

faster-whisper is a highly optimized version of OpenAI's Whisper model.
It runs completely locally — no internet, no API keys.

On CPU (your current setup): ~1-3 seconds for a short phrase
On GPU (after CUDA install): ~0.2-0.5 seconds

Models available (set in .env WHISPER_MODEL):
  tiny.en   — fastest, least accurate (~40MB)
  base.en   — good balance, recommended (~150MB)
  small.en  — more accurate, slower (~500MB)
  medium.en — very accurate, slow on CPU (~1.5GB)

The model downloads automatically on first use.
"""

import logging
import time
from typing import Optional

import numpy as np

from configs.settings import settings

logger = logging.getLogger(__name__)

# Minimum audio length to attempt transcription (avoid empty transcriptions)
MIN_AUDIO_SECONDS = 0.5
MIN_AUDIO_SAMPLES = int(16000 * MIN_AUDIO_SECONDS)


class SpeechToText:
    """
    Transcribes audio to text using faster-whisper.

    The model loads once on initialization and stays in memory.
    Subsequent transcriptions are fast.

    Usage:
        stt = SpeechToText()
        text = stt.transcribe(audio_array)
        if text:
            print(f"You said: {text}")
    """

    def __init__(self, model_size: Optional[str] = None):
        self.model_size = model_size or settings.WHISPER_MODEL
        self._model = None
        self._available = False
        self._load_model()

    def _load_model(self) -> None:
        """
        Load the Whisper model.
        Downloads automatically on first run (~150MB for base.en).
        """
        try:
            from faster_whisper import WhisperModel

            logger.info(
                f"Loading Whisper model '{self.model_size}'... "
                f"(first run downloads the model)"
            )
            start = time.time()

            # CPU mode — works without CUDA
            # Change compute_type to "float16" and device to "cuda"
            # after installing CUDA for GPU acceleration
            self._model = WhisperModel(
                self.model_size,
                device="cpu",
                compute_type="int8",  # int8 is fastest on CPU
                num_workers=2,
            )

            elapsed = time.time() - start
            self._available = True
            logger.info(f"Whisper model loaded in {elapsed:.1f}s")

        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            logger.error(
                "Try: pip install faster-whisper\n"
                "Also ensure FFmpeg is installed."
            )
            self._available = False

    def transcribe(
        self,
        audio: np.ndarray,
        language: str = "en",
        min_confidence: float = 0.4,
    ) -> Optional[str]:
        """
        Transcribe audio to text.

        Args:
            audio: Numpy float32 array at 16kHz sample rate.
            language: Language code (default "en").
            min_confidence: Minimum average log probability to accept result.
                            Lower = accept more uncertain transcriptions.

        Returns:
            Transcribed text string, or None if transcription failed/empty.
        """
        if not self._available or self._model is None:
            logger.warning("STT not available")
            return None

        if audio is None or len(audio) < MIN_AUDIO_SAMPLES:
            logger.debug("Audio too short to transcribe")
            return None

        # Ensure correct format
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        # Normalize audio
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            audio = audio / max_val

        try:
            start = time.time()

            segments, info = self._model.transcribe(
                audio,
                language=language,
                beam_size=5,
                vad_filter=True,
                vad_parameters={
                    "min_silence_duration_ms": 800,   # Wait longer before cutting
                    "speech_pad_ms": 400,              # Pad more around speech
                    "threshold": 0.3,                  # Less aggressive — catch quiet speech
                },
                condition_on_previous_text=False,
            )

            # Collect all segments
            text_parts = []
            total_confidence = 0.0
            segment_count = 0

            for segment in segments:
                text_parts.append(segment.text.strip())
                total_confidence += segment.avg_logprob
                segment_count += 1

            elapsed = time.time() - start

            if not text_parts:
                logger.debug("Whisper returned no segments")
                return None

            # Check confidence
            if segment_count > 0:
                avg_confidence = total_confidence / segment_count
                if avg_confidence < -2.0:  # Very low confidence
                    logger.debug(
                        f"Low confidence transcription ({avg_confidence:.2f}), discarding"
                    )
                    return None

            full_text = " ".join(text_parts).strip()

            # Filter out common Whisper hallucinations
            hallucinations = {
                "thank you",
                "thanks for watching",
                "you",
                ".",
                "",
                "bye",
                "bye bye",
                "thank you for watching",
                "thanks",
            }
            if full_text.lower().strip(".").strip() in hallucinations:
                logger.debug(f"Filtered hallucination: '{full_text}'")
                return None

            logger.info(
                f"Transcribed in {elapsed:.2f}s: '{full_text}' "
                f"(lang={info.language}, prob={info.language_probability:.2f})"
            )
            return full_text

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None

    def transcribe_file(self, file_path: str) -> Optional[str]:
        """
        Transcribe audio from a file path.

        Args:
            file_path: Path to audio file (WAV, MP3, etc.)

        Returns:
            Transcribed text or None.
        """
        if not self._available:
            return None

        try:
            import soundfile as sf
            audio, sr = sf.read(file_path, dtype="float32")

            # Resample to 16kHz if needed
            if sr != 16000:
                import scipy.signal as signal
                samples = int(len(audio) * 16000 / sr)
                audio = signal.resample(audio, samples)

            # Convert stereo to mono
            if len(audio.shape) > 1:
                audio = audio.mean(axis=1)

            return self.transcribe(audio)

        except Exception as e:
            logger.error(f"File transcription error: {e}")
            return None

    @property
    def is_available(self) -> bool:
        return self._available

    def __repr__(self) -> str:
        return (
            f"SpeechToText(model={self.model_size}, "
            f"available={self._available})"
        )


# Module-level singleton
stt = SpeechToText()
