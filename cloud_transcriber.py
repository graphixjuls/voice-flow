import base64
import io
import json
import logging
import wave
from typing import Optional

import numpy as np

DEFAULT_PROMPT = (
    "Clear speech dictation with proper punctuation, capitalization, contractions, and formatting."
)


class CloudTranscriber:
    """Sends audio to OpenAI, Groq, or Google Gemini API for high-accuracy cloud transcription."""

    def __init__(
        self,
        provider: str = "openai",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        samplerate: int = 16000,
    ):
        self.provider = provider.lower()
        self.api_key = api_key
        self.samplerate = samplerate

        if not model:
            if self.provider == "groq":
                self.model = "whisper-large-v3"
            elif self.provider == "gemini":
                self.model = "gemini-2.5-flash"
            else:
                self.model = "whisper-1"
        else:
            # Fix legacy invalid model name if present in old configs
            if model == "gpt-4o-transcribe":
                self.model = "whisper-1"
            else:
                self.model = model

        if not self.api_key:
            raise ValueError(f"No API key provided for cloud provider '{self.provider}'.")

        # Set up client if OpenAI or Groq
        if self.provider in ("openai", "groq"):
            from openai import OpenAI

            base_url = "https://api.groq.com/openai/v1" if self.provider == "groq" else None
            self.client = OpenAI(api_key=self.api_key, base_url=base_url)

    def transcribe(self, audio: np.ndarray, language: Optional[str] = None) -> str:
        if len(audio) == 0:
            return ""

        wav_buf = self._to_wav_buffer(audio)

        if self.provider in ("openai", "groq"):
            return self._transcribe_openai_compatible(wav_buf, language)
        elif self.provider == "gemini":
            return self._transcribe_gemini(wav_buf, language)
        else:
            raise ValueError(f"Unsupported cloud provider: '{self.provider}'")

    def _transcribe_openai_compatible(self, wav_buf: io.BytesIO, language: Optional[str]) -> str:
        wav_buf.seek(0)
        wav_buf.name = "audio.wav"
        kwargs = {
            "model": self.model,
            "file": wav_buf,
            "prompt": DEFAULT_PROMPT,
        }
        if language:
            kwargs["language"] = language

        response = self.client.audio.transcriptions.create(**kwargs)
        return response.text.strip()

    def _transcribe_gemini(self, wav_buf: io.BytesIO, language: Optional[str]) -> str:
        import requests

        wav_bytes = wav_buf.getvalue()
        b64_audio = base64.b64encode(wav_bytes).decode("utf-8")

        prompt_text = (
            "You are a professional speech-to-text transcriber. "
            "Transcribe the provided audio accurately with proper punctuation, capitalization, and formatting. "
            "Do not add any preamble, explanation, or commentary. Return ONLY the transcribed text."
        )
        if language:
            prompt_text += f" The spoken language is {language}."

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt_text},
                        {
                            "inlineData": {
                                "mimeType": "audio/wav",
                                "data": b64_audio,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.0,
            },
        }

        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"Gemini API error ({resp.status_code}): {resp.text}")

        data = resp.json()
        cand = data.get("candidates", [{}])[0]
        text_parts = cand.get("content", {}).get("parts", [{}])
        transcript = "".join(p.get("text", "") for p in text_parts).strip()
        return transcript

    def _to_wav_buffer(self, audio: np.ndarray) -> io.BytesIO:
        pcm16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.samplerate)
            wf.writeframes(pcm16.tobytes())
        buf.seek(0)
        return buf
