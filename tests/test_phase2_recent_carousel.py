"""Unit tests for P2-07: Recent Saves Carousel."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import pytest

from app.views.recent_carousel import (
    RecentSaveCard,
    RecentSavesCarousel,
    format_relative_timestamp,
)

FIXTURES_PATH = Path("Docs/api/fixtures")


def test_relative_timestamp_formatting() -> None:
    """Verify timestamp formatting handles valid ISO dates and nulls."""
    assert format_relative_timestamp(None) == "Recent"
    assert format_relative_timestamp("2026-10-31T12:00:00Z") != ""
    assert format_relative_timestamp("invalid-date") == "Recent"


def test_recent_carousel_empty_state() -> None:
    """Verify empty carousel displays empty label and no cards."""
    carousel = RecentSavesCarousel([])
    assert carousel.empty_label.visible is True
    assert len(carousel.cards_row.controls) == 0


def test_recent_carousel_loading_state() -> None:
    """Verify loading state activates loading indicator."""
    carousel = RecentSavesCarousel(is_loading=True)
    assert carousel.loading_indicator.visible is True
    assert carousel.empty_label.visible is False


def test_recent_carousel_populated_with_fixture() -> None:
    """Verify carousel populates cards from save-page fixture."""
    fixtures = json.loads((FIXTURES_PATH / "save-page.fixtures.json").read_text(encoding="utf-8"))
    items = fixtures["valid"][0]["items"]

    selected_item: dict[str, Any] = {}

    def on_select(it: dict[str, Any]) -> None:
        nonlocal selected_item
        selected_item = it

    carousel = RecentSavesCarousel(items, on_select_save=on_select)
    assert carousel.empty_label.visible is False
    assert len(carousel.cards_row.controls) == 1

    card = carousel.cards_row.controls[0]
    assert isinstance(card, RecentSaveCard)
    assert card.platform_chip.platform == "instagram"
    assert card.width == 150.0

    # Test click handler
    card._handle_click()
    assert selected_item["id"] == "018f4c1a-0000-7de6-9c8e-000000000001"


def test_recent_carousel_max_items_limit() -> None:
    """Verify carousel caps display at 10 items."""
    sample_item = {
        "id": "save-test",
        "url": "https://example.com/test",
        "platform": "web",
        "captured_at": "2026-10-31T12:00:00Z",
    }
    # Provide 15 items
    carousel = RecentSavesCarousel([sample_item] * 15)
    assert len(carousel.cards_row.controls) == 10
