"""Extraction result contracts derived from Docs/api/schemas/extraction-result.json (Rules.md).

Models extraction metadata, capability flags, and processing outcomes across
tier 1 (deterministic) and tier 2 (agent rescue) pipelines.
"""
from __future__ import annotations

import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.contracts.enums import Kind


class CapabilityFlags(BaseModel):
    """Media capability flags for a captured or extracted link."""

    model_config = ConfigDict(extra="forbid")

    has_audio: bool = False
    has_timeline: bool = False
    has_images: bool = False


class ExtractionResult(BaseModel):
    """Unified result contract emitted by all extraction tiers (ADR 0002).

    Conforms to Docs/api/schemas/extraction-result.json. Both tier 1 (yt-dlp,
    trafilatura) and tier 2 (agent rescue) must emit this exact contract so
    downstream pipeline stages remain decoupled from extraction mechanisms.
    """

    model_config = ConfigDict(extra="forbid")

    tier: int = Field(default=1, ge=1, le=2, description="Extraction tier: 1=deterministic, 2=agent rescue")
    kind: Kind = Field(description="Content classification: video | article | unknown")
    title: str | None = Field(default=None, description="Extracted content title")
    channel: str | None = Field(default=None, description="Author, channel, or uploader name")
    duration: int | None = Field(default=None, ge=0, description="Duration in integer seconds (if video/audio)")
    published: str | None = Field(default=None, description="ISO publication date (YYYY-MM-DD)")
    body: str | None = Field(default=None, description="Article body text or video transcript-from-captions")
    transcript_available: bool = Field(default=False, description="True if transcript text was extracted or available")
    capability_flags: CapabilityFlags = Field(default_factory=CapabilityFlags, description="Audio/timeline/image flags")
    source_meta: dict[str, Any] = Field(default_factory=dict, description="Platform-specific metadata (thumbnail, IDs)")

    @field_validator("published")
    @classmethod
    def _validate_published_iso_date(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v_clean = v.strip()
        if not v_clean:
            return None
        try:
            # Enforce strict ISO date format (YYYY-MM-DD) per schema format: date
            datetime.date.fromisoformat(v_clean)
        except ValueError as exc:
            raise ValueError(f"published date must be a valid ISO 8601 date (YYYY-MM-DD), got {v!r}") from exc
        return v_clean

    @model_validator(mode="before")
    @classmethod
    def _default_video_capability_flags(cls, data: Any) -> Any:
        # If kind is video and capability_flags not explicitly passed, default has_audio to True
        if isinstance(data, dict):
            if data.get("kind") in (Kind.VIDEO, "video") and "capability_flags" not in data:
                data = dict(data)
                data["capability_flags"] = {"has_audio": True, "has_timeline": False, "has_images": False}
        return data

    @model_validator(mode="after")
    def _enforce_kind_invariants(self) -> ExtractionResult:
        # Schema allOf invariant: if kind == video, has_audio must be True.
        # If caller explicitly provided capability_flags with has_audio=False, raise validation error.
        if self.kind == Kind.VIDEO and not self.capability_flags.has_audio:
            raise ValueError("A video extraction result must have has_audio=True per extraction-result.json schema")
        return self

    def needs_tier2_rescue(self) -> bool:
        """Determine whether this result qualifies for Tier 2 agent rescue per ADR 0002.

        ADR 0002 rule: Fires ONLY when all required fields for this kind are missing:
          - video: no title AND no transcript
          - article: no body
          - unknown: no title AND no body
        Optional fields (duration, channel, published, images) never trigger rescue.
        """
        has_title = bool(self.title and self.title.strip())
        has_transcript = bool(self.transcript_available or (self.body and self.body.strip()))
        has_body = bool(self.body and self.body.strip())

        if self.kind == Kind.VIDEO:
            return not has_title and not has_transcript
        if self.kind == Kind.ARTICLE:
            return not has_body
        if self.kind == Kind.UNKNOWN:
            return not has_title and not has_body
        return False

    @classmethod
    def degraded(cls, kind: Kind = Kind.UNKNOWN, title: str | None = None,
                 raw_url: str | None = None, source_meta: dict[str, Any] | None = None) -> ExtractionResult:
        """Construct a valid degraded result when extraction partially fails or platform blocks (ADR 0003)."""
        flags = CapabilityFlags(has_audio=(kind == Kind.VIDEO))
        meta = dict(source_meta or {})
        if raw_url and "raw_url" not in meta:
            meta["raw_url"] = raw_url
        return cls(
            tier=1,
            kind=kind,
            title=title,
            channel=None,
            duration=None,
            published=None,
            body=None,
            transcript_available=False,
            capability_flags=flags,
            source_meta=meta,
        )

    @classmethod
    def empty(cls, kind: Kind = Kind.UNKNOWN) -> ExtractionResult:
        """Construct an empty extraction result."""
        return cls(
            tier=1,
            kind=kind,
            title=None,
            channel=None,
            duration=None,
            published=None,
            body=None,
            transcript_available=False,
            capability_flags=CapabilityFlags(has_audio=(kind == Kind.VIDEO)),
            source_meta={},
        )
