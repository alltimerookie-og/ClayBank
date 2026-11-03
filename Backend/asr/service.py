"""Transcription service using multimodal transcription only."""

from __future__ import annotations

from pathlib import Path

from Backend.asr.multimodal import MultimodalTranscriber
from Backend.config import Settings, load_settings


class TranscriptionService:
    """Transcribe media through the configured multimodal model."""

    def __init__(
        self,
        settings: Settings | None = None,
        multimodal: MultimodalTranscriber | None = None,
    ) -> None:
        self.settings = settings or load_settings()
        self.multimodal = multimodal or MultimodalTranscriber(self.settings)

    def transcribe(self, media: Path | None, *, visual: bool = False) -> tuple[str | None, str]:
        """Transcribe media and report the multimodal provider result."""
        if media is None or not media.exists():
            return None, "unavailable"
        if self.settings.meta_model_contributor_tier:
            raise ValueError("Contributor training tier is forbidden")
        text = self.multimodal.transcribe(media, visual=visual)
        return (text, "multimodal") if text else (None, "unavailable")
