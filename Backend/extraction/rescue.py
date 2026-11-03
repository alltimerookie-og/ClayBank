"""Tier-two extraction rescue interface."""

from Backend.extraction.result import ExtractionResult


class RescueExtractor:
    """Interface-only tier-2 rescue for the hackathon build."""

    def rescue(self, url: str, kind: str) -> ExtractionResult:
        """Degrade to unknown rather than partial-write."""
        del url, kind
        return ExtractionResult(tier=2, kind="unknown")
