"""Multimodal transcription and visual description provider."""

from __future__ import annotations

from pathlib import Path

from Backend.config import Settings


class MultimodalTranscriber:
    """Transcribe or describe transient media with a multimodal model."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def enabled(self) -> bool:
        """Whether multimodal transcription is configured."""
        return bool(
            self.settings.meta_model_base_url
            and self.settings.meta_model_api_key
            and self.settings.meta_model_name
            and not self.settings.meta_model_contributor_tier
        )

    def transcribe(self, media: Path, *, visual: bool = False) -> str | None:
        """Transcribe audio/video or describe images through the model."""
        if not self.enabled:
            return None
        import httpx

        prompt = (
            "Describe the important visual content in detail."
            if visual
            else "Transcribe all speech verbatim. Return only the transcript."
        )
        with media.open("rb") as handle:
            response = httpx.post(
                f"{self.settings.meta_model_base_url.rstrip('/')}/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.settings.meta_model_api_key}"},
                data={"model": self.settings.meta_model_name, "prompt": prompt},
                files={"file": (media.name, handle, "application/octet-stream")},
                timeout=180,
            )
        response.raise_for_status()
        payload = response.json()
        text = payload.get("text") if isinstance(payload, dict) else None
        return text.strip() if isinstance(text, str) and text.strip() else None
