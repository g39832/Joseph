"""
tests/test_mic.py
------------------
Microphone diagnostic tool.

Run this to find your mic's actual volume level so we can
set the correct silence threshold in the voice system.

Run with:
    python tests/test_mic.py
"""

import sys
import os
import time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_mic_levels():
    """Record 5 seconds and show RMS levels while you speak."""
    import sounddevice as sd
    from voice.audio_manager import AudioManager

    SAMPLE_RATE = 16000
    DURATION = 5
    CHUNK = 1600  # 100ms chunks

    # Find the device Joseph will actually use
    audio_mgr = AudioManager()
    device = audio_mgr.device_index
    device_name = sd.query_devices(device)["name"] if device is not None else sd.query_devices(kind="input")["name"]

    print("\n" + "=" * 50)
    print("MICROPHONE LEVEL TEST")
    print("=" * 50)
    print(f"Testing device: [{device}] {device_name}")
    print("Speak normally for 5 seconds...")
    print("Watch the level bars — this tells us your threshold.\n")

    levels = []

    def callback(indata, frames, time_info, status):
        rms = float(np.sqrt(np.mean(indata.astype(np.float32) ** 2)))
        levels.append(rms)
        bar_len = int(rms * 1000)
        bar = "█" * min(bar_len, 50)
        silence = rms < 0.01
        label = "SILENCE" if silence else "SPEECH "
        print(f"  [{label}] {bar:<50} {rms:.4f}", end="\r")

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype=np.float32,
        blocksize=CHUNK,
        device=device,
        callback=callback,
    ):
        time.sleep(DURATION)

    print("\n")

    if not levels:
        print("ERROR: No audio captured. Check your microphone.")
        return

    max_level = max(levels)
    avg_level = sum(levels) / len(levels)
    speech_levels = [l for l in levels if l > 0.005]
    avg_speech = sum(speech_levels) / len(speech_levels) if speech_levels else 0

    print("=" * 50)
    print(f"Results:")
    print(f"  Peak level:          {max_level:.4f}")
    print(f"  Average level:       {avg_level:.4f}")
    print(f"  Average when speaking: {avg_speech:.4f}")
    print()

    # Recommend threshold
    if max_level < 0.005:
        print("⚠ WARNING: Very low signal. Check:")
        print("  - Is your microphone selected in Windows Sound settings?")
        print("  - Is the mic volume turned up? (Windows Settings > Sound > Input)")
        print("  - Is the mic muted?")
    elif max_level < 0.02:
        recommended = 0.005
        print(f"✓ Mic working but quiet.")
        print(f"  Recommended silence_threshold: {recommended}")
    elif max_level < 0.1:
        recommended = 0.01
        print(f"✓ Mic working at normal level.")
        print(f"  Recommended silence_threshold: {recommended}")
    else:
        recommended = 0.02
        print(f"✓ Mic working at good level.")
        print(f"  Recommended silence_threshold: {recommended}")

    print()
    print("Copy the recommended threshold value above.")
    print("We will update voice_controller.py with the correct value.")
    print("=" * 50)

    return max_level, avg_speech


if __name__ == "__main__":
    test_mic_levels()
