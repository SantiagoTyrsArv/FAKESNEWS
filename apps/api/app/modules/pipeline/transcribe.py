import asyncio
from typing import Protocol

from app.core.config import get_settings

settings = get_settings()


class Transcriber(Protocol):
    async def transcribe(self, audio_path: str) -> str: ...


class FasterWhisperTranscriber:
    """Transcribes an audio file to text using faster-whisper.

    The model is loaded lazily (first call) and cached on the instance,
    since loading is the expensive part and a worker process only needs one.
    """

    def __init__(self, model_size: str | None = None) -> None:
        self._model_size = model_size or settings.whisper_model_size
        self._model = None

    def _get_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(self._model_size, device="cpu", compute_type="int8")
        return self._model

    def _transcribe_sync(self, audio_path: str) -> str:
        model = self._get_model()
        segments, _info = model.transcribe(audio_path)
        return " ".join(segment.text.strip() for segment in segments).strip()

    async def transcribe(self, audio_path: str) -> str:
        return await asyncio.to_thread(self._transcribe_sync, audio_path)
