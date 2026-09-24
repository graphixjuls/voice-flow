import logging
import os
import sys
import threading
import time
import traceback

from PIL import Image, ImageDraw
from pystray import Icon, Menu, MenuItem

from cloud_transcriber import CloudTranscriber
from config import LOG_PATH, load_config, save_config
from hotkey_manager import HotkeyManager
from cuda_setup import setup_cuda_dlls
from paste_service import paste_text
from recorder import Recorder
from settings_dialog import SettingsDialog
from smart_dictation import is_hallucination, process_smart_dictation, run_ai_polish
from sound_cues import play_cue
from transcriber import Transcriber
from ui import VoiceFlowUI

# Logging setup
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
if not any(isinstance(h, logging.FileHandler) for h in root_logger.handlers):
    root_logger.addHandler(file_handler)

# Register CUDA DLL directories early before any model is accessed
try:
    setup_cuda_dlls()
except Exception as exc:
    logging.warning("Initial CUDA setup failed: %s", exc)


def log_exception(context: str):
    logging.error("%s\n%s", context, traceback.format_exc())


# Application State
cfg = load_config()
state = {
    "recording": False,
    "icon": None,
    "transcriber": None,
    "loaded_mode": None,
    "loaded_model": None,
}
model_lock = threading.Lock()

# Audio Recorder instance with live level feedback hook
recorder = Recorder(
    samplerate=cfg.get("sample_rate", 16000),
    device=cfg.get("input_device_index"),
)

# Tray Styling
TRAY_BG = (20, 21, 27, 255)
STATUS_COLORS = {
    "idle": (92, 98, 117),
    "recording": (255, 82, 82),
    "transcribing": (245, 159, 0),
    "ready": (81, 207, 102),
    "error": (250, 82, 82),
}


def make_icon_image(color):
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((2, 2, 62, 62), radius=14, fill=TRAY_BG)

    cx = 32
    draw.rounded_rectangle((cx - 8, 14, cx + 8, 40), radius=8, fill=color)
    draw.arc((cx - 12, 24, cx + 12, 46), start=20, end=160, fill=(245, 246, 250, 255), width=3)
    draw.line((cx, 46, cx, 52), fill=(245, 246, 250, 255), width=3)
    draw.line((cx - 7, 52, cx + 7, 52), fill=(245, 246, 250, 255), width=3)
    return img


def set_tray_state(status: str):
    icon = state["icon"]
    if icon:
        icon.icon = make_icon_image(STATUS_COLORS.get(status, (92, 98, 117)))
        icon.title = f"Voice Flow V2 - {status}"
    ui.set_status(status)


# Model Management
def ensure_model_loaded():
    with model_lock:
        stt_mode = cfg.get("stt_mode", "local")
        local_model = cfg.get("local_model", "large-v3-turbo")

        # Check if already loaded with identical settings
        if (
            state["transcriber"] is not None
            and state["loaded_mode"] == stt_mode
            and (stt_mode != "local" or state["loaded_model"] == local_model)
        ):
            return

        if stt_mode == "cloud":
            provider = cfg.get("cloud_provider", "openai")
            key_map = {
                "groq": cfg.get("groq_api_key", ""),
                "gemini": cfg.get("gemini_api_key", ""),
                "openai": cfg.get("openai_api_key", ""),
            }
            api_key = key_map.get(provider, "")
            if not api_key:
                raise ValueError(
                    f"Cloud mode '{provider}' requires an API key. Open Settings to configure it."
                )

            cloud_model = cfg.get("cloud_model")
            state["transcriber"] = CloudTranscriber(
                provider=provider,
                model=cloud_model,
                api_key=api_key,
                samplerate=cfg.get("sample_rate", 16000),
            )
            state["loaded_mode"] = "cloud"
            state["loaded_model"] = f"{provider}:{cloud_model}"
            logging.info("Cloud transcriber ready (%s / %s)", provider, cloud_model)
        else:
            # Local faster-whisper
            device = cfg.get("device")
            compute_type = cfg.get("compute_type")
            beam_size = cfg.get("beam_size", 5)

            state["transcriber"] = Transcriber(
                model_size=local_model,
                device=device,
                compute_type=compute_type,
                beam_size=beam_size,
            )
            state["loaded_mode"] = "local"
            state["loaded_model"] = local_model
            logging.info(
                "Local transcriber ready (%s on %s)",
                local_model,
                state["transcriber"].device,
            )


def load_model_worker():
    stt_mode = cfg.get("stt_mode", "local")
    try:
        ui.set_model_status("Loading speech model...")
        ensure_model_loaded()
        if stt_mode == "cloud":
            prov = cfg.get("cloud_provider", "openai")
            ui.set_model_status(f"Cloud Ready ({prov.upper()})")
        else:
            m = cfg.get("local_model", "large-v3-turbo")
            dev = state["transcriber"].device.upper() if state["transcriber"] else "LOCAL"
            ui.set_model_status(f"Model Ready ({m} • {dev})")
    except Exception as exc:
        log_exception("Model loading failed")
        ui.set_model_status("Model failed to load")
        ui.add_transcript(f"[error] {exc}")


def reload_model_async():
    with model_lock:
        state["transcriber"] = None
    threading.Thread(target=load_model_worker, daemon=True).start()


# Recording Triggers
def on_press():
    if state["recording"]:
        return
    logging.info("Recording triggered (Mode: %s)", cfg.get("hotkey_mode", "hold"))
    try:
        recorder.start()
        state["recording"] = True
        hotkey_mgr.set_recording_state(True)
        set_tray_state("recording")
        play_cue("start", cfg.get("sound_cues", True))
    except Exception as exc:
        log_exception("Failed to start recording")
        ui.add_transcript(f"[error] Microphone failed: {exc}")
        play_cue("error", cfg.get("sound_cues", True))


def on_release():
    if not state["recording"]:
        return
    state["recording"] = False
    hotkey_mgr.set_recording_state(False)
    play_cue("stop", cfg.get("sound_cues", True))

    audio = recorder.stop()
    duration = len(audio) / cfg.get("sample_rate", 16000)
    logging.info("Recording captured %.2f seconds", duration)

    if duration < cfg.get("min_duration_sec", 0.3):
        ui.add_transcript(f"[info] Audio too short ({duration:.2f}s) - ignored")
        set_tray_state("idle")
        return

    set_tray_state("transcribing")
    threading.Thread(target=process_audio, args=(audio,), daemon=True).start()


def process_audio(audio):
    try:
        ensure_model_loaded()
        t0 = time.time()
        raw_text = state["transcriber"].transcribe(audio, language=cfg.get("language"))
        transcribe_elapsed = time.time() - t0
        logging.info("Raw transcript (%.2fs): %r", transcribe_elapsed, raw_text)
    except Exception as exc:
        log_exception("Transcription failed")
        ui.add_transcript(f"[error] Transcription failed: {exc}")
        set_tray_state("idle")
        play_cue("error", cfg.get("sound_cues", True))
        return

    if not raw_text or is_hallucination(raw_text):
        logging.info("Ignored silence or hallucination: %r", raw_text)
        ui.add_transcript("[info] No speech detected")
        set_tray_state("idle")
        return

    # Smart Dictation processing
    cleaned_text = process_smart_dictation(
        raw_text,
        enable_smart=cfg.get("smart_dictation", True),
        format_punctuation=cfg.get("format_punctuation", True),
        clean_fillers=cfg.get("clean_fillers", True),
    )

    # Optional AI Polish
    if cfg.get("ai_polish", False):
        try:
            prov = cfg.get("cloud_provider", "openai")
            key_map = {
                "groq": cfg.get("groq_api_key", ""),
                "gemini": cfg.get("gemini_api_key", ""),
                "openai": cfg.get("openai_api_key", ""),
            }
            polished = run_ai_polish(cleaned_text, provider=prov, api_key=key_map.get(prov, ""))
            if polished:
                cleaned_text = polished
        except Exception as exc:
            logging.warning("AI polish failed: %s", exc)

    if not cleaned_text:
        set_tray_state("idle")
        return

    # Add to history and display
    ui.add_transcript(cleaned_text)
    play_cue("success", cfg.get("sound_cues", True))
    set_tray_state("ready")

    # Paste into active window
    paste_text(
        cleaned_text,
        auto_paste=cfg.get("auto_paste", True),
        restore_clipboard=cfg.get("restore_clipboard", True),
    )

    # Return to idle after brief notification
    time.sleep(0.6)
    set_tray_state("idle")


# UI & Settings Callbacks
def on_mode_change_from_ui(new_mode: str):
    if new_mode == cfg.get("stt_mode"):
        return

    if new_mode == "cloud":
        prov = cfg.get("cloud_provider", "openai")
        key_map = {
            "groq": cfg.get("groq_api_key", ""),
            "gemini": cfg.get("gemini_api_key", ""),
            "openai": cfg.get("openai_api_key", ""),
        }
        if not key_map.get(prov, ""):
            ui.add_transcript(f"[Cloud mode needs an API key for {prov} - configure in Settings ⚙]")
            ui.set_mode(cfg.get("stt_mode", "local"))
            return

    cfg["stt_mode"] = new_mode
    save_config(cfg)
    reload_model_async()


def on_settings_saved(new_cfg: dict):
    global cfg
    cfg = new_cfg
    # Update recorder device
    recorder.set_device(cfg.get("input_device_index"))
    # Update hotkey
    hotkey_mgr.update_config(
        cfg.get("hotkey", "ctrl+alt"),
        cfg.get("hotkey_mode", "hold"),
    )
    ui.set_hotkey_label(
        cfg.get("hotkey", "ctrl+alt").upper(),
        cfg.get("hotkey_mode", "hold"),
    )
    # Reload model if engine/model parameters changed
    reload_model_async()


def do_quit():
    icon = state["icon"]
    if icon:
        icon.stop()
    hotkey_mgr.stop()
    ui.request_quit()


def show_widget(_icon=None, _item=None):
    ui.request_show()


def open_settings_from_tray(_icon=None, _item=None):
    ui.request_show()
    # Trigger settings dialog
    ui._root.after(50, lambda: SettingsDialog(ui._root, on_settings_saved=on_settings_saved))


def start_tray():
    icon = Icon(
        "VoiceFlowV2",
        make_icon_image(STATUS_COLORS["idle"]),
        "Voice Flow V2 - Ready",
        Menu(
            MenuItem("Show widget", show_widget),
            MenuItem("Settings...", open_settings_from_tray),
            MenuItem("Quit", lambda icon, item: do_quit()),
        ),
    )
    state["icon"] = icon
    icon.run_detached()


# Hotkey Manager instance
hotkey_mgr = HotkeyManager(
    hotkey_str=cfg.get("hotkey", "ctrl+alt"),
    mode=cfg.get("hotkey_mode", "hold"),
    on_start_record=on_press,
    on_stop_record=on_release,
)

# UI Instance
ui = VoiceFlowUI(
    hotkey_label=cfg.get("hotkey", "ctrl+alt").upper(),
    mode=cfg.get("stt_mode", "local"),
    trigger_mode=cfg.get("hotkey_mode", "hold"),
    on_mode_change=on_mode_change_from_ui,
    on_settings_saved=on_settings_saved,
    on_quit=do_quit,
)
# Connect real-time VU meter callback to the UI
recorder.on_level = ui.update_audio_level


def main():
    logging.info("=" * 50)
    logging.info("Starting Voice Flow V2")
    logging.info("Log path: %s", LOG_PATH)
    logging.info("Config: %s", cfg)

    # Start background model loading
    reload_model_async()

    # Start global hotkey listener
    hotkey_mgr.start()

    # Start system tray icon
    start_tray()

    # Run UI mainloop (blocks until quit)
    ui.start()


if __name__ == "__main__":
    main()
