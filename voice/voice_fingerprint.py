"""
voice/voice_fingerprint.py
---------------------------
Voice fingerprint-based wake word detection for JOSEPH.

Since openWakeWord's verifier requires pre-detected clips,
we use a different approach: MFCC-based voice fingerprinting.

How it works:
1. Extract MFCC features from your "Joseph" recordings
2. Build a centroid (average feature vector)
3. At runtime, compare incoming audio against the centroid
4. If similarity > threshold AND hey_jarvis fires → confirmed detection

This gives you personal wake word detection without needing
a full ML training pipeline.
"""

import logging
import pickle
from pathlib import Path
from typing import Optional

import numpy as np

from configs.settings import settings

logger = logging.getLogger(__name__)

FINGERPRINT_PATH = settings.BASE_DIR / "configs" / "joseph_fingerprint.pkl"
SAMPLE_RATE = 16000


def extract_mfcc(audio: np.ndarray, n_mfcc: int = 13) -> np.ndarray:
    """
    Extract MFCC features from audio.
    Uses scipy for computation — no extra dependencies needed.
    """
    try:
        from scipy.fft import fft
        from scipy.signal import get_window

        # Pre-emphasis
        pre_emphasis = 0.97
        emphasized = np.append(audio[0], audio[1:] - pre_emphasis * audio[:-1])

        # Frame the signal
        frame_size = int(0.025 * SAMPLE_RATE)  # 25ms
        frame_step = int(0.010 * SAMPLE_RATE)  # 10ms
        frames = []
        for i in range(0, len(emphasized) - frame_size, frame_step):
            frames.append(emphasized[i:i + frame_size])

        if not frames:
            return np.zeros(n_mfcc)

        frames = np.array(frames)

        # Apply Hamming window
        window = get_window("hamming", frame_size)
        frames *= window

        # FFT magnitude
        mag_frames = np.abs(fft(frames, n=512))[:, :257]
        pow_frames = (1.0 / 512) * (mag_frames ** 2)

        # Mel filterbank
        n_filters = 26
        low_freq = 0
        high_freq = SAMPLE_RATE / 2
        mel_low = 2595 * np.log10(1 + low_freq / 700)
        mel_high = 2595 * np.log10(1 + high_freq / 700)
        mel_points = np.linspace(mel_low, mel_high, n_filters + 2)
        hz_points = 700 * (10 ** (mel_points / 2595) - 1)
        bin_points = np.floor((512 + 1) * hz_points / SAMPLE_RATE).astype(int)

        fbank = np.zeros((n_filters, 257))
        for m in range(1, n_filters + 1):
            f_m_minus = bin_points[m - 1]
            f_m = bin_points[m]
            f_m_plus = bin_points[m + 1]
            for k in range(f_m_minus, f_m):
                if f_m != f_m_minus:
                    fbank[m - 1, k] = (k - f_m_minus) / (f_m - f_m_minus)
            for k in range(f_m, f_m_plus):
                if f_m_plus != f_m:
                    fbank[m - 1, k] = (f_m_plus - k) / (f_m_plus - f_m)

        filter_banks = np.dot(pow_frames, fbank.T)
        filter_banks = np.where(filter_banks == 0, np.finfo(float).eps, filter_banks)
        filter_banks = 20 * np.log10(filter_banks)

        # DCT to get MFCCs
        from scipy.fft import dct
        mfcc = dct(filter_banks, type=2, axis=1, norm='ortho')[:, :n_mfcc]

        # Return mean across frames
        return np.mean(mfcc, axis=0)

    except Exception as e:
        logger.debug(f"MFCC extraction error: {e}")
        # Fallback: simple energy-based features
        return np.array([
            np.mean(np.abs(audio)),
            np.std(audio),
            np.max(np.abs(audio)),
            float(np.sum(np.diff(np.sign(audio)) != 0)) / len(audio),
        ] + [0.0] * 9)


def build_fingerprint(recordings_dir: Path) -> Optional[dict]:
    """
    Build a voice fingerprint from recordings.

    Args:
        recordings_dir: Directory containing .wav files.

    Returns:
        Fingerprint dict with centroid and threshold.
    """
    try:
        import soundfile as sf

        wav_files = sorted(recordings_dir.glob("*.wav"))
        if not wav_files:
            logger.error(f"No WAV files found in {recordings_dir}")
            return None

        features = []
        for wav_file in wav_files:
            audio, sr = sf.read(str(wav_file), dtype="float32")
            if len(audio.shape) > 1:
                audio = audio.mean(axis=1)
            mfcc = extract_mfcc(audio)
            features.append(mfcc)

        features = np.array(features)
        centroid = np.mean(features, axis=0)
        std = np.std(features, axis=0)

        # Calculate intra-class distances for threshold
        distances = []
        for f in features:
            dist = np.linalg.norm(f - centroid)
            distances.append(dist)

        avg_dist = np.mean(distances)
        threshold = avg_dist * 2.5  # Allow 2.5x average distance

        fingerprint = {
            "centroid": centroid.tolist(),
            "std": std.tolist(),
            "threshold": float(threshold),
            "n_samples": len(features),
            "avg_intra_distance": float(avg_dist),
        }

        logger.info(
            f"Fingerprint built from {len(features)} samples, "
            f"threshold={threshold:.3f}"
        )
        return fingerprint

    except Exception as e:
        logger.error(f"Fingerprint build error: {e}")
        return None


def save_fingerprint(fingerprint: dict, path: Path = FINGERPRINT_PATH) -> bool:
    """Save fingerprint to disk."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(fingerprint, f)
        logger.info(f"Fingerprint saved: {path}")
        return True
    except Exception as e:
        logger.error(f"Save fingerprint error: {e}")
        return False


def load_fingerprint(path: Path = FINGERPRINT_PATH) -> Optional[dict]:
    """Load fingerprint from disk."""
    if not path.exists():
        return None
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        logger.error(f"Load fingerprint error: {e}")
        return None


def match_audio(audio: np.ndarray, fingerprint: dict) -> tuple[bool, float]:
    """
    Check if audio matches the voice fingerprint.

    Args:
        audio: Audio samples to check.
        fingerprint: The stored fingerprint dict.

    Returns:
        (is_match, confidence_score)
    """
    try:
        mfcc = extract_mfcc(audio)
        centroid = np.array(fingerprint["centroid"])
        threshold = fingerprint["threshold"]

        distance = np.linalg.norm(mfcc - centroid)
        confidence = max(0.0, 1.0 - (distance / (threshold * 2)))
        is_match = distance <= threshold

        return is_match, confidence

    except Exception as e:
        logger.debug(f"Match error: {e}")
        return False, 0.0


def train_from_recordings() -> bool:
    """
    Build fingerprint from existing recordings in data/wake_word_samples/positive.

    Returns:
        True if fingerprint was built and saved successfully.
    """
    pos_dir = settings.DATA_DIR / "wake_word_samples" / "positive"

    if not pos_dir.exists():
        logger.error(f"No recordings found at {pos_dir}")
        return False

    print(f"Building voice fingerprint from {pos_dir}...")
    fingerprint = build_fingerprint(pos_dir)

    if fingerprint is None:
        print("✗ Failed to build fingerprint")
        return False

    if save_fingerprint(fingerprint):
        print(f"✓ Voice fingerprint saved ({fingerprint['n_samples']} samples)")
        print(f"  Threshold: {fingerprint['threshold']:.3f}")

        # Update wake word config
        import json
        config_path = settings.BASE_DIR / "configs" / "wake_word_config.json"
        config = {}
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)

        config["fingerprint_path"] = str(FINGERPRINT_PATH)
        config["use_fingerprint"] = True
        config["custom_trained"] = True
        config["wake_word"] = "joseph"

        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

        print("✓ Wake word config updated")
        return True

    return False


if __name__ == "__main__":
    success = train_from_recordings()
    if success:
        print("\nRestart Joseph to use your personal wake word fingerprint.")
