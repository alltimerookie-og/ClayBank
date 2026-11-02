"""Tests for Phase 3 Task 3 Component 3.4: Tier-2 Rescue Provider Stub.

Verifies protocol conformance, safe unconfigured status reporting, ADR 0002 trigger
compatibility, absence of fabricated content, and zero network calls.
"""
from __future__ import annotations

from unittest.mock import patch
import pytest

from backend.contracts.enums import Kind
from backend.contracts.extraction import CapabilityFlags, ExtractionResult
from backend.extraction.protocol import Tier2RescueProvider
from backend.extraction.rescue import Tier2RescueStub


def test_tier2_stub_conforms_to_protocol() -> None:
    """Verify Tier2RescueStub conforms to Tier2RescueProvider runtime protocol."""
    stub = Tier2RescueStub()
    assert isinstance(stub, Tier2RescueProvider)


@pytest.mark.anyio
async def test_rescue_requested_returns_unconfigured_unknown() -> None:
    """Verify degraded unknown result with tier2_status='unconfigured' when rescue triggers."""
    stub = Tier2RescueStub()
    # A video with no title and no transcript qualifies for rescue
    initial = ExtractionResult(
        tier=1,
        kind=Kind.VIDEO,
        title=None,
        body=None,
        transcript_available=False,
        capability_flags=CapabilityFlags(has_audio=True, has_timeline=False, has_images=False),
        source_meta={"category": "unavailable"},
    )
    assert initial.needs_tier2_rescue() is True

    result = await stub.rescue("https://www.youtube.com/watch?v=missing", initial)

    assert result.tier == 2
    assert result.kind == Kind.UNKNOWN
    assert result.title is None
    assert result.body is None
    assert result.transcript_available is False
    assert result.capability_flags.has_audio is False
    assert result.source_meta["tier2_status"] == "unconfigured"
    assert "MVP" in result.source_meta["reason"]
    assert result.source_meta["initial_kind"] == "video"
    assert result.source_meta["initial_category"] == "unavailable"


@pytest.mark.anyio
async def test_rescue_skipped_when_not_qualifying() -> None:
    """Verify initial result is returned unmodified if it does not qualify under ADR 0002."""
    stub = Tier2RescueStub()
    # Video with a title does NOT qualify for rescue
    initial = ExtractionResult(
        tier=1,
        kind=Kind.VIDEO,
        title="Valid Title",
        body=None,
        transcript_available=False,
        capability_flags=CapabilityFlags(has_audio=True, has_timeline=False, has_images=False),
        source_meta={"video_id": "123"},
    )
    assert initial.needs_tier2_rescue() is False

    result = await stub.rescue("https://www.youtube.com/watch?v=123", initial)

    assert result == initial
    assert result.tier == 1
    assert result.title == "Valid Title"


@pytest.mark.anyio
async def test_rescue_does_not_fabricate_content() -> None:
    """Verify that under no circumstances does the stub fabricate body or title."""
    stub = Tier2RescueStub()
    initial = ExtractionResult(
        tier=1,
        kind=Kind.UNKNOWN,
        title="",
        body=None,
        source_meta={},
    )

    result = await stub.rescue("https://example.com/empty", initial)

    assert result.title is None
    assert result.body is None
    assert result.transcript_available is False


@pytest.mark.anyio
async def test_rescue_makes_zero_network_calls() -> None:
    """Verify that rescue stub makes no network or socket calls."""
    stub = Tier2RescueStub()
    initial = ExtractionResult(tier=1, kind=Kind.UNKNOWN, title=None, body=None)

    with patch("socket.socket") as mock_socket:
        result = await stub.rescue("https://example.com/blocked", initial)
        assert not mock_socket.called

    assert result.tier == 2
    assert result.kind == Kind.UNKNOWN
