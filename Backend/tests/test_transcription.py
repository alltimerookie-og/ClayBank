"""Focused tests for multimodal-only transcription."""

from pathlib import Path

from Backend.asr.service import TranscriptionService
from Backend.config import Settings


class FailingProvider:
    """Provider that never returns text."""

    def transcribe(self, media: Path, **kwargs) -> str | None:
        """Simulate an unavailable provider."""
        del media, kwargs
        return None


class TextProvider:
    """Provider that returns fixed text."""

    def __init__(self, text: str) -> None:
        self.text = text

    def transcribe(self, media: Path, **kwargs) -> str | None:
        """Return fixed transcription text."""
        del media, kwargs
        return self.text


def test_multimodal_transcription_only(tmp_path: Path) -> None:
    """Multimodal transcription returns text without local fallback."""
    media = tmp_path / "source.m4a"
    media.write_bytes(b"fake audio")
    service = TranscriptionService(
        settings=Settings(),
        multimodal=TextProvider("multimodal transcript"),
    )
    assert service.transcribe(media) == ("multimodal transcript", "multimodal")


def test_multimodal_unavailable_returns_unavailable(tmp_path: Path) -> None:
    """Multimodal failure has no local fallback."""
    media = tmp_path / "source.m4a"
    media.write_bytes(b"fake audio")
    service = TranscriptionService(
        settings=Settings(),
        multimodal=FailingProvider(),
    )
    assert service.transcribe(media) == (None, "unavailable")
