"""Multimodal transcription and visual description provider."""

from __future__ import annotations

import logging
from pathlib import Path

from Backend.config import Settings
from Backend.errors import DomainError


log = logging.getLogger(__name__)


def _response_text(payload: object) -> str | None:
    """Extract assistant text from a Responses API payload."""
    if not isinstance(payload, dict):
        return None
    for item in payload.get("output", []) or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for part in item.get("content", []) or []:
            if isinstance(part, dict) and part.get("type") == "output_text":
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    return text.strip()
    return None


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
            log.info("multimodal: provider not configured, skipping")
            return None
        import httpx

        base = self.settings.meta_model_base_url.rstrip("/")

        log.info("multimodal: uploading media size=%d", media.stat().st_size)
        headers = {"Authorization": f"Bearer {self.settings.meta_model_api_key}"}
        prompt = (
            "Describe the important visual content in detail, prefixing each described segment with its [MM:SS] timestamp."
            if visual
            else "Transcribe all speech verbatim with an [MM:SS] timestamp prefix on each spoken segment. Return only the timestamped transcript."
        )
        with media.open("rb") as handle:
            upload = httpx.post(
                f"{base}/files",
                headers=headers,
                data={"purpose": "user_data"},
                files={"file": (media.name, handle, "video/mp4")},
                timeout=180,
            )
        try:
            upload.raise_for_status()
        except Exception as exc:
            raise DomainError("llm_unavailable", "Cloud file upload failed") from exc
        file_id = self._file_id(upload.json())
        if not file_id:
            raise DomainError("llm_unavailable", "Cloud file upload failed")
        try:
            self._wait_for_file(headers, base, file_id)
            response = httpx.post(
                f"{base}/responses",
                headers=headers,
                json={
                    "model": self.settings.meta_model_name,
                    "input": [
                        {
                            "type": "message",
                            "role": "user",
                            "content": [
                                {"type": "input_text", "text": prompt},
                                {"type": "input_file", "file_id": file_id},
                            ],
                        }
                    ],
                },
                timeout=180,
            )
            try:
                response.raise_for_status()
            except Exception as exc:
                raise DomainError("llm_unavailable", "Cloud transcription failed") from exc
            text = _response_text(response.json())
            if not text:
                raise DomainError("llm_unavailable", "Cloud transcription failed")
            return text
        finally:
            try:
                httpx.delete(f"{base}/files/{file_id}", headers=headers, timeout=60)
            except Exception:
                pass

    @staticmethod
    def _file_id(payload: object) -> str | None:
        """Extract a file identifier from an upload response."""
        if isinstance(payload, dict):
            for key in ("id", "file_id", "fileId"):
                value = payload.get(key)
                if isinstance(value, str) and value:
                    return value
            data = payload.get("data")
            if isinstance(data, dict):
                for key in ("id", "file_id", "fileId"):
                    value = data.get(key)
                    if isinstance(value, str) and value:
                        return value
        return None

    @staticmethod
    def _wait_for_file(headers: dict, base: str, file_id: str) -> None:
        """Check that the uploaded file is registered."""
        import httpx

        response = httpx.get(f"{base}/files/{file_id}", headers=headers, timeout=60)
        try:
            response.raise_for_status()
        except Exception as exc:
            raise DomainError("llm_unavailable", "Cloud file status check failed") from exc
        payload = response.json()
        file_object = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(file_object, dict):
            payload = file_object
        if not isinstance(payload, dict) or not payload.get("id"):
            raise DomainError("llm_unavailable", "Cloud file status check failed")
