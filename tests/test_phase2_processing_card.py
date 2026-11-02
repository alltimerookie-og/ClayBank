"""Unit tests for P2-05: Processing Stage Card."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from app.views.processing_card import (
    STAGE_METADATA,
    STAGE_ORDER,
    ProcessingCard,
    get_poll_interval,
)

FIXTURES_PATH = Path("Docs/api/fixtures")


def test_polling_intervals_schedule() -> None:
    """Verify polling backoff intervals: 1s, 2s, 3s."""
    assert get_poll_interval(0) == 1
    assert get_poll_interval(1) == 2
    assert get_poll_interval(2) == 3
    assert get_poll_interval(3) == 3
    assert get_poll_interval(10) == 3


def test_all_six_processing_stages() -> None:
    """Verify card handles all 6 enrichment stages properly."""
    card = ProcessingCard(
        {"state": "queued"},
        url="https://youtube.com/watch?v=123",
    )

    expected_progresses = [0.17, 0.33, 0.5, 0.67, 0.83, 1.0]

    for stage, exp_prog in zip(STAGE_ORDER, expected_progresses):
        card.update_job({"state": stage})
        assert card.current_state == stage
        assert card.stage_title.value == STAGE_METADATA[stage]["title"]
        assert card.state_badge_text.value == stage.upper()
        assert card.progress_bar.value == exp_prog

    assert card.is_complete() is True


def test_processing_card_with_ready_job_fixture() -> None:
    """Verify processing card binds correctly to ready job fixture."""
    fixtures = json.loads((FIXTURES_PATH / "job.fixtures.json").read_text(encoding="utf-8"))
    ready_job = fixtures["valid"][0]

    card = ProcessingCard(
        ready_job,
        url="https://www.instagram.com/reel/Cx9abc/",
    )

    assert card.current_state == "ready"
    assert card.domain_text.value == "instagram.com"
    assert card.progress_bar.value == 1.0
    assert card.is_complete() is True
    assert card.degraded_banner.visible is False


def test_processing_card_degraded_missing_audio_fixture() -> None:
    """Verify job fixture with failed/skipped transcription displays degraded banner gracefully."""
    fixtures = json.loads((FIXTURES_PATH / "job.fixtures.json").read_text(encoding="utf-8"))
    analyzing_job = fixtures["valid"][1]

    card = ProcessingCard(
        analyzing_job,
        url="https://example.com/silent-clip",
    )

    assert card.current_state == "analyzing"
    assert card.is_complete() is False
    assert card.degraded_banner.visible is True
    assert "transcript unavailable" in card.degraded_banner_text.value


def test_processing_card_unknown_kind_fallback() -> None:
    """Verify unknown kind displays non-blocking fallback banner."""
    card = ProcessingCard(
        {"state": "extracting"},
        url="https://example.com/binary.dat",
        kind="unknown",
    )

    assert card.degraded_banner.visible is True
    assert "Unknown content format" in card.degraded_banner_text.value
