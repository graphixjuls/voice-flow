import logging
from typing import Optional
import numpy as np
from faster_whisper import WhisperModel

from config import has_cuda
from cuda_setup import setup_cuda_dlls

# Register CUDA DLL search paths early
setup_cuda_dlls()

DEFAULT_PROMPT = (
    "Hello, this is clear, professional speech with accurate punctuation, "
    "proper capitalization, contractions, and formatting."
)

MODEL_ALIASES = {
    "large-v3-turbo": "distil-large-v3",
}


class Transcriber:
    """Wraps a local faster-whisper model optimized for speed and accuracy with CUDA support."""

    def __init__(
        self,
        model_size: str = "distil-large-v3",
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
        beam_size: int = 5,
    ):
        setup_cuda_dlls()

        if device is None:
            device = "cuda" if has_cuda() else "cpu"

        if compute_type is None:
            compute_type = "float16" if device == "cuda" else "int8"

        self.model_size = MODEL_ALIASES.get(model_size, model_size)
        self.device = device
        self.compute_type = compute_type
        self.beam_size = beam_size

        logging.info(
            "Initializing faster-whisper model '%s' on %s (%s)...",
            self.model_size,
            device,
            compute_type,
        )

        self._load_model()

    def _load_model(self):
        try:
            self.model = WhisperModel(
                model_size_or_path=self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            # If using CUDA, probe execution to ensure DLLs (cublas, cudnn) are actually loadable
            if self.device == "cuda":
                try:
                    dummy_audio = np.zeros(160, dtype=np.float32)
                    _ = list(self.model.transcribe(dummy_audio, beam_size=1, vad_filter=False)[0])
                    logging.info("CUDA GPU execution verified successfully.")
                except Exception as cuda_exc:
                    logging.warning(
                        "CUDA probe failed (%s). Falling back to CPU int8.", cuda_exc
                    )
                    self.device = "cpu"
                    self.compute_type = "int8"
                    self.model = WhisperModel(
                        model_size_or_path=self.model_size,
                        device="cpu",
                        compute_type="int8",
                    )
        except Exception as exc:
            # If target model failed (e.g. offline download), fallback to base
            if self.model_size != "base":
                logging.warning(
                    "Failed to load '%s' (%s). Falling back to 'base'.",
                    self.model_size,
                    exc,
                )
                self.model_size = "base"
                self.model = WhisperModel(
                    model_size_or_path="base",
                    device=self.device,
                    compute_type=self.compute_type,
                )
            elif self.device == "cuda":
                logging.warning("CUDA initialization failed (%s). Falling back to CPU int8.", exc)
                self.device = "cpu"
                self.compute_type = "int8"
                self.model = WhisperModel(
                    model_size_or_path="base",
                    device="cpu",
                    compute_type="int8",
                )
            else:
                raise exc

    def transcribe(
        self,
        audio: np.ndarray,
        language: Optional[str] = None,
        beam_size: Optional[int] = None,
        initial_prompt: Optional[str] = DEFAULT_PROMPT,
    ) -> str:
        """Transcribes audio array with tuned VAD, beam search, and prompt conditioning."""
        if len(audio) == 0:
            return ""

        # If audio is completely silent, skip transcription
        if float(np.max(np.abs(audio))) < 0.005:
            return ""

        bs = beam_size if beam_size is not None else self.beam_size

        # Tuned Silero VAD parameters to avoid clipping words at the start or end of audio
        vad_params = dict(
            min_silence_duration_ms=400,
            speech_pad_ms=250,
            threshold=0.45,
        )

        try:
            segments, _info = self.model.transcribe(
                audio,
                language=language,
                beam_size=bs,
                vad_filter=True,
                vad_parameters=vad_params,
                condition_on_previous_text=False,  # Prevents repetitive loop hallucinations
                initial_prompt=initial_prompt,     # Primes punctuation and capitalization
                temperature=[0.0, 0.2, 0.4],
            )
            result_text = "".join(segment.text for segment in segments).strip()
            return result_text
        except RuntimeError as exc:
            err_msg = str(exc).lower()
            if "cublas" in err_msg or "cudnn" in err_msg or "cannot be loaded" in err_msg:
                logging.warning("CUDA runtime failure during transcribe (%s). Falling back to CPU.", exc)
                self.device = "cpu"
                self.compute_type = "int8"
                self.model = WhisperModel(
                    model_size_or_path=self.model_size,
                    device="cpu",
                    compute_type="int8",
                )
                segments, _info = self.model.transcribe(
                    audio,
                    language=language,
                    beam_size=bs,
                    vad_filter=True,
                    vad_parameters=vad_params,
                    condition_on_previous_text=False,
                    initial_prompt=initial_prompt,
                    temperature=[0.0, 0.2, 0.4],
                )
                return "".join(segment.text for segment in segments).strip()
            raise exc
        except ValueError as exc:
            # Handles faster-whisper's VAD filtering 100% of silence before language detection
            if "empty sequence" in str(exc) or "max()" in str(exc):
                return ""
            raise exc
