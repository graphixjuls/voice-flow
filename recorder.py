import threading

import numpy as np
import sounddevice as sd


class Recorder:
    """Records microphone audio into memory while active."""

    def __init__(self, samplerate=16000, channels=1):
        self.samplerate = samplerate
        self.channels = channels
        self._frames = []
        self._stream = None
        self._lock = threading.Lock()

    def _callback(self, indata, frames, time_info, status):
        with self._lock:
            self._frames.append(indata.copy())

    def start(self):
        with self._lock:
            self._frames = []
        self._stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def stop(self):
        """Stops recording and returns the captured audio as a 1D float32 array."""
        if self._stream is None:
            return np.zeros((0,), dtype="float32")
        self._stream.stop()
        self._stream.close()
        self._stream = None
        with self._lock:
            if not self._frames:
                return np.zeros((0,), dtype="float32")
            audio = np.concatenate(self._frames, axis=0)
        return audio.flatten()
