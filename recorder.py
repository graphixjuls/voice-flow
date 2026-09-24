import logging
import threading
import time
from typing import Callable, List, Optional, Tuple

import numpy as np
import sounddevice as sd


def list_input_devices() -> List[Tuple[int, str]]:
    """Returns a list of available audio input devices as (index, display_name)."""
    devices = []
    try:
        dev_list = sd.query_devices()
        for idx, dev in enumerate(dev_list):
            if dev.get("max_input_channels", 0) > 0:
                raw_name = dev.get("name", f"Microphone {idx}")
                # Clean up encoding artifacts safely
                name = raw_name.encode("utf-8", errors="replace").decode("utf-8")
                devices.append((idx, name))
    except Exception as exc:
        logging.warning("Error querying audio input devices: %s", exc)
    return devices


class Recorder:
    """Records microphone audio with real-time level feedback and gain normalization."""

    def __init__(
        self,
        samplerate: int = 16000,
        channels: int = 1,
        device: Optional[int] = None,
        on_level: Optional[Callable[[float], None]] = None,
    ):
        self.samplerate = samplerate
        self.channels = channels
        self.device = device
        self.on_level = on_level

        self._frames = []
        self._stream = None
        self._lock = threading.Lock()
        self._is_recording = False
        self._last_level_time = 0.0

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def set_device(self, device_index: Optional[int]):
        with self._lock:
            self.device = device_index

    def _callback(self, indata, frames, time_info, status):
        if status:
            logging.debug("Audio stream status: %s", status)
        with self._lock:
            self._frames.append(indata.copy())

        # Throttle on_level callback to max ~30 FPS (every 33ms) to prevent UI event loop flooding
        now = time.time()
        if self.on_level and (now - self._last_level_time >= 0.033):
            self._last_level_time = now
            try:
                # Calculate Root Mean Square (RMS)
                rms = float(np.sqrt(np.mean(np.square(indata))))
                # Scale RMS to [0.0, 1.0] for the VU meter (typical speech rms is 0.01 - 0.25)
                level = min(1.0, max(0.0, rms * 5.5))
                self.on_level(level)
            except Exception:
                pass

    def start(self):
        with self._lock:
            if self._is_recording:
                return
            self._frames = []

        try:
            self._stream = sd.InputStream(
                samplerate=self.samplerate,
                channels=self.channels,
                dtype="float32",
                device=self.device,
                callback=self._callback,
            )
            self._stream.start()
            self._is_recording = True
        except Exception as exc:
            # If specified device fails (e.g., unplugged USB mic), fallback to default device
            if self.device is not None:
                logging.warning(
                    "Failed to open device %s (%s). Falling back to system default.",
                    self.device,
                    exc,
                )
                self.device = None
                self._stream = sd.InputStream(
                    samplerate=self.samplerate,
                    channels=self.channels,
                    dtype="float32",
                    device=None,
                    callback=self._callback,
                )
                self._stream.start()
                self._is_recording = True
            else:
                raise exc

    def stop(self) -> np.ndarray:
        """Stops recording and returns gain-normalized 1D float32 audio array."""
        with self._lock:
            self._is_recording = False
            stream = self._stream
            self._stream = None

        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass

        if self.on_level:
            try:
                self.on_level(0.0)
            except Exception:
                pass

        with self._lock:
            if not self._frames:
                return np.zeros((0,), dtype="float32")
            audio = np.concatenate(self._frames, axis=0).flatten()
            self._frames = []

        # Audio Gain Normalization: softly spoken audio often causes Whisper to miss words.
        # Normalize to target peak if within speech range.
        peak = float(np.max(np.abs(audio))) if len(audio) > 0 else 0.0
        if 0.01 < peak < 0.85:
            gain = min(0.95 / peak, 5.0)  # Max 5x boost to prevent amplifying faint background noise
            audio = audio * gain

        return audio.astype("float32")
