import io
import wave

import numpy as np
from openai import OpenAI


class CloudTranscriber:
    """Sends audio to OpenAI's transcription API for higher accuracy (requires internet + API key)."""

    def __init__(self, model="gpt-4o-transcribe", api_key=None, samplerate=16000):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.samplerate = samplerate

    def transcribe(self, audio, language=None):
        wav_file = self._to_wav_file(audio)
        kwargs = {"model": self.model, "file": wav_file}
        if language:
            kwargs["language"] = language
        response = self.client.audio.transcriptions.create(**kwargs)
        return response.text.strip()

    def _to_wav_file(self, audio):
        pcm16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.samplerate)
            wf.writeframes(pcm16.tobytes())
        buf.seek(0)
        buf.name = "audio.wav"  # the OpenAI SDK needs a filename to infer the format
        return buf
