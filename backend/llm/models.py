"""Structured output models and results for cloud LLM note generation (ADR 0005, Phase 4)."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


class LinkItem(BaseModel):
    """Structured link mentioned in note content, adhering to Docs/api/schemas/note.json."""

    url: str = Field(..., description="Target web link URL")
    anchor_text: str = Field(..., description="Descriptive anchor label")
    jump_target: str | None = Field(default=None, description="Optional timestamp (e.g. '0:42') or heading slug")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        cleaned = v.strip() if isinstance(v, str) else ""
        if not cleaned:
            raise ValueError("Link URL cannot be empty")
        parsed = urlparse(cleaned)
        if parsed.scheme.lower() not in ("http", "https"):
            raise ValueError(f"Link URL scheme must be http or https, got '{parsed.scheme}'")
        if not parsed.netloc:
            raise ValueError("Link URL missing hostname")
        return cleaned

    @field_validator("anchor_text")
    @classmethod
    def validate_anchor(cls, v: str) -> str:
        cleaned = re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else ""
        return cleaned or "Link"


class NoteStructuredOutput(BaseModel):
    """Guaranteed structured sections produced by LLM note generation."""

    overview: str = Field(..., description="Executive summary of the save")
    key_points: list[str] = Field(..., description="Core bullet takeaways")
    links: list[LinkItem] = Field(default_factory=list, description="Links mentioned with anchor text")

    @field_validator("overview")
    @classmethod
    def validate_overview(cls, v: str) -> str:
        cleaned = v.strip() if isinstance(v, str) else ""
        if not cleaned:
            raise ValueError("Overview cannot be empty")
        return cleaned

    @field_validator("key_points")
    @classmethod
    def validate_key_points(cls, v: list[Any]) -> list[str]:
        cleaned_points: list[str] = []
        for p in v:
            if isinstance(p, str):
                s = p.strip().lstrip("-*• ").strip()
                if s:
                    cleaned_points.append(s)
        if not cleaned_points:
            raise ValueError("At least one key point is required")
        return cleaned_points


class NoteGenerationResult(BaseModel):
    """Typed execution outcome of note generation."""

    is_success: bool = Field(default=True, description="Whether generation succeeded")
    structured_output: NoteStructuredOutput | None = Field(default=None, description="Parsed structured note sections")
    raw_text: str | None = Field(default=None, description="Raw completion text from provider")
    provider: str = Field(default="meta", description="Provider identifier")
    model: str = Field(default="gpt-oss-120b", description="Model identifier")
    tokens_used: int = Field(default=0, description="Total tokens consumed")
    error_category: str | None = Field(default=None, description="Safe error category if failed")
