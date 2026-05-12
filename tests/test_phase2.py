"""
tests/test_phase2.py
---------------------
Tests for Phase 2 voice components.

Run with:
    python tests/test_phase2.py
"""

import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_tts_available():
    """TTS engine should initialize."""
    from voice.text_to_speech import TextToSpeech
    tts = TextToSpeech()
    assert tts.is_available, "pyttsx3 TTS should be available"
    print("✓ TTS initialized")
    tts.stop()


def test_tts_clean_text():
    """TTS should clean markdown from text before speaking."""
    from voice.text_to_speech import TextToSpeech
    tts = TextToSpeech()

    dirty = "**Hello** there, check this `code` and https://example.com"
    clean = tts._clean_for_speech(dirty)

    assert "**" not in clean
    assert "`" not in clean
    assert "https" not in clean
    assert "Hello" in clean
    print(f"✓ TTS text cleaning works: '{clean}'")
    tts.stop()


def test_tts_speak():
    """TTS should speak without crashing."""
    from voice.text_to_speech import TextToSpeech
    tts = TextToSpeech()

    if tts.is_available:
        tts.speak("Hello, I am Joseph. Voice test successful.")
        import time
        time.sleep(3)  # Wait for speech to finish
        print("✓ TTS spoke successfully (you should have heard it)")
    else:
        print("⚠ TTS not available — skipping speak test")
    tts.stop()


def test_stt_loads():
    """Whisper model should load (downloads on first run)."""
    print("  Loading Whisper model (may download ~150MB on first run)...")
    from voice.speech_to_text import SpeechToText
    stt = SpeechToText(model_size="base.en")
    assert stt.is_available, "Whisper should load successfully"
    print(f"✓ STT loaded: {stt}")


def test_stt_transcribe_silence():
    """STT should return None for silent audio."""
    from voice.speech_to_text import SpeechToText
    stt = SpeechToText(model_size="base.en")

    if stt.is_available:
        # Silent audio
        silent = np.zeros(16000, dtype=np.float32)
        result = stt.transcribe(silent)
        # Should return None or empty for silence
        assert result is None or result == ""
        print("✓ STT correctly handles silent audio")
    else:
        print("⚠ STT not available — skipping")


def test_audio_manager():
    """AudioManager should detect available devices."""
    from voice.audio_manager import AudioManager
    audio = AudioManager()
    assert audio.is_available, "Should find at least one audio input device"
    devices = audio.list_devices()
    assert len(devices) > 0
    print(f"✓ AudioManager found {len(devices)} input device(s):")
    for d in devices:
        print(f"    [{d['index']}] {d['name']}")


def test_voice_controller_init():
    """VoiceController should initialize all components."""
    from voice.voice_controller import VoiceController
    vc = VoiceController()
    status = vc.get_status()
    print(f"✓ VoiceController initialized:")
    print(f"    Microphone: {status['microphone']}")
    print(f"    TTS:        {status['tts']}")
    print(f"    STT:        {status['stt']}")
    print(f"    Wake word:  {status['wake_word']}")
    vc.tts.stop()


if __name__ == "__main__":
    print("\nRunning Phase 2 Voice Tests\n" + "=" * 40)

    tests = [
        test_tts_available,
        test_tts_clean_text,
        test_audio_manager,
        test_voice_controller_init,
        test_stt_loads,
        test_stt_transcribe_silence,
        test_tts_speak,  # Last — actually speaks
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            print(f"\nRunning: {test.__name__}")
            test()
            passed += 1
        except Exception as e:
            print(f"✗ FAILED: {e}")
            failed += 1

    print(f"\n{'=' * 40}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("All Phase 2 tests passed!")
