import threading
import winsound


def _play_start_tone():
    try:
        winsound.Beep(587, 50)  # D5
        winsound.Beep(880, 70)  # A5
    except Exception:
        pass


def _play_stop_tone():
    try:
        winsound.Beep(784, 50)  # G5
        winsound.Beep(523, 70)  # C5
    except Exception:
        pass


def _play_success_tone():
    try:
        winsound.Beep(659, 40)  # E5
        winsound.Beep(880, 60)  # A5
    except Exception:
        pass


def _play_error_tone():
    try:
        winsound.Beep(330, 120)
    except Exception:
        pass


def play_cue(cue_type: str, enabled: bool = True):
    """Plays non-blocking sound cue in a daemon thread."""
    if not enabled:
        return

    targets = {
        "start": _play_start_tone,
        "stop": _play_stop_tone,
        "success": _play_success_tone,
        "error": _play_error_tone,
    }
    target = targets.get(cue_type)
    if target:
        threading.Thread(target=target, daemon=True).start()
