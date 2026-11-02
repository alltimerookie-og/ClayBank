"""Extraction protocols defining seams for content extractors and rescue (Rules.md §8, ADR 0002)."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.contracts.extraction import ExtractionResult


@runtime_checkable
class Extractor(Protocol):
    """Protocol for tier-1 deterministic extractors (yt-dlp, trafilatura)."""

    async def extract(self, url: str, platform: str) -> ExtractionResult:
        """Extract metadata and text from a target URL.

        Args:
            url: The canonical URL to extract from.
            platform: Platform derived from host (youtube, instagram, web, etc.).

        Returns:
            ExtractionResult conforming to Docs/api/schemas/extraction-result.json.
        """
        ...


@runtime_checkable
class Tier2RescueProvider(Protocol):
    """Protocol for tier-2 agent rescue fallback (ADR 0002)."""

    async def rescue(self, url: str, initial_result: ExtractionResult) -> ExtractionResult:
        """Attempt agent rescue when required fields are all absent.

        Caps: 5 tool calls / 45 seconds. Degrades to unknown rather than partial writes.
        """
        ...
