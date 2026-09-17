import logging
import os
import sys
import threading
import time
import traceback

import keyboard
import pyperclip
from PIL import Image, ImageDraw
from pystray import Icon, Menu, MenuItem

from recorder import Recorder
from transcriber import Transcriber
from ui import VoiceFlowUI

LOG_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "VoiceFlow")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, "voiceflow.log")
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


def log_exception(context):
    logging.error("%s\n%s", context, traceback.format_exc())

HOTKEY_KEYS = ("ctrl", "alt")  # hold all of these together to talk, release to transcribe & paste
SAMPLE_RATE = 16000
MIN_DURATION_SEC = 0.3
LANGUAGE = None  # e.g. "en" to force English, or None to auto-detect

STT_MODE = "local"  # "local" (offline, faster-whisper) or "cloud" (online, OpenAI - more accurate)
MODEL_SIZE = "base"  # used when STT_MODE == "local": tiny / base / small / medium / large-v3
CLOUD_MODEL = "gpt-4o-transcribe"  # used when STT_MODE == "cloud"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

recorder = Recorder(samplerate=SAMPLE_RATE)
transcriber = None
state = {"recording": False, "icon": None}
model_lock = threading.Lock()
ui = VoiceFlowUI(
    hotkey_label="+".join(k.upper() for k in HOTKEY_KEYS),
    mode=STT_MODE,
    on_mode_change=lambda new_mode: on_mode_change(new_mode),
    on_quit=lambda: do_quit(),
)


TRAY_BG = (23, 24, 29, 255)


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


STATUS_COLORS = {
    "idle": (91, 96, 114),
    "recording": (255, 92, 92),
    "transcribing": (255, 181, 69),
}


def set_tray_state(status):
    icon = state["icon"]
    if icon:
        icon.icon = make_icon_image(STATUS_COLORS.get(status, (90, 90, 90)))
        icon.title = f"Voice Flow - {status}"
    ui.set_status(status)


def ensure_model_loaded():
    global transcriber
    with model_lock:
        if transcriber is not None:
            return
        if STT_MODE == "cloud":
            if not OPENAI_API_KEY:
                raise RuntimeError(
                    "STT_MODE is 'cloud' but the OPENAI_API_KEY environment variable is not set."
                )
            from cloud_transcriber import CloudTranscriber

            transcriber = CloudTranscriber(
                model=CLOUD_MODEL, api_key=OPENAI_API_KEY, samplerate=SAMPLE_RATE
            )
        else:
            transcriber = Transcriber(model_size=MODEL_SIZE)


def load_model_and_report():
    try:
        ensure_model_loaded()
        ui.set_model_status(f"Model ready ({STT_MODE})")
    except Exception as exc:
        log_exception("Model load failed")
        ui.set_model_status("Model failed to load")
        ui.add_transcript(f"[error] {exc}")


def on_mode_change(new_mode):
    global STT_MODE, transcriber
    if new_mode == STT_MODE:
        return
    if new_mode == "cloud" and not OPENAI_API_KEY:
        ui.add_transcript("[Cloud mode needs OPENAI_API_KEY - staying on local]")
        ui.set_mode(STT_MODE)
        return
    STT_MODE = new_mode
    with model_lock:
        transcriber = None
    ui.set_model_status("Loading model...")
    threading.Thread(target=load_model_and_report, daemon=True).start()


def on_press():
    if state["recording"]:
        return
    logging.info("Hotkey pressed - starting recording")
    try:
        recorder.start()
    except Exception as exc:
        log_exception("Failed to start recording")
        ui.add_transcript(f"[error] Could not start microphone: {exc}")
        return
    state["recording"] = True
    set_tray_state("recording")


def on_release():
    if not state["recording"]:
        return
    state["recording"] = False
    audio = recorder.stop()
    duration = len(audio) / SAMPLE_RATE
    logging.info("Hotkey released - captured %.2fs of audio", duration)
    if duration < MIN_DURATION_SEC:
        ui.add_transcript(f"[info] Recording too short ({duration:.2f}s) - ignored")
        set_tray_state("idle")
        return
    set_tray_state("transcribing")
    threading.Thread(target=process_audio, args=(audio,), daemon=True).start()


def check_hotkey_combo(_event=None):
    try:
        all_down = all(keyboard.is_pressed(key) for key in HOTKEY_KEYS)
        if all_down and not state["recording"]:
            on_press()
        elif not all_down and state["recording"]:
            on_release()
    except Exception:
        log_exception("check_hotkey_combo failed")


def process_audio(audio):
    try:
        ensure_model_loaded()
        text = transcriber.transcribe(audio, language=LANGUAGE)
    except Exception as exc:
        log_exception(f"Transcription failed ({STT_MODE} mode)")
        ui.add_transcript(f"[error] Transcription failed: {exc}")
        set_tray_state("idle")
        return

    set_tray_state("idle")
    logging.info("Transcribed text: %r", text)
    if not text:
        ui.add_transcript("[info] No speech detected in that recording")
        return

    ui.add_transcript(text)

    try:
        previous_clipboard = pyperclip.paste()
    except Exception:
        previous_clipboard = None

    try:
        pyperclip.copy(text)
        # The hotkey itself is ctrl+alt; make sure those fully register as
        # released before sending ctrl+v, otherwise the OS can still see one
        # of them held and this lands as ctrl+alt+v, which most apps ignore.
        keyboard.release("ctrl+alt")
        time.sleep(0.15)
        keyboard.send("ctrl+v")
        logging.info("Pasted transcribed text into the focused window")
    except Exception as exc:
        log_exception("Failed to paste transcribed text")
        ui.add_transcript(f"[error] Could not paste text: {exc}")
    finally:
        if previous_clipboard is not None:
            time.sleep(0.3)
            pyperclip.copy(previous_clipboard)


def do_quit():
    icon = state["icon"]
    if icon:
        icon.stop()
    ui.request_quit()


def show_widget(_icon=None, _item=None):
    ui.request_show()


def quit_app(icon, _item):
    do_quit()


def start_tray():
    icon = Icon(
        "VoiceFlow",
        make_icon_image(STATUS_COLORS["idle"]),
        "Voice Flow - idle",
        Menu(MenuItem("Show widget", show_widget), MenuItem("Quit", quit_app)),
    )
    state["icon"] = icon
    icon.run_detached()


def main():
    combo_label = "+".join(k.upper() for k in HOTKEY_KEYS)
    logging.info("Voice Flow starting up (log file: %s)", LOG_PATH)
    threading.Thread(target=load_model_and_report, daemon=True).start()

    try:
        keyboard.hook(check_hotkey_combo)
    except Exception as exc:
        log_exception("Failed to install global hotkey hook")
        ui.add_transcript(f"[error] Hotkey hook failed: {exc}")

    start_tray()
    ui.start()  # blocks in the Tk main loop until quit


if __name__ == "__main__":
    main()
