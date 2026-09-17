from faster_whisper import WhisperModel


class Transcriber:
    """Wraps a local faster-whisper model for speech-to-text."""

    def __init__(self, model_size="base", device="cpu", compute_type="int8"):
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(self, audio, language=None):
        segments, _info = self.model.transcribe(audio, language=language, vad_filter=True)
        return "".join(segment.text for segment in segments).strip()
