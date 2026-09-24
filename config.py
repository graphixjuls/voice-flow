import json
import os
import sys

CONFIG_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "VoiceFlow")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
LOG_PATH = os.path.join(CONFIG_DIR, "voiceflow.log")


def has_cuda() -> bool:
    """Checks if CUDA is available via ctranslate2."""
    try:
        import ctranslate2

        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def get_default_config() -> dict:
    cuda_available = has_cuda()
    default_device = "cuda" if cuda_available else "cpu"
    default_compute = "float16" if cuda_available else "int8"
    default_local_model = "distil-large-v3" if cuda_available else "base"

    return {
        "version": "2.0",
        "stt_mode": "local",  # "local" or "cloud"
        # Local settings
        "local_model": default_local_model,  # tiny, base, small, medium, large-v3-turbo, large-v3
        "device": default_device,  # "cuda" or "cpu"
        "compute_type": default_compute,  # "float16", "int8_float16", "int8"
        "beam_size": 5,
        # Cloud settings
        "cloud_provider": "openai",  # "openai", "groq", "gemini"
        "cloud_model": "whisper-1",  # "whisper-1" (OpenAI), "whisper-large-v3" (Groq), "gemini-2.5-flash" (Gemini)
        "openai_api_key": os.environ.get("OPENAI_API_KEY", ""),
        "groq_api_key": os.environ.get("GROQ_API_KEY", ""),
        "gemini_api_key": os.environ.get("GEMINI_API_KEY", ""),
        # Audio & Device
        "input_device_index": None,  # None = system default
        "sample_rate": 16000,
        "min_duration_sec": 0.3,
        "sound_cues": True,
        # Hotkey & Trigger
        "hotkey": "ctrl+alt",
        "hotkey_mode": "hold",  # "hold" (push-to-talk) or "toggle" (tap to start/stop)
        # Formatting & Post-processing
        "smart_dictation": True,
        "format_punctuation": True,
        "clean_fillers": True,
        "ai_polish": False,
        "auto_paste": True,
        "restore_clipboard": True,
        "language": None,  # None for auto-detect, or "en", "es", "fr", etc.
    }


def load_config() -> dict:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    defaults = get_default_config()
    if not os.path.exists(CONFIG_PATH):
        save_config(defaults)
        return defaults

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)
        # Merge with defaults in case new keys were added in V2
        for k, v in defaults.items():
            if k not in saved:
                saved[k] = v
        return saved
    except Exception:
        return defaults


def save_config(cfg: dict) -> bool:
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False
