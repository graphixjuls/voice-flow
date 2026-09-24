import numpy as np

from config import get_default_config, has_cuda, load_config
from paste_service import paste_text
from recorder import Recorder, list_input_devices
from smart_dictation import (
    clean_filler_words,
    format_spoken_punctuation,
    is_hallucination,
    normalize_typography,
    process_smart_dictation,
)


def test_cuda_detection():
    # Verify CUDA detection returns boolean and works
    cuda_status = has_cuda()
    assert isinstance(cuda_status, bool)
    print(f"CUDA Available: {cuda_status}")


def test_default_config():
    cfg = get_default_config()
    assert cfg["version"] == "2.0"
    assert "stt_mode" in cfg
    assert "local_model" in cfg
    assert "hotkey_mode" in cfg
    assert "smart_dictation" in cfg


def test_hallucination_detection():
    assert is_hallucination("Thank you for watching.") is True
    assert is_hallucination("Thanks for watching!") is True
    assert is_hallucination("Subtitles by the community") is True
    assert is_hallucination("[music]") is True
    assert is_hallucination("♪♪") is True
    assert is_hallucination("like and subscribe") is True
    assert is_hallucination("I am building a speech recognition app.") is False


def test_filler_word_removal():
    raw = "I um think uh we should er go ah to the the park"
    cleaned = clean_filler_words(raw)
    assert "um" not in cleaned.lower().split()
    assert "uh" not in cleaned.lower().split()
    assert "er" not in cleaned.lower().split()
    assert "the the" not in cleaned
    assert "I think we should go to the park" == cleaned


def test_spoken_punctuation():
    text = "Hello world comma how are you question mark new line I am fine period"
    formatted = format_spoken_punctuation(text)
    assert "," in formatted
    assert "?" in formatted
    assert "\n" in formatted
    assert "." in formatted


def test_smart_dictation_pipeline():
    raw = "hello um world comma how are you question mark new line this is great period"
    result = process_smart_dictation(raw, enable_smart=True)
    assert result == "Hello world, how are you?\nThis is great."


def test_recorder_gain_normalization():
    rec = Recorder()
    # Quiet audio
    quiet_audio = np.sin(np.linspace(0, 100, 16000)).astype("float32") * 0.05
    rec._frames = [quiet_audio]
    rec._stream = None
    processed = rec.stop()
    assert len(processed) == 16000
    # Peak should be boosted close to 0.95 (within max 5x gain)
    assert np.max(np.abs(processed)) > 0.20


def test_device_listing():
    devices = list_input_devices()
    assert isinstance(devices, list)
    assert len(devices) > 0
    for idx, name in devices:
        assert isinstance(idx, int)
        assert isinstance(name, str)


if __name__ == "__main__":
    print("Running Voice Flow V2 Test Suite...")
    test_cuda_detection()
    test_default_config()
    test_hallucination_detection()
    test_filler_word_removal()
    test_spoken_punctuation()
    test_smart_dictation_pipeline()
    test_recorder_gain_normalization()
    test_device_listing()
    print("ALL TESTS PASSED SUCCESSFULLY! [OK]")
