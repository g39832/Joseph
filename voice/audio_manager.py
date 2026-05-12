"""
voice/audio_manager.py
-----------------------
Microphone management for JOSEPH.

Handles:
- Listing available audio devices
- Recording audio from microphone
- Voice activity detection (silence detection)
- Audio buffering for wake word + STT

Uses sounddevice for cross-platform audio capture.
"""

import logging
import threading
import time
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

from configs.settings import settings

logger = logging.getLogger(__name__)

# Audio constants
SAMPLE_RATE = 16000       # 16kHz — required by Whisper and openWakeWord
CHANNELS = 1              # Mono
DTYPE = np.float32        # Float32 audio samples
CHUNK_DURATION = 0.1      # 100ms chunks
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION)


class AudioManager:
    """
    Manages microphone input for JOSEPH.

    Provides a continuous audio stream that other modules
    (wake word detector, speech-to-text) can read from.

    Usage:
        audio = AudioManager()
        audio.start_stream()
        chunk = audio.read_chunk()   # Returns numpy array
        audio.stop_stream()
    """

    def __init__(self, device_index: Optional[int] = None):
        self.device_index = device_index or settings.MIC_DEVICE_INDEX
        self._stream: Optional[sd.InputStream] = None
        self._buffer: list = []
        self._buffer_lock = threading.Lock()
        self._is_streaming = False
        self._available = False
        self._check_availability()

    def _check_availability(self) -> None:
        """Check if audio input is available."""
        try:
            devices = sd.query_devices()
            input_devices = [d for d in devices if d["max_input_channels"] > 0]
            if input_devices:
                self._available = True
                logger.info(f"Audio available: {len(input_devices)} input device(s)")
                logger.debug(f"Default input: {sd.query_devices(kind='input')['name']}")
            else:
                logger.warning("No audio input devices found")
        except Exception as e:
            logger.warning(f"Audio check failed: {e}")

    def list_devices(self) -> list[dict]:
        """
        Return all available audio input devices.

        Returns:
            List of device dicts with name, index, channels.
        """
        try:
            devices = sd.query_devices()
            return [
                {
                    "index": i,
                    "name": d["name"],
                    "channels": d["max_input_channels"],
                    "sample_rate": int(d["default_samplerate"]),
                }
                for i, d in enumerate(devices)
                if d["max_input_channels"] > 0
            ]
        except Exception as e:
            logger.error(f"Error listing devices: {e}")
            return []

    def start_stream(self) -> bool:
        """
        Start the microphone input stream.

        Returns:
            True if stream started successfully.
        """
        if not self._available:
            logger.error("No audio input available")
            return False

        if self._is_streaming:
            return True

        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=CHUNK_SAMPLES,
                device=self.device_index,
                callback=self._audio_callback,
            )
            self._stream.start()
            self._is_streaming = True
            logger.info(
                f"Microphone stream started "
                f"(device={self.device_index}, rate={SAMPLE_RATE}Hz)"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to start microphone: {e}")
            self._is_streaming = False
            return False

    def stop_stream(self) -> None:
        """Stop the microphone input stream."""
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.debug(f"Stream stop error: {e}")
            finally:
                self._stream = None
                self._is_streaming = False
                logger.info("Microphone stream stopped")

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info,
        status,
    ) -> None:
        """
        Called by sounddevice for each audio chunk.
        Appends data to the buffer.
        """
        if status:
            logger.debug(f"Audio callback status: {status}")

        with self._buffer_lock:
            self._buffer.append(indata.copy().flatten())

            # Keep buffer from growing too large (max 5 seconds)
            max_chunks = int(5.0 / CHUNK_DURATION)
            if len(self._buffer) > max_chunks:
                self._buffer.pop(0)

    def read_chunk(self) -> Optional[np.ndarray]:
        """
        Read the oldest chunk from the audio buffer.

        Returns:
            Numpy array of audio samples, or None if buffer is empty.
        """
        with self._buffer_lock:
            if self._buffer:
                return self._buffer.pop(0)
        return None

    def read_seconds(self, seconds: float) -> Optional[np.ndarray]:
        """
        Read approximately N seconds of audio from the buffer.

        Args:
            seconds: How many seconds of audio to collect.

        Returns:
            Concatenated numpy array of audio samples.
        """
        chunks_needed = int(seconds / CHUNK_DURATION)
        collected = []

        deadline = time.time() + seconds + 1.0  # 1 second grace period

        while len(collected) < chunks_needed and time.time() < deadline:
            chunk = self.read_chunk()
            if chunk is not None:
                collected.append(chunk)
            else:
                time.sleep(0.01)

        if collected:
            return np.concatenate(collected)
        return None

    def record_until_silence(
        self,
        max_seconds: float = 10.0,
        silence_threshold: float = 0.01,
        silence_duration: float = 1.2,
    ) -> Optional[np.ndarray]:
        """
        Record audio until the user stops speaking.

        Stops when:
        - Silence detected for silence_duration seconds
        - max_seconds reached

        Args:
            max_seconds: Maximum recording time.
            silence_threshold: RMS level below which audio is considered silence.
            silence_duration: How long silence must last to stop recording.

        Returns:
            Numpy array of the recorded audio.
        """
        chunks = []
        silent_chunks = 0
        silence_chunks_needed = int(silence_duration / CHUNK_DURATION)
        max_chunks = int(max_seconds / CHUNK_DURATION)
        has_speech = False

        logger.debug("Recording until silence...")

        while len(chunks) < max_chunks:
            chunk = self.read_chunk()
            if chunk is None:
                time.sleep(0.01)
                continue

            chunks.append(chunk)
            rms = float(np.sqrt(np.mean(chunk ** 2)))

            if rms > silence_threshold:
                has_speech = True
                silent_chunks = 0
            else:
                if has_speech:
                    silent_chunks += 1
                    if silent_chunks >= silence_chunks_needed:
                        logger.debug(f"Silence detected after {len(chunks)} chunks")
                        break

        if not chunks or not has_speech:
            return None

        return np.concatenate(chunks)

    def flush_buffer(self) -> None:
        """Clear all buffered audio."""
        with self._buffer_lock:
            self._buffer.clear()

    @property
    def is_streaming(self) -> bool:
        return self._is_streaming

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def buffer_size(self) -> int:
        with self._buffer_lock:
            return len(self._buffer)

    def __repr__(self) -> str:
        return (
            f"AudioManager(available={self._available}, "
            f"streaming={self._is_streaming}, "
            f"buffer={self.buffer_size} chunks)"
        )
