import logging
import threading
import time
from typing import Optional

import keyboard
import pyperclip


def _restore_clipboard_worker(previous_content: Optional[str], delay: float = 0.5):
    if previous_content is None:
        return
    time.sleep(delay)
    try:
        pyperclip.copy(previous_content)
    except Exception as exc:
        logging.debug("Failed to restore clipboard: %s", exc)


def paste_text(
    text: str,
    auto_paste: bool = True,
    restore_clipboard: bool = True,
) -> bool:
    """Copies text to clipboard and pastes it into the currently focused window."""
    if not text:
        return False

    previous_clipboard = None
    if restore_clipboard:
        try:
            previous_clipboard = pyperclip.paste()
        except Exception:
            previous_clipboard = None

    try:
        pyperclip.copy(text)
    except Exception as exc:
        logging.error("Failed to copy to clipboard: %s", exc)
        return False

    if not auto_paste:
        logging.info("Text copied to clipboard (auto-paste disabled).")
        return True

    # Ensure modifier keys from push-to-talk are not considered held by the OS
    for key in ("ctrl", "alt", "shift", "win"):
        try:
            keyboard.release(key)
        except Exception:
            pass

    time.sleep(0.08)

    try:
        keyboard.send("ctrl+v")
        logging.info("Pasted text into focused window.")
    except Exception as exc:
        logging.warning("ctrl+v failed (%s), attempting direct keyboard write fallback", exc)
        try:
            keyboard.write(text)
        except Exception as write_exc:
            logging.error("Direct write fallback also failed: %s", write_exc)
            return False

    if restore_clipboard and previous_clipboard is not None:
        # Restore asynchronously with generous 500ms delay so target app has read the clipboard
        threading.Thread(
            target=_restore_clipboard_worker,
            args=(previous_clipboard, 0.5),
            daemon=True,
        ).start()

    return True
