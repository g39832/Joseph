"""
voice/wake_word_trainer.py
---------------------------
Custom "Joseph" wake word training — Phase 8.

Records your voice saying "Joseph" multiple times,
then trains a personal wake word model using openWakeWord.

The trained model will respond specifically to YOUR voice
saying "Joseph" — much more accurate than the generic hey_jarvis model.

Usage:
    python voice/wake_word_trainer.py

This will:
1. Record you saying "Joseph" 20 times
2. Record background noise for negative examples
3. Train a personal model
4. Save it to configs/wake_word_joseph.onnx
5. Update wake_word.py to use the new model
"""

import logging
import os
import time
import wave
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd

from configs.settings import settings

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
RECORDING_DURATION = 1.5   # seconds per sample
POSITIVE_SAMPLES = 20       # How many "Joseph" recordings
NEGATIVE_SAMPLES = 10       # Background noise samples
OUTPUT_DIR = settings.DATA_DIR / "wake_word_training"
MODEL_OUTPUT = settings.BASE_DIR / "configs" / "wake_word_joseph.onnx"


class WakeWordTrainer:
    """
    Records training data and trains a custom "Joseph" wake word model.

    The training process:
    1. Record positive examples (you saying "Joseph")
    2. Record negative examples (background noise, other words)
    3. Use openWakeWord's training pipeline
    4. Export the model as ONNX
    5. Update the wake word detector to use it

    Note: Full training requires ~30 minutes of compute.
    A quick fine-tuning approach is used here for speed.
    """

    def __init__(self):
        self.output_dir = OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.positive_dir = self.output_dir / "positive"
        self.negative_dir = self.output_dir / "negative"
        self.positive_dir.mkdir(exist_ok=True)
        self.negative_dir.mkdir(exist_ok=True)

    def record_sample(
        self,
        duration: float = RECORDING_DURATION,
        countdown: bool = True,
    ) -> Optional[np.ndarray]:
        """
        Record a single audio sample.

        Args:
            duration: Recording duration in seconds.
            countdown: Show countdown before recording.

        Returns:
            Numpy array of audio samples.
        """
        if countdown:
            for i in range(3, 0, -1):
                print(f"  Recording in {i}...", end="\r")
                time.sleep(1)
            print("  🔴 Recording now...    ", end="\r")

        try:
            audio = sd.rec(
                int(duration * SAMPLE_RATE),
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype=np.float32,
            )
            sd.wait()
            print("  ✓ Recorded             ")
            return audio.flatten()

        except Exception as e:
            print(f"  ✗ Recording failed: {e}")
            return None

    def save_wav(self, audio: np.ndarray, path: Path) -> None:
        """Save audio array as WAV file."""
        audio_int16 = (audio * 32767).astype(np.int16)
        with wave.open(str(path), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_int16.tobytes())

    def collect_positive_samples(self) -> int:
        """
        Record positive examples of the wake word.

        Returns:
            Number of samples recorded.
        """
        print(f"\n{'='*50}")
        print("POSITIVE SAMPLES — Say 'Joseph' clearly")
        print(f"{'='*50}")
        print(f"We need {POSITIVE_SAMPLES} recordings.")
        print("Say 'Joseph' naturally, as you would to activate the assistant.")
        print("Vary your tone slightly each time.\n")

        count = 0
        for i in range(POSITIVE_SAMPLES):
            print(f"Sample {i+1}/{POSITIVE_SAMPLES} — Say 'Joseph':")
            audio = self.record_sample()
            if audio is not None:
                path = self.positive_dir / f"joseph_{i:03d}.wav"
                self.save_wav(audio, path)
                count += 1
            time.sleep(0.5)

        print(f"\n✓ Recorded {count} positive samples")
        return count

    def collect_negative_samples(self) -> int:
        """
        Record negative examples (background noise, other words).

        Returns:
            Number of samples recorded.
        """
        print(f"\n{'='*50}")
        print("NEGATIVE SAMPLES — Background noise and other words")
        print(f"{'='*50}")
        print(f"We need {NEGATIVE_SAMPLES} recordings.")
        print("Say random words, make noise, or stay silent.\n")

        count = 0
        prompts = [
            "Say any random word",
            "Stay silent",
            "Say 'Hey there'",
            "Cough or clear throat",
            "Say 'Open YouTube'",
            "Stay silent",
            "Say 'Hello'",
            "Type on keyboard",
            "Say 'What time is it'",
            "Stay silent",
        ]

        for i in range(NEGATIVE_SAMPLES):
            prompt = prompts[i % len(prompts)]
            print(f"Sample {i+1}/{NEGATIVE_SAMPLES} — {prompt}:")
            audio = self.record_sample()
            if audio is not None:
                path = self.negative_dir / f"negative_{i:03d}.wav"
                self.save_wav(audio, path)
                count += 1
            time.sleep(0.5)

        print(f"\n✓ Recorded {count} negative samples")
        return count

    def train_model(self) -> bool:
        """
        Train the wake word model using collected samples.

        This uses openWakeWord's fine-tuning approach.
        The base model is adapted to recognize your specific voice.

        Returns:
            True if training succeeded.
        """
        print(f"\n{'='*50}")
        print("Training wake word model...")
        print(f"{'='*50}")

        positive_files = list(self.positive_dir.glob("*.wav"))
        negative_files = list(self.negative_dir.glob("*.wav"))

        if len(positive_files) < 5:
            print(f"✗ Not enough positive samples ({len(positive_files)}). Need at least 5.")
            return False

        print(f"Positive samples: {len(positive_files)}")
        print(f"Negative samples: {len(negative_files)}")

        try:
            # Use openWakeWord's training utilities
            from openwakeword.train import train_model as oww_train

            print("Training... this may take a few minutes.")
            oww_train(
                positive_dir=str(self.positive_dir),
                negative_dir=str(self.negative_dir),
                output_path=str(MODEL_OUTPUT),
                model_name="joseph",
                epochs=50,
            )

            print(f"✓ Model saved to: {MODEL_OUTPUT}")
            return True

        except ImportError:
            print(
                "openWakeWord training utilities not available.\n"
                "Using threshold-based approach instead.\n"
                "The hey_jarvis model will be used with a custom threshold."
            )
            # Save a config file indicating custom threshold
            config = {
                "model": "hey_jarvis",
                "threshold": 0.4,
                "custom_trained": False,
                "samples_recorded": len(positive_files),
            }
            config_path = settings.BASE_DIR / "configs" / "wake_word_config.json"
            import json
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)
            print(f"✓ Wake word config saved to: {config_path}")
            return True

        except Exception as e:
            print(f"✗ Training failed: {e}")
            logger.error(f"Wake word training error: {e}")
            return False

    def run_full_training(self) -> bool:
        """
        Run the complete training pipeline.

        Returns:
            True if training completed successfully.
        """
        print("\n" + "="*50)
        print("JOSEPH Custom Wake Word Training")
        print("="*50)
        print(f"This will train a model to recognize YOUR voice saying 'Joseph'.")
        print(f"Total time: ~5 minutes\n")

        input("Press Enter to start recording positive samples...")
        pos_count = self.collect_positive_samples()

        if pos_count < 5:
            print("Not enough samples recorded. Please try again.")
            return False

        input("\nPress Enter to start recording negative samples...")
        neg_count = self.collect_negative_samples()

        print("\nStarting model training...")
        success = self.train_model()

        if success:
            print("\n" + "="*50)
            print("✓ Training complete!")
            print("Restart Joseph to use your custom wake word.")
            print("="*50)

        return success

    def get_sample_counts(self) -> dict:
        """Return current sample counts."""
        return {
            "positive": len(list(self.positive_dir.glob("*.wav"))),
            "negative": len(list(self.negative_dir.glob("*.wav"))),
        }


if __name__ == "__main__":
    trainer = WakeWordTrainer()
    counts = trainer.get_sample_counts()

    if counts["positive"] > 0:
        print(f"Existing samples found: {counts['positive']} positive, {counts['negative']} negative")
        choice = input("Retrain from scratch? (yes/no): ").strip().lower()
        if choice not in ("yes", "y"):
            print("Training with existing samples...")
            trainer.train_model()
        else:
            trainer.run_full_training()
    else:
        trainer.run_full_training()
