"""ASR protocols defining provider seams for audio transcription (Rules.md §8)."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class ASRProvider(Protocol):
    """Protocol for audio transcription engines (Muse Voice cloud / faster-whisper local)."""

    async def transcribe(self, audio_path: Path, language: str | None = None) -> str:
        """Transcribe a temporary audio file and return plain transcript text.

        Args:
            audio_path: Path to the local temporary audio file.
            language: Optional language hint (e.g. 'en', 'es').

        Returns:
            Plain text transcript.

        Raises:
            Exception: If transcription fails or service is unavailable.
        """
        ...
