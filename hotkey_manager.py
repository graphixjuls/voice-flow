import logging
import threading
from typing import Callable, List, Optional

import keyboard


class HotkeyManager:
    """Manages global hotkey listening for both Push-to-Talk (Hold) and Toggle modes."""

    def __init__(
        self,
        hotkey_str: str = "ctrl+alt",
        mode: str = "hold",  # "hold" or "toggle"
        on_start_record: Optional[Callable[[], None]] = None,
        on_stop_record: Optional[Callable[[], None]] = None,
    ):
        self.hotkey_str = hotkey_str.lower().strip()
        self.mode = mode.lower().strip()
        self.on_start_record = on_start_record
        self.on_stop_record = on_stop_record

        self._keys: List[str] = [k.strip() for k in self.hotkey_str.split("+") if k.strip()]
        self._was_down = False
        self._is_recording = False
        self._lock = threading.Lock()
        self._hooked = False

    def update_config(self, hotkey_str: str, mode: str):
        """Updates hotkey keys and mode dynamically."""
        with self._lock:
            self.hotkey_str = hotkey_str.lower().strip()
            self.mode = mode.lower().strip()
            self._keys = [k.strip() for k in self.hotkey_str.split("+") if k.strip()]
            self._was_down = False

    def set_recording_state(self, recording: bool):
        with self._lock:
            self._is_recording = recording

    def _on_key_event(self, _event):
        try:
            with self._lock:
                if not self._keys:
                    return

                all_down = all(keyboard.is_pressed(k) for k in self._keys)

                if all_down and not self._was_down:
                    # Hotkey combo just transitioned to DOWN
                    self._was_down = True
                    if self.mode == "toggle":
                        if self._is_recording:
                            if self.on_stop_record:
                                self.on_stop_record()
                        else:
                            if self.on_start_record:
                                self.on_start_record()
                    else:
                        # Hold mode
                        if not self._is_recording and self.on_start_record:
                            self.on_start_record()

                elif not all_down and self._was_down:
                    # Hotkey combo released
                    self._was_down = False
                    if self.mode == "hold":
                        if self._is_recording and self.on_stop_record:
                            self.on_stop_record()

        except Exception as exc:
            logging.debug("Hotkey evaluation exception: %s", exc)

    def start(self):
        with self._lock:
            if self._hooked:
                return
            try:
                keyboard.hook(self._on_key_event)
                self._hooked = True
                logging.info(
                    "Global hotkey hook active: '%s' (mode: %s)",
                    self.hotkey_str,
                    self.mode,
                )
            except Exception as exc:
                logging.error("Failed to install global keyboard hook: %s", exc)

    def stop(self):
        with self._lock:
            if not self._hooked:
                return
            try:
                keyboard.unhook(self._on_key_event)
                self._hooked = False
            except Exception:
                pass
