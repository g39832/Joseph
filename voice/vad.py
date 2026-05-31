"""
voice/vad.py
-------------
Voice Activity Detection for JOSEPH.

Uses energy-based threshold detection — works without any external
dependencies beyond numpy. Optionally wraps WebRTC VAD (webrtcvad)
for hardware-level voice detection if installed.

Detection flow:
  Audio chunk → RMS energy → threshold comparison → speech/non-speech

The threshold auto-calibrates to the microphone's noise floor
during the first few seconds of silence.
"""

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Default VAD parameters
DEFAULT_FRAME_DURATION = 30        # ms — must be 10, 20, or 30 for webrtcvad
DEFAULT_FRAME_SIZE = int(16000 * DEFAULT_FRAME_DURATION / 1000)  # 480 samples
DEFAULT_THRESHOLD = 0.035          # RMS energy threshold — calibrated for typical mics
SAMPLE_RATE = 16000
AUTO_CALIBRATE_SECONDS = 2.0       # Seconds of noise to sample for calibration


class VAD:
    """
    Voice Activity Detector — tells you if a chunk of audio contains speech.

    Primary method: energy-based (RMS) threshold detection.
    Falls back gracefully if webrtcvad is not installed.

    Usage:
        vad = VAD(threshold=0.04)
        if vad.is_speech(audio_chunk):
            print("Someone is speaking")
    """

    def __init__(
        self,
        threshold: Optional[float] = None,
        frame_duration_ms: int = DEFAULT_FRAME_DURATION,
        use_webrtc: bool = False,
    ):
        """
        Args:
            threshold: RMS energy threshold (0.0–1.0). Auto-calibrated if None.
            frame_duration_ms: Frame size in ms (10, 20, or 30).
            use_webrtc: Prefer WebRTC VAD over energy-based. Falls back
                        to energy if webrtcvad not installed.
        """
        self.frame_duration = frame_duration_ms
        self.frame_size = int(SAMPLE_RATE * frame_duration_ms / 1000)

        self._threshold = threshold
        self._calibrated = threshold is not None
        self._noise_floor = 0.0
        self._calibration_buffer: list[float] = []

        # Try to load webrtcvad
        self._webrtc_vad = None
        self._use_webrtc = use_webrtc
        self._load_webrtc()

    def _load_webrtc(self) -> None:
        """Attempt to load webrtcvad — non-fatal if unavailable."""
        if not self._use_webrtc:
            return
        try:
            import webrtcvad

            self._webrtc_vad = webrtcvad.Vad()
            self._webrtc_vad.set_mode(2)  # 0=most permissive, 3=most aggressive
            logger.info("WebRTC VAD loaded successfully")
        except ImportError:
            logger.info(
                "webrtcvad not installed — falling back to energy-based VAD. "
                "Install with: pip install webrtcvad"
            )
        except Exception as e:
            logger.warning(f"WebRTC VAD init failed: {e}")

    def calibrate(self, audio: np.ndarray) -> float:
        """
        Calibrate the threshold based on ambient noise.

        Samples the RMS energy of the provided audio (should be silence/noise)
        and sets the threshold slightly above the noise floor.

        Args:
            audio: Audio samples at 16kHz (should contain only background noise).

        Returns:
            The calibrated threshold value.
        """
        if len(audio) < self.frame_size:
            logger.warning("Audio too short for calibration — using default threshold")
            if self._threshold is None:
                self._threshold = DEFAULT_THRESHOLD
            return self._threshold

        # Compute RMS for each frame
        rms_values = []
        for i in range(0, len(audio) - self.frame_size + 1, self.frame_size):
            frame = audio[i:i + self.frame_size]
            rms = float(np.sqrt(np.mean(frame ** 2)))
            rms_values.append(rms)

        if not rms_values:
            self._threshold = DEFAULT_THRESHOLD
            return self._threshold

        self._noise_floor = float(np.median(rms_values))
        noise_std = float(np.std(rms_values))

        # Set threshold: noise floor + 3 standard deviations (or min 2x floor)
        self._threshold = max(
            self._noise_floor + 3.0 * noise_std,
            self._noise_floor * 2.0,
            DEFAULT_THRESHOLD,
        )

        self._calibrated = True
        logger.info(
            f"VAD calibrated: noise_floor={self._noise_floor:.5f}, "
            f"threshold={self._threshold:.5f}"
        )
        return self._threshold

    def is_speech(self, chunk: np.ndarray) -> bool:
        """
        Determine if an audio chunk contains speech.

        Args:
            chunk: Numpy float32 array at 16kHz sample rate.

        Returns:
            True if speech is detected, False otherwise.
        """
        if chunk is None or len(chunk) == 0:
            return False

        # Auto-calibrate on first call if no threshold set
        if not self._calibrated:
            self._feed_calibration(chunk)
            return False

        if self._webrtc_vad is not None:
            return self._check_webrtc(chunk)

        return self._check_energy(chunk)

    def _feed_calibration(self, chunk: np.ndarray) -> None:
        """Feed audio into the calibration buffer."""
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        self._calibration_buffer.append(rms)

        # Keep last N seconds of RMS values
        max_frames = int(AUTO_CALIBRATE_SECONDS / (self.frame_duration / 1000))
        if len(self._calibration_buffer) > max_frames:
            self._calibration_buffer.pop(0)

        # Calibrate once we have enough samples
        if len(self._calibration_buffer) >= max_frames:
            noise = np.array(self._calibration_buffer)
            self._noise_floor = float(np.median(noise))
            noise_std = float(np.std(noise))
            self._threshold = max(
                self._noise_floor + 3.0 * noise_std,
                self._noise_floor * 2.0,
                DEFAULT_THRESHOLD,
            )
            self._calibrated = True
            logger.info(
                f"VAD auto-calibrated: noise_floor={self._noise_floor:.5f}, "
                f"threshold={self._threshold:.5f}"
            )

    def _check_webrtc(self, chunk: np.ndarray) -> bool:
        """Check speech using WebRTC VAD."""
        try:
            # WebRTC VAD requires 16-bit PCM
            if chunk.dtype != np.int16:
                chunk_int16 = (chunk * 32767).astype(np.int16)
            else:
                chunk_int16 = chunk

            # WebRTC VAD expects bytes
            audio_bytes = chunk_int16.tobytes()
            return self._webrtc_vad.is_speech(audio_bytes, SAMPLE_RATE)
        except Exception as e:
            logger.debug(f"WebRTC VAD error: {e}")
            return self._check_energy(chunk)

    def _check_energy(self, chunk: np.ndarray) -> bool:
        """Check speech using energy-based RMS threshold."""
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        return rms > self._threshold

    @property
    def threshold(self) -> float:
        return self._threshold if self._threshold is not None else DEFAULT_THRESHOLD

    @property
    def noise_floor(self) -> float:
        return self._noise_floor

    @property
    def is_calibrated(self) -> bool:
        return self._calibrated

    @property
    def using_webrtc(self) -> bool:
        return self._webrtc_vad is not None

    def __repr__(self) -> str:
        return (
            f"VAD(threshold={self.threshold:.5f}, "
            f"noise_floor={self._noise_floor:.5f}, "
            f"method={'webrtc' if self.using_webrtc else 'energy'}, "
            f"calibrated={self._calibrated})"
        )
