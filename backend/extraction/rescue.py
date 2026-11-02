"""Tier-2 agent rescue provider stub (ADR 0002, Rules.md §5).

Enforces the ADR 0002 contract: Tier-2 agent rescue triggers only when all required
fields for a kind are absent. In MVP, Tier-2 is unconfigured and safely degrades to
Kind.UNKNOWN without fabricating text or making external scraping calls.
"""
from __future__ import annotations

import logging
from typing import Any

from backend.contracts.enums import Kind
from backend.contracts.extraction import CapabilityFlags, ExtractionResult

logger = logging.getLogger(__name__)


class Tier2RescueStub:
    """Safe stub implementation of Tier2RescueProvider protocol."""

    async def rescue(self, url: str, initial_result: ExtractionResult) -> ExtractionResult:
        """Evaluate rescue request and return explicit unconfigured/unavailable outcome.

        Args:
            url: The canonical URL that failed initial tier-1 extraction.
            initial_result: The tier-1 extraction outcome.

        Returns:
            ExtractionResult: Degraded to UNKNOWN with explicit tier2_status metadata.
        """
        # If the result didn't qualify under ADR 0002 rules, return it unmodified
        if not initial_result.needs_tier2_rescue():
            logger.info("Tier-2 rescue evaluated: content does not qualify for rescue")
            return initial_result

        logger.info("Tier-2 rescue requested but unconfigured; safely degrading to unknown")

        source_meta: dict[str, Any] = {
            "tier2_status": "unconfigured",
            "reason": "Tier-2 agent rescue is unconfigured in the MVP release",
            "initial_kind": initial_result.kind.value,
        }

        # Preserve harmless diagnostic status from initial result if present
        if "category" in initial_result.source_meta:
            source_meta["initial_category"] = initial_result.source_meta["category"]

        return ExtractionResult(
            tier=2,
            kind=Kind.UNKNOWN,
            title=None,
            channel=None,
            duration=None,
            published=None,
            body=None,
            transcript_available=False,
            capability_flags=CapabilityFlags(has_audio=False, has_timeline=False, has_images=False),
            source_meta=source_meta,
        )
