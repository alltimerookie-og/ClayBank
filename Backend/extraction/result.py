"""Shared tier-1 extraction result shape."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """Contract-shaped tier-1 extraction result."""

    tier: int = 1
    kind: str = "unknown"
    title: str | None = None
    channel: str | None = None
    duration: int | None = None
    published: str | None = None
    body: str | None = None
    transcript_available: bool = False
    capability_flags: dict = field(default_factory=dict)
    source_meta: dict = field(default_factory=dict)

    def to_contract(self) -> dict:
        """Return the wire shape defined by extraction-result.json."""
        return {
            "tier": self.tier,
            "kind": self.kind,
            "title": self.title,
            "channel": self.channel,
            "duration": self.duration,
            "published": self.published,
            "body": self.body,
            "transcript_available": self.transcript_available,
            "capability_flags": {
                "has_audio": bool(self.capability_flags.get("has_audio", False)),
                "has_timeline": bool(self.capability_flags.get("has_timeline", False)),
                "has_images": bool(self.capability_flags.get("has_images", False)),
            },
            "source_meta": dict(self.source_meta),
        }


def merge_kind(preferred: str, title: str | None, body: str | None) -> str:
    """Degrade to unknown when required fields are absent."""
    if title or body:
        return preferred
    return "unknown"
